from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stationary_smp_rea import build_ms400_stationary_input_from_label, solve_stationary_smp_profile
from core.stationary_smp_rea.air import moist_air_density
from core.stationary_smp_rea.ms400 import load_ms400_experiments


OUTPUT_PATH = Path("docs/stationary_smp_rea_v2_feedrate_velocity_diagnostics.csv")
HUMID_AIR_MASS_FLOW_KG_H = 304.0
FEED_RATE_KG_H = 14.0
HEAT_LOSS_COEFF_W_M2K = 2.0


def _humid_air_mass_flow_to_volumetric_flow_m3_h(sim_input, humid_air_mass_flow_kg_h: float) -> float:
    inlet_density = moist_air_density(
        sim_input.inlet_air_temp_c + 273.15,
        sim_input.inlet_abs_humidity_g_kg / 1000.0,
        sim_input.pressure_pa,
    )
    return humid_air_mass_flow_kg_h / max(inlet_density, 1e-12)


def _row(
    *,
    scenario: str,
    notes: str,
    result,
    reference_tout_c: float,
    reference_wb_pct: float,
) -> dict[str, float | str]:
    outlet = result.report_points["pre_cyclone"]
    outlet_x_db = float(outlet["X"])
    outlet_wb_pct = 100.0 * outlet_x_db / (1.0 + outlet_x_db)
    series = result.series
    return {
        "case_id": "V2",
        "feed_rate_kg_h": FEED_RATE_KG_H,
        "humid_air_mass_flow_kg_h": HUMID_AIR_MASS_FLOW_KG_H,
        "heat_loss_coeff_w_m2k": HEAT_LOSS_COEFF_W_M2K,
        "scenario": scenario,
        "notes": notes,
        "fixed_particle_velocity_ms": (
            "" if result.inputs.fixed_particle_velocity_ms is None else float(result.inputs.fixed_particle_velocity_ms)
        ),
        "fixed_air_velocity_ms": (
            "" if result.inputs.fixed_air_velocity_ms is None else float(result.inputs.fixed_air_velocity_ms)
        ),
        "Tout_pre_cyclone_c": float(outlet["T_a_c"]),
        "Tp_pre_cyclone_c": float(outlet["T_p_c"]),
        "powder_moisture_db": outlet_x_db,
        "powder_moisture_wb_pct": outlet_wb_pct,
        "x_b_pre_cyclone_db": float(series["x_b"].iloc[-1]),
        "x_b_pre_cyclone_wb_pct": 100.0 * float(series["x_b"].iloc[-1]) / (1.0 + float(series["x_b"].iloc[-1])),
        "Yout_g_kg_da": 1000.0 * float(outlet["Y"]),
        "RHout_pct": 100.0 * float(series["RH_a"].iloc[-1]),
        "tau_out_s": float(outlet["tau_s"]) if outlet["tau_s"] is not None else "",
        "U_a_out_ms": float(outlet["U_a_ms"]),
        "U_p_out_ms": float(outlet["U_p_ms"]),
        "U_a_mean_ms": float(series["U_a_ms"].mean()),
        "U_p_mean_ms": float(series["U_p_ms"].mean()),
        "Re_mean": float(series["Re"].mean()),
        "hm_mean_ms": float(series["h_m_ms"].mean()),
        "total_q_loss_w": float(result.outlet["total_q_loss_w"]),
        "reference_Tout_c": reference_tout_c,
        "reference_powder_moisture_wb_pct": reference_wb_pct,
        "delta_Tout_c": float(outlet["T_a_c"]) - reference_tout_c,
        "delta_powder_moisture_wb_pct_points": outlet_wb_pct - reference_wb_pct,
    }


def main() -> None:
    experiment = load_ms400_experiments().set_index("label").loc["V2"]
    reference_tout_c = float(experiment["Tout_C"])
    reference_wb_pct = float(experiment["powder_moisture_wb_pct"])

    base_input = build_ms400_stationary_input_from_label("V2")
    air_flow_m3_h = _humid_air_mass_flow_to_volumetric_flow_m3_h(
        base_input,
        HUMID_AIR_MASS_FLOW_KG_H,
    )
    dynamic_input = replace(
        base_input,
        air_flow_m3_h=air_flow_m3_h,
        feed_rate_kg_h=FEED_RATE_KG_H,
        heat_loss_coeff_w_m2k=HEAT_LOSS_COEFF_W_M2K,
    )
    dynamic_result = solve_stationary_smp_profile(dynamic_input)
    dynamic_pre_cyclone = dynamic_result.report_points["pre_cyclone"]
    fixed_u_a_value = float(dynamic_pre_cyclone["U_a_ms"])
    fixed_u_p_value = float(dynamic_pre_cyclone["U_p_ms"])

    scenarios = [
        (
            "dynamic",
            "Fully coupled velocities.",
            dynamic_result,
        ),
        (
            "fixed_air_from_dynamic_pre_cyclone",
            "Only U_a fixed to the dynamic pre-cyclone value.",
            solve_stationary_smp_profile(
                replace(dynamic_input, fixed_air_velocity_ms=fixed_u_a_value)
            ),
        ),
        (
            "fixed_particle_from_dynamic_pre_cyclone",
            "Only U_p fixed to the dynamic pre-cyclone value.",
            solve_stationary_smp_profile(
                replace(dynamic_input, fixed_particle_velocity_ms=fixed_u_p_value)
            ),
        ),
        (
            "fixed_both_from_dynamic_pre_cyclone",
            "U_a and U_p both fixed to the dynamic pre-cyclone values.",
            solve_stationary_smp_profile(
                replace(
                    dynamic_input,
                    fixed_air_velocity_ms=fixed_u_a_value,
                    fixed_particle_velocity_ms=fixed_u_p_value,
                )
            ),
        ),
    ]

    rows = [
        _row(
            scenario=scenario,
            notes=notes,
            result=result,
            reference_tout_c=reference_tout_c,
            reference_wb_pct=reference_wb_pct,
        )
        for scenario, notes, result in scenarios
    ]
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
