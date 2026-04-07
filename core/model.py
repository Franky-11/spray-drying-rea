from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from io import BytesIO
from math import exp, isclose, log, pi, sqrt
from typing import Any

import numpy as np
import pandas as pd
from scipy.integrate import solve_ivp


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

    def validate(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warnings: list[str] = []

        positive_fields = {
            "dryer_height_m": self.dryer_height_m,
            "droplet_size_um": self.droplet_size_um,
            "feed_rate_kg_h": self.feed_rate_kg_h,
            "air_flow_m3_h": self.air_flow_m3_h,
            "dryer_diameter_m": self.dryer_diameter_m,
            "heat_loss_coeff_w_m2k": self.heat_loss_coeff_w_m2k,
            "initial_droplet_velocity_ms": self.initial_droplet_velocity_ms,
            "simulation_end_s": self.simulation_end_s,
        }
        for name, value in positive_fields.items():
            if value <= 0:
                errors.append(f"{name} muss groesser als 0 sein.")

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
            supported_exact = any(
                isclose(self.feed_total_solids, supported, rel_tol=0.0, abs_tol=1e-9)
                for supported in (0.2, 0.3, 0.5)
            )
            supported_balloon = self.feed_total_solids < 0.2
            if not (supported_exact or supported_balloon):
                errors.append(
                    "SMP unterstuetzt nur TS < 0.2 sowie die diskreten TS-Werte 0.2, 0.3 und 0.5."
                )
        if self.material == "WPC" and not isclose(
            self.feed_total_solids, 0.3, rel_tol=0.0, abs_tol=1e-9
        ):
            errors.append("WPC ist in diesem Modell nur fuer TS = 0.3 validiert.")

        if not 120 <= self.inlet_air_temp_c <= 220:
            warnings.append(
                "Die Zulufttemperatur liegt ausserhalb des im Skript typischen Bereichs von etwa 120-220 degC."
            )
        if not 50 <= self.droplet_size_um <= 150:
            warnings.append(
                "Die Tropfengroesse liegt ausserhalb des im Skript typischen Bereichs von etwa 50-150 um."
            )
        if self.feed_total_solids < 0.2:
            warnings.append(
                "TS < 0.2 nutzt das Ballon-Shrinkage-Modell und ist empfindlicher gegen Randbedingungen."
            )

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
    hmax: float
    tb0_k: float
    tp0_k: float
    tu_k: float
    dpi_m: float
    mf_kg_s: float
    y0: float
    vluft_m3_h: float
    tsfeed: float
    x0: float
    xi: float
    ddryer_m: float
    udryer: float
    adryer: float
    aodryer: float
    p_pa: float
    rs: float
    rd: float
    kb: float
    viskair: float
    cpdryair: float
    cpv: float
    ma: float
    dm: float
    gas_constant: float
    cpw: float
    rhos: float
    rhow: float
    mw: float
    rw: float
    rhomilk: float
    ms: float
    np_droplets: float
    vb: float
    g_air_kg_s: float
    vp0: float
    xcrit: float
    rhopballoni: float
    prot: float
    lac: float
    fett: float
    asche: float
    cps: float
    up: float
    constant_air: bool


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
    rh = (total_pressure_pa / pvsat) * (abs_humidity / (0.622 + abs_humidity))
    return max(rh, EPS)


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
    return total_pressure_pa / (rf * temp_k)


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


def _build_derived(inputs: SimulationInput) -> _Derived:
    rs = 287.058
    rd = 461.523
    p_pa = 101000.0
    tb0_k = inputs.inlet_air_temp_c + 273.0
    tp0_k = inputs.feed_temp_c + 273.0
    tu_k = inputs.ambient_temp_c + 273.0
    dpi_m = inputs.droplet_size_um / 1_000_000.0
    mf_kg_s = inputs.feed_rate_kg_h / 3600.0
    y0 = inputs.inlet_abs_humidity_g_kg / 1000.0
    ddryer_m = inputs.dryer_diameter_m
    adryer = (pi / 4.0) * ddryer_m**2
    x0 = (1.0 - inputs.feed_total_solids) / inputs.feed_total_solids
    rhomilk = inputs.solid_density_kg_m3 * (
        (1 + x0) / (1 + (inputs.solid_density_kg_m3 / inputs.water_density_kg_m3) * x0)
    )
    vp0 = (pi / 6.0) * dpi_m**3
    ms = vp0 * rhomilk * inputs.feed_total_solids
    rhoair = air_density(tb0_k, y0, p_pa, rs, rd)
    g_air_kg_s = (rhoair * inputs.air_flow_m3_h) / 3600.0
    vb = (inputs.air_flow_m3_h / 3600.0) / adryer
    udryer = pi * ddryer_m
    aodryer = inputs.dryer_height_m * pi * ddryer_m
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
    return _Derived(
        hmax=inputs.dryer_height_m,
        tb0_k=tb0_k,
        tp0_k=tp0_k,
        tu_k=tu_k,
        dpi_m=dpi_m,
        mf_kg_s=mf_kg_s,
        y0=y0,
        vluft_m3_h=inputs.air_flow_m3_h,
        tsfeed=inputs.feed_total_solids,
        x0=x0,
        xi=x0,
        ddryer_m=ddryer_m,
        udryer=udryer,
        adryer=adryer,
        aodryer=aodryer,
        p_pa=p_pa,
        rs=rs,
        rd=rd,
        kb=0.0262,
        viskair=18.2 / 1_000_000.0,
        cpdryair=1.0067 * 1000.0,
        cpv=1.93 * 1000.0,
        ma=29.0,
        dm=2.20e-05,
        gas_constant=8.314,
        cpw=4.186 * 1000.0,
        rhos=inputs.solid_density_kg_m3,
        rhow=inputs.water_density_kg_m3,
        mw=18.0,
        rw=461.52,
        rhomilk=rhomilk,
        ms=ms,
        np_droplets=(mf_kg_s / rhomilk) / vp0,
        vb=vb,
        g_air_kg_s=g_air_kg_s,
        vp0=inputs.initial_droplet_velocity_ms,
        xcrit=inputs.xcrit,
        rhopballoni=rhopballoni,
        prot=inputs.protein_fraction,
        lac=inputs.lactose_fraction,
        fett=inputs.fat_fraction,
        asche=asche,
        cps=cps,
        up=inputs.heat_loss_coeff_w_m2k,
        constant_air=inputs.constant_drying_air,
    )


def _particle_diameter(x: float, xe: float, material: str, d: _Derived) -> float:
    base = d.dpi_m
    denom = max(d.xi - xe, EPS)
    delta = (x - xe) / denom

    if d.tsfeed >= 0.2:
        if material == "SMP":
            if isclose(d.tsfeed, 0.3, rel_tol=0.0, abs_tol=1e-9):
                return base * (0.76 + (1 - 0.76) * delta)
            if isclose(d.tsfeed, 0.2, rel_tol=0.0, abs_tol=1e-9):
                return base * (0.67 + (1 - 0.67) * delta)
            if isclose(d.tsfeed, 0.5, rel_tol=0.0, abs_tol=1e-9):
                return base * (0.0447 * (x - xe) + 0.959)
        if material == "WPC":
            return base * (0.873 + (1 - 0.873) * delta)
        raise ValueError("Ungueltige Material-/TS-Kombination fuer das Schrumpfungsmodell.")

    rhopballon = d.rhos * ((1 + x) / (1 + (d.rhos / d.rhow) * x))
    if x >= d.xcrit:
        return base * ((d.rhomilk - 1000.0) / max(rhopballon - 1000.0, EPS)) ** (1 / 3)
    return base * ((d.rhomilk - 1000.0) / max(d.rhopballoni - 1000.0, EPS)) ** (1 / 3)


def _material_factor(x: float, xe: float, material: str, d: _Derived) -> float:
    delta = x - xe

    if material == "SMP":
        if isclose(d.tsfeed, 0.5, rel_tol=0.0, abs_tol=1e-9):
            if x >= 1:
                raw_factor = 0.05
            else:
                raw_factor = (
                    1.0063
                    - 1.5828 * delta
                    + 3.3561 * delta**2
                    - 9.389 * delta**3
                    + 12.22 * delta**4
                    - 5.5924 * delta**5
                )
        elif delta > 1.362:
            raw_factor = -0.1617 * delta + 0.3768
        else:
            raw_factor = (
                1 - 1.305 * delta + 0.7097 * delta**2 - 0.1721 * delta**3 + 0.0151 * delta**4
            )
    else:
        delta_non_negative = max(delta, 0.0)
        raw_factor = 1.335 - 0.3669 * exp(delta_non_negative**0.3011)

    # Ev/Evb must not become negative; otherwise psi > 1 and the surface vapor density
    # exceeds saturation, which is not physically admissible in this REA closure.
    factor = max(raw_factor, 0.0)

    if material == "SMP" and any(
        isclose(d.tsfeed, supported, rel_tol=0.0, abs_tol=1e-9) for supported in (0.2, 0.3)
    ):
        # Chen (2008) notes that skim milk droplets with 20-30 % TS may exhibit a very short
        # initial period with water-like surface activity. We model this as a smooth blend from
        # a pure-water surface (Ev/Evb = 0) into the literature REA correlation after 5-10 %
        # of the removable moisture has been depleted.
        removable_moisture = max(d.x0 - xe, EPS)
        drying_progress = (d.x0 - x) / removable_moisture
        if drying_progress <= 0.05:
            return 0.0
        if drying_progress < 0.10:
            blend = (drying_progress - 0.05) / 0.05
            return factor * blend

    return factor


def _ode_rhs(material: str, d: _Derived):
    def rhs(_: float, state: np.ndarray) -> np.ndarray:
        x, tp, tb, y, height, vp, rhopcrit = state

        pvsat_tb = saturation_vapor_pressure(tb)
        rh = relative_humidity_from_abs_humidity(tb, y, d.p_pa)
        c_const = 0.001645 * exp(24831 / (tb * 8.314))
        k_const = 5.710 * exp(-5118 / (tb * 8.314))
        rhopballon = d.rhos * ((1 + x) / (1 + (d.rhos / d.rhow) * x))
        xe = (c_const * k_const * 0.06156 * rh) / max(
            (1 - k_const * rh) * (1 - (k_const * rh) + (c_const * k_const * rh)),
            EPS,
        )

        dp = _particle_diameter(x, xe, material, d)
        ap = pi * dp**2
        mp = x * d.ms + d.ms
        mw = mp - d.ms
        rf = humid_air_gas_constant(tb, y, d.p_pa, d.rs, d.rd)
        rhoair = d.p_pa / (rf * tb)

        cp = (
            ((d.ms * d.prot) / mp) * 1600.0
            + ((d.ms * d.lac) / mp) * 1400.0
            + ((d.ms * d.fett) / mp) * 1700.0
            + ((d.ms * d.asche) / mp) * 800.0
            + (mw / mp) * 4180.0
        )

        height_rate = vp
        ur = sqrt((vp - d.vb) ** 2)
        re = max((dp * ur * rhoair) / d.viskair, EPS)

        cpair = d.cpdryair + d.cpv * y
        pr = (cpair * d.viskair) / d.kb
        sc = d.viskair / max(d.dm * rhoair, EPS)
        nu = 2.04 + 0.62 * re ** 0.5 * pr ** (1 / 3)
        sh = 1.54 + 0.54 * re ** 0.5 * sc ** (1 / 3)
        dwm = (rhoair * d.dm) / d.ma

        alpha = (nu * d.kb) / dp
        hm = (sh * dwm * d.mw) / (dp * rhoair)

        pvsat_tp = saturation_vapor_pressure(tp)
        rhovsat_tp = pvsat_tp / (d.rw * tp)
        rhovsat_tb = pvsat_tb / (d.rw * tb)
        rhovb = rh * rhovsat_tb

        evb = -d.gas_constant * tb * log(max(rhovb / max(rhovsat_tb, EPS), EPS))
        matfkt = _material_factor(x, xe, material, d)
        ev = matfkt * evb
        psi = exp(-ev / (d.gas_constant * tp))
        rhovs = psi * rhovsat_tp

        hv = 2.792e6 - 160 * tb - 3.43 * tb**2
        qstn = 633000.0 if x <= 0.08 else 0.0

        driv_force = rhovs - rhovb if x > xe else 0.0
        dmpdt = -hm * ap * driv_force
        dxdt = dmpdt / d.ms
        dtpdt = (alpha * ap * (tb - tp) + (hv + qstn) * dxdt * d.ms) / (mp * cp)

        if height <= d.hmax:
            qloss = (d.aodryer / d.hmax) * d.up * (tb - d.tu_k) * vp
        else:
            qloss = 0.0

        if d.constant_air:
            dydt = 0.0
            dtbdt = 0.0
            drhopcritdt = 0.0
            dvpdt = 0.0
        else:
            dydt = -(d.np_droplets * d.ms * dxdt) / d.g_air_kg_s
            denthalpy_dt = (d.ms * (d.cps + x * d.cpw) * dtpdt * d.np_droplets + qloss) * (
                -1.0 / d.g_air_kg_s
            )
            if x >= 0.08 or x < xe:
                dtbdt = (denthalpy_dt - dydt * (hv + d.cpv * tb)) / cpair
            else:
                dtbdt = (denthalpy_dt - dydt * ((hv + qstn) + d.cpv * tb)) / cpair

            cd = (24.0 / re) * (1 + 0.15 * re**0.687)
            if x >= d.xcrit:
                dvpdt = (1 - (rhoair / rhopballon)) * 9.81 - 0.75 * (
                    (rhoair * cd * ur * (vp - d.vb)) / (rhopballon * dp)
                )
                drhopcritdt = 0.0
            else:
                drhopcritdt = (6.0 * dmpdt) / (dp * ap)
                dvpdt = (1 - (rhoair / rhopcrit)) * 9.81 - 0.75 * (
                    (rhoair * cd * ur * (vp - d.vb)) / (rhopcrit * dp)
                )

        return np.array([dxdt, dtpdt, dtbdt, dydt, height_rate, dvpdt, drhopcritdt], dtype=float)

    return rhs


def _diagnostic_snapshot(
    x: float,
    tp: float,
    tb: float,
    y: float,
    vp: float,
    xe: float,
    material: str,
    d: _Derived,
) -> dict[str, float]:
    pvsat_tb = saturation_vapor_pressure(tb)
    rh = relative_humidity_from_abs_humidity(tb, y, d.p_pa)
    dp = _particle_diameter(x, xe, material, d)
    ap = pi * dp**2
    mp = x * d.ms + d.ms
    mw = mp - d.ms
    rf = humid_air_gas_constant(tb, y, d.p_pa, d.rs, d.rd)
    rhoair = d.p_pa / (rf * tb)

    cp = (
        ((d.ms * d.prot) / mp) * 1600.0
        + ((d.ms * d.lac) / mp) * 1400.0
        + ((d.ms * d.fett) / mp) * 1700.0
        + ((d.ms * d.asche) / mp) * 800.0
        + (mw / mp) * 4180.0
    )

    ur = sqrt((vp - d.vb) ** 2)
    re = max((dp * ur * rhoair) / d.viskair, EPS)
    cpair = d.cpdryair + d.cpv * y
    pr = (cpair * d.viskair) / d.kb
    sc = d.viskair / max(d.dm * rhoair, EPS)
    nu = 2.04 + 0.62 * re ** 0.5 * pr ** (1 / 3)
    sh = 1.54 + 0.54 * re ** 0.5 * sc ** (1 / 3)
    dwm = (rhoair * d.dm) / d.ma

    alpha = (nu * d.kb) / dp
    hm = (sh * dwm * d.mw) / (dp * rhoair)

    pvsat_tp = saturation_vapor_pressure(tp)
    rhovsat_tp = pvsat_tp / (d.rw * tp)
    rhovsat_tb = pvsat_tb / (d.rw * tb)
    rhovb = rh * rhovsat_tb

    evb = -d.gas_constant * tb * log(max(rhovb / max(rhovsat_tb, EPS), EPS))
    matfkt = _material_factor(x, xe, material, d)
    ev = matfkt * evb
    psi = exp(-ev / (d.gas_constant * tp))
    rhovs = psi * rhovsat_tp

    hv = 2.792e6 - 160 * tb - 3.43 * tb**2
    qstn = 633000.0 if x <= 0.08 else 0.0
    driv_force = rhovs - rhovb if x > xe else 0.0
    dmpdt = -hm * ap * driv_force
    dxdt = dmpdt / d.ms

    q_conv = alpha * ap * (tb - tp)
    q_latent = hv * dxdt * d.ms
    q_sorption = qstn * dxdt * d.ms
    dtpdt = (q_conv + q_latent + q_sorption) / (mp * cp)
    tadsat = adiabatic_saturation_temp(tb, y, d.p_pa)

    return {
        "mat_factor": matfkt,
        "psi": psi,
        "rhovb": rhovb,
        "rhovs": rhovs,
        "driving_force": driv_force,
        "q_conv_w": q_conv,
        "q_latent_w": q_latent,
        "q_sorption_w": q_sorption,
        "dTpdt_K_s": dtpdt,
        "TadSat": tadsat,
        "Tp_minus_TadSat": tp - tadsat,
    }


def _post_process(solution: Any, inputs: SimulationInput, label: str, d: _Derived, warnings: list[str]) -> SimulationResult:
    t = solution.t
    states = solution.y.T
    x = states[:, 0]
    tp = states[:, 1]
    tb = states[:, 2]
    y = states[:, 3]
    height = states[:, 4]
    vp = states[:, 5]

    rh_values: list[float] = []
    xe_values: list[float] = []
    dp_values: list[float] = []
    diag_rows: list[dict[str, float]] = []
    for x_i, tb_i, y_i in zip(x, tb, y):
        rh_i = relative_humidity_from_abs_humidity(tb_i, y_i, d.p_pa)
        xe_i = gab_equilibrium_moisture(tb_i, y_i, d.p_pa)
        dp_i = _particle_diameter(x_i, xe_i, inputs.material, d)
        rh_values.append(rh_i)
        xe_values.append(xe_i)
        dp_values.append(dp_i)
    for x_i, tp_i, tb_i, y_i, vp_i, xe_i in zip(x, tp, tb, y, vp, xe_values):
        diag_rows.append(_diagnostic_snapshot(x_i, tp_i, tb_i, y_i, vp_i, xe_i, inputs.material, d))

    series = pd.DataFrame(
        {
            "t": t,
            "height": height,
            "X": x,
            "Tp": tp,
            "Tb": tb,
            "Y": y,
            "RH": rh_values,
            "vp": vp,
            "dp": dp_values,
            "Xe": xe_values,
            "mat_factor": [row["mat_factor"] for row in diag_rows],
            "psi": [row["psi"] for row in diag_rows],
            "rhovb": [row["rhovb"] for row in diag_rows],
            "rhovs": [row["rhovs"] for row in diag_rows],
            "driving_force": [row["driving_force"] for row in diag_rows],
            "q_conv_w": [row["q_conv_w"] for row in diag_rows],
            "q_latent_w": [row["q_latent_w"] for row in diag_rows],
            "q_sorption_w": [row["q_sorption_w"] for row in diag_rows],
            "dTpdt_K_s": [row["dTpdt_K_s"] for row in diag_rows],
            "TadSat": [row["TadSat"] for row in diag_rows],
            "Tp_minus_TadSat": [row["Tp_minus_TadSat"] for row in diag_rows],
        }
    )

    drying_mask = series["X"] <= 0.04
    drying_time: float | None = None
    drying_height: float | None = None
    if drying_mask.any():
        row = series.loc[drying_mask].iloc[0]
        drying_time = float(row["t"])
        drying_height = float(row["height"])
    else:
        warnings.append("Die Feuchteschwelle X <= 0.04 wurde innerhalb der Simulationszeit nicht erreicht.")

    outlet_mask = series["height"] >= inputs.dryer_height_m
    outlet_time: float | None = None
    outlet_x: float | None = None
    outlet_tb: float | None = None
    outlet_tp: float | None = None
    outlet_rh: float | None = None
    if outlet_mask.any():
        row = series.loc[outlet_mask].iloc[0]
        outlet_time = float(row["t"])
        outlet_x = float(row["X"])
        outlet_tb = float(row["Tb"])
        outlet_tp = float(row["Tp"])
        outlet_rh = float(row["RH"])
    else:
        warnings.append("Die Partikelhoehe Hmax wurde innerhalb der Simulationszeit nicht erreicht.")

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
        "outlet_time": outlet_time,
        "outlet_X": outlet_x,
        "outlet_Tb": outlet_tb,
        "outlet_Tp": outlet_tp,
        "outlet_RH": outlet_rh,
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
    }

    return SimulationResult(
        label=label,
        inputs=inputs,
        series=series,
        metrics=metrics,
        warnings=warnings,
        solver_status=int(solution.status),
        solver_message=str(solution.message),
    )


