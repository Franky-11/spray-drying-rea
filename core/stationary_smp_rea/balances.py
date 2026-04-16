from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .air import (
    CP_WATER_VAPOR,
    air_superficial_velocity,
    dynamic_viscosity_air,
    invert_humid_air_enthalpy,
    latent_heat_evaporation,
    moist_air_density,
    relative_humidity,
    saturated_vapor_density,
    saturation_vapor_pressure,
    thermal_conductivity_air,
    vapor_partial_pressure,
    water_vapor_density,
    water_vapor_diffusivity,
)
from .closures import equilibrium_moisture
from .inputs import StationarySMPREADerivedInputs, StationarySMPREAInput
from .materials import chew_material_state
from .particle import (
    particle_area,
    particle_density_from_mass_and_diameter,
    particle_mass,
)
from .transport import TransportState, evaluate_transport


EPS = 1e-12


@dataclass(frozen=True)
class AlgebraicState:
    h_m: float
    X: float
    T_p_k: float
    Y: float
    H_h_j_kg_da: float
    U_p_ms: float
    tau_s: float | None
    T_a_k: float
    T_p_c: float
    T_a_c: float
    p_v_pa: float
    p_sat_air_pa: float
    p_sat_particle_pa: float
    RH_a: float
    rho_v_air_kg_m3: float
    rho_v_sat_air_kg_m3: float
    rho_v_sat_particle_kg_m3: float
    rho_v_surface_kg_m3: float
    rho_air_kg_m3: float
    air_viscosity_kg_m_s: float
    air_thermal_conductivity_w_m_k: float
    water_vapor_diffusivity_m2_s: float
    U_a_ms: float
    particle_mass_kg: float
    particle_diameter_m: float
    particle_density_kg_m3: float
    particle_area_m2: float
    particle_cp_j_kg_k: float
    h_fg_j_kg: float
    x_b: float
    delta: float
    initial_moisture_dry_basis: float
    linear_slope: float
    linear_intercept: float
    critical_delta: float
    critical_ratio: float
    activation_ratio: float
    delta_e_max_j_mol: float
    delta_e_j_mol: float
    psi: float
    q_loss_prime_w_m: float
    transport: TransportState


@dataclass(frozen=True)
class RHSState:
    algebraic: AlgebraicState
    dm_p_dh_kg_m: float
    dX_dh: float
    dT_p_dh: float
    dY_dh: float
    dH_h_dh: float
    dU_p_dh: float
    dtau_dh: float | None


def _state_components(vector: np.ndarray, include_tau_state: bool) -> tuple[float, float, float, float, float, float | None]:
    if include_tau_state:
        return float(vector[0]), float(vector[1]), float(vector[2]), float(vector[3]), float(vector[4]), float(vector[5])
    return float(vector[0]), float(vector[1]), float(vector[2]), float(vector[3]), float(vector[4]), None


def evaluate_algebraic_state(
    h_m: float,
    state_vector: np.ndarray,
    inputs: StationarySMPREAInput,
    derived: StationarySMPREADerivedInputs,
) -> AlgebraicState:
    x, t_p_k, y, h_h, u_p_ms, tau = _state_components(
        state_vector,
        inputs.include_tau_state,
    )
    bounded_x = max(x, EPS)
    bounded_t_p_k = max(t_p_k, 250.0)
    bounded_y = max(y, EPS)
    bounded_u_p_ms = max(u_p_ms, inputs.min_particle_velocity_ms)

    t_a_k = max(invert_humid_air_enthalpy(h_h, bounded_y), 250.0)
    rh_air = relative_humidity(t_a_k, bounded_y, inputs.pressure_pa)
    p_v = vapor_partial_pressure(bounded_y, inputs.pressure_pa)
    p_sat_air = saturation_vapor_pressure(t_a_k)
    p_sat_particle = saturation_vapor_pressure(bounded_t_p_k)
    rho_v_air = water_vapor_density(t_a_k, bounded_y, inputs.pressure_pa)
    rho_v_sat_air = saturated_vapor_density(t_a_k)
    rho_v_sat_particle = saturated_vapor_density(bounded_t_p_k)
    rho_air = moist_air_density(t_a_k, bounded_y, inputs.pressure_pa)
    mu_air = dynamic_viscosity_air(t_a_k)
    k_air = thermal_conductivity_air(t_a_k)
    d_v = water_vapor_diffusivity(t_a_k, inputs.pressure_pa)
    u_air = air_superficial_velocity(
        t_a_k,
        bounded_y,
        inputs.pressure_pa,
        derived.dry_air_mass_flow_kg_s,
        derived.chamber_cross_section_area_m2,
    )
    x_b = equilibrium_moisture(t_a_k, rh_air, inputs.x_b_model)
    chew = chew_material_state(
        moisture_dry_basis=bounded_x,
        x_b=x_b,
        feed_total_solids=inputs.feed_total_solids,
        temp_particle_k=bounded_t_p_k,
        temp_air_k=t_a_k,
        rh_air=rh_air,
    )
    particle_diameter = derived.droplet_diameter_m * chew.shrinkage_ratio
    particle_mass_value = particle_mass(derived.representative_dry_solids_mass_kg, bounded_x)
    particle_density = particle_density_from_mass_and_diameter(
        particle_mass_value,
        particle_diameter,
    )
    transport = evaluate_transport(
        air_density_kg_m3=rho_air,
        air_viscosity_kg_m_s=mu_air,
        air_thermal_conductivity_w_m_k=k_air,
        water_vapor_diffusivity_m2_s=d_v,
        air_cp_j_kg_k=derived.cpa_j_kg_k + bounded_y * CP_WATER_VAPOR,
        particle_diameter_m=particle_diameter,
        particle_velocity_ms=bounded_u_p_ms,
        air_velocity_ms=u_air,
    )
    return AlgebraicState(
        h_m=h_m,
        X=bounded_x,
        T_p_k=bounded_t_p_k,
        Y=bounded_y,
        H_h_j_kg_da=h_h,
        U_p_ms=bounded_u_p_ms,
        tau_s=tau,
        T_a_k=t_a_k,
        T_p_c=bounded_t_p_k - 273.15,
        T_a_c=t_a_k - 273.15,
        p_v_pa=p_v,
        p_sat_air_pa=p_sat_air,
        p_sat_particle_pa=p_sat_particle,
        RH_a=rh_air,
        rho_v_air_kg_m3=rho_v_air,
        rho_v_sat_air_kg_m3=rho_v_sat_air,
        rho_v_sat_particle_kg_m3=rho_v_sat_particle,
        rho_v_surface_kg_m3=chew.psi * rho_v_sat_particle,
        rho_air_kg_m3=rho_air,
        air_viscosity_kg_m_s=mu_air,
        air_thermal_conductivity_w_m_k=k_air,
        water_vapor_diffusivity_m2_s=d_v,
        U_a_ms=u_air,
        particle_mass_kg=particle_mass_value,
        particle_diameter_m=particle_diameter,
        particle_density_kg_m3=particle_density,
        particle_area_m2=particle_area(particle_diameter),
        particle_cp_j_kg_k=derived.cps_j_kg_k + bounded_x * derived.cpw_j_kg_k,
        h_fg_j_kg=latent_heat_evaporation(bounded_t_p_k),
        x_b=chew.x_b,
        delta=chew.delta,
        initial_moisture_dry_basis=chew.initial_moisture_dry_basis,
        linear_slope=chew.linear_slope,
        linear_intercept=chew.linear_intercept,
        critical_delta=chew.critical_delta,
        critical_ratio=chew.critical_ratio,
        activation_ratio=chew.activation_ratio,
        delta_e_max_j_mol=chew.delta_e_max_j_mol,
        delta_e_j_mol=chew.delta_e_j_mol,
        psi=chew.psi,
        q_loss_prime_w_m=derived.chamber_ua_w_k / max(inputs.dryer_height_m, EPS) * (t_a_k - derived.ambient_temp_k),
        transport=transport,
    )


