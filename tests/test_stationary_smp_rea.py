from __future__ import annotations

import unittest

from core.stationary_smp_rea import (
    MS400GeometryAssumption,
    StationarySMPREAInput,
    build_ms400_stationary_input_from_label,
    solve_stationary_smp_profile,
)
from core.stationary_smp_rea.air import latent_heat_evaporation
from core.stationary_smp_rea.balances import evaluate_rhs
from core.stationary_smp_rea.inputs import derive_inputs
from core.stationary_smp_rea.ms400 import load_ms400_experiments
from core.stationary_smp_rea.materials.smp_chew import (
    legacy_extended_shrinkage_ratio,
    initial_moisture_dry_basis,
    linear_parameters_from_initial_moisture,
    low_solids_activation_parameters,
    table2_anchor_parameters,
)


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

    def test_sub_37_percent_case_warns_but_runs(self) -> None:
        result = solve_stationary_smp_profile(
            StationarySMPREAInput(feed_total_solids=0.35)
        )

        self.assertTrue(result.success)
        self.assertTrue(
            any("20/30-wt%-Ankern" in warning for warning in result.warnings)
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

    def test_20_percent_case_runs_with_low_solids_extension(self) -> None:
        result = solve_stationary_smp_profile(
            StationarySMPREAInput(feed_total_solids=0.20)
        )

        self.assertTrue(result.success)
        self.assertEqual(result.series["shrinkage_mode"].iloc[0], "legacy_extended")
        self.assertTrue(
            any("unter 30 wt%" in warning.lower() for warning in result.warnings)
        )
        self.assertLess(result.outlet["outlet_X"], result.series["X"].iloc[0])

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
            any("effektive 1D-Strombahn" in warning for warning in result.warnings)
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
        self.assertEqual(sim_input.feed_total_solids, 0.37)
        self.assertEqual(sim_input.x_b_model, "lin_gab")
        self.assertEqual(sim_input.cylinder_height_m, MS400GeometryAssumption().cylinder_height_m)
        self.assertEqual(sim_input.cone_height_m, MS400GeometryAssumption().cone_height_m)
        self.assertEqual(
            sim_input.outlet_duct_diameter_m,
            MS400GeometryAssumption().outlet_duct_diameter_m,
        )
        self.assertGreater(sim_input.droplet_size_um, 46.0)
        self.assertAlmostEqual(experiment["d32_um"], 46.0)
        self.assertGreater(sim_input.air_flow_m3_h, 390.0)

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
            any("Geschwindigkeitsdiagnose" in warning for warning in result.warnings)
        )
        self.assertAlmostEqual(float(result.series["U_p_ms"].iloc[0]), 5.0, places=9)
        self.assertAlmostEqual(float(result.series["U_p_ms"].iloc[-1]), 5.0, places=9)
        self.assertAlmostEqual(float(result.series["U_a_ms"].iloc[0]), 100.0, places=9)
        self.assertAlmostEqual(float(result.series["U_a_ms"].iloc[-1]), 100.0, places=9)
        self.assertAlmostEqual(float(result.series["dtau_dh"].iloc[-1]), 0.2, places=9)
        self.assertAlmostEqual(float(result.series["dU_p_dh"].abs().max()), 0.0, places=9)

    def test_particle_energy_term_uses_air_side_latent_heat_and_sorption_heat(self) -> None:
        sim_input = StationarySMPREAInput(
            inlet_air_temp_c=190.0,
            feed_total_solids=0.40,
            fixed_particle_velocity_ms=5.0,
            fixed_air_velocity_ms=100.0,
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


if __name__ == "__main__":
    unittest.main()
