from __future__ import annotations

from math import exp
from pathlib import Path
import sys

import pandas as pd
from scipy.optimize import brentq, root


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stationary_smp_rea.air import moist_air_density, vapor_partial_pressure
from core.stationary_smp_rea.closures import equilibrium_moisture_lin_gab
from core.stationary_smp_rea.ms400 import build_ms400_stationary_input_from_label, load_ms400_experiments


OUTPUT_PATH = Path("docs/stationary_smp_rea_coarse_gab_v2.csv")

CP_DRY_AIR_KJ_KG_K = 1.0
CP_WATER_VAPOR_KJ_KG_K = 1.8
CP_LIQUID_WATER_KJ_KG_K = 4.2
LAMBDA_REF_KJ_KG = 2500.0


def saturation_vapor_pressure_pa(temp_c: float) -> float:
    return 133.3 * exp(18.3036 - 3816.44 / (temp_c + 229.02))


def solve_coarse_gab_state(
    *,
    sim_input,
    air_flow_m3_h: float,
) -> dict[str, float]:
    inlet_air_temp_c = sim_input.inlet_air_temp_c
    inlet_feed_temp_c = sim_input.feed_temp_c
    inlet_humidity_ratio = sim_input.inlet_abs_humidity_g_kg / 1000.0
    feed_moisture_db = (1.0 - sim_input.feed_total_solids) / sim_input.feed_total_solids
    dry_solids_mass_flow_kg_s = sim_input.feed_rate_kg_h * sim_input.feed_total_solids / 3600.0

    inlet_air_density_kg_m3 = moist_air_density(
        inlet_air_temp_c + 273.15,
        inlet_humidity_ratio,
        sim_input.pressure_pa,
    )
    humid_air_mass_flow_kg_s = inlet_air_density_kg_m3 * air_flow_m3_h / 3600.0
    dry_air_mass_flow_kg_s = humid_air_mass_flow_kg_s / (1.0 + inlet_humidity_ratio)

    feed_enthalpy_kw = dry_solids_mass_flow_kg_s * (
        sim_input.dry_solids_specific_heat_j_kg_k / 1000.0 * inlet_feed_temp_c
        + feed_moisture_db * CP_LIQUID_WATER_KJ_KG_K * inlet_feed_temp_c
    )
    air_enthalpy_kw = dry_air_mass_flow_kg_s * (
        CP_DRY_AIR_KJ_KG_K * inlet_air_temp_c
        + inlet_humidity_ratio
        * (LAMBDA_REF_KJ_KG + CP_WATER_VAPOR_KJ_KG_K * inlet_air_temp_c)
    )
    inlet_enthalpy_kw = feed_enthalpy_kw + air_enthalpy_kw

    def residuals(variables: list[float]) -> list[float]:
        outlet_temp_c, outlet_moisture_db = variables
        outlet_humidity_ratio = inlet_humidity_ratio + (
            dry_solids_mass_flow_kg_s / dry_air_mass_flow_kg_s
        ) * (feed_moisture_db - outlet_moisture_db)
        outlet_pv_pa = vapor_partial_pressure(outlet_humidity_ratio, sim_input.pressure_pa)
        outlet_psat_pa = saturation_vapor_pressure_pa(outlet_temp_c)
        outlet_rh = outlet_pv_pa / max(outlet_psat_pa, 1e-12)
        xeq_gab_db = equilibrium_moisture_lin_gab(outlet_temp_c + 273.15, outlet_rh)
        outlet_enthalpy_kw = dry_solids_mass_flow_kg_s * (
            sim_input.dry_solids_specific_heat_j_kg_k / 1000.0 * outlet_temp_c
            + outlet_moisture_db * CP_LIQUID_WATER_KJ_KG_K * outlet_temp_c
        ) + dry_air_mass_flow_kg_s * (
            CP_DRY_AIR_KJ_KG_K * outlet_temp_c
            + outlet_humidity_ratio
            * (LAMBDA_REF_KJ_KG + CP_WATER_VAPOR_KJ_KG_K * outlet_temp_c)
        )
        return [
            outlet_moisture_db - xeq_gab_db,
            outlet_enthalpy_kw - inlet_enthalpy_kw,
        ]

    solution = root(residuals, x0=[80.0, 0.04], method="hybr")
    if not solution.success:
        raise RuntimeError(f"Coarse GAB solve failed: {solution.message}")

    outlet_temp_c = float(solution.x[0])
    outlet_moisture_db = float(solution.x[1])
    outlet_moisture_wb_pct = 100.0 * outlet_moisture_db / (1.0 + outlet_moisture_db)
    outlet_humidity_ratio = inlet_humidity_ratio + (
        dry_solids_mass_flow_kg_s / dry_air_mass_flow_kg_s
    ) * (feed_moisture_db - outlet_moisture_db)
    outlet_pv_pa = vapor_partial_pressure(outlet_humidity_ratio, sim_input.pressure_pa)
    outlet_psat_pa = saturation_vapor_pressure_pa(outlet_temp_c)
    outlet_rh = outlet_pv_pa / max(outlet_psat_pa, 1e-12)

    return {
        "inlet_air_temp_c": inlet_air_temp_c,
        "inlet_feed_temp_c": inlet_feed_temp_c,
        "feed_rate_kg_h": sim_input.feed_rate_kg_h,
        "feed_total_solids": sim_input.feed_total_solids,
        "feed_moisture_db": feed_moisture_db,
        "air_flow_m3_h": air_flow_m3_h,
        "humid_air_mass_flow_kg_h": humid_air_mass_flow_kg_s * 3600.0,
        "dry_air_mass_flow_kg_h": dry_air_mass_flow_kg_s * 3600.0,
        "inlet_humidity_ratio_g_kg_da": 1000.0 * inlet_humidity_ratio,
        "predicted_outlet_temp_c": outlet_temp_c,
        "predicted_outlet_moisture_db": outlet_moisture_db,
        "predicted_outlet_moisture_wb_pct": outlet_moisture_wb_pct,
        "predicted_outlet_humidity_ratio_g_kg_da": 1000.0 * outlet_humidity_ratio,
        "predicted_outlet_rh_pct": 100.0 * outlet_rh,
        "predicted_outlet_pv_pa": outlet_pv_pa,
        "predicted_outlet_psat_pa": outlet_psat_pa,
    }


