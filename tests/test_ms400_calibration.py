from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core import (
    MS400CalibrationParameters,
    MS400CalibrationSettings,
    evaluate_ms400_stationary_model,
    load_ms400_stationary_experiments,
    ms400_calibration_residuals,
    run_simulation,
)
from core.model import SimulationInput, _build_derived, _rea_snapshot


class MS400CalibrationTests(unittest.TestCase):
    def test_smp_37_percent_runs(self) -> None:
        result = run_simulation(
            SimulationInput(
                material="SMP",
                feed_total_solids=0.37,
                feed_rate_kg_h=17.0,
                droplet_size_um=85.0,
                air_flow_m3_h=170.0,
                inlet_air_temp_c=180.0,
                inlet_abs_humidity_g_kg=5.0,
                feed_temp_c=40.0,
                simulation_end_s=30.0,
                time_points=300,
            )
        )

        self.assertGreater(len(result.series), 50)
        self.assertLess(result.metrics["outlet_X"], result.series["X"].iloc[0])
        self.assertGreater(result.metrics["outlet_Tb"], 273.15)

    def test_loader_falls_back_to_summary_d43_when_psd_missing(self) -> None:
        experiments = load_ms400_stationary_experiments(psd_path=Path("missing_psd.csv"))

        self.assertEqual(len(experiments), 6)
        self.assertIn("d32_um", experiments.columns)
        self.assertAlmostEqual(
            float(experiments.loc[experiments["label"] == "V1", "d32_um"].iloc[0]),
            78.0,
        )

    def test_loader_merges_psd_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "psd.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "Versuch,D50 [um],D10 [um],D90 [um],d32,d43,Span",
                        "V1,73,39,122,61,78,1.14",
                        "V2,55,27,106,46,63,1.44",
                    ]
                ),
                encoding="utf-8",
            )
            experiments = load_ms400_stationary_experiments(csv_path)

        v1 = experiments.loc[experiments["label"] == "V1"].iloc[0]
        v3 = experiments.loc[experiments["label"] == "V3"].iloc[0]
        self.assertAlmostEqual(float(v1["d32_um"]), 61.0)
        self.assertAlmostEqual(float(v1["d10_um"]), 39.0)
        self.assertAlmostEqual(float(v3["d32_um"]), 78.0)

    def test_evaluation_returns_prediction_frame(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "psd.csv"
            csv_path.write_text(
                "\n".join(
                    [
                        "Versuch,D50 [um],D10 [um],D90 [um],d32,d43,Span",
                        "V1,73,39,122,61,78,1.14",
                        "V2,55,27,106,46,63,1.44",
                        "V3,62,29,147,52,78,1.90",
                    ]
                ),
                encoding="utf-8",
            )
            experiments = load_ms400_stationary_experiments(csv_path).head(3)

        series = evaluate_ms400_stationary_model(
            experiments,
            MS400CalibrationSettings(simulation_end_s=25.0, time_points=240),
            MS400CalibrationParameters(
                particle_scale=1.0,
                rea_transfer_scale=1.0,
                heat_loss_coeff_w_m2k=4.5,
                equilibrium_moisture_offset=0.0,
            ),
        )

        self.assertEqual(series["label"].tolist(), ["V1", "V2", "V3"])
        for column in (
            "Tout_predicted_C",
            "moisture_predicted_wb_pct",
            "effective_input_diameter_um",
        ):
            self.assertIn(column, series.columns)
        self.assertTrue(series["Tout_predicted_C"].notna().all())
        self.assertTrue(series["moisture_predicted_wb_pct"].gt(0.0).all())

    def test_default_settings_exclude_v1_and_v4_from_fit_only(self) -> None:
        experiments = load_ms400_stationary_experiments(psd_path=Path("missing_psd.csv"))
        settings = MS400CalibrationSettings()
        series = evaluate_ms400_stationary_model(
            experiments,
            settings,
            MS400CalibrationParameters(),
        )

        used = dict(zip(series["label"], series["use_for_calibration"], strict=True))
        self.assertFalse(used["V1"])
        self.assertFalse(used["V4"])
        self.assertTrue(used["V2"])
        self.assertTrue(used["V3"])
        self.assertTrue(used["V5"])
        self.assertTrue(used["V6"])

    def test_residuals_only_use_non_blowup_cases_by_default(self) -> None:
        experiments = load_ms400_stationary_experiments(psd_path=Path("missing_psd.csv"))
        residuals = ms400_calibration_residuals(
            vector=[1.0, 1.0, 4.5, 0.0],
            experiments=experiments,
            settings=MS400CalibrationSettings(),
        )

        self.assertEqual(len(residuals), 8)

    def test_air_energy_balance_uses_only_sensible_evaporation_term(self) -> None:
        sim_input = SimulationInput(
            material="SMP",
            feed_total_solids=0.37,
            feed_rate_kg_h=17.0,
            droplet_size_um=85.0,
            air_flow_m3_h=170.0,
            inlet_air_temp_c=180.0,
            inlet_abs_humidity_g_kg=5.0,
            feed_temp_c=40.0,
        )
        derived = _build_derived(sim_input)
        snapshot = _rea_snapshot(
            derived.x0,
            derived.tp0_k,
            derived.tb0_k,
            derived.y0,
            sim_input.material,
            derived,
            air_to_solid_ratio=derived.air_to_solid_ratio,
            heat_loss_factor_w_kgk=derived.heat_loss_factor_w_kgk,
        )

        cp_air = derived.cpdryair + derived.y0 * derived.cpv
        expected = (
            -snapshot["q_conv_w"]
            - snapshot["q_loss_w"]
            - snapshot["evap_rate_kg_per_kg_s"] * derived.cpv * (derived.tb0_k - derived.tp0_k)
        ) / (derived.air_to_solid_ratio * cp_air)

        self.assertAlmostEqual(snapshot["dTbdt_K_s"], expected)
        self.assertGreater(snapshot["q_latent_w"], snapshot["q_air_sensible_evap_w"])


if __name__ == "__main__":
    unittest.main()
