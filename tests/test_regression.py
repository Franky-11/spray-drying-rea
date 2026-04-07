from __future__ import annotations

import unittest

from core.model import ScenarioConfig, SimulationInput, run_batch, run_simulation, summarize_input


class SimulationRegressionTests(unittest.TestCase):
    def test_default_case_runs_and_returns_expected_columns(self) -> None:
        result = run_simulation(SimulationInput())
        self.assertGreater(len(result.series), 50)
        self.assertEqual(
            list(result.series.columns),
            ["t", "height", "X", "Tp", "Tb", "Y", "RH", "vp", "dp", "Xe"],
        )
        self.assertLess(result.series["X"].iloc[-1], result.series["X"].iloc[0])
        self.assertGreater(result.series["height"].iloc[-1], result.series["height"].iloc[0])
        self.assertIsNotNone(result.metrics["outlet_time"])
        self.assertAlmostEqual(result.metrics["drying_time"], 1.6541353383458646, places=6)
        self.assertAlmostEqual(result.metrics["drying_height"], 0.8859828453220324, places=6)
        self.assertAlmostEqual(result.metrics["outlet_X"], 0.01734420817127426, places=9)
        self.assertAlmostEqual(result.metrics["outlet_Tb"], 351.4977067911271, places=6)
        self.assertAlmostEqual(result.metrics["outlet_Tp"], 351.51808070263723, places=6)
        self.assertAlmostEqual(result.metrics["outlet_RH"], 0.06926419191166566, places=9)

    def test_invalid_wpc_total_solids_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            run_simulation(SimulationInput(material="WPC", feed_total_solids=0.5))

    def test_batch_run_preserves_order_and_labels(self) -> None:
        base = SimulationInput()
        variant = ScenarioConfig(label="Groeber", overrides={"droplet_size_um": 120.0}).apply(base)
        results = run_batch([base, variant], labels=["Basis", "Groeber"])
        self.assertEqual([result.label for result in results], ["Basis", "Groeber"])
        self.assertEqual(results[1].inputs.droplet_size_um, 120.0)

    def test_summary_contains_operating_point_values(self) -> None:
        summary = summarize_input(SimulationInput())
        self.assertGreater(summary["air_superficial_velocity_ms"], 0.0)
        self.assertGreater(summary["humid_air_mass_flow_kg_s"], 0.0)
        self.assertGreater(summary["droplets_per_s"], 0.0)


if __name__ == "__main__":
    unittest.main()