def main() -> None:
    sim_input = build_ms400_stationary_input_from_label("V2")
    experiment = load_ms400_experiments().set_index("label").loc["V2"]
    reference_outlet_temp_c = float(experiment["Tout_C"])
    reference_outlet_moisture_wb_pct = float(experiment["powder_moisture_wb_pct"])

    baseline_state = solve_coarse_gab_state(
        sim_input=sim_input,
        air_flow_m3_h=sim_input.air_flow_m3_h,
    )
    matched_air_flow_m3_h = brentq(
        lambda airflow: solve_coarse_gab_state(
            sim_input=sim_input,
            air_flow_m3_h=airflow,
        )["predicted_outlet_temp_c"]
        - reference_outlet_temp_c,
        sim_input.air_flow_m3_h,
        1000.0,
    )
    matched_state = solve_coarse_gab_state(
        sim_input=sim_input,
        air_flow_m3_h=matched_air_flow_m3_h,
    )

    rows = []
    for scenario, state in (
        ("baseline_builder_airflow", baseline_state),
        ("airflow_matched_to_reference_tout", matched_state),
    ):
        rows.append(
            {
                "case_id": "V2",
                "scenario": scenario,
                "model_scale": "coarse_well_mixed",
                "equilibrium_closure": "lin_gab",
                **state,
                "reference_outlet_temp_c": reference_outlet_temp_c,
                "reference_outlet_moisture_wb_pct": reference_outlet_moisture_wb_pct,
                "delta_temp_c": state["predicted_outlet_temp_c"] - reference_outlet_temp_c,
                "delta_moisture_wb_pct_points": state["predicted_outlet_moisture_wb_pct"] - reference_outlet_moisture_wb_pct,
            }
        )

    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