def run_simulation(inputs: SimulationInput, label: str = "Basis") -> SimulationResult:
    errors, warnings = inputs.validate()
    if errors:
        raise ValueError(" ".join(errors))

    derived = _build_derived(inputs)
    initial_state = np.array(
        [
            derived.x0,
            derived.tp0_k,
            derived.tb0_k,
            derived.y0,
            0.0,
            derived.vp0,
            derived.rhopballoni,
        ],
        dtype=float,
    )
    t_eval = np.linspace(0.0, inputs.simulation_end_s, inputs.time_points)
    solution = solve_ivp(
        _ode_rhs(inputs.material, derived),
        (0.0, inputs.simulation_end_s),
        initial_state,
        method="BDF",
        t_eval=t_eval,
        rtol=1e-6,
        atol=1e-8,
    )
    if not solution.success:
        warnings.append(f"Solver-Warnung: {solution.message}")
    return _post_process(solution, inputs, label, derived, warnings)


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
    droplet_volume = (pi / 6.0) * derived.dpi_m**3
    droplet_surface = pi * derived.dpi_m**2
    return {
        "initial_moisture_content": derived.x0,
        "dryer_cross_section_m2": derived.adryer,
        "dryer_surface_m2": derived.aodryer,
        "air_superficial_velocity_ms": derived.vb,
        "humid_air_mass_flow_kg_s": derived.g_air_kg_s,
        "initial_air_density_kg_m3": air_density(
            derived.tb0_k,
            derived.y0,
            derived.p_pa,
            derived.rs,
            derived.rd,
        ),
        "droplet_volume_m3": droplet_volume,
        "droplet_surface_m2": droplet_surface,
        "solid_mass_per_droplet_kg": derived.ms,
        "droplets_per_s": derived.np_droplets,
        "air_residence_time_s": derived.hmax / max(derived.vb, EPS),
    }
