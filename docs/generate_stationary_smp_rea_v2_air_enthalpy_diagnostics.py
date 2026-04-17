from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stationary_smp_rea import build_ms400_stationary_input_from_label, solve_stationary_smp_profile
from core.stationary_smp_rea.air import CP_WATER_VAPOR, LAMBDA_REF_J_KG, T_REF_K, moist_air_density
from core.stationary_smp_rea.balances import evaluate_rhs
from core.stationary_smp_rea.inputs import derive_inputs


OUTPUT_PATH = Path("docs/stationary_smp_rea_v2_air_enthalpy_diagnostics.csv")
HUMID_AIR_MASS_FLOW_KG_H = 304.0


def main() -> None:
    base_input = build_ms400_stationary_input_from_label("V2")
    inlet_density = moist_air_density(
        base_input.inlet_air_temp_c + 273.15,
        base_input.inlet_abs_humidity_g_kg / 1000.0,
        base_input.pressure_pa,
    )
    sim_input = replace(
        base_input,
        air_flow_m3_h=HUMID_AIR_MASS_FLOW_KG_H / inlet_density,
        heat_loss_coeff_w_m2k=0.0,
    )
    derived = derive_inputs(sim_input)
    dry_basis_ratio = derived.dry_solids_mass_flow_kg_s / derived.dry_air_mass_flow_kg_s
    result = solve_stationary_smp_profile(sim_input)

    rows: list[dict[str, float | str]] = []
    for row in result.series.itertuples(index=False):
        state = [
            float(row.X),
            float(row.T_p_k),
            float(row.Y),
            float(row.H_h_j_kg_da),
            float(row.U_p_ms),
            float(row.tau_s),
        ]
        rhs = evaluate_rhs(float(row.h), state, sim_input, derived)
        algebraic = rhs.algebraic
        cp_air = derived.cpa_j_kg_k + algebraic.Y * CP_WATER_VAPOR
        dH_particle_sensible_dh = -dry_basis_ratio * algebraic.particle_cp_j_kg_k * rhs.dT_p_dh
        dH_particle_liquid_dh = -dry_basis_ratio * derived.cpw_j_kg_k * (
            algebraic.T_p_k - T_REF_K
        ) * rhs.dX_dh
        dH_q_loss_dh = -algebraic.q_loss_prime_w_m / derived.dry_air_mass_flow_kg_s
        dH_sensible_only_dh = dH_particle_sensible_dh + dH_q_loss_dh
        dT_a_dh_model = (
            rhs.dH_h_dh
            - rhs.dY_dh * (LAMBDA_REF_J_KG + CP_WATER_VAPOR * (algebraic.T_a_k - T_REF_K))
        ) / cp_air
        dT_a_dh_sensible_only = (
            dH_sensible_only_dh
            - rhs.dY_dh * (LAMBDA_REF_J_KG + CP_WATER_VAPOR * (algebraic.T_a_k - T_REF_K))
        ) / cp_air

        rows.append(
            {
                "scenario": "V2_dynamic_no_heat_loss_304kg_h_lin_gab",
                "h_m": float(row.h),
                "section": str(row.section),
                "T_a_c": float(row.T_a_c),
                "T_p_c": float(row.T_p_c),
                "X_db": float(row.X),
                "Y_kg_kg_da": float(row.Y),
                "RH_a_pct": 100.0 * float(row.RH_a),
                "dX_dh": float(rhs.dX_dh),
                "dY_dh": float(rhs.dY_dh),
                "dT_p_dh": float(rhs.dT_p_dh),
                "dH_h_dh_model": float(rhs.dH_h_dh),
                "dH_h_dh_sensible_only": float(dH_sensible_only_dh),
                "dH_particle_sensible_dh": float(dH_particle_sensible_dh),
                "dH_particle_liquid_dh": float(dH_particle_liquid_dh),
                "dH_q_loss_dh": float(dH_q_loss_dh),
                "dT_a_dh_model": float(dT_a_dh_model),
                "dT_a_dh_sensible_only": float(dT_a_dh_sensible_only),
                "cp_air_j_kg_da_k": float(cp_air),
                "liquid_term_share_of_dH_pct": float(
                    100.0 * dH_particle_liquid_dh / max(abs(rhs.dH_h_dh), 1e-12)
                ),
            }
        )

    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
