from __future__ import annotations

import unittest

from core.stationary_smp_rea import StationarySMPREAInput, solve_stationary_smp_profile
from core.stationary_smp_rea.materials.smp_chew import (
    initial_moisture_dry_basis,
    linear_parameters_from_initial_moisture,
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
            any("37-43 wt%" in warning for warning in result.warnings)
        )
        self.assertLess(
            result.outlet["outlet_X"],
            result.series["X"].iloc[0],
        )

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


if __name__ == "__main__":
    unittest.main()
