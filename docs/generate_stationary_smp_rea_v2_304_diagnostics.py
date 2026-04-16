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


OUTPUT_PATH = Path("docs/stationary_smp_rea_v2_304_diagnostics.csv")
HUMID_AIR_MASS_FLOW_KG_H = 304.0


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
        "scenario": scenario,
        "notes": notes,
        "humid_air_mass_flow_kg_h": HUMID_AIR_MASS_FLOW_KG_H,
        "air_flow_m3_h": float(result.inputs.air_flow_m3_h),
        "heat_loss_coeff_w_m2k": float(result.inputs.heat_loss_coeff_w_m2k),
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
        "Yout_g_kg_da": 1000.0 * float(outlet["Y"]),
        "RHout_pct": 100.0 * float(series["RH_a"].iloc[-1]),
        "tau_out_s": float(outlet["tau_s"]) if outlet["tau_s"] is not None else "",
        "U_a_out_ms": float(outlet["U_a_ms"]),
        "U_p_out_ms": float(outlet["U_p_ms"]),
        "U_p_min_ms": float(series["U_p_ms"].min()),
        "U_p_mean_ms": float(series["U_p_ms"].mean()),
        "U_p_max_ms": float(series["U_p_ms"].max()),
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
    baseline_input = replace(base_input, air_flow_m3_h=air_flow_m3_h)
    baseline_result = solve_stationary_smp_profile(baseline_input)

    baseline_pre_cyclone = baseline_result.report_points["pre_cyclone"]
    fixed_velocity_input = replace(
        baseline_input,
        fixed_particle_velocity_ms=float(baseline_pre_cyclone["U_p_ms"]),
        fixed_air_velocity_ms=float(baseline_pre_cyclone["U_a_ms"]),
    )
    no_heat_loss_input = replace(baseline_input, heat_loss_coeff_w_m2k=0.0)

    no_heat_loss_result = solve_stationary_smp_profile(no_heat_loss_input)
    fixed_velocity_result = solve_stationary_smp_profile(fixed_velocity_input)

    rows = [
        _row(
            scenario="baseline_dynamic",
            notes="V2 fine kernel with the fixed 304 kg/h humid-air reference flow.",
            result=baseline_result,
            reference_tout_c=reference_tout_c,
            reference_wb_pct=reference_wb_pct,
        ),
        _row(
            scenario="dynamic_no_heat_loss",
            notes="Same V2 case, but q_loss disabled to isolate wall-loss sensitivity.",
            result=no_heat_loss_result,
            reference_tout_c=reference_tout_c,
            reference_wb_pct=reference_wb_pct,
        ),
        _row(
            scenario="fixed_velocities_from_baseline_pre_cyclone",
            notes="Same V2 case, but U_p and U_a fixed to the baseline pre-cyclone values to isolate dynamic residence-time coupling.",
            result=fixed_velocity_result,
            reference_tout_c=reference_tout_c,
            reference_wb_pct=reference_wb_pct,
        ),
    ]
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
