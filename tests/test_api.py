from __future__ import annotations

import sys
import unittest
from pathlib import Path

import httpx


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
for candidate in (REPO_ROOT, SRC_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from spray_drying.api import create_app


class SprayDryingApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        transport = httpx.ASGITransport(app=create_app())
        self.client = httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_health_endpoint(self) -> None:
        response = await self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    async def test_model_defaults_expose_v2_reference_case(self) -> None:
        response = await self.client.get("/model/defaults")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["x_b_models"], ["langrish", "lin_gab"])
        self.assertEqual(data["solver_methods"], ["BDF", "RK45", "Radau"])
        self.assertAlmostEqual(data["default_inputs"]["Tin"], 190.0)
        self.assertAlmostEqual(data["default_inputs"]["feed_rate_kg_h"], 15.0)
        self.assertAlmostEqual(data["default_inputs"]["droplet_size_um"], 65.0)
        self.assertAlmostEqual(data["default_inputs"]["humid_air_mass_flow_kg_h"], 300.0)
        self.assertAlmostEqual(data["default_inputs"]["inlet_abs_humidity_g_kg"], 6.0)
        self.assertAlmostEqual(data["default_inputs"]["feed_total_solids"], 0.37)
        labels = [item["label"] for item in data["reference_cases"]]
        self.assertEqual(labels[:3], ["V1", "V2", "V3"])

    async def test_reference_cases_endpoint_matches_defaults(self) -> None:
        response = await self.client.get("/presets/reference-cases")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 6)
        self.assertEqual(data[1]["label"], "V2")
        self.assertAlmostEqual(data[1]["measured_powder_moisture_wb_pct"], 3.2)

    async def test_simulate_returns_summary_and_profile(self) -> None:
        response = await self.client.post(
            "/simulate",
            json={
                "inputs": {
                    "Tin": 180.0,
                    "humid_air_mass_flow_kg_h": 304.0,
                    "feed_rate_kg_h": 17.0,
                    "droplet_size_um": 64.6,
                    "inlet_abs_humidity_g_kg": 5.7,
                    "feed_total_solids": 0.37,
                    "heat_loss_coeff_w_m2k": 1.4,
                    "x_b_model": "lin_gab",
                    "nozzle_delta_p_bar": 47.0,
                    "nozzle_velocity_coefficient": 0.6,
                    "dryer_diameter_m": 1.15,
                    "cylinder_height_m": 2.2,
                    "cone_height_m": 1.0,
                    "outlet_duct_length_m": 1.0,
                    "outlet_duct_diameter_m": 0.2
                },
                "target_moisture_wb_pct": 4.0,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["summary"]["solver_success"])
        self.assertGreater(data["profile"]["n_points"], 50)
        self.assertEqual(len(data["profile"]["series"]), data["profile"]["n_points"])
        self.assertIn("x_out_minus_x_b_out", data["summary"])
        self.assertIn("RHout_pct", data["summary"])
        self.assertIn("dmean_out_um", data["summary"])
        self.assertGreater(data["summary"]["Tout_c"], 50.0)
        self.assertGreaterEqual(data["summary"]["end_moisture_wb_pct"], 0.0)
        self.assertEqual(data["outlet"]["section"], "outlet_duct")
        self.assertIn("dmean_out_um", data["outlet"])
        self.assertIn("total_q_loss_w", data["outlet"])

    async def test_simulate_rejects_invalid_feed_solids(self) -> None:
        response = await self.client.post(
            "/simulate",
            json={
                "inputs": {
                    "Tin": 180.0,
                    "humid_air_mass_flow_kg_h": 304.0,
                    "feed_rate_kg_h": 17.0,
                    "droplet_size_um": 64.6,
                    "inlet_abs_humidity_g_kg": 5.7,
                    "feed_total_solids": 0.1,
                    "heat_loss_coeff_w_m2k": 1.4,
                    "x_b_model": "lin_gab",
                    "nozzle_delta_p_bar": 47.0,
                    "nozzle_velocity_coefficient": 0.6,
                    "dryer_diameter_m": 1.15,
                    "cylinder_height_m": 2.2,
                    "cone_height_m": 1.0,
                    "outlet_duct_length_m": 1.0,
                    "outlet_duct_diameter_m": 0.2
                }
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("feed_total_solids", response.json()["detail"])

    async def test_compare_returns_multiple_scenarios_and_base_id(self) -> None:
        response = await self.client.post(
            "/compare",
            json={
                "base_scenario_id": "base",
                "scenarios": [
                    {
                        "scenario_id": "base",
                        "label": "Basisfall",
                        "inputs": {
                            "Tin": 190.0,
                            "humid_air_mass_flow_kg_h": 300.0,
                            "feed_rate_kg_h": 15.0,
                            "droplet_size_um": 65.0,
                            "inlet_abs_humidity_g_kg": 6.0,
                            "feed_total_solids": 0.37,
                            "heat_loss_coeff_w_m2k": 1.4,
                            "x_b_model": "lin_gab",
                            "nozzle_delta_p_bar": 47.0,
                            "nozzle_velocity_coefficient": 0.6,
                            "dryer_diameter_m": 1.15,
                            "cylinder_height_m": 2.2,
                            "cone_height_m": 1.0,
                            "outlet_duct_length_m": 1.0,
                            "outlet_duct_diameter_m": 0.2,
                        },
                        "target_moisture_wb_pct": 4.0,
                    },
                    {
                        "scenario_id": "var-1",
                        "label": "Variante 1",
                        "inputs": {
                            "Tin": 195.0,
                            "humid_air_mass_flow_kg_h": 300.0,
                            "feed_rate_kg_h": 15.0,
                            "droplet_size_um": 65.0,
                            "inlet_abs_humidity_g_kg": 6.0,
                            "feed_total_solids": 0.37,
                            "heat_loss_coeff_w_m2k": 1.4,
                            "x_b_model": "lin_gab",
                            "nozzle_delta_p_bar": 47.0,
                            "nozzle_velocity_coefficient": 0.6,
                            "dryer_diameter_m": 1.15,
                            "cylinder_height_m": 2.2,
                            "cone_height_m": 1.0,
                            "outlet_duct_length_m": 1.0,
                            "outlet_duct_diameter_m": 0.2,
                        },
                        "target_moisture_wb_pct": 4.0,
                    },
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["base_scenario_id"], "base")
        self.assertEqual(len(data["scenarios"]), 2)
        self.assertEqual(data["scenarios"][0]["label"], "Basisfall")
        self.assertEqual(data["scenarios"][1]["scenario_id"], "var-1")
        self.assertIn("summary", data["scenarios"][0])
        self.assertIn("profile", data["scenarios"][1])
