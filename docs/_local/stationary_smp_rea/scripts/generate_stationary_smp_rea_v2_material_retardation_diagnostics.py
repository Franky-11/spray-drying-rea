from __future__ import annotations

from math import log
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stationary_smp_rea import build_ms400_stationary_input_from_label, solve_stationary_smp_profile
from core.stationary_smp_rea.air import saturated_vapor_density
from core.stationary_smp_rea.materials.smp_chew import R_GAS
from core.stationary_smp_rea.ms400 import load_ms400_experiments


OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "stationary_smp_rea_v2_material_retardation_diagnostics.csv"
)
HUMID_AIR_MASS_FLOW_KG_H = 304.0
FEED_RATE_KG_H = 14.0
HEAT_LOSS_COEFF_W_M2K = 2.0
X_B_MODEL = "lin_gab"
EPS = 1e-12


def _wb_pct_to_db(wet_basis_pct: float) -> float:
    wet_basis = wet_basis_pct / 100.0
    return wet_basis / max(1.0 - wet_basis, EPS)


def _bounded_fraction(value: float) -> float:
    return min(max(value, 0.0), 1.0)


def main() -> None:
    experiment = load_ms400_experiments().set_index("label").loc["V2"]
    target_x_wb_pct = float(experiment["powder_moisture_wb_pct"])
    target_x_db = _wb_pct_to_db(target_x_wb_pct)

    sim_input = build_ms400_stationary_input_from_label(
        "V2",
        feed_rate_kg_h=FEED_RATE_KG_H,
        humid_air_mass_flow_kg_h=HUMID_AIR_MASS_FLOW_KG_H,
        heat_loss_coeff_w_m2k=HEAT_LOSS_COEFF_W_M2K,
        x_b_model=X_B_MODEL,
    )
    result = solve_stationary_smp_profile(sim_input)
    series = result.series.copy()
    tau_out_s = float(series["tau_s"].iloc[-1])
    outlet_x_db = float(series["X"].iloc[-1])
    outlet_x_wb_pct = 100.0 * outlet_x_db / (1.0 + outlet_x_db)

    rows: list[dict[str, float | str]] = []
    for row in series.itertuples(index=False):
        x_db = float(row.X)
        x_wb_pct = 100.0 * x_db / (1.0 + x_db)
        x_b_db = float(row.x_b)
        x_b_wb_pct = 100.0 * x_b_db / (1.0 + x_b_db)
        delta_db = float(row.delta)
        tau_s = float(row.tau_s)
        remaining_tau_s = max(tau_out_s - tau_s, 0.0)

        rho_v_air = float(row.rho_v_air_kg_m3)
        rho_v_surface = float(row.rho_v_surface_kg_m3)
        rho_v_sat = saturated_vapor_density(float(row.T_p_k))
        net_driving_force_current = max(rho_v_surface - rho_v_air, 0.0)
        net_driving_force_unhindered = max(rho_v_sat - rho_v_air, 0.0)

        if net_driving_force_unhindered <= EPS:
            xi_eff_current = 0.0
        else:
            xi_eff_current = _bounded_fraction(
                net_driving_force_current / net_driving_force_unhindered
            )

        dX_dt_current = float(row.dX_dh) * float(row.U_p_ms)
        drying_rate_current_db_s = max(-dX_dt_current, 0.0)

        removable_moisture_to_target_db = max(x_db - target_x_db, 0.0)
        if remaining_tau_s <= EPS or removable_moisture_to_target_db <= EPS:
            drying_rate_required_avg_to_target_db_s = 0.0
        else:
            # This is a heuristic average rate-to-target, not an exact inverse solve.
            drying_rate_required_avg_to_target_db_s = (
                removable_moisture_to_target_db / remaining_tau_s
            )

        if drying_rate_current_db_s <= EPS:
            slowdown_factor_avg_to_target = 0.0
        else:
            slowdown_factor_avg_to_target = _bounded_fraction(
                drying_rate_required_avg_to_target_db_s / drying_rate_current_db_s
            )

        xi_eff_required_avg_to_target = _bounded_fraction(
            slowdown_factor_avg_to_target * xi_eff_current
        )
        net_driving_force_required_avg_to_target = (
            xi_eff_required_avg_to_target * net_driving_force_unhindered
        )
        rho_v_surface_required_avg_to_target = (
            rho_v_air + net_driving_force_required_avg_to_target
        )

        if rho_v_sat <= EPS:
            psi_required_avg_to_target = 0.0
        else:
            psi_required_avg_to_target = _bounded_fraction(
                rho_v_surface_required_avg_to_target / rho_v_sat
            )

        psi_current = _bounded_fraction(float(row.psi))
        if psi_current <= EPS or psi_required_avg_to_target <= EPS:
            delta_e_add_avg_to_target_j_mol = 0.0
        else:
            delta_e_add_avg_to_target_j_mol = max(
                -R_GAS
                * float(row.T_p_k)
                * log(psi_required_avg_to_target / psi_current),
                0.0,
            )

        delta_e_current_j_mol = float(row.DeltaE_v_j_mol)
        delta_e_max_j_mol = float(row.DeltaE_v_max_j_mol)
        delta_e_add_to_equilibrium_j_mol = max(
            delta_e_max_j_mol - delta_e_current_j_mol,
            0.0,
        )

        rows.append(
            {
                "case_id": "V2_material_retardation",
                "feed_rate_kg_h": FEED_RATE_KG_H,
                "humid_air_mass_flow_kg_h": HUMID_AIR_MASS_FLOW_KG_H,
                "heat_loss_coeff_w_m2k": HEAT_LOSS_COEFF_W_M2K,
                "x_b_model": X_B_MODEL,
                "target_powder_moisture_wb_pct": target_x_wb_pct,
                "target_powder_moisture_db": target_x_db,
                "model_outlet_powder_moisture_wb_pct": outlet_x_wb_pct,
                "model_outlet_powder_moisture_db": outlet_x_db,
                "h_m": float(row.h),
                "tau_s": tau_s,
                "remaining_tau_s": remaining_tau_s,
                "section": str(row.section),
                "T_a_c": float(row.T_a_c),
                "T_p_c": float(row.T_p_c),
                "X_db": x_db,
                "X_wb_pct": x_wb_pct,
                "x_b_db": x_b_db,
                "x_b_wb_pct": x_b_wb_pct,
                "delta_db": delta_db,
                "normalized_delta": float(row.normalized_delta),
                "activation_ratio_base": float(row.activation_ratio_base),
                "activation_ratio_add": float(row.activation_ratio_add),
                "activation_ratio_total": float(row.activation_ratio),
                "psi_current": psi_current,
                "xi_eff_current": xi_eff_current,
                "rho_v_air_kg_m3": rho_v_air,
                "rho_v_surface_kg_m3": rho_v_surface,
                "rho_v_sat_particle_kg_m3": rho_v_sat,
                "net_driving_force_current_kg_m3": net_driving_force_current,
                "net_driving_force_unhindered_kg_m3": net_driving_force_unhindered,
                "drying_rate_current_db_s": drying_rate_current_db_s,
                "drying_rate_required_avg_to_target_db_s": drying_rate_required_avg_to_target_db_s,
                "slowdown_factor_avg_to_target": slowdown_factor_avg_to_target,
                "xi_eff_required_avg_to_target": xi_eff_required_avg_to_target,
                "psi_required_avg_to_target": psi_required_avg_to_target,
                "delta_e_current_j_mol": delta_e_current_j_mol,
                "delta_e_max_j_mol": delta_e_max_j_mol,
                "delta_e_add_to_equilibrium_j_mol": delta_e_add_to_equilibrium_j_mol,
                "delta_e_add_avg_to_target_j_mol": delta_e_add_avg_to_target_j_mol,
                "U_a_ms": float(row.U_a_ms),
                "U_p_ms": float(row.U_p_ms),
                "Re": float(row.Re),
                "Sh": float(row.Sh),
                "h_m_ms": float(row.h_m_ms),
                "d_p_um": float(row.d_p_m) * 1e6,
            }
        )

    diagnostics = pd.DataFrame(rows)
    diagnostics.to_csv(OUTPUT_PATH, index=False)

    print(f"Wrote {OUTPUT_PATH}")
    print(
        "Target/model outlet wb%:",
        round(target_x_wb_pct, 4),
        round(outlet_x_wb_pct, 4),
    )
    interesting = diagnostics[
        (diagnostics["X_wb_pct"] <= 15.0) & (diagnostics["X_wb_pct"] >= 2.0)
    ]
    if not interesting.empty:
        summary = interesting[
            [
                "h_m",
                "tau_s",
                "X_wb_pct",
                "x_b_wb_pct",
                "normalized_delta",
                "activation_ratio_base",
                "activation_ratio_add",
                "psi_current",
                "xi_eff_current",
                "slowdown_factor_avg_to_target",
                "xi_eff_required_avg_to_target",
                "delta_e_add_avg_to_target_j_mol",
            ]
        ]
        print(summary.iloc[:: max(len(summary) // 8, 1)].to_string(index=False))


if __name__ == "__main__":
    main()
