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


def base_case() -> StationarySMPREAInput:
    default_input = StationarySMPREAInput()
    return replace(
        default_input,
        inlet_air_temp_c=190.0,
        air_flow_m3_h=humid_air_mass_flow_to_volumetric_flow_m3_h(
            200.0,
            190.0,
            default_input.inlet_abs_humidity_g_kg,
        ),
    )


def case_rows() -> list[dict[str, float | str]]:
    base = base_case()
    cases = [
        (
            "dynamic",
            "air_200",
            base,
            200.0,
        ),
        (
            "dynamic",
            "air_250",
            replace(
                base,
                air_flow_m3_h=humid_air_mass_flow_to_volumetric_flow_m3_h(
                    250.0,
                    190.0,
                    base.inlet_abs_humidity_g_kg,
                ),
            ),
            250.0,
        ),
        (
            "dynamic",
            "feed_10",
            replace(base, feed_rate_kg_h=10.0),
            200.0,
        ),
        (
            "dynamic",
            "feed_20",
            replace(base, feed_rate_kg_h=20.0),
            200.0,
        ),
        (
            "foods_fixed_vp5_va100",
            "air_200",
            replace(base, fixed_particle_velocity_ms=5.0, fixed_air_velocity_ms=100.0),
            200.0,
        ),
        (
            "foods_fixed_vp5_va100",
            "air_250",
            replace(
                base,
                air_flow_m3_h=humid_air_mass_flow_to_volumetric_flow_m3_h(
                    250.0,
                    190.0,
                    base.inlet_abs_humidity_g_kg,
                ),
                fixed_particle_velocity_ms=5.0,
                fixed_air_velocity_ms=100.0,
            ),
            250.0,
        ),
        (
            "foods_fixed_vp5_va100",
            "feed_10",
            replace(
                base,
                feed_rate_kg_h=10.0,
                fixed_particle_velocity_ms=5.0,
                fixed_air_velocity_ms=100.0,
            ),
            200.0,
        ),
        (
            "foods_fixed_vp5_va100",
            "feed_20",
            replace(
                base,
                feed_rate_kg_h=20.0,
                fixed_particle_velocity_ms=5.0,
                fixed_air_velocity_ms=100.0,
            ),
            200.0,
        ),
    ]

    rows: list[dict[str, float | str]] = []
    for velocity_mode, case_id, sim_input, humid_air_mass_flow_kg_h in cases:
        result = solve_stationary_smp_profile(sim_input)
        pre_cyclone = result.report_points["pre_cyclone"]
        outlet_row = result.series.iloc[-1]
        outlet_x_db = float(pre_cyclone["X"])
        rows.append(
            {
                "velocity_mode": velocity_mode,
                "case_id": case_id,
                "humid_air_mass_flow_kg_h": humid_air_mass_flow_kg_h,
                "air_flow_m3_h": sim_input.air_flow_m3_h,
                "feed_rate_kg_h": sim_input.feed_rate_kg_h,
                "fixed_particle_velocity_ms": sim_input.fixed_particle_velocity_ms
                if sim_input.fixed_particle_velocity_ms is not None
                else "",
                "fixed_air_velocity_ms": sim_input.fixed_air_velocity_ms
                if sim_input.fixed_air_velocity_ms is not None
                else "",
                "Tout_pre_cyclone_c": float(pre_cyclone["T_a_c"]),
                "Yout_g_kg_da": 1000.0 * float(pre_cyclone["Y"]),
                "RHout_pct": 100.0 * float(outlet_row["RH_a"]),
                "powder_moisture_wb_pct": 100.0 * outlet_x_db / (1.0 + outlet_x_db),
                "powder_moisture_db": outlet_x_db,
                "tau_out_s": float(pre_cyclone["tau_s"]),
                "U_a_out_ms": float(pre_cyclone["U_a_ms"]),
                "U_p_out_ms": float(pre_cyclone["U_p_ms"]),
                "Re_mean": float(result.series["Re"].mean()),
                "h_m_mean_ms": float(result.series["h_m_ms"].mean()),
                "warnings": " | ".join(result.warnings),
            }
        )
    return rows


def main() -> None:
    output_path = Path(__file__).with_name("stationary_smp_rea_velocity_mode_comparison.csv")
    rows = case_rows()
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(output_path)


if __name__ == "__main__":
    main()