def evaluate_rhs(
    h_m: float,
    state_vector: np.ndarray,
    inputs: StationarySMPREAInput,
    derived: StationarySMPREADerivedInputs,
) -> RHSState:
    algebraic = evaluate_algebraic_state(h_m, state_vector, inputs, derived)
    dm_p_dh = -(
        algebraic.transport.mass_transfer_coeff_ms
        * algebraic.particle_area_m2
        / max(algebraic.U_p_ms, EPS)
        * (algebraic.rho_v_surface_kg_m3 - algebraic.rho_v_air_kg_m3)
    )
    dX_dh = dm_p_dh / max(derived.representative_dry_solids_mass_kg, EPS)
    dT_p_dh = (
        np.pi
        * algebraic.particle_diameter_m
        * algebraic.air_thermal_conductivity_w_m_k
        * algebraic.transport.nusselt_number
        * (algebraic.T_a_k - algebraic.T_p_k)
        + dm_p_dh * algebraic.U_p_ms * algebraic.h_fg_j_kg
    ) / max(
        derived.representative_dry_solids_mass_kg
        * algebraic.particle_cp_j_kg_k
        * algebraic.U_p_ms,
        EPS,
    )
    dY_dh = -derived.dry_solids_mass_flow_kg_s / max(derived.dry_air_mass_flow_kg_s, EPS) * dX_dh
    dH_h_dh = -(
        derived.dry_solids_mass_flow_kg_s / max(derived.dry_air_mass_flow_kg_s, EPS)
    ) * algebraic.particle_cp_j_kg_k * dT_p_dh - algebraic.q_loss_prime_w_m / max(
        derived.dry_air_mass_flow_kg_s,
        EPS,
    )
    dU_p_dh = (
        (
            (1.0 - algebraic.rho_air_kg_m3 / max(algebraic.particle_density_kg_m3, EPS))
            * derived.gravity_m_s2
        )
        - (
            0.75
            * algebraic.rho_air_kg_m3
            * algebraic.transport.drag_coefficient
            * algebraic.transport.relative_velocity_ms
            * (algebraic.U_p_ms - algebraic.U_a_ms)
            / max(algebraic.particle_density_kg_m3 * algebraic.particle_diameter_m, EPS)
        )
    ) / max(algebraic.U_p_ms, EPS)
    dtau_dh = 1.0 / max(algebraic.U_p_ms, EPS) if inputs.include_tau_state else None
    return RHSState(
        algebraic=algebraic,
        dm_p_dh_kg_m=dm_p_dh,
        dX_dh=dX_dh,
        dT_p_dh=dT_p_dh,
        dY_dh=dY_dh,
        dH_h_dh=dH_h_dh,
        dU_p_dh=dU_p_dh,
        dtau_dh=dtau_dh,
    )


def axial_rhs(
    h_m: float,
    state_vector: np.ndarray,
    inputs: StationarySMPREAInput,
    derived: StationarySMPREADerivedInputs,
) -> np.ndarray:
    rhs = evaluate_rhs(h_m, state_vector, inputs, derived)
    values = [rhs.dX_dh, rhs.dT_p_dh, rhs.dY_dh, rhs.dH_h_dh, rhs.dU_p_dh]
    if inputs.include_tau_state:
        values.append(rhs.dtau_dh if rhs.dtau_dh is not None else 0.0)
    return np.array(values, dtype=float)
