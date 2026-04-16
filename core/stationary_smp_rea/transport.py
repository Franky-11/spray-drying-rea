from __future__ import annotations

from dataclasses import dataclass


EPS = 1e-12


@dataclass(frozen=True)
class TransportState:
    relative_velocity_ms: float
    reynolds_number: float
    schmidt_number: float
    sherwood_number: float
    prandtl_number: float
    nusselt_number: float
    drag_coefficient: float
    mass_transfer_coeff_ms: float
    heat_transfer_coeff_w_m2_k: float


def evaluate_transport(
    *,
    air_density_kg_m3: float,
    air_viscosity_kg_m_s: float,
    air_thermal_conductivity_w_m_k: float,
    water_vapor_diffusivity_m2_s: float,
    air_cp_j_kg_k: float,
    particle_diameter_m: float,
    particle_velocity_ms: float,
    air_velocity_ms: float,
) -> TransportState:
    relative_velocity = abs(particle_velocity_ms - air_velocity_ms)
    reynolds_number = (
        air_density_kg_m3
        * relative_velocity
        * particle_diameter_m
        / max(air_viscosity_kg_m_s, EPS)
    )
    reynolds_number = max(reynolds_number, EPS)
    schmidt_number = air_viscosity_kg_m_s / max(
        air_density_kg_m3 * water_vapor_diffusivity_m2_s,
        EPS,
    )
    prandtl_number = air_cp_j_kg_k * air_viscosity_kg_m_s / max(
        air_thermal_conductivity_w_m_k,
        EPS,
    )
    sherwood_number = 2.0 + 0.6 * reynolds_number**0.5 * schmidt_number ** (1.0 / 3.0)
    nusselt_number = 2.0 + 0.6 * reynolds_number**0.5 * prandtl_number ** (1.0 / 3.0)
    drag_coefficient = 24.0 / reynolds_number * (1.0 + 0.15 * reynolds_number**0.687)
    mass_transfer_coeff = sherwood_number * water_vapor_diffusivity_m2_s / max(
        particle_diameter_m,
        EPS,
    )
    heat_transfer_coeff = nusselt_number * air_thermal_conductivity_w_m_k / max(
        particle_diameter_m,
        EPS,
    )
    return TransportState(
        relative_velocity_ms=relative_velocity,
        reynolds_number=reynolds_number,
        schmidt_number=schmidt_number,
        sherwood_number=sherwood_number,
        prandtl_number=prandtl_number,
        nusselt_number=nusselt_number,
        drag_coefficient=drag_coefficient,
        mass_transfer_coeff_ms=mass_transfer_coeff,
        heat_transfer_coeff_w_m2_k=heat_transfer_coeff,
    )
