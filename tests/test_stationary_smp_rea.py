from __future__ import annotations

from dataclasses import replace
from math import exp, log
import unittest

from core.stationary_smp_rea import (
    MS400GeometryAssumption,
    StationarySMPREAInput,
    build_ms400_stationary_input_from_label,
    solve_stationary_smp_profile,
)
from core.stationary_smp_rea.air import latent_heat_evaporation
from core.stationary_smp_rea.air import T_REF_K
from core.stationary_smp_rea.balances import evaluate_algebraic_state, evaluate_rhs
from core.stationary_smp_rea.closures import equilibrium_moisture_closure
from core.stationary_smp_rea.inputs import derive_inputs
from core.stationary_smp_rea.ms400 import load_ms400_experiments
from core.stationary_smp_rea.materials.smp_chew import (
    activation_ratio,
    chew_shrinkage_ratio,
    chew_material_state,
    fu_50_shrinkage_ratio,
    legacy_extended_shrinkage_ratio,
    legacy_high_solids_activation_ratio,
    initial_moisture_dry_basis,
    linear_parameters_from_initial_moisture,
    low_solids_activation_parameters,
    table2_anchor_parameters,
)
from core.stationary_smp_rea.particle import pressure_nozzle_exit_velocity


class StationarySMPREAKernelTests(unittest.TestCase):
    def test_default_profile_runs_and_drives_drying(self) -> None:
        result = solve_stationary_smp_profile(StationarySMPREAInput())

        self.assertTrue(result.success)
        self.assertGreater(len(result.series), 50)
        for column in (
            "h",
            "X",
            "T_p_k",
            "T_a_k",
            "Y",
            "H_h_j_kg_da",
            "U_p_ms",
            "tau_s",
            "x_b",
            "delta",
            "psi",
            "Re",
            "Sh",
            "Nu",
            "axial_exposure_factor",
            "combined_contact_exposure_factor",
            "RH_eff",
            "Y_eff",
            "humidity_bias_active",
            "delta_t_air_particle_k",
            "rho_v_driving_force_kg_m3",
            "q_conv_w",
            "q_latent_w",
            "q_evap_total_w",
            "q_evap_to_conv_ratio",
        ):
            self.assertIn(column, result.series.columns)

        start = result.series.iloc[0]
        end = result.series.iloc[-1]
        self.assertLess(end["X"], start["X"])
        self.assertGreater(end["Y"], start["Y"])
        self.assertGreater(end["tau_s"], 0.0)
        self.assertLessEqual(float(result.series["psi"].max()), 1.0)
        self.assertGreater(float(result.series["Re"].min()), 0.0)

    def test_xb_closure_switch_changes_outlet_prediction(self) -> None:
        baseline = solve_stationary_smp_profile(
            StationarySMPREAInput(x_b_model="langrish")
        )
        gab = solve_stationary_smp_profile(StationarySMPREAInput(x_b_model="lin_gab"))

        self.assertTrue(baseline.success)
        self.assertTrue(gab.success)
        self.assertNotAlmostEqual(
            baseline.outlet["outlet_X"],
            gab.outlet["outlet_X"],
            places=4,
        )
        self.assertNotAlmostEqual(
            float(baseline.series["x_b"].iloc[-1]),
            float(gab.series["x_b"].iloc[-1]),
            places=4,
        )

    def test_xb_blend_closure_reproduces_both_endpoints(self) -> None:
        temp_k = 333.15
        rh = 0.23

        lin_gab = equilibrium_moisture_closure(temp_k, rh, "lin_gab")
        langrish = equilibrium_moisture_closure(temp_k, rh, "langrish")
        blend_zero = equilibrium_moisture_closure(
            temp_k,
            rh,
            "lin_gab_langrish_blend",
            x_b_blend_langrish_weight=0.0,
        )
        blend_one = equilibrium_moisture_closure(
            temp_k,
            rh,
            "lin_gab_langrish_blend",
            x_b_blend_langrish_weight=1.0,
        )
        blend_mid = equilibrium_moisture_closure(
            temp_k,
            rh,
            "lin_gab_langrish_blend",
            x_b_blend_langrish_weight=0.35,
        )

        self.assertAlmostEqual(blend_zero.x_b, lin_gab.x_b, places=12)
        self.assertAlmostEqual(blend_one.x_b, langrish.x_b, places=12)
        self.assertGreater(blend_mid.x_b, lin_gab.x_b)
        self.assertLess(blend_mid.x_b, langrish.x_b)

    def test_langrish_closure_matches_log_form_without_power_law(self) -> None:
        temp_k = 353.15
        rh = 0.17

        closure = equilibrium_moisture_closure(temp_k, rh, "langrish")
        expected = 0.1499 * exp(-2.306e-3 * temp_k) * log(1.0 / rh)

        self.assertAlmostEqual(closure.x_b, expected, places=12)

    def test_xb_blend_profile_sits_between_endpoints(self) -> None:
        baseline = solve_stationary_smp_profile(StationarySMPREAInput(x_b_model="lin_gab"))
        blended = solve_stationary_smp_profile(
            StationarySMPREAInput(
                x_b_model="lin_gab_langrish_blend",
                x_b_blend_langrish_weight=0.35,
            )
        )
        langrish = solve_stationary_smp_profile(
            StationarySMPREAInput(x_b_model="langrish")
        )

        self.assertTrue(blended.success)
        self.assertGreater(blended.outlet["outlet_X"], baseline.outlet["outlet_X"])
        self.assertLess(blended.outlet["outlet_X"], langrish.outlet["outlet_X"])
        self.assertGreater(
            float(blended.series["x_b"].iloc[-1]),
            float(baseline.series["x_b"].iloc[-1]),
        )
        self.assertLess(
            float(blended.series["x_b"].iloc[-1]),
            float(langrish.series["x_b"].iloc[-1]),
        )
        self.assertAlmostEqual(
            float(blended.series["x_b_langrish_weight"].iloc[-1]),
            0.35,
            places=12,
        )

    def test_xb_rh_blend_closure_uses_clamped_rh_dependent_weight(self) -> None:
        temp_k = 333.15
        rh_low = 0.04
        rh_high = 0.11
        low = equilibrium_moisture_closure(
            temp_k,
            rh_low,
            "lin_gab_langrish_blend_rh",
            x_b_blend_langrish_weight_base=0.05,
            x_b_blend_langrish_weight_rh_coeff=5.0,
        )
        high = equilibrium_moisture_closure(
            temp_k,
            rh_high,
            "lin_gab_langrish_blend_rh",
            x_b_blend_langrish_weight_base=0.05,
            x_b_blend_langrish_weight_rh_coeff=5.0,
        )
        saturated = equilibrium_moisture_closure(
            temp_k,
            0.30,
            "lin_gab_langrish_blend_rh",
            x_b_blend_langrish_weight_base=0.30,
            x_b_blend_langrish_weight_rh_coeff=5.0,
        )

        self.assertAlmostEqual(low.x_b_langrish_weight, 0.25, places=12)
        self.assertAlmostEqual(high.x_b_langrish_weight, 0.60, places=12)
        self.assertGreater(high.x_b, low.x_b)
        self.assertAlmostEqual(saturated.x_b_langrish_weight, 1.0, places=12)

    def test_xb_rh_blend_profile_increases_applied_weight_for_more_humid_case(self) -> None:
        v2_input = build_ms400_stationary_input_from_label(
            "V2",
            feed_rate_kg_h=14.0,
            humid_air_mass_flow_kg_h=304.0,
            heat_loss_coeff_w_m2k=1.4,
            x_b_model="lin_gab_langrish_blend_rh",
        )
        v3_input = build_ms400_stationary_input_from_label(
            "V3",
            feed_rate_kg_h=14.0,
            humid_air_mass_flow_kg_h=304.0,
            heat_loss_coeff_w_m2k=1.4,
            x_b_model="lin_gab_langrish_blend_rh",
        )
        v2 = solve_stationary_smp_profile(v2_input)
        v3 = solve_stationary_smp_profile(v3_input)
        v2_mean_weight = float(v2.series["x_b_langrish_weight"].mean())
        v3_mean_weight = float(v3.series["x_b_langrish_weight"].mean())

        self.assertTrue(v2.success)
        self.assertTrue(v3.success)
        self.assertAlmostEqual(v2.inputs.x_b_blend_langrish_weight_base, 0.0, places=12)
        self.assertAlmostEqual(v2.inputs.x_b_blend_langrish_weight_rh_coeff, 0.0, places=12)
        self.assertAlmostEqual(v2_mean_weight, 0.0, places=12)
        self.assertAlmostEqual(v3_mean_weight, 0.0, places=12)

        tuned_v2 = solve_stationary_smp_profile(
            replace(
                v2_input,
                enable_material_retardation_add=False,
                x_b_blend_langrish_weight_base=0.05,
                x_b_blend_langrish_weight_rh_coeff=5.0,
            )
        )
        tuned_v3 = solve_stationary_smp_profile(
            replace(
                v3_input,
                enable_material_retardation_add=False,
                x_b_blend_langrish_weight_base=0.05,
                x_b_blend_langrish_weight_rh_coeff=5.0,
            )
        )

        self.assertGreater(
            float(tuned_v3.series["x_b_langrish_weight"].mean()),
            float(tuned_v2.series["x_b_langrish_weight"].mean()),
        )
        self.assertGreater(tuned_v3.outlet["outlet_X"], tuned_v2.outlet["outlet_X"])

    def test_sub_37_percent_case_warns_but_runs(self) -> None:
        result = solve_stationary_smp_profile(
            StationarySMPREAInput(feed_total_solids=0.35)
        )

        self.assertTrue(result.success)
        self.assertTrue(
            any("20/30-wt% anchors" in warning for warning in result.warnings)
        )
        self.assertLess(
            result.outlet["outlet_X"],
            result.series["X"].iloc[0],
        )
        self.assertEqual(result.series["shrinkage_mode"].iloc[0], "legacy_extended")

    def test_chew_table3_reproduces_table2_anchor_values(self) -> None:
        for feed_total_solids in (0.30, 0.37, 0.40, 0.43):
            initial_moisture = initial_moisture_dry_basis(feed_total_solids)
            slope, intercept, critical_delta, critical_ratio = (
                linear_parameters_from_initial_moisture(initial_moisture)
            )
            (
                expected_slope,
                expected_intercept,
                expected_critical_delta,
                expected_critical_ratio,
            ) = table2_anchor_parameters(feed_total_solids)

            self.assertAlmostEqual(slope, expected_slope, delta=0.01)
            self.assertAlmostEqual(intercept, expected_intercept, delta=0.02)
            self.assertAlmostEqual(critical_delta, expected_critical_delta, delta=0.01)
            self.assertAlmostEqual(critical_ratio, expected_critical_ratio, delta=0.01)

    def test_low_solids_rea_extension_uses_30_percent_anchor(self) -> None:
        slope, intercept, critical_delta, critical_ratio = low_solids_activation_parameters()

        self.assertAlmostEqual(slope, 0.1617, places=4)
        self.assertAlmostEqual(intercept, 0.172 + 0.1617 * 1.362, places=4)
        self.assertAlmostEqual(critical_delta, 1.362, places=4)
        self.assertAlmostEqual(critical_ratio, 0.172, places=4)

    def test_legacy_shrinkage_extension_covers_20_and_30_percent(self) -> None:
        ratio_20_dry = legacy_extended_shrinkage_ratio(delta=0.0, x_b=0.0, feed_total_solids=0.20)
        ratio_20_wet = legacy_extended_shrinkage_ratio(delta=4.0, x_b=0.0, feed_total_solids=0.20)
        ratio_30_dry = legacy_extended_shrinkage_ratio(delta=0.0, x_b=0.0, feed_total_solids=0.30)
        ratio_30_wet = legacy_extended_shrinkage_ratio(delta=4.0, x_b=0.0, feed_total_solids=0.30)

        self.assertAlmostEqual(ratio_20_dry, 0.67, places=4)
        self.assertAlmostEqual(ratio_20_wet, 1.0, places=4)
        self.assertAlmostEqual(ratio_30_dry, 0.76, places=4)
        self.assertAlmostEqual(ratio_30_wet, 1.0, places=4)

    def test_high_solids_shrinkage_interpolates_to_legacy_50_anchor(self) -> None:
        delta = 0.4
        temp_air_k = 363.15
        ratio_43 = chew_shrinkage_ratio(delta=delta, feed_total_solids=0.43, temp_air_k=temp_air_k)
        ratio_46 = chew_shrinkage_ratio(delta=delta, feed_total_solids=0.46, temp_air_k=temp_air_k)
        ratio_50 = chew_shrinkage_ratio(delta=delta, feed_total_solids=0.50, temp_air_k=temp_air_k)

        self.assertAlmostEqual(ratio_50, fu_50_shrinkage_ratio(delta, temp_air_k), places=12)
        self.assertGreater(ratio_46, ratio_43)
        self.assertLess(ratio_46, ratio_50)

    def test_fu_50_shrinkage_uses_reported_70c_and_90c_relations(self) -> None:
        self.assertAlmostEqual(
            fu_50_shrinkage_ratio(delta=0.20, temp_air_k=343.15),
            0.0301 * 0.20 + 0.9238,
            places=6,
        )
        self.assertAlmostEqual(
            fu_50_shrinkage_ratio(delta=0.50, temp_air_k=343.15),
            0.0866 * 0.50 + 0.9061,
            places=6,
        )
        self.assertAlmostEqual(
            fu_50_shrinkage_ratio(delta=0.50, temp_air_k=363.15),
            0.0447 * 0.50 + 0.959,
            places=6,
        )

    def test_fu_50_shrinkage_interpolates_between_70c_and_90c(self) -> None:
        delta = 0.50
        ratio_70 = fu_50_shrinkage_ratio(delta=delta, temp_air_k=343.15)
        ratio_80 = fu_50_shrinkage_ratio(delta=delta, temp_air_k=353.15)
        ratio_90 = fu_50_shrinkage_ratio(delta=delta, temp_air_k=363.15)

        self.assertGreater(ratio_80, ratio_70)
        self.assertLess(ratio_80, ratio_90)
        self.assertAlmostEqual(ratio_80, 0.5 * (ratio_70 + ratio_90), places=6)

    def test_high_solids_rea_blends_toward_legacy_50_branch(self) -> None:
        delta = 0.6
        ratio_43, *_ = activation_ratio(delta, 0.43)
        ratio_47, *_ = activation_ratio(delta, 0.47)
        ratio_50, *_ = activation_ratio(delta, 0.50)

        self.assertGreater(ratio_43, ratio_47)
        self.assertGreater(ratio_47, ratio_50)
        self.assertAlmostEqual(
            ratio_50,
            legacy_high_solids_activation_ratio(delta),
            places=12,
        )

    def test_high_solids_rea_uses_legacy_50_polynomial_and_saturates_at_delta_one(self) -> None:
        ratio_50, *_ = activation_ratio(
            delta=1.20,
            feed_total_solids=0.50,
        )

        self.assertAlmostEqual(
            ratio_50,
            legacy_high_solids_activation_ratio(1.0),
            places=12,
        )
        self.assertAlmostEqual(ratio_50, 0.0182, places=4)

    def test_20_percent_case_runs_with_low_solids_extension(self) -> None:
        result = solve_stationary_smp_profile(
            StationarySMPREAInput(feed_total_solids=0.20)
        )

        self.assertTrue(result.success)
        self.assertEqual(result.series["shrinkage_mode"].iloc[0], "legacy_extended")
        self.assertTrue(
            any("below 30 wt%" in warning.lower() for warning in result.warnings)
        )
        self.assertLess(result.outlet["outlet_X"], result.series["X"].iloc[0])

    def test_50_percent_case_runs_with_high_solids_extension(self) -> None:
        result = solve_stationary_smp_profile(
            StationarySMPREAInput(feed_total_solids=0.50)
        )

        self.assertTrue(result.success)
        self.assertEqual(result.series["shrinkage_mode"].iloc[0], "chew")
        self.assertTrue(
            any("above 43 wt%" in warning.lower() for warning in result.warnings)
        )
        self.assertLess(result.outlet["outlet_X"], result.series["X"].iloc[0])

    def test_material_retardation_add_term_is_windowed_to_early_falling_rate(self) -> None:
        early = chew_material_state(
            moisture_dry_basis=0.14,
            x_b=0.01,
            feed_total_solids=0.37,
            shrinkage_model="auto",
            temp_particle_k=333.15,
            temp_air_k=353.15,
            rh_air=0.12,
        )
        wet = chew_material_state(
            moisture_dry_basis=0.45,
            x_b=0.01,
            feed_total_solids=0.37,
            shrinkage_model="auto",
            temp_particle_k=333.15,
            temp_air_k=353.15,
            rh_air=0.12,
        )
        near_equilibrium = chew_material_state(
            moisture_dry_basis=0.02,
            x_b=0.01,
            feed_total_solids=0.37,
            shrinkage_model="auto",
            temp_particle_k=333.15,
            temp_air_k=353.15,
            rh_air=0.12,
        )

        self.assertGreater(early.activation_ratio_add, 0.0)
        self.assertLess(wet.activation_ratio_add, early.activation_ratio_add)
        self.assertLess(near_equilibrium.activation_ratio_add, early.activation_ratio_add)
        self.assertAlmostEqual(
            early.activation_ratio,
            early.activation_ratio_base + early.activation_ratio_add,
            places=12,
        )

    def test_material_retardation_add_can_be_disabled(self) -> None:
        with_add = chew_material_state(
            moisture_dry_basis=0.14,
            x_b=0.01,
            feed_total_solids=0.37,
            shrinkage_model="auto",
            temp_particle_k=333.15,
            temp_air_k=353.15,
            rh_air=0.12,
            enable_material_retardation_add=True,
        )
        without_add = chew_material_state(
            moisture_dry_basis=0.14,
            x_b=0.01,
            feed_total_solids=0.37,
            shrinkage_model="auto",
            temp_particle_k=333.15,
            temp_air_k=353.15,
            rh_air=0.12,
            enable_material_retardation_add=False,
        )

        self.assertGreater(with_add.activation_ratio_add, 0.0)
        self.assertAlmostEqual(without_add.activation_ratio_add, 0.0, places=12)
        self.assertAlmostEqual(
            without_add.activation_ratio,
            without_add.activation_ratio_base,
            places=12,
        )
        self.assertGreater(with_add.activation_ratio, without_add.activation_ratio)

    def test_sectionwise_geometry_updates_local_air_velocity_and_pre_cyclone_report(self) -> None:
        result = solve_stationary_smp_profile(
            StationarySMPREAInput(
                dryer_height_m=2.2,
                dryer_diameter_m=1.15,
                cylinder_height_m=2.2,
                cone_height_m=1.0,
                cylinder_diameter_m=1.15,
                outlet_duct_length_m=1.0,
                outlet_duct_diameter_m=0.20,
                inlet_air_temp_c=180.0,
                inlet_abs_humidity_g_kg=5.7,
                feed_total_solids=0.37,
                feed_rate_kg_h=17.0,
                air_flow_m3_h=170.0,
                droplet_size_um=64.0,
                axial_points=180,
            )
        )

        self.assertTrue(result.success)
        self.assertIn("section", result.series.columns)
        self.assertIn("A_cross_m2", result.series.columns)
        self.assertIn("wall_area_density_m2_m", result.series.columns)

        cylinder_row = result.series[result.series["section"] == "cylinder"].iloc[0]
        duct_row = result.series[result.series["section"] == "outlet_duct"].iloc[-1]
        self.assertLess(duct_row["A_cross_m2"], cylinder_row["A_cross_m2"])
        self.assertGreater(duct_row["U_a_ms"], cylinder_row["U_a_ms"])

        dryer_exit = result.report_points["dryer_exit"]
        pre_cyclone = result.report_points["pre_cyclone"]
        self.assertLess(float(dryer_exit["h_m"]), float(pre_cyclone["h_m"]))
        self.assertEqual(pre_cyclone["section"], "outlet_duct")
        self.assertEqual(result.outlet["outlet_section"], "outlet_duct")
        self.assertTrue(
            any("effective 1d flow path" in warning.lower() for warning in result.warnings)
        )
        self.assertAlmostEqual(
            float(pre_cyclone["T_a_c"]),
            float(result.outlet["outlet_T_a_c"]),
            places=6,
        )

    def test_ms400_builder_exposes_effective_geometry_defaults(self) -> None:
        sim_input = build_ms400_stationary_input_from_label("V2")
        experiment = load_ms400_experiments().set_index("label").loc["V2"]

        self.assertEqual(sim_input.inlet_air_temp_c, 180.0)
        self.assertEqual(sim_input.feed_rate_kg_h, 14.0)
        self.assertEqual(sim_input.feed_total_solids, 0.37)
        self.assertEqual(sim_input.x_b_model, "lin_gab")
        self.assertAlmostEqual(sim_input.x_b_blend_langrish_weight, 0.5)
        self.assertEqual(sim_input.cylinder_height_m, MS400GeometryAssumption().cylinder_height_m)
        self.assertEqual(sim_input.cone_height_m, MS400GeometryAssumption().cone_height_m)
        self.assertEqual(
            sim_input.outlet_duct_diameter_m,
            MS400GeometryAssumption().outlet_duct_diameter_m,
        )
        self.assertGreater(sim_input.droplet_size_um, 46.0)
        self.assertAlmostEqual(experiment["d32_um"], 46.0)
        self.assertGreater(sim_input.air_flow_m3_h, 390.0)

    def test_ms400_v3_builder_uses_shared_304kg_h_air_default(self) -> None:
        sim_input = build_ms400_stationary_input_from_label("V3")
        derived = derive_inputs(sim_input)

        self.assertEqual(sim_input.feed_rate_kg_h, 14.0)
        self.assertAlmostEqual(derived.humid_air_mass_flow_kg_s * 3600.0, 304.0, places=9)
        self.assertEqual(sim_input.x_b_model, "lin_gab")
        self.assertAlmostEqual(sim_input.x_b_blend_langrish_weight, 0.5)

    def test_pressure_nozzle_default_initial_velocity_uses_feed_density(self) -> None:
        sim_input = StationarySMPREAInput(
            feed_total_solids=0.37,
            nozzle_delta_p_bar=47.0,
            nozzle_velocity_coefficient=0.60,
        )
        derived = derive_inputs(sim_input)

        expected = pressure_nozzle_exit_velocity(
            sim_input.nozzle_delta_p_bar,
            derived.initial_particle_density_kg_m3,
            sim_input.nozzle_velocity_coefficient,
        )

        self.assertAlmostEqual(derived.initial_droplet_velocity_ms, expected, places=12)
        self.assertGreater(derived.initial_droplet_velocity_ms, 30.0)

    def test_fixed_velocity_diagnostic_overrides_air_and_particle_velocity(self) -> None:
        result = solve_stationary_smp_profile(
            StationarySMPREAInput(
                inlet_air_temp_c=190.0,
                fixed_particle_velocity_ms=5.0,
                fixed_air_velocity_ms=100.0,
                axial_points=80,
            )
        )

        self.assertTrue(result.success)
        self.assertTrue(
            any("velocity diagnostic" in warning.lower() for warning in result.warnings)
        )
        self.assertAlmostEqual(float(result.series["U_p_ms"].iloc[0]), 5.0, places=9)
        self.assertAlmostEqual(float(result.series["U_p_ms"].iloc[-1]), 5.0, places=9)
        self.assertAlmostEqual(float(result.series["U_a_ms"].iloc[0]), 100.0, places=9)
        self.assertAlmostEqual(float(result.series["U_a_ms"].iloc[-1]), 100.0, places=9)
        self.assertAlmostEqual(float(result.series["dtau_dh"].iloc[-1]), 0.2, places=9)
        self.assertAlmostEqual(float(result.series["dU_p_dh"].abs().max()), 0.0, places=9)

    def test_particle_energy_term_uses_air_side_latent_heat_and_sorption_heat(self) -> None:
        sim_input = StationarySMPREAInput(
            inlet_air_temp_c=210.0,
            feed_total_solids=0.40,
            fixed_particle_velocity_ms=5.0,
            fixed_air_velocity_ms=120.0,
            heat_loss_coeff_w_m2k=0.0,
            x_b_model="lin_gab",
            axial_points=80,
        )
        derived = derive_inputs(sim_input)
        result = solve_stationary_smp_profile(sim_input)

        inlet = result.series.iloc[0]
        self.assertGreater(float(inlet["dT_p_dh"]), 0.0)
        self.assertAlmostEqual(
            float(inlet["h_fg_j_kg"]),
            latent_heat_evaporation(float(inlet["T_a_k"])),
            places=6,
        )

        late_row = result.series[result.series["X"] <= 0.08].iloc[0]
        state = [
            float(late_row["X"]),
            float(late_row["T_p_k"]),
            float(late_row["Y"]),
            float(late_row["H_h_j_kg_da"]),
            float(late_row["U_p_ms"]),
            float(late_row["tau_s"]),
        ]
        rhs = evaluate_rhs(float(late_row["h"]), state, sim_input, derived)
        algebraic = rhs.algebraic
        cp_product = derived.cps_j_kg_k + algebraic.X * derived.cpw_j_kg_k
        expected = (
            algebraic.transport.heat_transfer_coeff_w_m2_k
            * algebraic.particle_area_m2
            * (algebraic.T_a_k - algebraic.T_p_k)
            + rhs.dm_p_dh_kg_m
            * algebraic.U_p_ms
            * (algebraic.h_fg_j_kg + algebraic.q_sorption_j_kg)
        ) / (
            derived.representative_dry_solids_mass_kg
            * cp_product
            * algebraic.U_p_ms
        )

        self.assertAlmostEqual(algebraic.q_sorption_j_kg, 633.0e3, places=6)
        self.assertAlmostEqual(rhs.dT_p_dh, expected, places=9)

    def test_contact_efficiency_scales_transfer_and_slows_drying(self) -> None:
        baseline_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            contact_efficiency=1.0,
            axial_points=120,
        )
        reduced_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            contact_efficiency=0.65,
            axial_points=120,
        )

        baseline_derived = derive_inputs(baseline_input)
        reduced_derived = derive_inputs(reduced_input)
        baseline_result = solve_stationary_smp_profile(baseline_input)
        reduced_result = solve_stationary_smp_profile(reduced_input)
        baseline_state = evaluate_algebraic_state(
            0.0,
            baseline_result.series[["X", "T_p_k", "Y", "H_h_j_kg_da", "U_p_ms", "tau_s"]].iloc[0].to_numpy(),
            baseline_input,
            baseline_derived,
        )
        reduced_state = evaluate_algebraic_state(
            0.0,
            reduced_result.series[["X", "T_p_k", "Y", "H_h_j_kg_da", "U_p_ms", "tau_s"]].iloc[0].to_numpy(),
            reduced_input,
            reduced_derived,
        )

        self.assertAlmostEqual(
            reduced_state.effective_mass_transfer_coeff_ms,
            0.65 * reduced_state.transport.mass_transfer_coeff_ms,
            places=12,
        )
        self.assertAlmostEqual(
            reduced_state.effective_heat_transfer_coeff_w_m2_k,
            0.65 * reduced_state.transport.heat_transfer_coeff_w_m2_k,
            places=12,
        )
        self.assertGreater(reduced_result.outlet["outlet_X"], baseline_result.outlet["outlet_X"])

    def test_atomization_zone_exposure_factor_scales_only_upper_zone_and_slows_drying(self) -> None:
        baseline_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            axial_points=160,
        )
        staged_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            atomization_zone_length_m=0.30,
            atomization_zone_exposure_factor=0.70,
            axial_points=160,
        )

        baseline_result = solve_stationary_smp_profile(baseline_input)
        staged_result = solve_stationary_smp_profile(staged_input)

        self.assertAlmostEqual(
            float(staged_result.series["axial_exposure_factor"].iloc[0]),
            0.70,
            places=12,
        )
        self.assertAlmostEqual(
            float(staged_result.series["combined_contact_exposure_factor"].iloc[0]),
            0.70,
            places=12,
        )
        post_atomization_row = staged_result.series[
            staged_result.series["h"] >= 0.35
        ].iloc[0]
        self.assertAlmostEqual(
            float(post_atomization_row["axial_exposure_factor"]),
            1.0,
            places=12,
        )
        self.assertAlmostEqual(
            float(post_atomization_row["h_m_eff_ms"]),
            float(post_atomization_row["h_m_ms"]),
            places=12,
        )
        self.assertAlmostEqual(
            float(post_atomization_row["h_h_eff_w_m2_k"]),
            float(post_atomization_row["h_h_w_m2_k"]),
            places=12,
        )
        self.assertGreater(staged_result.outlet["outlet_X"], baseline_result.outlet["outlet_X"])
        self.assertTrue(
            any("atomization-zone exposure" in warning.lower() for warning in staged_result.warnings)
        )

    def test_secondary_exposure_zone_extends_tower_side_reduction_downstream(self) -> None:
        stage1_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            atomization_zone_length_m=0.20,
            atomization_zone_exposure_factor=0.70,
            axial_points=200,
        )
        stage2_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            atomization_zone_length_m=0.20,
            atomization_zone_exposure_factor=0.70,
            secondary_exposure_zone_length_m=0.40,
            secondary_exposure_zone_factor=0.85,
            axial_points=200,
        )

        stage1_result = solve_stationary_smp_profile(stage1_input)
        stage2_result = solve_stationary_smp_profile(stage2_input)

        first_zone_row = stage2_result.series[stage2_result.series["h"] <= 0.10].iloc[-1]
        second_zone_row = stage2_result.series[
            (stage2_result.series["h"] >= 0.30) & (stage2_result.series["h"] <= 0.50)
        ].iloc[0]
        downstream_row = stage2_result.series[stage2_result.series["h"] >= 0.70].iloc[0]
        stage1_compare_row = stage1_result.series[
            (stage1_result.series["h"] >= 0.30) & (stage1_result.series["h"] <= 0.50)
        ].iloc[0]

        self.assertAlmostEqual(
            float(first_zone_row["axial_exposure_factor"]),
            0.70,
            delta=0.03,
        )
        self.assertAlmostEqual(
            float(second_zone_row["axial_exposure_factor"]),
            0.85,
            delta=0.03,
        )
        self.assertAlmostEqual(
            float(downstream_row["axial_exposure_factor"]),
            1.0,
            places=12,
        )
        self.assertGreater(
            float(stage1_compare_row["axial_exposure_factor"]),
            float(second_zone_row["axial_exposure_factor"]),
        )
        self.assertGreater(stage2_result.outlet["outlet_X"], stage1_result.outlet["outlet_X"])
        self.assertTrue(
            any("secondary axial exposure zone" in warning.lower() for warning in stage2_result.warnings)
        )

    def test_effective_local_humidity_bias_raises_particle_side_humidity_and_slows_drying(self) -> None:
        baseline_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            axial_points=160,
            enable_material_retardation_add=False,
        )
        humid_bias_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            axial_points=160,
            enable_material_retardation_add=False,
            effective_gas_humidity_mode="target_rh",
            humidity_bias_zone_length_m=0.50,
            humidity_bias_zone_target_rh=0.25,
        )

        baseline_result = solve_stationary_smp_profile(baseline_input)
        humid_bias_result = solve_stationary_smp_profile(humid_bias_input)

        early_row = humid_bias_result.series[humid_bias_result.series["h"] <= 0.10].iloc[-1]
        late_row = humid_bias_result.series[humid_bias_result.series["h"] >= 0.70].iloc[0]

        self.assertGreater(float(early_row["RH_eff"]), float(early_row["RH_a"]))
        self.assertGreater(float(early_row["Y_eff"]), float(early_row["Y"]))
        self.assertEqual(float(early_row["humidity_bias_active"]), 1.0)
        self.assertAlmostEqual(float(late_row["RH_eff"]), float(late_row["RH_a"]), places=12)
        self.assertAlmostEqual(float(late_row["Y_eff"]), float(late_row["Y"]), places=12)
        self.assertGreater(humid_bias_result.outlet["outlet_X"], baseline_result.outlet["outlet_X"])
        self.assertTrue(
            any("effective local gas humidity correction" in warning.lower() for warning in humid_bias_result.warnings)
        )

    def test_second_humidity_bias_zone_extends_effective_local_humidity_downstream(self) -> None:
        stage3_zone1 = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            axial_points=200,
            enable_material_retardation_add=False,
            effective_gas_humidity_mode="target_rh",
            humidity_bias_zone_length_m=0.30,
            humidity_bias_zone_target_rh=0.25,
        )
        stage3_zone2 = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            axial_points=200,
            enable_material_retardation_add=False,
            effective_gas_humidity_mode="target_rh",
            humidity_bias_zone_length_m=0.30,
            humidity_bias_zone_target_rh=0.25,
            humidity_bias_zone2_length_m=0.50,
            humidity_bias_zone2_target_rh=0.18,
        )

        zone1_result = solve_stationary_smp_profile(stage3_zone1)
        zone2_result = solve_stationary_smp_profile(stage3_zone2)

        downstream_zone1 = zone1_result.series[
            (zone1_result.series["h"] >= 0.45) & (zone1_result.series["h"] <= 0.65)
        ].iloc[0]
        downstream_zone2 = zone2_result.series[
            (zone2_result.series["h"] >= 0.45) & (zone2_result.series["h"] <= 0.65)
        ].iloc[0]
        late_zone2 = zone2_result.series[zone2_result.series["h"] >= 1.00].iloc[0]

        self.assertGreater(float(downstream_zone2["RH_eff"]), float(downstream_zone1["RH_eff"]))
        self.assertGreater(float(downstream_zone2["Y_eff"]), float(downstream_zone1["Y_eff"]))
        self.assertGreater(zone2_result.outlet["outlet_X"], zone1_result.outlet["outlet_X"])
        self.assertAlmostEqual(float(late_zone2["RH_eff"]), float(late_zone2["RH_a"]), places=12)
        self.assertTrue(
            any("secondary humidity-bias zone" in warning.lower() for warning in zone2_result.warnings)
        )

    def test_disabling_material_retardation_add_reduces_outlet_moisture(self) -> None:
        baseline = solve_stationary_smp_profile(
            StationarySMPREAInput(
                inlet_air_temp_c=180.0,
                feed_total_solids=0.37,
                axial_points=120,
                enable_material_retardation_add=True,
            )
        )
        without_add = solve_stationary_smp_profile(
            StationarySMPREAInput(
                inlet_air_temp_c=180.0,
                feed_total_solids=0.37,
                axial_points=120,
                enable_material_retardation_add=False,
            )
        )

        self.assertLess(
            without_add.outlet["outlet_X"],
            baseline.outlet["outlet_X"],
        )

    def test_air_enthalpy_balance_includes_particle_liquid_water_enthalpy_change(self) -> None:
        sim_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.37,
            fixed_particle_velocity_ms=5.0,
            fixed_air_velocity_ms=100.0,
            heat_loss_coeff_w_m2k=0.0,
            x_b_model="lin_gab",
            axial_points=80,
        )
        derived = derive_inputs(sim_input)
        result = solve_stationary_smp_profile(sim_input)

        row = result.series[result.series["X"] < result.series["X"].iloc[0]].iloc[0]
        state = [
            float(row["X"]),
            float(row["T_p_k"]),
            float(row["Y"]),
            float(row["H_h_j_kg_da"]),
            float(row["U_p_ms"]),
            float(row["tau_s"]),
        ]
        rhs = evaluate_rhs(float(row["h"]), state, sim_input, derived)
        algebraic = rhs.algebraic
        dry_basis_ratio = (
            derived.dry_solids_mass_flow_kg_s / derived.dry_air_mass_flow_kg_s
        )
        expected = -dry_basis_ratio * (
            algebraic.particle_cp_j_kg_k * rhs.dT_p_dh
            + derived.cpw_j_kg_k * (algebraic.T_p_k - T_REF_K) * rhs.dX_dh
        )

        self.assertLess(rhs.dX_dh, 0.0)
        self.assertGreater(algebraic.T_p_k, T_REF_K)
        self.assertAlmostEqual(rhs.dH_h_dh, expected, places=9)

    def test_drying_stops_once_local_equilibrium_moisture_is_reached(self) -> None:
        sim_input = build_ms400_stationary_input_from_label(
            "V2",
            feed_rate_kg_h=14.0,
            humid_air_mass_flow_kg_h=304.0,
            heat_loss_coeff_w_m2k=2.0,
            x_b_model="lin_gab",
        )
        derived = derive_inputs(sim_input)
        result = solve_stationary_smp_profile(sim_input)

        late_row = result.series.iloc[-1]
        state = [
            float(late_row["x_b"]) - 1e-6,
            float(late_row["T_p_k"]) + 5.0,
            float(late_row["Y"]),
            float(late_row["H_h_j_kg_da"]),
            float(late_row["U_p_ms"]),
            float(late_row["tau_s"]),
        ]
        algebraic = evaluate_algebraic_state(float(late_row["h"]), state, sim_input, derived)
        raw_dm_p_dh = -(
            algebraic.transport.mass_transfer_coeff_ms
            * algebraic.particle_area_m2
            / algebraic.U_p_ms
            * (algebraic.rho_v_surface_kg_m3 - algebraic.rho_v_air_kg_m3)
        )
        rhs = evaluate_rhs(float(late_row["h"]), state, sim_input, derived)
        self.assertLessEqual(algebraic.X, algebraic.x_b)
        self.assertLess(raw_dm_p_dh, 0.0)
        self.assertAlmostEqual(rhs.dm_p_dh_kg_m, 0.0, places=12)
        self.assertAlmostEqual(rhs.dX_dh, 0.0, places=12)


if __name__ == "__main__":
    unittest.main()
