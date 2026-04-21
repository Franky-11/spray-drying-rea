from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import pandas as pd

from .air import (
    CP_DRY_AIR,
    CP_LIQUID_WATER,
    CP_WATER_VAPOR,
    LAMBDA_REF_J_KG,
    R_DRY_AIR,
    R_WATER_VAPOR,
    humid_air_enthalpy,
    moist_air_density,
)
from .closures import XBModel
from .geometry import EffectiveDryerGeometry, build_effective_dryer_geometry
from .materials import chew_validity_warnings
from .particle import (
    feed_mixture_density,
    initial_dry_solids_mass,
    pressure_nozzle_exit_velocity,
)


EPS = 1e-12
SUPPORTED_SOLVER_METHODS = {"BDF", "RK45", "Radau"}
ShrinkageModel = Literal["auto", "chew", "legacy_extended"]


@dataclass(frozen=True)
class StationarySMPREAInput:
    dryer_height_m: float = 2.0
    dryer_diameter_m: float = 0.8
    cylinder_height_m: float | None = None
    cone_height_m: float = 0.0
    cylinder_diameter_m: float | None = None
    outlet_duct_length_m: float = 0.0
    outlet_duct_diameter_m: float | None = None
    inlet_air_temp_c: float = 190.0
    droplet_size_um: float = 95.0
    feed_rate_kg_h: float = 3.0
    air_flow_m3_h: float = 140.0
    inlet_abs_humidity_g_kg: float = 5.7
    ambient_temp_c: float = 20.0
    feed_temp_c: float = 40.0
    feed_total_solids: float = 0.40
    initial_droplet_velocity_ms: float | None = None
    nozzle_delta_p_bar: float = 47.0
    nozzle_velocity_coefficient: float = 0.60
    pressure_pa: float = 101325.0
    heat_loss_coeff_w_m2k: float = 4.5
    contact_efficiency: float = 1.0
    enable_material_retardation_add: bool = True
    dry_solids_density_kg_m3: float = 1400.0
    water_density_kg_m3: float = 1000.0
    dry_solids_specific_heat_j_kg_k: float = 1500.0
    material: Literal["SMP"] = "SMP"
    x_b_model: XBModel = "lin_gab"
    shrinkage_model: ShrinkageModel = "auto"
    axial_points: int = 250
    include_tau_state: bool = True
    min_particle_velocity_ms: float = 0.05
    fixed_particle_velocity_ms: float | None = None
    fixed_air_velocity_ms: float | None = None
    solver_method: str = "BDF"
    solver_rtol: float = 1e-6
    solver_atol: float = 1e-8

    def validate(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []

        positive_fields = {
            "dryer_height_m": self.dryer_height_m,
            "dryer_diameter_m": self.dryer_diameter_m,
            "droplet_size_um": self.droplet_size_um,
            "feed_rate_kg_h": self.feed_rate_kg_h,
            "air_flow_m3_h": self.air_flow_m3_h,
            "pressure_pa": self.pressure_pa,
            "dry_solids_density_kg_m3": self.dry_solids_density_kg_m3,
            "water_density_kg_m3": self.water_density_kg_m3,
            "dry_solids_specific_heat_j_kg_k": self.dry_solids_specific_heat_j_kg_k,
            "min_particle_velocity_ms": self.min_particle_velocity_ms,
            "nozzle_delta_p_bar": self.nozzle_delta_p_bar,
            "nozzle_velocity_coefficient": self.nozzle_velocity_coefficient,
            "solver_rtol": self.solver_rtol,
            "solver_atol": self.solver_atol,
        }
        for name, value in positive_fields.items():
            if value <= 0.0:
                errors.append(f"{name} muss groesser als 0 sein.")

        optional_positive_fields = {
            "cylinder_height_m": self.cylinder_height_m,
            "cylinder_diameter_m": self.cylinder_diameter_m,
            "outlet_duct_diameter_m": self.outlet_duct_diameter_m,
            "initial_droplet_velocity_ms": self.initial_droplet_velocity_ms,
            "fixed_particle_velocity_ms": self.fixed_particle_velocity_ms,
            "fixed_air_velocity_ms": self.fixed_air_velocity_ms,
        }
        for name, value in optional_positive_fields.items():
            if value is not None and value <= 0.0:
                errors.append(f"{name} muss groesser als 0 sein, falls gesetzt.")

        nonnegative_fields = {
            "cone_height_m": self.cone_height_m,
            "outlet_duct_length_m": self.outlet_duct_length_m,
        }
        for name, value in nonnegative_fields.items():
            if value < 0.0:
                errors.append(f"{name} darf nicht negativ sein.")

        if self.heat_loss_coeff_w_m2k < 0.0:
            errors.append("heat_loss_coeff_w_m2k darf nicht negativ sein.")
        if not 0.0 < self.contact_efficiency <= 1.0:
            errors.append("contact_efficiency muss im Bereich (0, 1] liegen.")
        if self.inlet_abs_humidity_g_kg < 0.0:
            errors.append("inlet_abs_humidity_g_kg darf nicht negativ sein.")
        if self.axial_points < 25:
            errors.append("axial_points muss mindestens 25 sein.")
        if self.solver_method not in SUPPORTED_SOLVER_METHODS:
            errors.append(
                f"solver_method muss eine von {sorted(SUPPORTED_SOLVER_METHODS)} sein."
            )
        if self.material != "SMP":
            errors.append("Der neue stationaere Kern unterstuetzt nur SMP.")
        if not 0.20 <= self.feed_total_solids <= 0.50:
            errors.append(
                "feed_total_solids muss fuer den aktuellen SMP-Kern zwischen 0.20 und 0.50 liegen."
            )
        for name, value in {
            "inlet_air_temp_c": self.inlet_air_temp_c,
            "feed_temp_c": self.feed_temp_c,
            "ambient_temp_c": self.ambient_temp_c,
        }.items():
            if value <= -273.15:
                errors.append(f"{name} must be greater than -273.15 degC.")

        warnings.extend(chew_validity_warnings(self.feed_total_solids))
        if not 120.0 <= self.inlet_air_temp_c <= 220.0:
            warnings.append(
                "The inlet air temperature is outside the typical design window of about 120-220 degC."
            )
        if self.feed_total_solids < 0.30:
            warnings.append(
                "Below 30 wt%, the core uses the low-solids legacy branch for the early REA phase with a shared polynomial curve and a 30-wt% linear branch."
            )
        if self.feed_total_solids < 0.37 and self.shrinkage_model == "chew":
            warnings.append(
                "For SMP shrinkage below 37 wt%, the first core uses the 37-wt% anchor as a conservative approximation."
            )
        if self.feed_total_solids < 0.37 and self.shrinkage_model in {"auto", "legacy_extended"}:
            warnings.append(
                "Below 37 wt%, SMP shrinkage uses the extended legacy branch with 20/30-wt% anchors."
            )
        if self.cone_height_m > 0.0 or self.outlet_duct_length_m > 0.0:
            warnings.append(
                "The section-wise geometry treats cylinder, cone, and outlet duct as an effective 1D flow path with local cross section; redirection, back-mixing, and changes in flow direction are not resolved separately."
            )
        if self.outlet_duct_length_m > 0.0:
            warnings.append(
                "The report point 'pre_cyclone' is located at the end of the effective outlet duct section directly upstream of the cyclone inlet."
            )
        if self.fixed_particle_velocity_ms is not None or self.fixed_air_velocity_ms is not None:
            warnings.append(
                "The velocity diagnostic uses fixed particle and/or air velocities; drag-coupled velocity development and/or the local continuity velocity are intentionally overridden."
            )
        if self.contact_efficiency < 1.0:
            warnings.append(
                "The tower contact efficiency scales both heat and mass transfer below the ideal 1D reference to emulate reduced effective particle-air exposure."
            )
        if not self.enable_material_retardation_add:
            warnings.append(
                "The extra early falling-rate material-side REA retardation is disabled; drying follows only the baseline REA branch."
            )

        return errors, warnings

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StationarySMPREADerivedInputs:
    inlet_air_temp_k: float
    inlet_particle_temp_k: float
    ambient_temp_k: float
    inlet_humidity_ratio: float
    x0_dry_basis: float
    droplet_diameter_m: float
    geometry: EffectiveDryerGeometry
    total_axial_length_m: float
    dryer_exit_h_m: float
    pre_cyclone_h_m: float
    chamber_cross_section_area_m2: float
    chamber_lateral_area_m2: float
    chamber_ua_w_k: float
    dry_air_mass_flow_kg_s: float
    humid_air_mass_flow_kg_s: float
    dry_solids_mass_flow_kg_s: float
    water_mass_flow_kg_s: float
    air_to_solids_ratio_kg_kg: float
    initial_air_enthalpy_j_kg_da: float
    initial_particle_density_kg_m3: float
    initial_droplet_velocity_ms: float
    representative_dry_solids_mass_kg: float
    representative_initial_particle_mass_kg: float
    cpa_j_kg_k: float
    cpv_j_kg_k: float
    cpw_j_kg_k: float
    cps_j_kg_k: float
    lambda_ref_j_kg: float
    r_dry_air_j_kg_k: float
    r_water_vapor_j_kg_k: float
    gas_constant_j_mol_k: float
    gravity_m_s2: float


@dataclass
class StationarySMPREAResult:
    inputs: StationarySMPREAInput
    series: pd.DataFrame
    outlet: dict[str, float | str | None]
    report_points: dict[str, dict[str, float | str | None]]
    warnings: list[str]
    solver_status: int
    solver_message: str
    success: bool
    provenance: dict[str, str]


def derive_inputs(inputs: StationarySMPREAInput) -> StationarySMPREADerivedInputs:
    inlet_air_temp_k = inputs.inlet_air_temp_c + 273.15
    inlet_particle_temp_k = inputs.feed_temp_c + 273.15
    ambient_temp_k = inputs.ambient_temp_c + 273.15
    inlet_humidity_ratio = inputs.inlet_abs_humidity_g_kg / 1000.0
    x0_dry_basis = (1.0 - inputs.feed_total_solids) / inputs.feed_total_solids
    droplet_diameter_m = inputs.droplet_size_um / 1_000_000.0
    geometry = build_effective_dryer_geometry(
        dryer_height_m=inputs.dryer_height_m,
        dryer_diameter_m=inputs.dryer_diameter_m,
        cylinder_height_m=inputs.cylinder_height_m,
        cone_height_m=inputs.cone_height_m,
        cylinder_diameter_m=inputs.cylinder_diameter_m,
        outlet_duct_length_m=inputs.outlet_duct_length_m,
        outlet_duct_diameter_m=inputs.outlet_duct_diameter_m,
    )
    chamber_cross_section_area_m2 = geometry.cross_section_area_at(0.0)
    chamber_lateral_area_m2 = geometry.total_wall_area_m2
    chamber_ua_w_k = chamber_lateral_area_m2 * inputs.heat_loss_coeff_w_m2k
    inlet_air_density = moist_air_density(
        inlet_air_temp_k,
        inlet_humidity_ratio,
        inputs.pressure_pa,
    )
    humid_air_mass_flow_kg_s = inlet_air_density * inputs.air_flow_m3_h / 3600.0
    dry_air_mass_flow_kg_s = humid_air_mass_flow_kg_s / max(1.0 + inlet_humidity_ratio, EPS)
    dry_solids_mass_flow_kg_s = inputs.feed_rate_kg_h * inputs.feed_total_solids / 3600.0
    water_mass_flow_kg_s = inputs.feed_rate_kg_h * (1.0 - inputs.feed_total_solids) / 3600.0
    air_to_solids_ratio = dry_air_mass_flow_kg_s / max(dry_solids_mass_flow_kg_s, EPS)
    initial_density = feed_mixture_density(
        x0_dry_basis,
        inputs.dry_solids_density_kg_m3,
        inputs.water_density_kg_m3,
    )
    representative_dry_solids_mass_kg = initial_dry_solids_mass(
        droplet_diameter_m,
        x0_dry_basis,
        inputs.dry_solids_density_kg_m3,
        inputs.water_density_kg_m3,
    )
    representative_initial_particle_mass_kg = representative_dry_solids_mass_kg * (1.0 + x0_dry_basis)
    initial_air_enthalpy_j_kg_da = humid_air_enthalpy(inlet_air_temp_k, inlet_humidity_ratio)
    initial_droplet_velocity_ms = (
        inputs.initial_droplet_velocity_ms
        if inputs.initial_droplet_velocity_ms is not None
        else pressure_nozzle_exit_velocity(
            inputs.nozzle_delta_p_bar,
            initial_density,
            inputs.nozzle_velocity_coefficient,
        )
    )
    return StationarySMPREADerivedInputs(
        inlet_air_temp_k=inlet_air_temp_k,
        inlet_particle_temp_k=inlet_particle_temp_k,
        ambient_temp_k=ambient_temp_k,
        inlet_humidity_ratio=inlet_humidity_ratio,
        x0_dry_basis=x0_dry_basis,
        droplet_diameter_m=droplet_diameter_m,
        geometry=geometry,
        total_axial_length_m=geometry.total_length_m,
        dryer_exit_h_m=geometry.cone_end_h_m,
        pre_cyclone_h_m=geometry.pre_cyclone_h_m,
        chamber_cross_section_area_m2=chamber_cross_section_area_m2,
        chamber_lateral_area_m2=chamber_lateral_area_m2,
        chamber_ua_w_k=chamber_ua_w_k,
        dry_air_mass_flow_kg_s=dry_air_mass_flow_kg_s,
        humid_air_mass_flow_kg_s=humid_air_mass_flow_kg_s,
        dry_solids_mass_flow_kg_s=dry_solids_mass_flow_kg_s,
        water_mass_flow_kg_s=water_mass_flow_kg_s,
        air_to_solids_ratio_kg_kg=air_to_solids_ratio,
        initial_air_enthalpy_j_kg_da=initial_air_enthalpy_j_kg_da,
        initial_particle_density_kg_m3=initial_density,
        initial_droplet_velocity_ms=initial_droplet_velocity_ms,
        representative_dry_solids_mass_kg=representative_dry_solids_mass_kg,
        representative_initial_particle_mass_kg=representative_initial_particle_mass_kg,
        cpa_j_kg_k=CP_DRY_AIR,
        cpv_j_kg_k=CP_WATER_VAPOR,
        cpw_j_kg_k=CP_LIQUID_WATER,
        cps_j_kg_k=inputs.dry_solids_specific_heat_j_kg_k,
        lambda_ref_j_kg=LAMBDA_REF_J_KG,
        r_dry_air_j_kg_k=R_DRY_AIR,
        r_water_vapor_j_kg_k=R_WATER_VAPOR,
        gas_constant_j_mol_k=8.314,
        gravity_m_s2=9.81,
    )
