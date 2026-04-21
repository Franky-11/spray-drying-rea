from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from io import BytesIO
from math import exp, isclose, log, pi
from typing import Any

import numpy as np
import pandas as pd


EPS = 1e-12


@dataclass(frozen=True)
class SimulationInput:
    dryer_height_m: float = 2.0
    inlet_air_temp_c: float = 190.0
    droplet_size_um: float = 95.0
    feed_rate_kg_h: float = 3.0
    air_flow_m3_h: float = 140.0
    inlet_abs_humidity_g_kg: float = 5.7
    ambient_temp_c: float = 20.0
    feed_temp_c: float = 40.0
    feed_total_solids: float = 0.5
    material: str = "SMP"
    dryer_diameter_m: float = 0.8
    heat_loss_coeff_w_m2k: float = 4.5
    xcrit: float = 0.2
    initial_droplet_velocity_ms: float = 30.0
    simulation_end_s: float = 20.0
    time_points: int = 400
    constant_drying_air: bool = False
    solid_density_kg_m3: float = 1400.0
    water_density_kg_m3: float = 1000.0
    protein_fraction: float = 0.35
    lactose_fraction: float = 0.55
    fat_fraction: float = 0.01
    rea_transfer_scale: float = 1.0
    equilibrium_moisture_offset: float = 0.0

    def validate(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []

        positive_fields = {
            "dryer_height_m": self.dryer_height_m,
            "droplet_size_um": self.droplet_size_um,
            "feed_rate_kg_h": self.feed_rate_kg_h,
            "air_flow_m3_h": self.air_flow_m3_h,
            "dryer_diameter_m": self.dryer_diameter_m,
            "simulation_end_s": self.simulation_end_s,
            "solid_density_kg_m3": self.solid_density_kg_m3,
            "water_density_kg_m3": self.water_density_kg_m3,
            "rea_transfer_scale": self.rea_transfer_scale,
        }
        for name, value in positive_fields.items():
            if value <= 0:
                errors.append(f"{name} muss groesser als 0 sein.")

        if self.heat_loss_coeff_w_m2k < 0:
            errors.append("heat_loss_coeff_w_m2k darf nicht negativ sein.")

        if self.inlet_abs_humidity_g_kg < 0:
            errors.append("inlet_abs_humidity_g_kg darf nicht negativ sein.")

        if self.time_points < 50:
            errors.append("time_points muss mindestens 50 sein.")

        for name, value in {
            "inlet_air_temp_c": self.inlet_air_temp_c,
            "ambient_temp_c": self.ambient_temp_c,
            "feed_temp_c": self.feed_temp_c,
        }.items():
            if value <= -273.15:
                errors.append(f"{name} muss groesser als -273.15 degC sein.")

        if not (0 < self.feed_total_solids < 1):
            errors.append("feed_total_solids muss zwischen 0 und 1 liegen.")

        if self.material not in {"SMP", "WPC"}:
            errors.append("material muss 'SMP' oder 'WPC' sein.")

        ash_fraction = 1.0 - (
            self.protein_fraction + self.lactose_fraction + self.fat_fraction
        )
        if ash_fraction < 0:
            errors.append("Protein-, Lactose- und Fettanteil duerfen zusammen hoechstens 1 ergeben.")

        if self.material == "SMP":
            supported_balloon = self.feed_total_solids < 0.2
            supported_dense = 0.2 <= self.feed_total_solids <= 0.5
            if not (supported_balloon or supported_dense):
                errors.append(
                    "SMP unterstuetzt TS < 0.2 sowie den Bereich 0.2 bis 0.5."
                )
        if self.material == "WPC" and not isclose(
            self.feed_total_solids, 0.3, rel_tol=0.0, abs_tol=1e-9
        ):
            errors.append("WPC ist in diesem Modell nur fuer TS = 0.3 validiert.")

        if not 120 <= self.inlet_air_temp_c <= 220:
            warnings.append(
                "Die Zulufttemperatur liegt ausserhalb des fuer das Minimalmodell typischen Bereichs von etwa 120-220 degC."
            )
        if not 50 <= self.droplet_size_um <= 150:
            warnings.append(
                "Die Partikel-/Tropfengroesse liegt ausserhalb des fuer das Minimalmodell typischen Bereichs von etwa 50-150 um."
            )
        if self.feed_total_solids < 0.2:
            warnings.append(
                "TS < 0.2 nutzt das Ballon-Shrinkage-Modell und ist empfindlicher gegen Randbedingungen."
            )
        if self.initial_droplet_velocity_ms < 0:
            errors.append("initial_droplet_velocity_ms darf nicht negativ sein.")

        return errors, warnings

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScenarioConfig:
    label: str
    overrides: dict[str, Any] = field(default_factory=dict)

    def apply(self, base_input: SimulationInput) -> SimulationInput:
        unknown_fields = set(self.overrides) - set(base_input.to_dict())
        if unknown_fields:
            unknown = ", ".join(sorted(unknown_fields))
            raise ValueError(f"Unbekannte Override-Felder: {unknown}")
        return replace(base_input, **self.overrides)


@dataclass
class SimulationResult:
    label: str
    inputs: SimulationInput
    series: pd.DataFrame
    metrics: dict[str, float | None]
    warnings: list[str]
    solver_status: int
    solver_message: str

    def metrics_record(self) -> dict[str, Any]:
        return {"scenario": self.label, **self.metrics}


@dataclass(frozen=True)
class _Derived:
    tb0_k: float
    tp0_k: float
    tu_k: float
    dpi_m: float
    tsfeed: float
    x0: float
    xi: float
    y0: float
    p_pa: float
    rs: float
    rd: float
    rw: float
    gas_constant: float
    cpdryair: float
    cpv: float
    cpw: float
    kb: float
    air_dynamic_viscosity_kg_ms: float
    molecular_weight_dry_air_kg_kmol: float
    molecular_weight_water_kg_kmol: float
    rhos: float
    rhow: float
    rhomilk: float
    rhopballoni: float
    xcrit: float
    prot: float
    lac: float
    fett: float
    asche: float
    cps: float
    solids_rate_kg_s: float
    water_rate_kg_s: float
    humid_air_mass_flow_kg_s: float
    dry_air_mass_flow_kg_s: float
    air_to_solid_ratio: float
    chamber_cross_section_area_m2: float
    chamber_lateral_area_m2: float
    air_superficial_velocity_ms: float
    initial_droplet_velocity_ms: float
    effective_residence_time_s: float
    display_height_m: float
    display_velocity_ms: float
    heat_loss_factor_w_kgk: float
    mass_transfer_base_ms: float
    heat_transfer_base_w_m2k: float
    nominal_air_ratio: float
    rea_transfer_scale: float
    equilibrium_moisture_offset: float


def saturation_vapor_pressure(temp_k: float) -> float:
    temp_c = temp_k - 273.15
    return (
        1.46311e-8 * temp_c**4
        - 1.72583e-6 * temp_c**3
        + 1.73564e-4 * temp_c**2
        - 5.39273e-3 * temp_c
        + 8.13209e-2
    ) * 100000.0


def relative_humidity_from_abs_humidity(
    temp_k: float, abs_humidity: float, total_pressure_pa: float
) -> float:
    pvsat = saturation_vapor_pressure(temp_k)
    rh = (total_pressure_pa / max(pvsat, EPS)) * (
        abs_humidity / max(0.622 + abs_humidity, EPS)
    )
    return min(max(rh, EPS), 0.999)


def humid_air_gas_constant(
    temp_k: float, abs_humidity: float, total_pressure_pa: float, rs: float, rd: float
) -> float:
    rh = relative_humidity_from_abs_humidity(temp_k, abs_humidity, total_pressure_pa)
    pvsat = saturation_vapor_pressure(temp_k)
    denominator = 1 - rh * (pvsat / total_pressure_pa) * (1 - (rs / rd))
    return rs / max(denominator, EPS)


def air_density(
    temp_k: float, abs_humidity: float, total_pressure_pa: float, rs: float, rd: float
) -> float:
    rf = humid_air_gas_constant(temp_k, abs_humidity, total_pressure_pa, rs, rd)
    return total_pressure_pa / max(rf * temp_k, EPS)


def gab_equilibrium_moisture(
    temp_k: float, abs_humidity: float, total_pressure_pa: float
) -> float:
    rh = relative_humidity_from_abs_humidity(temp_k, abs_humidity, total_pressure_pa)
    c_const = 0.001645 * exp(24831 / (temp_k * 8.314))
    k_const = 5.710 * exp(-5118 / (temp_k * 8.314))
    numerator = c_const * k_const * 0.06156 * rh
    denominator = (1 - k_const * rh) * (1 - (k_const * rh) + (c_const * k_const * rh))
    return numerator / max(denominator, EPS)


def adiabatic_saturation_temp(
    temp_k: float, abs_humidity: float, total_pressure_pa: float
) -> float:
    cpdryair = 1.0067 * 1000.0
    cpv = 1.93 * 1000.0

    def moist_air_enthalpy(temp_inner_k: float, humidity_inner: float) -> float:
        temp_c = temp_inner_k - 273.15
        return cpdryair * temp_c + humidity_inner * (2.501e6 + cpv * temp_c)

    def saturation_abs_humidity(temp_inner_k: float) -> float:
        pvsat = saturation_vapor_pressure(temp_inner_k)
        return 0.622 * pvsat / max(total_pressure_pa - pvsat, EPS)

    target_enthalpy = moist_air_enthalpy(temp_k, abs_humidity)
    lower = 273.15
    upper = temp_k
    for _ in range(80):
        mid = 0.5 * (lower + upper)
        saturated_enthalpy = moist_air_enthalpy(mid, saturation_abs_humidity(mid))
        if saturated_enthalpy > target_enthalpy:
            upper = mid
        else:
            lower = mid
    return 0.5 * (lower + upper)


def _mixture_density(x: float, d: _Derived) -> float:
    return d.rhos * ((1 + x) / (1 + (d.rhos / d.rhow) * x))


def _estimate_residence_time(
    inputs: SimulationInput,
    air_superficial_velocity_ms: float,
) -> float:
    air_residence = inputs.dryer_height_m / max(air_superficial_velocity_ms, EPS)
    return float(np.clip(air_residence, 3.0, max(inputs.simulation_end_s * 0.95, 3.0)))


def _water_vapor_diffusivity_air(temp_k: float) -> float:
    return 0.22e-4 * (temp_k / 273.15) ** 1.75


def _specific_heat_loss_rate(
    tb: float,
    d: _Derived,
    heat_loss_factor_w_m2k: float,
) -> tuple[float, float]:
    q_loss_total_w = (
        heat_loss_factor_w_m2k
        * d.chamber_lateral_area_m2
        * max(tb - d.tu_k, 0.0)
    )
    q_loss_w_per_kg_s = q_loss_total_w / max(
        d.solids_rate_kg_s * d.effective_residence_time_s,
        EPS,
    )
    return q_loss_total_w, q_loss_w_per_kg_s


def _build_derived(inputs: SimulationInput) -> _Derived:
    rs = 287.058
    rd = 461.523
    p_pa = 101000.0
    tb0_k = inputs.inlet_air_temp_c + 273.15
    tp0_k = inputs.feed_temp_c + 273.15
    tu_k = inputs.ambient_temp_c + 273.15
    dpi_m = inputs.droplet_size_um / 1_000_000.0
    y0 = inputs.inlet_abs_humidity_g_kg / 1000.0
    tsfeed = inputs.feed_total_solids
    x0 = (1.0 - tsfeed) / tsfeed
    rhoair = air_density(tb0_k, y0, p_pa, rs, rd)
    humid_air_mass_flow_kg_s = (rhoair * inputs.air_flow_m3_h) / 3600.0
    dry_air_mass_flow_kg_s = humid_air_mass_flow_kg_s / max(1.0 + y0, EPS)
    chamber_cross_section_area_m2 = pi * inputs.dryer_diameter_m**2 / 4.0
    chamber_lateral_area_m2 = pi * inputs.dryer_diameter_m * inputs.dryer_height_m
    air_superficial_velocity_ms = (inputs.air_flow_m3_h / 3600.0) / max(
        chamber_cross_section_area_m2, EPS
    )
    solids_rate_kg_s = (inputs.feed_rate_kg_h * tsfeed) / 3600.0
    water_rate_kg_s = (inputs.feed_rate_kg_h * (1.0 - tsfeed)) / 3600.0
    air_to_solid_ratio = dry_air_mass_flow_kg_s / max(solids_rate_kg_s, EPS)
    rhomilk = inputs.solid_density_kg_m3 * (
        (1 + x0) / (1 + (inputs.solid_density_kg_m3 / inputs.water_density_kg_m3) * x0)
    )
    rhopballoni = inputs.solid_density_kg_m3 * (
        (1 + inputs.xcrit)
        / (1 + (inputs.solid_density_kg_m3 / inputs.water_density_kg_m3) * inputs.xcrit)
    )
    asche = 1.0 - (
        inputs.protein_fraction + inputs.lactose_fraction + inputs.fat_fraction
    )
    cps = (
        inputs.protein_fraction * 1600.0
        + inputs.lactose_fraction * 1400.0
        + inputs.fat_fraction * 1700.0
        + asche * 800.0
    )
    effective_residence_time_s = _estimate_residence_time(inputs, air_superficial_velocity_ms)
    display_height_m = inputs.dryer_height_m if inputs.dryer_height_m > 0 else 1.0
    display_velocity_ms = display_height_m / max(effective_residence_time_s, EPS)
    return _Derived(
        tb0_k=tb0_k,
        tp0_k=tp0_k,
        tu_k=tu_k,
        dpi_m=dpi_m,
        tsfeed=tsfeed,
        x0=x0,
        xi=x0,
        y0=y0,
        p_pa=p_pa,
        rs=rs,
        rd=rd,
        rw=461.52,
        gas_constant=8.314,
        cpdryair=1.0067 * 1000.0,
        cpv=1.93 * 1000.0,
        cpw=4.186 * 1000.0,
        kb=0.0262,
        air_dynamic_viscosity_kg_ms=18.2e-6,
        molecular_weight_dry_air_kg_kmol=29.0,
        molecular_weight_water_kg_kmol=18.0,
        rhos=inputs.solid_density_kg_m3,
        rhow=inputs.water_density_kg_m3,
        rhomilk=rhomilk,
        rhopballoni=rhopballoni,
        xcrit=inputs.xcrit,
        prot=inputs.protein_fraction,
        lac=inputs.lactose_fraction,
        fett=inputs.fat_fraction,
        asche=asche,
        cps=cps,
        solids_rate_kg_s=solids_rate_kg_s,
        water_rate_kg_s=water_rate_kg_s,
        humid_air_mass_flow_kg_s=humid_air_mass_flow_kg_s,
        dry_air_mass_flow_kg_s=dry_air_mass_flow_kg_s,
        air_to_solid_ratio=air_to_solid_ratio,
        chamber_cross_section_area_m2=chamber_cross_section_area_m2,
        chamber_lateral_area_m2=chamber_lateral_area_m2,
        air_superficial_velocity_ms=air_superficial_velocity_ms,
        initial_droplet_velocity_ms=inputs.initial_droplet_velocity_ms,
        effective_residence_time_s=effective_residence_time_s,
        display_height_m=display_height_m,
        display_velocity_ms=display_velocity_ms,
        heat_loss_factor_w_kgk=inputs.heat_loss_coeff_w_m2k,
        mass_transfer_base_ms=0.03,
        heat_transfer_base_w_m2k=30.0,
        nominal_air_ratio=air_to_solid_ratio,
        rea_transfer_scale=inputs.rea_transfer_scale,
        equilibrium_moisture_offset=inputs.equilibrium_moisture_offset,
    )


def _interpolate_piecewise(anchor_lo: float, value_lo: float, anchor_hi: float, value_hi: float, x: float) -> float:
    blend = (x - anchor_lo) / max(anchor_hi - anchor_lo, EPS)
    blend = float(np.clip(blend, 0.0, 1.0))
    return value_lo + blend * (value_hi - value_lo)


def _particle_diameter(x: float, xe: float, material: str, d: _Derived) -> float:
    base = d.dpi_m
    denom = max(d.xi - xe, EPS)
    delta = (x - xe) / denom

    if d.tsfeed >= 0.2:
        if material == "SMP":
            factor_02 = 0.67 + (1 - 0.67) * delta
            factor_03 = 0.76 + (1 - 0.76) * delta
            factor_05 = 0.0447 * (x - xe) + 0.959
            if d.tsfeed <= 0.2:
                return base * factor_02
            if d.tsfeed <= 0.3:
                return base * _interpolate_piecewise(0.2, factor_02, 0.3, factor_03, d.tsfeed)
            if d.tsfeed <= 0.5:
                return base * _interpolate_piecewise(0.3, factor_03, 0.5, factor_05, d.tsfeed)
        if material == "WPC":
            return base * (0.873 + (1 - 0.873) * delta)
        raise ValueError("Ungueltige Material-/TS-Kombination fuer das Schrumpfungsmodell.")

    rhopballon = _mixture_density(x, d)
    if x >= d.xcrit:
        return base * ((d.rhomilk - 1000.0) / max(rhopballon - 1000.0, EPS)) ** (1 / 3)
    return base * ((d.rhomilk - 1000.0) / max(d.rhopballoni - 1000.0, EPS)) ** (1 / 3)


def _material_factor(x: float, xe: float, material: str, d: _Derived) -> float:
    delta = x - xe

    if material == "SMP":
        if x >= 1:
            high_ts_factor = 0.05
        else:
            high_ts_factor = (
                1.0063
                - 1.5828 * delta
                + 3.3561 * delta**2
                - 9.389 * delta**3
                + 12.22 * delta**4
                - 5.5924 * delta**5
            )

        if delta > 1.362:
            low_ts_factor = -0.1617 * delta + 0.3768
        else:
            low_ts_factor = (
                1 - 1.305 * delta + 0.7097 * delta**2 - 0.1721 * delta**3 + 0.0151 * delta**4
            )
        if d.tsfeed <= 0.3:
            raw_factor = low_ts_factor
        elif d.tsfeed >= 0.5:
            raw_factor = high_ts_factor
        else:
            raw_factor = _interpolate_piecewise(0.3, low_ts_factor, 0.5, high_ts_factor, d.tsfeed)
    else:
        delta_non_negative = max(delta, 0.0)
        raw_factor = 1.335 - 0.3669 * exp(delta_non_negative**0.3011)

    factor = max(raw_factor, 0.0)

    if material == "SMP" and any(
        isclose(d.tsfeed, supported, rel_tol=0.0, abs_tol=1e-9) for supported in (0.2, 0.3)
    ):
        removable_moisture = max(d.x0 - xe, EPS)
        drying_progress = (d.x0 - x) / removable_moisture
        if drying_progress <= 0.05:
            return 0.0
        if drying_progress < 0.10:
            blend = (drying_progress - 0.05) / 0.05
            return factor * blend

    return factor


def _latent_heat_vaporization(temp_k: float) -> float:
    temp_c = temp_k - 273.15
    return max(2.501e6 - 2360.0 * temp_c, 1.9e6)


def _rea_snapshot(
    x: float,
    tp: float,
    tb: float,
    y: float,
    material: str,
    d: _Derived,
    *,
    air_to_solid_ratio: float,
    heat_loss_factor_w_kgk: float,
    transfer_scale: float = 1.0,
) -> dict[str, float]:
    rh = relative_humidity_from_abs_humidity(tb, y, d.p_pa)
    xe = max(gab_equilibrium_moisture(tb, y, d.p_pa) + d.equilibrium_moisture_offset, EPS)
    dp = max(_particle_diameter(x, xe, material, d), 20e-6)
    rho_particle = _mixture_density(x, d)
    area_per_kg_dry = 6.0 * (1.0 + max(x, 0.0)) / max(rho_particle * dp, EPS)

    pvsat_tb = saturation_vapor_pressure(tb)
    pvsat_tp = saturation_vapor_pressure(tp)
    rhovsat_tp = pvsat_tp / max(d.rw * tp, EPS)
    rhovsat_tb = pvsat_tb / max(d.rw * tb, EPS)
    rhovb = rh * rhovsat_tb

    evb = -d.gas_constant * tb * log(max(rh, EPS))
    mat_factor = _material_factor(x, xe, material, d)
    ev = mat_factor * evb
    psi = exp(-ev / max(d.gas_constant * tp, EPS))
    psi = min(max(psi, EPS), 1.0)
    rhovs = psi * rhovsat_tp

    rho_air = air_density(tb, y, d.p_pa, d.rs, d.rd)
    cp_air = d.cpdryair + max(y, 0.0) * d.cpv
    diffusivity = _water_vapor_diffusivity_air(tb)
    # In the reduced stationary kernel the velocity ODE is absent, so the
    # reference Re/Nu/Sh closure must use the mean particle flight velocity
    # from the residence-time closure instead of freezing the nozzle exit
    # velocity over the whole dryer.
    relative_velocity = max(abs(d.display_velocity_ms - d.air_superficial_velocity_ms), 0.05)
    reynolds = dp * relative_velocity * rho_air / max(d.air_dynamic_viscosity_kg_ms, EPS)
    prandtl = cp_air * d.air_dynamic_viscosity_kg_ms / max(d.kb, EPS)
    schmidt = d.air_dynamic_viscosity_kg_ms / max(diffusivity * rho_air, EPS)
    nusselt = 2.04 + 0.62 * reynolds**0.5 * prandtl ** (1.0 / 3.0)
    sherwood = 1.54 + 0.54 * reynolds**0.5 * schmidt ** (1.0 / 3.0)
    transfer_multiplier = transfer_scale * d.rea_transfer_scale
    alpha = transfer_multiplier * nusselt * d.kb / max(dp, EPS)
    hm = transfer_multiplier * (
        sherwood
        * diffusivity
        * d.molecular_weight_water_kg_kmol
        / max(dp * d.molecular_weight_dry_air_kg_kmol, EPS)
    )

    driving_force = max(rhovs - rhovb, 0.0) if x > xe else 0.0
    evap_rate_kg_per_kg_s = hm * area_per_kg_dry * driving_force

    cp_product = d.cps + max(x, 0.0) * d.cpw
    hv = _latent_heat_vaporization(tb)
    q_sorption_specific = 633000.0 if x <= 0.08 else 0.0
    q_conv_w = alpha * area_per_kg_dry * (tb - tp)
    q_latent_w = evap_rate_kg_per_kg_s * hv
    q_sorption_w = evap_rate_kg_per_kg_s * q_sorption_specific
    q_loss_total_w, q_loss_w = _specific_heat_loss_rate(tb, d, heat_loss_factor_w_kgk)
    d_tp_dt = (q_conv_w - q_latent_w - q_sorption_w) / max(cp_product, EPS)

    d_y_dt = evap_rate_kg_per_kg_s / max(air_to_solid_ratio, EPS)
    q_air_sensible_evap_w = evap_rate_kg_per_kg_s * d.cpv * (tb - tp)
    d_h_air_dt = (
        -cp_product * d_tp_dt / max(air_to_solid_ratio, EPS)
        - q_loss_w / max(air_to_solid_ratio, EPS)
    )
    d_tb_dt = (
        d_h_air_dt
        - d_y_dt * (hv + d.cpv * tb)
    ) / max(cp_air, EPS)

    return {
        "Xe": xe,
        "RH": rh,
        "dp": dp,
        "mat_factor": mat_factor,
        "psi": psi,
        "rhovb": rhovb,
        "rhovs": rhovs,
        "rho_air": rho_air,
        "Re": reynolds,
        "Pr": prandtl,
        "Sc": schmidt,
        "relative_velocity_ms": relative_velocity,
        "Nu": nusselt,
        "Sh": sherwood,
        "driving_force": driving_force,
        "evap_rate_kg_per_kg_s": evap_rate_kg_per_kg_s,
        "q_conv_w": q_conv_w,
        "q_latent_w": q_latent_w,
        "q_sorption_w": q_sorption_w,
        "q_loss_total_w": q_loss_total_w,
        "q_loss_w": q_loss_w,
        "dH_air_dt": d_h_air_dt,
        "q_air_sensible_evap_w": q_air_sensible_evap_w,
        "dXdt": -evap_rate_kg_per_kg_s,
        "dYdt": d_y_dt,
        "dTpdt_K_s": d_tp_dt,
        "dTbdt_K_s": d_tb_dt,
        "TadSat": adiabatic_saturation_temp(tb, y, d.p_pa),
    }


def _advance_stationary_state(
    state: np.ndarray,
    dt: float,
    *,
    material: str,
    d: _Derived,
) -> np.ndarray:
    substeps = max(1, int(np.ceil(dt / 0.0025)))
    sub_dt = dt / substeps
    current = state.astype(float, copy=True)

    for _ in range(substeps):
        x, tp, tb, y = current
        snap = _rea_snapshot(
            x,
            tp,
            tb,
            y,
            material,
            d,
            air_to_solid_ratio=d.air_to_solid_ratio,
            heat_loss_factor_w_kgk=d.heat_loss_factor_w_kgk,
        )
        dx = snap["dXdt"] * sub_dt
        min_dx = -(x - snap["Xe"])
        if dx < min_dx:
            scale = min_dx / min(dx, -EPS)
        else:
            scale = 1.0

        next_x = max(snap["Xe"], x + dx)
        next_tp = tp + snap["dTpdt_K_s"] * sub_dt * scale
        next_tb = tb + snap["dTbdt_K_s"] * sub_dt * scale
        next_y = y + snap["dYdt"] * sub_dt * scale
        next_tb = float(np.clip(next_tb, d.tu_k, d.tb0_k))
        next_tp = float(np.clip(next_tp, 273.15, next_tb))
        next_y = float(max(next_y, d.y0))
        current = np.array([next_x, next_tp, next_tb, next_y], dtype=float)

    return current


def _run_profile(inputs: SimulationInput, label: str, d: _Derived, warnings: list[str]) -> SimulationResult:
    t = np.linspace(0.0, inputs.simulation_end_s, inputs.time_points)
    state = np.array([d.x0, d.tp0_k, d.tb0_k, d.y0], dtype=float)
    rows: list[dict[str, float]] = []

    for index, current_time in enumerate(t):
        x, tp, tb, y = state
        snapshot = _rea_snapshot(
            x,
            tp,
            tb,
            y,
            inputs.material,
            d,
            air_to_solid_ratio=d.air_to_solid_ratio,
            heat_loss_factor_w_kgk=d.heat_loss_factor_w_kgk,
        )
        progress = current_time / max(d.effective_residence_time_s, EPS)
        rows.append(
            {
                "t": float(current_time),
                "height": float(progress * d.display_height_m),
                "progress": float(progress),
                "X": float(x),
                "Tp": float(tp),
                "Tb": float(tb),
                "Y": float(y),
                "RH": float(snapshot["RH"]),
                "vp": float(d.display_velocity_ms),
                "dp": float(snapshot["dp"]),
                "Xe": float(snapshot["Xe"]),
                "mat_factor": float(snapshot["mat_factor"]),
                "psi": float(snapshot["psi"]),
                "rhovb": float(snapshot["rhovb"]),
                "rhovs": float(snapshot["rhovs"]),
                "driving_force": float(snapshot["driving_force"]),
                "q_conv_w": float(snapshot["q_conv_w"]),
                "q_latent_w": float(snapshot["q_latent_w"]),
                "q_sorption_w": float(snapshot["q_sorption_w"]),
                "dTpdt_K_s": float(snapshot["dTpdt_K_s"]),
                "TadSat": float(snapshot["TadSat"]),
                "Tp_minus_TadSat": float(tp - snapshot["TadSat"]),
            }
        )
        if index + 1 < len(t):
            dt = float(t[index + 1] - current_time)
            state = _advance_stationary_state(
                state,
                dt,
                material=inputs.material,
                d=d,
            )

    series = pd.DataFrame(rows)

    drying_mask = series["X"] <= 0.04
    drying_time: float | None = None
    drying_height: float | None = None
    drying_progress: float | None = None
    if drying_mask.any():
        row = series.loc[drying_mask].iloc[0]
        drying_time = float(row["t"])
        drying_height = float(row["height"])
        drying_progress = float(row["progress"])
    else:
        warnings.append("Die Feuchteschwelle X <= 0.04 wurde innerhalb der Simulationszeit nicht erreicht.")

    outlet_mask = series["progress"] >= 1.0
    outlet_time: float | None = None
    outlet_x: float | None = None
    outlet_tb: float | None = None
    outlet_tp: float | None = None
    outlet_rh: float | None = None
    outlet_y: float | None = None
    if outlet_mask.any():
        row = series.loc[outlet_mask].iloc[0]
        outlet_time = float(row["t"])
        outlet_x = float(row["X"])
        outlet_tb = float(row["Tb"])
        outlet_tp = float(row["Tp"])
        outlet_rh = float(row["RH"])
        outlet_y = float(row["Y"])
    else:
        warnings.append("Die effektive Verweilzeit wurde innerhalb der Simulationszeit nicht erreicht.")

    tp_limit_mask = series["Tp"] > 373.15
    tp_limit_time: float | None = None
    tp_limit_height: float | None = None
    tp_limit_x: float | None = None
    tp_limit_tb: float | None = None
    tp_limit_rh: float | None = None
    tp_limit_xe: float | None = None
    if tp_limit_mask.any():
        row = series.loc[tp_limit_mask].iloc[0]
        tp_limit_time = float(row["t"])
        tp_limit_height = float(row["height"])
        tp_limit_x = float(row["X"])
        tp_limit_tb = float(row["Tb"])
        tp_limit_rh = float(row["RH"])
        tp_limit_xe = float(row["Xe"])

    metrics = {
        "drying_time": drying_time,
        "drying_height": drying_height,
        "drying_progress": drying_progress,
        "outlet_time": outlet_time,
        "outlet_X": outlet_x,
        "outlet_Tb": outlet_tb,
        "outlet_Tp": outlet_tp,
        "outlet_RH": outlet_rh,
        "outlet_Y": outlet_y,
        "max_Tp": float(series["Tp"].max()),
        "time_Tp_gt_100C": tp_limit_time,
        "height_Tp_gt_100C": tp_limit_height,
        "X_at_Tp_gt_100C": tp_limit_x,
        "Tb_at_Tp_gt_100C": tp_limit_tb,
        "RH_at_Tp_gt_100C": tp_limit_rh,
        "Xe_at_Tp_gt_100C": tp_limit_xe,
        "final_X": float(series["X"].iloc[-1]),
        "final_Tb": float(series["Tb"].iloc[-1]),
        "final_Tp": float(series["Tp"].iloc[-1]),
        "final_RH": float(series["RH"].iloc[-1]),
        "final_Y": float(series["Y"].iloc[-1]),
    }

    return SimulationResult(
        label=label,
        inputs=inputs,
        series=series,
        metrics=metrics,
        warnings=warnings,
        solver_status=0,
        solver_message="explicit profile integration",
    )


def run_simulation(inputs: SimulationInput, label: str = "Basis") -> SimulationResult:
    errors, warnings = inputs.validate()
    if errors:
        raise ValueError(" ".join(errors))

    derived = _build_derived(inputs)
    return _run_profile(inputs, label, derived, warnings)


def run_batch(inputs: list[SimulationInput], labels: list[str] | None = None) -> list[SimulationResult]:
    if labels is not None and len(labels) != len(inputs):
        raise ValueError("labels muss dieselbe Laenge wie inputs haben.")

    results: list[SimulationResult] = []
    for index, simulation_input in enumerate(inputs):
        label = labels[index] if labels else f"Szenario {index + 1}"
        results.append(run_simulation(simulation_input, label=label))
    return results


def results_to_metrics_frame(results: list[SimulationResult]) -> pd.DataFrame:
    return pd.DataFrame([result.metrics_record() for result in results])


def results_to_timeseries_frame(results: list[SimulationResult]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for result in results:
        frame = result.series.copy()
        frame.insert(0, "scenario", result.label)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def results_to_excel_bytes(results: list[SimulationResult]) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        results_to_metrics_frame(results).to_excel(writer, sheet_name="metrics", index=False)
        for result in results:
            sheet_name = result.label[:31] or "scenario"
            result.series.to_excel(writer, sheet_name=sheet_name, index=False)
    return buffer.getvalue()


def summarize_input(inputs: SimulationInput) -> dict[str, float]:
    derived = _build_derived(inputs)
    return {
        "initial_moisture_content": derived.x0,
        "dry_solids_rate_kg_s": derived.solids_rate_kg_s,
        "humid_air_mass_flow_kg_s": derived.humid_air_mass_flow_kg_s,
        "dry_air_mass_flow_kg_s": derived.dry_air_mass_flow_kg_s,
        "air_to_solid_ratio_kg_kg": derived.air_to_solid_ratio,
        "initial_air_density_kg_m3": air_density(
            derived.tb0_k,
            derived.y0,
            derived.p_pa,
            derived.rs,
            derived.rd,
        ),
        "effective_residence_time_s": derived.effective_residence_time_s,
        "display_height_m": derived.display_height_m,
        "display_velocity_ms": derived.display_velocity_ms,
    }
