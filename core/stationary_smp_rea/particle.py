from __future__ import annotations

from math import pi


EPS = 1e-12


def feed_mixture_density(x_dry_basis: float, dry_solids_density_kg_m3: float, water_density_kg_m3: float) -> float:
    return (1.0 + x_dry_basis) / (
        (1.0 / dry_solids_density_kg_m3) + (x_dry_basis / water_density_kg_m3)
    )


def initial_dry_solids_mass(
    initial_diameter_m: float,
    x0_dry_basis: float,
    dry_solids_density_kg_m3: float,
    water_density_kg_m3: float,
) -> float:
    volume_m3 = pi * initial_diameter_m**3 / 6.0
    initial_density = feed_mixture_density(
        x0_dry_basis,
        dry_solids_density_kg_m3,
        water_density_kg_m3,
    )
    initial_particle_mass = initial_density * volume_m3
    return initial_particle_mass / max(1.0 + x0_dry_basis, EPS)


def particle_mass(dry_solids_mass_kg: float, moisture_dry_basis: float) -> float:
    return dry_solids_mass_kg * (1.0 + moisture_dry_basis)


def particle_area(diameter_m: float) -> float:
    return pi * diameter_m**2


def particle_density_from_mass_and_diameter(particle_mass_kg: float, diameter_m: float) -> float:
    return 6.0 * particle_mass_kg / max(pi * diameter_m**3, EPS)
