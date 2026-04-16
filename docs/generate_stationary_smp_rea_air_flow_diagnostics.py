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


def build_air_sweep_cases() -> list[tuple[str, float, StationarySMPREAInput]]:
    default_input = StationarySMPREAInput()
    inlet_air_temp_c = 190.0
    baseline_humid_air_mass_flow_kg_h = 200.0
    higher_humid_air_mass_flow_kg_h = 250.0
    base = replace(
        default_input,
        inlet_air_temp_c=inlet_air_temp_c,
        air_flow_m3_h=humid_air_mass_flow_to_volumetric_flow_m3_h(
            baseline_humid_air_mass_flow_kg_h,
            inlet_air_temp_c,
            default_input.inlet_abs_humidity_g_kg,
        ),
    )
    higher_air = replace(
        base,
        air_flow_m3_h=humid_air_mass_flow_to_volumetric_flow_m3_h(
            higher_humid_air_mass_flow_kg_h,
            inlet_air_temp_c,
            base.inlet_abs_humidity_g_kg,
        ),
    )
    return [
        ("air_200", baseline_humid_air_mass_flow_kg_h, base),
        ("air_250", higher_humid_air_mass_flow_kg_h, higher_air),
    ]


def profile_rows() -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for case_id, humid_air_mass_flow_kg_h, sim_input in build_air_sweep_cases():
        result = solve_stationary_smp_profile(sim_input)
        series = result.series.copy()
        series["relative_velocity_ms"] = (series["U_p_ms"] - series["U_a_ms"]).abs()
        series["driving_force_kg_m3"] = (
            series["rho_v_surface_kg_m3"] - series["rho_v_air_kg_m3"]
        )
        series["dX_dt"] = series["dX_dh"] * series["U_p_ms"]
        series["dY_dt"] = series["dY_dh"] * series["U_p_ms"]
        series["dH_dt_j_kg_da_s"] = series["dH_h_dh"] * series["U_p_ms"]
        for _, row in series.iterrows():
            rows.append(
                {
                    "case_id": case_id,
                    "humid_air_mass_flow_kg_h": humid_air_mass_flow_kg_h,
                    "h_m": float(row["h"]),
                    "tau_s": float(row["tau_s"]),
                    "T_a_c": float(row["T_a_c"]),
                    "T_p_c": float(row["T_p_c"]),
                    "Y_g_kg_da": 1000.0 * float(row["Y"]),
                    "RH_a_pct": 100.0 * float(row["RH_a"]),
                    "X_db": float(row["X"]),
                    "U_a_ms": float(row["U_a_ms"]),
                    "U_p_ms": float(row["U_p_ms"]),
                    "relative_velocity_ms": float(row["relative_velocity_ms"]),
                    "Re": float(row["Re"]),
                    "h_m_ms": float(row["h_m_ms"]),
                    "Nu": float(row["Nu"]),
                    "psi": float(row["psi"]),
                    "driving_force_kg_m3": float(row["driving_force_kg_m3"]),
                    "dX_dh": float(row["dX_dh"]),
                    "dX_dt": float(row["dX_dt"]),
                    "dY_dh": float(row["dY_dh"]),
                    "dY_dt": float(row["dY_dt"]),
                    "dH_h_dh": float(row["dH_h_dh"]),
                    "dH_dt_j_kg_da_s": float(row["dH_dt_j_kg_da_s"]),
                    "dU_p_dh": float(row["dU_p_dh"]),
                }
            )
    return rows


def summary_rows() -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    segments = [
        ("full", 0.0, 2.0),
        ("entry_0_0p2", 0.0, 0.2),
        ("flash_0p2_0p5", 0.2, 0.5),
        ("tail_0p5_2p0", 0.5, 2.0),
    ]
    for case_id, humid_air_mass_flow_kg_h, sim_input in build_air_sweep_cases():
        result = solve_stationary_smp_profile(sim_input)
        series = result.series.copy()
        series["relative_velocity_ms"] = (series["U_p_ms"] - series["U_a_ms"]).abs()
        series["driving_force_kg_m3"] = (
            series["rho_v_surface_kg_m3"] - series["rho_v_air_kg_m3"]
        )
        series["dX_dt"] = series["dX_dh"] * series["U_p_ms"]
        series["dH_dt_j_kg_da_s"] = series["dH_h_dh"] * series["U_p_ms"]

        for segment_name, h_min, h_max in segments:
            mask = (series["h"] >= h_min) & (series["h"] <= h_max)
            subset = series.loc[mask]
            rows.append(
                {
                    "case_id": case_id,
                    "humid_air_mass_flow_kg_h": humid_air_mass_flow_kg_h,
                    "segment": segment_name,
                    "h_min_m": h_min,
                    "h_max_m": h_max,
                    "mean_U_a_ms": float(subset["U_a_ms"].mean()),
                    "mean_U_p_ms": float(subset["U_p_ms"].mean()),
                    "mean_relative_velocity_ms": float(subset["relative_velocity_ms"].mean()),
                    "mean_Re": float(subset["Re"].mean()),
                    "mean_h_m_ms": float(subset["h_m_ms"].mean()),
                    "mean_driving_force_kg_m3": float(subset["driving_force_kg_m3"].mean()),
                    "mean_dX_dh": float(subset["dX_dh"].mean()),
                    "mean_dX_dt": float(subset["dX_dt"].mean()),
                    "mean_dH_h_dh": float(subset["dH_h_dh"].mean()),
                    "mean_dH_dt_j_kg_da_s": float(subset["dH_dt_j_kg_da_s"].mean()),
                    "X_start_db": float(subset["X"].iloc[0]),
                    "X_end_db": float(subset["X"].iloc[-1]),
                    "T_a_start_c": float(subset["T_a_c"].iloc[0]),
                    "T_a_end_c": float(subset["T_a_c"].iloc[-1]),
                    "tau_end_s": float(subset["tau_s"].iloc[-1]),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict[str, float | str]]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    profile_path = Path(__file__).with_name("stationary_smp_rea_air_flow_diagnostics_profile.csv")
    summary_path = Path(__file__).with_name("stationary_smp_rea_air_flow_diagnostics_summary.csv")
    write_csv(profile_path, profile_rows())
    write_csv(summary_path, summary_rows())
    print(profile_path)
    print(summary_path)


if __name__ == "__main__":
    main()
