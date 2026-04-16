from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp

from .balances import axial_rhs, evaluate_rhs
from .inputs import (
    StationarySMPREADerivedInputs,
    StationarySMPREAInput,
    StationarySMPREAResult,
    derive_inputs,
)


def _initial_state_vector(
    inputs: StationarySMPREAInput,
    derived: StationarySMPREADerivedInputs,
) -> np.ndarray:
    state = [
        derived.x0_dry_basis,
        derived.inlet_particle_temp_k,
        derived.inlet_humidity_ratio,
        derived.initial_air_enthalpy_j_kg_da,
        inputs.initial_droplet_velocity_ms,
    ]
    if inputs.include_tau_state:
        state.append(0.0)
    return np.array(state, dtype=float)


def _series_from_solution(
    solution_y: np.ndarray,
    h_grid: np.ndarray,
    inputs: StationarySMPREAInput,
    derived: StationarySMPREADerivedInputs,
) -> pd.DataFrame:
    rows: list[dict[str, float | None]] = []
    for index, h_value in enumerate(h_grid):
        state = solution_y[:, index]
        rhs = evaluate_rhs(float(h_value), state, inputs, derived)
        algebraic = rhs.algebraic
        row: dict[str, float | None] = {
            "h": float(h_value),
            "X": algebraic.X,
            "T_p_k": algebraic.T_p_k,
            "T_p_c": algebraic.T_p_c,
            "T_a_k": algebraic.T_a_k,
            "T_a_c": algebraic.T_a_c,
            "Y": algebraic.Y,
            "H_h_j_kg_da": algebraic.H_h_j_kg_da,
            "U_p_ms": algebraic.U_p_ms,
            "U_a_ms": algebraic.U_a_ms,
            "tau_s": algebraic.tau_s,
            "RH_a": algebraic.RH_a,
            "p_v_pa": algebraic.p_v_pa,
            "p_sat_air_pa": algebraic.p_sat_air_pa,
            "p_sat_particle_pa": algebraic.p_sat_particle_pa,
            "rho_air_kg_m3": algebraic.rho_air_kg_m3,
            "rho_v_air_kg_m3": algebraic.rho_v_air_kg_m3,
            "rho_v_surface_kg_m3": algebraic.rho_v_surface_kg_m3,
            "x_b": algebraic.x_b,
            "delta": algebraic.delta,
            "critical_delta": algebraic.critical_delta,
            "critical_ratio": algebraic.critical_ratio,
            "activation_ratio": algebraic.activation_ratio,
            "DeltaE_v_max_j_mol": algebraic.delta_e_max_j_mol,
            "DeltaE_v_j_mol": algebraic.delta_e_j_mol,
            "psi": algebraic.psi,
            "d_p_m": algebraic.particle_diameter_m,
            "rho_p_kg_m3": algebraic.particle_density_kg_m3,
            "m_p_kg": algebraic.particle_mass_kg,
            "A_p_m2": algebraic.particle_area_m2,
            "Re": algebraic.transport.reynolds_number,
            "Sc": algebraic.transport.schmidt_number,
            "Sh": algebraic.transport.sherwood_number,
            "Pr": algebraic.transport.prandtl_number,
            "Nu": algebraic.transport.nusselt_number,
            "C_D": algebraic.transport.drag_coefficient,
            "h_m_ms": algebraic.transport.mass_transfer_coeff_ms,
            "h_h_w_m2_k": algebraic.transport.heat_transfer_coeff_w_m2_k,
            "q_loss_prime_w_m": algebraic.q_loss_prime_w_m,
            "dm_p_dh_kg_m": rhs.dm_p_dh_kg_m,
            "dX_dh": rhs.dX_dh,
            "dT_p_dh": rhs.dT_p_dh,
            "dY_dh": rhs.dY_dh,
            "dH_h_dh": rhs.dH_h_dh,
            "dU_p_dh": rhs.dU_p_dh,
            "dtau_dh": rhs.dtau_dh,
        }
        rows.append(row)

    frame = pd.DataFrame(rows)
    if not inputs.include_tau_state:
        inverse_velocity = 1.0 / frame["U_p_ms"].clip(lower=inputs.min_particle_velocity_ms)
        frame["tau_s"] = np.concatenate(
            ([0.0], np.cumsum(0.5 * (inverse_velocity.iloc[1:].to_numpy() + inverse_velocity.iloc[:-1].to_numpy()) * np.diff(frame["h"].to_numpy())))
        )
    return frame


def solve_stationary_smp_profile(
    inputs: StationarySMPREAInput,
) -> StationarySMPREAResult:
    errors, warnings = inputs.validate()
    if errors:
        raise ValueError(" ".join(errors))

    derived = derive_inputs(inputs)
    initial_state = _initial_state_vector(inputs, derived)
    h_grid = np.linspace(0.0, inputs.dryer_height_m, inputs.axial_points)
    solution = solve_ivp(
        fun=lambda h_value, state: axial_rhs(h_value, state, inputs, derived),
        t_span=(0.0, inputs.dryer_height_m),
        y0=initial_state,
        t_eval=h_grid,
        method=inputs.solver_method,
        rtol=inputs.solver_rtol,
        atol=inputs.solver_atol,
        max_step=max(inputs.dryer_height_m / max(inputs.axial_points - 1, 1), 1e-6),
    )
    series = _series_from_solution(solution.y, h_grid, inputs, derived)
    last_row = series.iloc[-1]
    outlet = {
        "outlet_X": float(last_row["X"]),
        "outlet_T_p_k": float(last_row["T_p_k"]),
        "outlet_T_p_c": float(last_row["T_p_c"]),
        "outlet_T_a_k": float(last_row["T_a_k"]),
        "outlet_T_a_c": float(last_row["T_a_c"]),
        "outlet_Y": float(last_row["Y"]),
        "outlet_H_h_j_kg_da": float(last_row["H_h_j_kg_da"]),
        "outlet_U_p_ms": float(last_row["U_p_ms"]),
        "outlet_tau_s": float(last_row["tau_s"]) if pd.notna(last_row["tau_s"]) else None,
        "total_q_loss_w": float(np.trapezoid(series["q_loss_prime_w_m"], series["h"])),
    }
    provenance = {
        "coordinate": "Langrish parallel-flow height coordinate h",
        "balances": "Langrish (2009), Eqs. (20), (36), (41), (42)",
        "material_closure": "Chew (2013), Eqs. (11)-(13), Table 1, Table 2",
        "x_b_default": "Langrish coarsest-scale skim milk isotherm, Eq. (11)",
        "x_b_optional": "Lin, Chen, Pearce (2005) temperature-dependent GAB",
    }
    return StationarySMPREAResult(
        inputs=inputs,
        series=series,
        outlet=outlet,
        warnings=warnings,
        solver_status=int(solution.status),
        solver_message=solution.message,
        success=bool(solution.success),
        provenance=provenance,
    )
