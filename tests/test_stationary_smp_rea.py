from __future__ import annotations

import unittest

from core.stationary_smp_rea import StationarySMPREAInput, solve_stationary_smp_profile


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


if __name__ == "__main__":
    unittest.main()
