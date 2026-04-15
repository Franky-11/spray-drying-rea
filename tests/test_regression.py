from __future__ import annotations

import unittest

from app.ui_state import material_composition_defaults
from core.model import ScenarioConfig, SimulationInput, run_batch, run_simulation, summarize_input


class SimulationRegressionTests(unittest.TestCase):
    def test_default_case_runs_and_returns_expected_columns(self) -> None:
        result = run_simulation(SimulationInput())
        self.assertGreater(len(result.series), 50)
        self.assertEqual(
            list(result.series.columns),
            [
                "t",
                "height",
                "progress",
                "X",
                "Tp",
                "Tb",
                "Y",
                "RH",
                "vp",
                "dp",
                "Xe",
                "mat_factor",
                "psi",
                "rhovb",
                "rhovs",
                "driving_force",
                "q_conv_w",
                "q_latent_w",
                "q_sorption_w",
                "dTpdt_K_s",
                "TadSat",
                "Tp_minus_TadSat",
            ],
        )
        self.assertLess(result.series["X"].iloc[-1], result.series["X"].iloc[0])
        self.assertGreater(result.series["height"].iloc[-1], result.series["height"].iloc[0])
        self.assertGreater(result.series["progress"].iloc[-1], result.series["progress"].iloc[0])
        self.assertIsNotNone(result.metrics["outlet_time"])
        self.assertGreater(result.metrics["outlet_time"], 0.0)
        self.assertLess(result.metrics["outlet_X"], result.series["X"].iloc[0])
        self.assertGreater(result.metrics["outlet_X"], 0.0)
        self.assertLess(result.metrics["outlet_Tb"], result.series["Tb"].iloc[0])
        self.assertGreater(result.metrics["outlet_Tp"], result.series["Tp"].iloc[0])
        self.assertGreater(result.metrics["outlet_RH"], 0.0)
        self.assertLessEqual(float(result.series["psi"].max()), 1.0)
        self.assertGreater(float(result.series["mat_factor"].max()), 0.0)
        self.assertGreater(result.metrics["max_Tp"], result.series["Tp"].iloc[0])
        self.assertIsNotNone(result.metrics["time_Tp_gt_100C"])
        self.assertIsNotNone(result.metrics["X_at_Tp_gt_100C"])

    def test_invalid_wpc_total_solids_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_simulation(SimulationInput(material="WPC", feed_total_solids=0.5))

    def test_smp_20_percent_material_factor_stays_physical(self) -> None:
        result = run_simulation(SimulationInput(material="SMP", feed_total_solids=0.2))
        self.assertGreaterEqual(float(result.series["mat_factor"].min()), 0.0)
        self.assertLessEqual(float(result.series["psi"].max()), 1.0)
        self.assertAlmostEqual(float(result.series["mat_factor"].iloc[0]), 0.0)

    def test_smp_20_percent_uses_short_initial_wet_surface_regime(self) -> None:
        result = run_simulation(SimulationInput(material="SMP", feed_total_solids=0.2, time_points=4000))
        early = result.series[result.series["X"] > 3.8]
        later = result.series[result.series["X"] < 3.5]
        self.assertTrue((early["mat_factor"] == 0.0).all())
        self.assertGreater(float(later["mat_factor"].max()), 0.0)

    def test_material_composition_defaults_match_selected_material(self) -> None:
        self.assertEqual(material_composition_defaults("SMP"), {
            "protein_fraction": 0.35,
            "lactose_fraction": 0.55,
            "fat_fraction": 0.01,
        })
        self.assertEqual(material_composition_defaults("WPC"), {
            "protein_fraction": 0.8,
            "lactose_fraction": 0.074,
            "fat_fraction": 0.056,
        })

    def test_batch_run_preserves_order_and_labels(self) -> None:
        base = SimulationInput()
        variant = ScenarioConfig(label="Groeber", overrides={"droplet_size_um": 120.0}).apply(base)
        results = run_batch([base, variant], labels=["Basis", "Groeber"])
        self.assertEqual([result.label for result in results], ["Basis", "Groeber"])
        self.assertEqual(results[1].inputs.droplet_size_um, 120.0)

    def test_summary_contains_operating_point_values(self) -> None:
        summary = summarize_input(SimulationInput())
        self.assertGreater(summary["dry_solids_rate_kg_s"], 0.0)
        self.assertGreater(summary["humid_air_mass_flow_kg_s"], 0.0)
        self.assertGreater(summary["dry_air_mass_flow_kg_s"], 0.0)
        self.assertGreater(summary["air_to_solid_ratio_kg_kg"], 0.0)
        self.assertGreater(summary["effective_residence_time_s"], 0.0)

    def test_default_input_uses_smp_composition(self) -> None:
        default_input = SimulationInput()
        self.assertEqual(default_input.material, "SMP")
        self.assertAlmostEqual(default_input.protein_fraction, 0.35)
        self.assertAlmostEqual(default_input.lactose_fraction, 0.55)
        self.assertAlmostEqual(default_input.fat_fraction, 0.01)


if __name__ == "__main__":
    unittest.main()
