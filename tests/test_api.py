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

    async def test_model_defaults_expose_runtime_defaults(self) -> None:
        response = await self.client.get("/model/defaults")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(
            data["x_b_models"],
            ["langrish", "lin_gab", "lin_gab_langrish_blend", "lin_gab_langrish_blend_rh"],
        )
        self.assertEqual(data["solver_methods"], ["BDF", "RK45", "Radau"])
        self.assertAlmostEqual(data["default_inputs"]["Tin"], 190.0)
        self.assertAlmostEqual(data["default_inputs"]["feed_rate_kg_h"], 15.0)
        self.assertAlmostEqual(data["default_inputs"]["droplet_size_um"], 65.0)
        self.assertAlmostEqual(data["default_inputs"]["humid_air_mass_flow_kg_h"], 300.0)
        self.assertAlmostEqual(data["default_inputs"]["inlet_abs_humidity_g_kg"], 6.0)
        self.assertAlmostEqual(data["default_inputs"]["feed_total_solids"], 0.37)
        self.assertAlmostEqual(data["default_inputs"]["contact_efficiency"], 1.0)
        self.assertAlmostEqual(data["default_inputs"]["atomization_zone_length_m"], 0.0)
        self.assertAlmostEqual(data["default_inputs"]["atomization_zone_exposure_factor"], 1.0)
        self.assertAlmostEqual(data["default_inputs"]["secondary_exposure_zone_length_m"], 0.0)
        self.assertAlmostEqual(data["default_inputs"]["secondary_exposure_zone_factor"], 1.0)
        self.assertEqual(data["default_inputs"]["effective_gas_humidity_mode"], "off")
        self.assertAlmostEqual(data["default_inputs"]["humidity_bias_zone_length_m"], 0.0)
        self.assertAlmostEqual(data["default_inputs"]["humidity_bias_zone_target_rh"], 0.0)
        self.assertAlmostEqual(data["default_inputs"]["humidity_bias_zone2_length_m"], 0.0)
        self.assertAlmostEqual(data["default_inputs"]["humidity_bias_zone2_target_rh"], 0.0)
        self.assertFalse(data["default_inputs"]["enable_material_retardation_add"])
        self.assertEqual(data["default_inputs"]["x_b_model"], "lin_gab_langrish_blend_rh")
        self.assertAlmostEqual(data["default_inputs"]["x_b_blend_langrish_weight"], 0.5)
        self.assertAlmostEqual(data["default_inputs"]["x_b_blend_langrish_weight_base"], 0.02)
        self.assertAlmostEqual(data["default_inputs"]["x_b_blend_langrish_weight_rh_coeff"], 2.0)
        self.assertNotIn("reference_cases", data)

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
                    "contact_efficiency": 0.9,
                    "atomization_zone_length_m": 0.3,
                    "atomization_zone_exposure_factor": 0.75,
                    "secondary_exposure_zone_length_m": 0.5,
                    "secondary_exposure_zone_factor": 0.85,
                    "effective_gas_humidity_mode": "target_rh",
                    "humidity_bias_zone_length_m": 0.4,
                    "humidity_bias_zone_target_rh": 0.25,
                    "humidity_bias_zone2_length_m": 0.6,
                    "humidity_bias_zone2_target_rh": 0.18,
                    "enable_material_retardation_add": False,
                    "x_b_model": "lin_gab_langrish_blend_rh",
                    "x_b_blend_langrish_weight_base": 0.05,
                    "x_b_blend_langrish_weight_rh_coeff": 5.0,
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
        self.assertIn("delta_t_air_particle_c", data["profile"]["series"][0])
        self.assertIn("axial_exposure_factor", data["profile"]["series"][0])
        self.assertIn("combined_contact_exposure_factor", data["profile"]["series"][0])
        self.assertIn("RH_eff_pct", data["profile"]["series"][0])
        self.assertIn("Y_eff", data["profile"]["series"][0])
        self.assertIn("humidity_bias_active", data["profile"]["series"][0])
        self.assertIn("q_evap_to_conv_ratio", data["profile"]["series"][0])
        self.assertAlmostEqual(data["inputs"]["contact_efficiency"], 0.9)
        self.assertAlmostEqual(data["inputs"]["atomization_zone_length_m"], 0.3)
        self.assertAlmostEqual(data["inputs"]["atomization_zone_exposure_factor"], 0.75)
        self.assertAlmostEqual(data["inputs"]["secondary_exposure_zone_length_m"], 0.5)
        self.assertAlmostEqual(data["inputs"]["secondary_exposure_zone_factor"], 0.85)
        self.assertEqual(data["inputs"]["effective_gas_humidity_mode"], "target_rh")
        self.assertAlmostEqual(data["inputs"]["humidity_bias_zone_length_m"], 0.4)
        self.assertAlmostEqual(data["inputs"]["humidity_bias_zone_target_rh"], 0.25)
        self.assertAlmostEqual(data["inputs"]["humidity_bias_zone2_length_m"], 0.6)
        self.assertAlmostEqual(data["inputs"]["humidity_bias_zone2_target_rh"], 0.18)
        self.assertFalse(data["inputs"]["enable_material_retardation_add"])
        self.assertEqual(data["inputs"]["x_b_model"], "lin_gab_langrish_blend_rh")
        self.assertAlmostEqual(data["inputs"]["x_b_blend_langrish_weight_base"], 0.05)
        self.assertAlmostEqual(data["inputs"]["x_b_blend_langrish_weight_rh_coeff"], 5.0)

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

    async def test_simulate_accepts_50_percent_feed_solids(self) -> None:
        response = await self.client.post(
            "/simulate",
            json={
                "inputs": {
                    "Tin": 180.0,
                    "humid_air_mass_flow_kg_h": 304.0,
                    "feed_rate_kg_h": 17.0,
                    "droplet_size_um": 64.6,
                    "inlet_abs_humidity_g_kg": 5.7,
                    "feed_total_solids": 0.50,
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
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["summary"]["solver_success"])
        self.assertTrue(
            any("Above 43 wt%" in warning for warning in data["warnings"])
        )

    async def test_compare_returns_multiple_scenarios_and_base_id(self) -> None:
        response = await self.client.post(
            "/compare",
            json={
                "base_scenario_id": "base",
                "scenarios": [
                    {
                        "scenario_id": "base",
                        "label": "Base case",
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
                        "label": "Scenario 1",
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
        self.assertEqual(data["scenarios"][0]["label"], "Base case")
        self.assertEqual(data["scenarios"][1]["scenario_id"], "var-1")
        self.assertIn("summary", data["scenarios"][0])
        self.assertIn("profile", data["scenarios"][1])
