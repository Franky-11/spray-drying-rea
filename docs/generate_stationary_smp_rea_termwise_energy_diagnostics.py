from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.stationary_smp_rea.air import (
    CP_WATER_VAPOR,
    LAMBDA_REF_J_KG,
    latent_heat_evaporation,
)
from core.stationary_smp_rea.balances import evaluate_rhs
from core.stationary_smp_rea.inputs import StationarySMPREAInput, derive_inputs
from core.stationary_smp_rea.kernel import solve_stationary_smp_profile


OUTPUT_PATH = Path("docs/stationary_smp_rea_termwise_energy_diagnostics.csv")


def main() -> None:
    sim_input = StationarySMPREAInput(
        inlet_air_temp_c=190.0,
        feed_temp_c=40.0,
        inlet_abs_humidity_g_kg=5.7,
        feed_rate_kg_h=3.0,
        air_flow_m3_h=140.0,
        feed_total_solids=0.40,
        fixed_particle_velocity_ms=5.0,
        fixed_air_velocity_ms=100.0,
        x_b_model="lin_gab",
        axial_points=120,
    )
    derived = derive_inputs(sim_input)
    result = solve_stationary_smp_profile(sim_input)

    rows: list[dict[str, float]] = []
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
        cp_product = derived.cps_j_kg_k + algebraic.X * derived.cpw_j_kg_k
        cp_air = derived.cpa_j_kg_k + algebraic.Y * CP_WATER_VAPOR

        dT_p_dh_matlab_like = (
            algebraic.transport.heat_transfer_coeff_w_m2_k
            * algebraic.particle_area_m2
            * (algebraic.T_a_k - algebraic.T_p_k)
            + rhs.dm_p_dh_kg_m
            * algebraic.U_p_ms
            * (latent_heat_evaporation(algebraic.T_a_k) + algebraic.q_sorption_j_kg)
        ) / (
            derived.representative_dry_solids_mass_kg
            * cp_product
            * algebraic.U_p_ms
        )
        dH_h_dh_matlab_like = -(
            derived.dry_solids_mass_flow_kg_s / derived.dry_air_mass_flow_kg_s
        ) * cp_product * dT_p_dh_matlab_like - algebraic.q_loss_prime_w_m / derived.dry_air_mass_flow_kg_s

        dT_a_dh_current = (
            rhs.dH_h_dh
            - rhs.dY_dh * (LAMBDA_REF_J_KG + CP_WATER_VAPOR * (algebraic.T_a_k - 273.15))
        ) / cp_air
        dT_a_dh_matlab_like = (
            dH_h_dh_matlab_like
            - rhs.dY_dh
            * (
                latent_heat_evaporation(algebraic.T_a_k)
                + algebraic.q_sorption_j_kg
                + CP_WATER_VAPOR * algebraic.T_a_k
            )
        ) / cp_air

        rows.append(
            {
                "h_m": float(row.h),
                "tau_s": float(row.tau_s),
                "X_db": float(row.X),
                "T_a_c": float(row.T_a_c),
                "T_p_c": float(row.T_p_c),
                "Y_kg_kg_da": float(row.Y),
                "dX_dh_current": float(rhs.dX_dh),
                "dY_dh_current": float(rhs.dY_dh),
                "dT_p_dh_current": float(rhs.dT_p_dh),
                "dT_p_dh_matlab_like": float(dT_p_dh_matlab_like),
                "dT_p_dh_delta": float(rhs.dT_p_dh - dT_p_dh_matlab_like),
                "dH_h_dh_current": float(rhs.dH_h_dh),
                "dH_h_dh_matlab_like": float(dH_h_dh_matlab_like),
                "dT_a_dh_current": float(dT_a_dh_current),
                "dT_a_dh_matlab_like": float(dT_a_dh_matlab_like),
                "h_fg_current_j_kg": float(algebraic.h_fg_j_kg),
                "h_fg_particle_j_kg": float(latent_heat_evaporation(algebraic.T_p_k)),
                "q_sorption_j_kg": float(algebraic.q_sorption_j_kg),
            }
        )

    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
