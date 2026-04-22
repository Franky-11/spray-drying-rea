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


def _axial_grid(
    inputs: StationarySMPREAInput,
    derived: StationarySMPREADerivedInputs,
) -> np.ndarray:
    base_grid = np.linspace(0.0, derived.total_axial_length_m, inputs.axial_points)
    geometry_points = np.array(
        [
            0.0,
            derived.geometry.cylinder_end_h_m,
            derived.geometry.cone_end_h_m,
            derived.pre_cyclone_h_m,
        ],
        dtype=float,
    )
    return np.unique(np.concatenate([base_grid, geometry_points]))


def _initial_state_vector(
    inputs: StationarySMPREAInput,
    derived: StationarySMPREADerivedInputs,
) -> np.ndarray:
    initial_particle_velocity_ms = (
        inputs.fixed_particle_velocity_ms
        if inputs.fixed_particle_velocity_ms is not None
        else derived.initial_droplet_velocity_ms
    )
    state = [
        derived.x0_dry_basis,
        derived.inlet_particle_temp_k,
        derived.inlet_humidity_ratio,
        derived.initial_air_enthalpy_j_kg_da,
        initial_particle_velocity_ms,
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
        local_cross_section_area_m2 = derived.geometry.cross_section_area_at(float(h_value))
        local_wall_area_density_m2_m = derived.geometry.wall_area_density_at(float(h_value))
        row: dict[str, float | None] = {
            "h": float(h_value),
            "section": derived.geometry.section_at(float(h_value)),
            "A_cross_m2": local_cross_section_area_m2,
            "wall_area_density_m2_m": local_wall_area_density_m2_m,
            "X": algebraic.X,
            "T_p_k": algebraic.T_p_k,
            "T_p_c": algebraic.T_p_c,
            "T_a_k": algebraic.T_a_k,
            "T_a_c": algebraic.T_a_c,
            "Y": algebraic.Y,
            "Y_eff": algebraic.Y_eff,
            "H_h_j_kg_da": algebraic.H_h_j_kg_da,
            "U_p_ms": algebraic.U_p_ms,
            "U_a_ms": algebraic.U_a_ms,
            "tau_s": algebraic.tau_s,
            "RH_a": algebraic.RH_a,
            "RH_eff": algebraic.RH_eff,
            "humidity_bias_active": algebraic.humidity_bias_active,
            "p_v_pa": algebraic.p_v_pa,
            "p_v_eff_pa": algebraic.p_v_eff_pa,
            "p_sat_air_pa": algebraic.p_sat_air_pa,
            "p_sat_particle_pa": algebraic.p_sat_particle_pa,
            "rho_air_kg_m3": algebraic.rho_air_kg_m3,
            "rho_v_air_kg_m3": algebraic.rho_v_air_kg_m3,
            "rho_v_air_eff_kg_m3": algebraic.rho_v_air_eff_kg_m3,
            "rho_v_surface_kg_m3": algebraic.rho_v_surface_kg_m3,
            "x_b": algebraic.x_b,
            "x_b_lin_gab": algebraic.x_b_lin_gab,
            "x_b_kockel": algebraic.x_b_kockel,
            "x_b_kockel_weight": algebraic.x_b_kockel_weight,
            "delta": algebraic.delta,
            "initial_moisture_dry_basis": algebraic.initial_moisture_dry_basis,
            "linear_slope": algebraic.linear_slope,
            "linear_intercept": algebraic.linear_intercept,
            "shrinkage_mode": algebraic.shrinkage_mode,
            "critical_delta": algebraic.critical_delta,
            "critical_ratio": algebraic.critical_ratio,
            "normalized_delta": algebraic.normalized_delta,
            "activation_ratio_base": algebraic.activation_ratio_base,
            "activation_ratio_add": algebraic.activation_ratio_add,
            "activation_ratio": algebraic.activation_ratio,
            "DeltaE_v_max_j_mol": algebraic.delta_e_max_j_mol,
            "DeltaE_v_j_mol": algebraic.delta_e_j_mol,
            "psi": algebraic.psi,
            "contact_efficiency": algebraic.contact_efficiency,
            "axial_exposure_factor": algebraic.axial_exposure_factor,
            "combined_contact_exposure_factor": algebraic.combined_contact_exposure_factor,
            "d_p_m": algebraic.particle_diameter_m,
            "rho_p_kg_m3": algebraic.particle_density_kg_m3,
            "m_p_kg": algebraic.particle_mass_kg,
            "A_p_m2": algebraic.particle_area_m2,
            "h_fg_j_kg": algebraic.h_fg_j_kg,
            "q_sorption_j_kg": algebraic.q_sorption_j_kg,
            "Re": algebraic.transport.reynolds_number,
            "Sc": algebraic.transport.schmidt_number,
            "Sh": algebraic.transport.sherwood_number,
            "Pr": algebraic.transport.prandtl_number,
            "Nu": algebraic.transport.nusselt_number,
            "C_D": algebraic.transport.drag_coefficient,
            "h_m_ms": algebraic.transport.mass_transfer_coeff_ms,
            "h_m_eff_ms": algebraic.effective_mass_transfer_coeff_ms,
            "h_h_w_m2_k": algebraic.transport.heat_transfer_coeff_w_m2_k,
            "h_h_eff_w_m2_k": algebraic.effective_heat_transfer_coeff_w_m2_k,
            "q_loss_prime_w_m": algebraic.q_loss_prime_w_m,
            "delta_t_air_particle_k": algebraic.T_a_k - algebraic.T_p_k,
            "rho_v_driving_force_kg_m3": (
                algebraic.rho_v_surface_kg_m3 - algebraic.rho_v_air_eff_kg_m3
            ),
            "dm_p_dh_kg_m": rhs.dm_p_dh_kg_m,
            "dX_dh": rhs.dX_dh,
            "dT_p_dh": rhs.dT_p_dh,
            "dY_dh": rhs.dY_dh,
            "dH_h_dh": rhs.dH_h_dh,
            "dU_p_dh": rhs.dU_p_dh,
            "dtau_dh": rhs.dtau_dh,
            "q_conv_w": rhs.q_conv_w,
            "q_latent_w": rhs.q_latent_w,
            "q_sorption_w": rhs.q_sorption_w,
            "q_evap_total_w": rhs.q_evap_total_w,
            "q_evap_to_conv_ratio": rhs.q_evap_to_conv_ratio,
        }
        rows.append(row)

    frame = pd.DataFrame(rows)
    if not inputs.include_tau_state:
        inverse_velocity = 1.0 / frame["U_p_ms"].clip(lower=inputs.min_particle_velocity_ms)
        frame["tau_s"] = np.concatenate(
            ([0.0], np.cumsum(0.5 * (inverse_velocity.iloc[1:].to_numpy() + inverse_velocity.iloc[:-1].to_numpy()) * np.diff(frame["h"].to_numpy())))
        )
    return frame


def _report_point(frame: pd.DataFrame, h_target_m: float) -> dict[str, float | str | None]:
    index = int((frame["h"] - h_target_m).abs().idxmin())
    row = frame.iloc[index]
    return {
        "h_m": float(row["h"]),
        "section": str(row["section"]),
        "T_a_c": float(row["T_a_c"]),
        "T_a_k": float(row["T_a_k"]),
        "T_p_c": float(row["T_p_c"]),
        "T_p_k": float(row["T_p_k"]),
        "Y": float(row["Y"]),
        "X": float(row["X"]),
        "U_a_ms": float(row["U_a_ms"]),
        "U_p_ms": float(row["U_p_ms"]),
        "tau_s": float(row["tau_s"]) if pd.notna(row["tau_s"]) else None,
    }


def solve_stationary_smp_profile(
    inputs: StationarySMPREAInput,
) -> StationarySMPREAResult:
    errors, warnings = inputs.validate()
    if errors:
        raise ValueError(" ".join(errors))

    derived = derive_inputs(inputs)
    initial_state = _initial_state_vector(inputs, derived)
    h_grid = _axial_grid(inputs, derived)
    solution = solve_ivp(
        fun=lambda h_value, state: axial_rhs(h_value, state, inputs, derived),
        t_span=(0.0, derived.total_axial_length_m),
        y0=initial_state,
        t_eval=h_grid,
        method=inputs.solver_method,
        rtol=inputs.solver_rtol,
        atol=inputs.solver_atol,
        max_step=max(derived.total_axial_length_m / max(inputs.axial_points - 1, 1), 1e-6),
    )
    series = _series_from_solution(solution.y, h_grid, inputs, derived)
    last_row = series.iloc[-1]
    report_points = {
        "dryer_exit": _report_point(series, derived.dryer_exit_h_m),
        "pre_cyclone": _report_point(series, derived.pre_cyclone_h_m),
    }
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
        "outlet_section": str(last_row["section"]),
        "outlet_h_m": float(last_row["h"]),
        "total_q_loss_w": float(np.trapezoid(series["q_loss_prime_w_m"], series["h"])),
    }
    provenance = {
        "coordinate": "Effective 1D co-current flow-path coordinate h (cylinder, cone, optional outlet duct)",
        "balances": "Langrish (2009), Eqs. (20), (36), (41), (42)",
        "material_closure": "Chew (2013), Eqs. (11)-(13), Table 1, Table 2",
        "x_b_default": "Lin, Chen, Pearce (2005) temperature-dependent GAB",
        "x_b_optional": "Kockel et al. (2002) skim milk powder equilibrium fit at elevated temperature, plus an explicit constant blend between Lin-GAB and Kockel via x_b_blend_kockel_weight, or a clamped RH-dependent blend via x_b_blend_kockel_weight_base + x_b_blend_kockel_weight_rh_coeff * RH_eff.",
        "geometry": "Section-wise effective geometry with local U_a(h) and wall-loss density; outlet duct uses the same 1D axial momentum simplification as the main chamber.",
    }
    return StationarySMPREAResult(
        inputs=inputs,
        series=series,
        outlet=outlet,
        report_points=report_points,
        warnings=warnings,
        solver_status=int(solution.status),
        solver_message=solution.message,
        success=bool(solution.success),
        provenance=provenance,
    )
