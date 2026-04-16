from __future__ import annotations

import csv
import sys
from dataclasses import replace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.stationary_smp_rea import StationarySMPREAInput, solve_stationary_smp_profile
from core.stationary_smp_rea.air import moist_air_density


def humid_air_mass_flow_to_volumetric_flow_m3_h(
    humid_air_mass_flow_kg_h: float,
    inlet_air_temp_c: float,
    inlet_abs_humidity_g_kg: float,
    pressure_pa: float = 101325.0,
) -> float:
    rho_air = moist_air_density(
        inlet_air_temp_c + 273.15,
        inlet_abs_humidity_g_kg / 1000.0,
        pressure_pa,
    )
    return humid_air_mass_flow_kg_h / max(rho_air, 1e-12)


def summarize_case(
    *,
    sweep: str,
    case_id: str,
    baseline_case_id: str,
    varied_parameter: str,
    sim_input: StationarySMPREAInput,
    humid_air_mass_flow_kg_h: float,
) -> dict[str, float | str]:
    result = solve_stationary_smp_profile(sim_input)
    pre_cyclone = result.report_points["pre_cyclone"]
    outlet_x_db = float(pre_cyclone["X"])
    outlet_wb_pct = 100.0 * outlet_x_db / (1.0 + outlet_x_db)
    outlet_row = result.series.iloc[-1]
    inlet_row = result.series.iloc[0]
    return {
        "sweep": sweep,
        "case_id": case_id,
        "baseline_case_id": baseline_case_id,
        "varied_parameter": varied_parameter,
        "inlet_air_temp_c": sim_input.inlet_air_temp_c,
        "humid_air_mass_flow_kg_h": humid_air_mass_flow_kg_h,
        "air_flow_m3_h": sim_input.air_flow_m3_h,
        "feed_rate_kg_h": sim_input.feed_rate_kg_h,
        "feed_total_solids": sim_input.feed_total_solids,
        "droplet_size_um": sim_input.droplet_size_um,
        "inlet_u_a_ms": float(inlet_row["U_a_ms"]),
        "outlet_u_a_ms": float(pre_cyclone["U_a_ms"]),
        "outlet_tau_s": float(pre_cyclone["tau_s"]),
        "Tout_pre_cyclone_c": float(pre_cyclone["T_a_c"]),
        "Yout_g_kg_da": 1000.0 * float(pre_cyclone["Y"]),
        "RHout_pct": 100.0 * float(outlet_row["RH_a"]),
        "powder_moisture_wb_pct": outlet_wb_pct,
        "powder_moisture_db": outlet_x_db,
        "Re_mean": float(result.series["Re"].mean()),
        "hm_mean_ms": float(result.series["h_m_ms"].mean()),
        "Nu_mean": float(result.series["Nu"].mean()),
        "total_q_loss_w": float(result.outlet["total_q_loss_w"]),
    }


def build_rows() -> list[dict[str, float | str]]:
    default_input = StationarySMPREAInput()
    inlet_air_temp_c = 190.0
    humid_air_200 = 200.0
    humid_air_250 = 250.0

    base_air_200 = replace(
        default_input,
        inlet_air_temp_c=inlet_air_temp_c,
        air_flow_m3_h=humid_air_mass_flow_to_volumetric_flow_m3_h(
            humid_air_200,
            inlet_air_temp_c,
            default_input.inlet_abs_humidity_g_kg,
        ),
    )
    air_250 = replace(
        base_air_200,
        air_flow_m3_h=humid_air_mass_flow_to_volumetric_flow_m3_h(
            humid_air_250,
            inlet_air_temp_c,
            default_input.inlet_abs_humidity_g_kg,
        ),
    )
    feed_10 = replace(base_air_200, feed_rate_kg_h=10.0)
    feed_20 = replace(base_air_200, feed_rate_kg_h=20.0)

    return [
        summarize_case(
            sweep="air_mass_sweep",
            case_id="air_200",
            baseline_case_id="air_200",
            varied_parameter="humid_air_mass_flow_kg_h",
            sim_input=base_air_200,
            humid_air_mass_flow_kg_h=humid_air_200,
        ),
        summarize_case(
            sweep="air_mass_sweep",
            case_id="air_250",
            baseline_case_id="air_200",
            varied_parameter="humid_air_mass_flow_kg_h",
            sim_input=air_250,
            humid_air_mass_flow_kg_h=humid_air_250,
        ),
        summarize_case(
            sweep="feed_rate_sweep",
            case_id="feed_10",
            baseline_case_id="feed_10",
            varied_parameter="feed_rate_kg_h",
            sim_input=feed_10,
            humid_air_mass_flow_kg_h=humid_air_200,
        ),
        summarize_case(
            sweep="feed_rate_sweep",
            case_id="feed_20",
            baseline_case_id="feed_10",
            varied_parameter="feed_rate_kg_h",
            sim_input=feed_20,
            humid_air_mass_flow_kg_h=humid_air_200,
        ),
    ]


def main() -> None:
    output_path = Path(__file__).with_name("stationary_smp_rea_sanity_sweeps.csv")
    rows = build_rows()
    fieldnames = list(rows[0].keys())
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(output_path)


if __name__ == "__main__":
    main()
