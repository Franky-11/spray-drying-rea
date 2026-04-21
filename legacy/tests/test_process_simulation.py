from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from legacy.python_core import (
    ProcessEvent,
    ProcessSimulationInput,
    SimulationInput,
    build_stepwise_inputs,
    run_process_simulation,
)


class ProcessSimulationTests(unittest.TestCase):
    def test_build_stepwise_inputs_carries_forward_values_and_labels(self) -> None:
        sim_input = ProcessSimulationInput(
            base_input=SimulationInput(),
            events=[
                ProcessEvent(time_s=10.0, inlet_air_temp_c=200.0, label="Tin hoch"),
                ProcessEvent(time_s=20.0, feed_rate_kg_h=4.0),
                ProcessEvent(time_s=30.0, feed_total_solids=0.3, label="TS runter"),
            ],
            duration_s=40.0,
            time_step_s=10.0,
        )

        schedule = build_stepwise_inputs(sim_input)

        self.assertEqual(schedule["t"].tolist(), [0.0, 10.0, 20.0, 30.0, 40.0])
        self.assertEqual(schedule["inlet_air_temp_c"].tolist(), [190.0, 200.0, 200.0, 200.0, 200.0])
        self.assertEqual(schedule["feed_rate_kg_h"].tolist(), [3.0, 3.0, 4.0, 4.0, 4.0])
        self.assertEqual(schedule["feed_total_solids"].tolist(), [0.5, 0.5, 0.5, 0.3, 0.3])
        self.assertEqual(schedule["event_label"].tolist(), ["", "Tin hoch", "Tin hoch", "TS runter", "TS runter"])

    def test_segment_change_updates_targets_immediately_but_actuals_with_delay(self) -> None:
        result = run_process_simulation(
            ProcessSimulationInput(
                base_input=SimulationInput(),
                events=[ProcessEvent(time_s=10.0, inlet_air_temp_c=200.0, label="Tin hoch")],
                duration_s=40.0,
                time_step_s=10.0,
            )
        )

        series = result.series
        before = series.loc[series["t"] == 0.0].iloc[0]
        at_switch = series.loc[series["t"] == 10.0].iloc[0]
        after_switch = series.loc[series["t"] == 20.0].iloc[0]
        later = series.loc[series["t"] == 40.0].iloc[0]

        self.assertEqual(at_switch["event_label"], "Tin hoch")
        self.assertGreater(at_switch["target_outlet_Tb"], before["target_outlet_Tb"])
        self.assertLess(at_switch["target_outlet_X"], before["target_outlet_X"])
        self.assertAlmostEqual(at_switch["outlet_Tb"], before["outlet_Tb"], places=5)
        self.assertAlmostEqual(at_switch["outlet_X"], before["outlet_X"], places=5)
        self.assertGreater(after_switch["outlet_Tb"], before["outlet_Tb"])
        self.assertLess(after_switch["outlet_X"], before["outlet_X"])
        self.assertGreater(later["outlet_Tb"], before["outlet_Tb"])
        self.assertLess(later["outlet_X"], before["outlet_X"])
        self.assertGreater(at_switch["target_outlet_time_s"], 0.0)

    def test_inlet_temperature_step_drives_hotter_and_drier_output(self) -> None:
        result = run_process_simulation(
            ProcessSimulationInput(
                base_input=SimulationInput(),
                events=[ProcessEvent(time_s=20.0, inlet_air_temp_c=205.0)],
                duration_s=120.0,
                time_step_s=10.0,
            )
        )

        start = result.series.iloc[0]
        end = result.series.iloc[-1]

        self.assertLess(end["outlet_X"], start["outlet_X"])
        self.assertGreater(end["outlet_Tb"], start["outlet_Tb"])
        self.assertLess(end["moisture_error"], start["moisture_error"])
        self.assertGreater(end["q_loss_w"], start["q_loss_w"])
        self.assertGreaterEqual(end["evaporation_rate_kg_s"], 0.0)
        self.assertGreaterEqual(end["latent_load_w"], 0.0)

    def test_higher_inlet_humidity_increases_residual_moisture(self) -> None:
        result = run_process_simulation(
            ProcessSimulationInput(
                base_input=SimulationInput(),
                events=[ProcessEvent(time_s=20.0, inlet_abs_humidity_g_kg=12.0, label="Sommerregen")],
                duration_s=120.0,
                time_step_s=10.0,
            )
        )

        start = result.series.iloc[0]
        end = result.series.iloc[-1]

        self.assertGreater(end["outlet_X"], start["outlet_X"])
        self.assertGreater(end["outlet_Y"], start["outlet_Y"])
        self.assertGreater(end["moisture_error"], start["moisture_error"])
        self.assertGreaterEqual(end["evaporation_rate_kg_s"], 0.0)

    def test_lower_total_solids_increases_residual_moisture(self) -> None:
        result = run_process_simulation(
            ProcessSimulationInput(
                base_input=SimulationInput(),
                events=[ProcessEvent(time_s=20.0, feed_total_solids=0.3, label="TS runter")],
                duration_s=120.0,
                time_step_s=10.0,
            )
        )

        start = result.series.iloc[0]
        end = result.series.iloc[-1]

        self.assertNotAlmostEqual(end["outlet_X"], start["outlet_X"])
        self.assertNotAlmostEqual(end["outlet_Tb"], start["outlet_Tb"])
        self.assertGreaterEqual(end["evaporation_rate_kg_s"], 0.0)

    def test_process_result_contains_derived_balance_columns(self) -> None:
        result = run_process_simulation(
            ProcessSimulationInput(
                base_input=SimulationInput(),
                events=[],
                duration_s=20.0,
                time_step_s=10.0,
            )
        )

        for column in (
            "target_outlet_time_s",
            "q_loss_w",
            "evaporation_rate_kg_s",
            "latent_load_w",
        ):
            self.assertIn(column, result.series.columns)

        self.assertGreater(result.series["target_outlet_time_s"].iloc[0], 0.0)
        self.assertGreater(result.series["q_loss_w"].iloc[0], 0.0)
        self.assertGreaterEqual(result.series["evaporation_rate_kg_s"].iloc[0], 0.0)
        self.assertGreaterEqual(result.series["latent_load_w"].iloc[0], 0.0)
        self.assertAlmostEqual(
            result.kpis["final_q_loss_w"],
            float(result.series["q_loss_w"].iloc[-1]),
        )


if __name__ == "__main__":
    unittest.main()
