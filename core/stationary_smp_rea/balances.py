from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .air import (
    CP_WATER_VAPOR,
    T_REF_K,
    air_superficial_velocity,
    dynamic_viscosity_air,
    humidity_ratio_from_vapor_pressure,
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
from .closures import equilibrium_moisture_closure
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
    Y_eff: float
    H_h_j_kg_da: float
    U_p_ms: float
    tau_s: float | None
    T_a_k: float
    T_p_c: float
    T_a_c: float
    p_v_pa: float
    p_v_eff_pa: float
    p_sat_air_pa: float
    p_sat_particle_pa: float
    RH_a: float
    RH_eff: float
    humidity_bias_active: float
    rho_v_air_kg_m3: float
    rho_v_air_eff_kg_m3: float
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
    q_sorption_j_kg: float
    x_b: float
    x_b_lin_gab: float
    x_b_langrish: float
    x_b_langrish_weight: float
    delta: float
    initial_moisture_dry_basis: float
    linear_slope: float
    linear_intercept: float
    shrinkage_mode: str
    critical_delta: float
    critical_ratio: float
    normalized_delta: float
    activation_ratio_base: float
    activation_ratio_add: float
    activation_ratio: float
    delta_e_max_j_mol: float
    delta_e_j_mol: float
    psi: float
    contact_efficiency: float
    axial_exposure_factor: float
    combined_contact_exposure_factor: float
    effective_mass_transfer_coeff_ms: float
    effective_heat_transfer_coeff_w_m2_k: float
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
    q_conv_w: float
    q_latent_w: float
    q_sorption_w: float
    q_evap_total_w: float
    q_evap_to_conv_ratio: float


def _state_components(vector: np.ndarray, include_tau_state: bool) -> tuple[float, float, float, float, float, float | None]:
    if include_tau_state:
        return float(vector[0]), float(vector[1]), float(vector[2]), float(vector[3]), float(vector[4]), float(vector[5])
    return float(vector[0]), float(vector[1]), float(vector[2]), float(vector[3]), float(vector[4]), None


def _smoothstep01(value: float) -> float:
    bounded_value = min(max(value, 0.0), 1.0)
    return bounded_value * bounded_value * (3.0 - 2.0 * bounded_value)


def _smooth_transition(
    h_m: float,
    start_h_m: float,
    end_h_m: float,
    start_value: float,
    end_value: float,
) -> float:
    if end_h_m <= start_h_m:
        return end_value
    blend = _smoothstep01((h_m - start_h_m) / max(end_h_m - start_h_m, EPS))
    return start_value + (end_value - start_value) * blend


def _atomization_zone_axial_exposure_factor(
    h_m: float,
    inputs: StationarySMPREAInput,
) -> float:
    atomization_zone_length_m = inputs.atomization_zone_length_m
    atomization_zone_exposure_factor = inputs.atomization_zone_exposure_factor
    secondary_zone_length_m = inputs.secondary_exposure_zone_length_m
    secondary_zone_factor = inputs.secondary_exposure_zone_factor

    stage1_active = (
        atomization_zone_length_m > 0.0 and atomization_zone_exposure_factor < 1.0
    )
    stage2_active = (
        secondary_zone_length_m > 0.0 and secondary_zone_factor < 1.0
    )

    if not stage1_active and not stage2_active:
        return 1.0

    if stage2_active:
        first_zone_end_h_m = atomization_zone_length_m if atomization_zone_length_m > 0.0 else 0.0
        second_zone_end_h_m = first_zone_end_h_m + secondary_zone_length_m
        transition_width_h_m = min(
            0.05,
            0.25 * max(min(secondary_zone_length_m, max(atomization_zone_length_m, secondary_zone_length_m)), EPS),
        )

        if atomization_zone_length_m > 0.0 and h_m < max(first_zone_end_h_m - transition_width_h_m, 0.0):
            return atomization_zone_exposure_factor
        if atomization_zone_length_m > 0.0 and h_m < first_zone_end_h_m + transition_width_h_m:
            return _smooth_transition(
                h_m,
                max(first_zone_end_h_m - transition_width_h_m, 0.0),
                first_zone_end_h_m + transition_width_h_m,
                atomization_zone_exposure_factor,
                secondary_zone_factor,
            )
        if h_m < max(second_zone_end_h_m - transition_width_h_m, first_zone_end_h_m):
            return secondary_zone_factor
        if h_m < second_zone_end_h_m + transition_width_h_m:
            return _smooth_transition(
                h_m,
                max(second_zone_end_h_m - transition_width_h_m, first_zone_end_h_m),
                second_zone_end_h_m + transition_width_h_m,
                secondary_zone_factor,
                1.0,
            )
        return 1.0

    ramp_coordinate = _smoothstep01(h_m / max(atomization_zone_length_m, EPS))
    return atomization_zone_exposure_factor + (
        1.0 - atomization_zone_exposure_factor
    ) * ramp_coordinate


def _effective_local_target_rh(
    h_m: float,
    inputs: StationarySMPREAInput,
    bulk_rh: float,
) -> float:
    if inputs.effective_gas_humidity_mode != "target_rh":
        return bulk_rh

    zone1_active = (
        inputs.humidity_bias_zone_length_m > 0.0 and inputs.humidity_bias_zone_target_rh > 0.0
    )
    zone2_active = (
        inputs.humidity_bias_zone2_length_m > 0.0 and inputs.humidity_bias_zone2_target_rh > 0.0
    )
    if not zone1_active and not zone2_active:
        return bulk_rh

    zone1_target = max(inputs.humidity_bias_zone_target_rh, bulk_rh)
    zone2_target = max(inputs.humidity_bias_zone2_target_rh, bulk_rh)

    if zone2_active:
        first_zone_end_h_m = inputs.humidity_bias_zone_length_m if zone1_active else 0.0
        second_zone_end_h_m = first_zone_end_h_m + inputs.humidity_bias_zone2_length_m
        transition_width_h_m = min(
            0.05,
            0.25
            * max(
                min(
                    inputs.humidity_bias_zone2_length_m,
                    max(inputs.humidity_bias_zone_length_m, inputs.humidity_bias_zone2_length_m),
                ),
                EPS,
            ),
        )

        if zone1_active and h_m < max(first_zone_end_h_m - transition_width_h_m, 0.0):
            return zone1_target
        if zone1_active and h_m < first_zone_end_h_m + transition_width_h_m:
            return _smooth_transition(
                h_m,
                max(first_zone_end_h_m - transition_width_h_m, 0.0),
                first_zone_end_h_m + transition_width_h_m,
                zone1_target,
                zone2_target,
            )
        if h_m < max(second_zone_end_h_m - transition_width_h_m, first_zone_end_h_m):
            return zone2_target
        if h_m < second_zone_end_h_m + transition_width_h_m:
            return _smooth_transition(
                h_m,
                max(second_zone_end_h_m - transition_width_h_m, first_zone_end_h_m),
                second_zone_end_h_m + transition_width_h_m,
                zone2_target,
                bulk_rh,
            )
        return bulk_rh

    return _smooth_transition(
        h_m,
        0.0,
        max(inputs.humidity_bias_zone_length_m, EPS),
        zone1_target,
        bulk_rh,
    )


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
    raw_particle_velocity_ms = (
        inputs.fixed_particle_velocity_ms
        if inputs.fixed_particle_velocity_ms is not None
        else u_p_ms
    )
    bounded_u_p_ms = max(raw_particle_velocity_ms, inputs.min_particle_velocity_ms)

    t_a_k = max(invert_humid_air_enthalpy(h_h, bounded_y), 250.0)
    rh_air = relative_humidity(t_a_k, bounded_y, inputs.pressure_pa)
    rh_eff = min(
        max(_effective_local_target_rh(h_m, inputs, rh_air), rh_air),
        0.999999,
    )
    p_v = vapor_partial_pressure(bounded_y, inputs.pressure_pa)
    p_v_eff = min(
        max(rh_eff * saturation_vapor_pressure(t_a_k), 0.0),
        0.999999 * inputs.pressure_pa,
    )
    y_eff = max(humidity_ratio_from_vapor_pressure(p_v_eff, inputs.pressure_pa), EPS)
    p_sat_air = saturation_vapor_pressure(t_a_k)
    p_sat_particle = saturation_vapor_pressure(bounded_t_p_k)
    rho_v_air = water_vapor_density(t_a_k, bounded_y, inputs.pressure_pa)
    rho_v_air_eff = water_vapor_density(t_a_k, y_eff, inputs.pressure_pa)
    rho_v_sat_air = saturated_vapor_density(t_a_k)
    rho_v_sat_particle = saturated_vapor_density(bounded_t_p_k)
    rho_air = moist_air_density(t_a_k, bounded_y, inputs.pressure_pa)
    mu_air = dynamic_viscosity_air(t_a_k)
    k_air = thermal_conductivity_air(t_a_k)
    d_v = water_vapor_diffusivity(t_a_k, inputs.pressure_pa)
    local_cross_section_area_m2 = derived.geometry.cross_section_area_at(h_m)
    local_wall_area_density_m2_m = derived.geometry.wall_area_density_at(h_m)
    u_air = (
        inputs.fixed_air_velocity_ms
        if inputs.fixed_air_velocity_ms is not None
        else air_superficial_velocity(
            t_a_k,
            bounded_y,
            inputs.pressure_pa,
            derived.dry_air_mass_flow_kg_s,
            local_cross_section_area_m2,
        )
    )
    x_b_closure = equilibrium_moisture_closure(
        t_a_k,
        rh_eff,
        inputs.x_b_model,
        x_b_blend_langrish_weight=inputs.x_b_blend_langrish_weight,
        x_b_blend_langrish_weight_base=inputs.x_b_blend_langrish_weight_base,
        x_b_blend_langrish_weight_rh_coeff=inputs.x_b_blend_langrish_weight_rh_coeff,
    )
    x_b = x_b_closure.x_b
    chew = chew_material_state(
        moisture_dry_basis=bounded_x,
        x_b=x_b,
        feed_total_solids=inputs.feed_total_solids,
        shrinkage_model=inputs.shrinkage_model,
        temp_particle_k=bounded_t_p_k,
        temp_air_k=t_a_k,
        rh_air=rh_eff,
        enable_material_retardation_add=inputs.enable_material_retardation_add,
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
    axial_exposure_factor = _atomization_zone_axial_exposure_factor(h_m, inputs)
    combined_contact_exposure_factor = inputs.contact_efficiency * axial_exposure_factor
    return AlgebraicState(
        h_m=h_m,
        X=bounded_x,
        T_p_k=bounded_t_p_k,
        Y=bounded_y,
        Y_eff=y_eff,
        H_h_j_kg_da=h_h,
        U_p_ms=bounded_u_p_ms,
        tau_s=tau,
        T_a_k=t_a_k,
        T_p_c=bounded_t_p_k - 273.15,
        T_a_c=t_a_k - 273.15,
        p_v_pa=p_v,
        p_v_eff_pa=p_v_eff,
        p_sat_air_pa=p_sat_air,
        p_sat_particle_pa=p_sat_particle,
        RH_a=rh_air,
        RH_eff=rh_eff,
        humidity_bias_active=1.0 if rh_eff > rh_air + 1e-12 else 0.0,
        rho_v_air_kg_m3=rho_v_air,
        rho_v_air_eff_kg_m3=rho_v_air_eff,
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
        h_fg_j_kg=latent_heat_evaporation(t_a_k),
        q_sorption_j_kg=633.0e3 if bounded_x <= 0.08 else 0.0,
        x_b=chew.x_b,
        x_b_lin_gab=x_b_closure.x_b_lin_gab,
        x_b_langrish=x_b_closure.x_b_langrish,
        x_b_langrish_weight=x_b_closure.x_b_langrish_weight,
        delta=chew.delta,
        initial_moisture_dry_basis=chew.initial_moisture_dry_basis,
        linear_slope=chew.linear_slope,
        linear_intercept=chew.linear_intercept,
        shrinkage_mode=chew.shrinkage_mode,
        critical_delta=chew.critical_delta,
        critical_ratio=chew.critical_ratio,
        normalized_delta=chew.normalized_delta,
        activation_ratio_base=chew.activation_ratio_base,
        activation_ratio_add=chew.activation_ratio_add,
        activation_ratio=chew.activation_ratio,
        delta_e_max_j_mol=chew.delta_e_max_j_mol,
        delta_e_j_mol=chew.delta_e_j_mol,
        psi=chew.psi,
        contact_efficiency=inputs.contact_efficiency,
        axial_exposure_factor=axial_exposure_factor,
        combined_contact_exposure_factor=combined_contact_exposure_factor,
        effective_mass_transfer_coeff_ms=(
            combined_contact_exposure_factor * transport.mass_transfer_coeff_ms
        ),
        effective_heat_transfer_coeff_w_m2_k=(
            combined_contact_exposure_factor * transport.heat_transfer_coeff_w_m2_k
        ),
        q_loss_prime_w_m=(
            inputs.heat_loss_coeff_w_m2k
            * local_wall_area_density_m2_m
            * (t_a_k - derived.ambient_temp_k)
        ),
        transport=transport,
    )


def evaluate_rhs(
    h_m: float,
    state_vector: np.ndarray,
    inputs: StationarySMPREAInput,
    derived: StationarySMPREADerivedInputs,
) -> RHSState:
    algebraic = evaluate_algebraic_state(h_m, state_vector, inputs, derived)
    raw_dm_p_dh = -(
        algebraic.effective_mass_transfer_coeff_ms
        * algebraic.particle_area_m2
        / max(algebraic.U_p_ms, EPS)
        * (algebraic.rho_v_surface_kg_m3 - algebraic.rho_v_air_eff_kg_m3)
    )
    # Enforce zero drying rate once the local equilibrium moisture is reached.
    # The current REA closure is only calibrated on the drying side (X >= X_b),
    # so we must not continue evaporating once X drops to or below X_b.
    dm_p_dh = (
        0.0
        if algebraic.X <= algebraic.x_b and raw_dm_p_dh < 0.0
        else raw_dm_p_dh
    )
    dX_dh = dm_p_dh / max(derived.representative_dry_solids_mass_kg, EPS)
    q_conv_w = (
        algebraic.effective_heat_transfer_coeff_w_m2_k
        * algebraic.particle_area_m2
        * (algebraic.T_a_k - algebraic.T_p_k)
    )
    q_latent_w = -dm_p_dh * algebraic.U_p_ms * algebraic.h_fg_j_kg
    q_sorption_w = -dm_p_dh * algebraic.U_p_ms * algebraic.q_sorption_j_kg
    q_evap_total_w = q_latent_w + q_sorption_w
    q_evap_to_conv_ratio = q_evap_total_w / max(abs(q_conv_w), EPS)
    dT_p_dh = (
        q_conv_w
        - q_evap_total_w
    ) / max(
        derived.representative_dry_solids_mass_kg
        * algebraic.particle_cp_j_kg_k
        * algebraic.U_p_ms,
        EPS,
    )
    dY_dh = -derived.dry_solids_mass_flow_kg_s / max(derived.dry_air_mass_flow_kg_s, EPS) * dX_dh
    particle_enthalpy_moisture_term_dh = derived.cpw_j_kg_k * (
        algebraic.T_p_k - T_REF_K
    ) * dX_dh
    dH_h_dh = -(
        derived.dry_solids_mass_flow_kg_s / max(derived.dry_air_mass_flow_kg_s, EPS)
    ) * (
        algebraic.particle_cp_j_kg_k * dT_p_dh
        + particle_enthalpy_moisture_term_dh
    ) - algebraic.q_loss_prime_w_m / max(
        derived.dry_air_mass_flow_kg_s,
        EPS,
    )
    if inputs.fixed_particle_velocity_ms is not None:
        dU_p_dh = 0.0
    else:
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
        q_conv_w=q_conv_w,
        q_latent_w=q_latent_w,
        q_sorption_w=q_sorption_w,
        q_evap_total_w=q_evap_total_w,
        q_evap_to_conv_ratio=q_evap_to_conv_ratio,
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
