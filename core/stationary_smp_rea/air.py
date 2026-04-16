from __future__ import annotations

from math import exp


EPS = 1e-12
T_REF_K = 273.15
R_DRY_AIR = 287.058
R_WATER_VAPOR = 461.523
CP_DRY_AIR = 1.0067e3
CP_WATER_VAPOR = 1.93e3
CP_LIQUID_WATER = 4.186e3
LAMBDA_REF_J_KG = 2.501e6
SUTHERLAND_C = 110.4
SUTHERLAND_MU0 = 1.716e-5
SUTHERLAND_T0 = 273.15


def saturation_vapor_pressure(temp_k: float) -> float:
    temp_c = temp_k - 273.15
    return 133.3 * exp(18.3036 - (3816.44 / max(temp_c + 229.02, EPS)))


def vapor_partial_pressure(humidity_ratio: float, pressure_pa: float) -> float:
    return pressure_pa * humidity_ratio / max(0.622 + humidity_ratio, EPS)


def humidity_ratio_from_vapor_pressure(vapor_pressure_pa: float, pressure_pa: float) -> float:
    return 0.622 * vapor_pressure_pa / max(pressure_pa - vapor_pressure_pa, EPS)


def relative_humidity(temp_k: float, humidity_ratio: float, pressure_pa: float) -> float:
    pv = vapor_partial_pressure(humidity_ratio, pressure_pa)
    psat = saturation_vapor_pressure(temp_k)
    return min(max(pv / max(psat, EPS), EPS), 0.999999)


def humid_air_enthalpy(temp_k: float, humidity_ratio: float) -> float:
    delta_t = temp_k - T_REF_K
    return CP_DRY_AIR * delta_t + humidity_ratio * (
        LAMBDA_REF_J_KG + CP_WATER_VAPOR * delta_t
    )


def invert_humid_air_enthalpy(enthalpy_j_kg_da: float, humidity_ratio: float) -> float:
    denominator = CP_DRY_AIR + humidity_ratio * CP_WATER_VAPOR
    return T_REF_K + (enthalpy_j_kg_da - humidity_ratio * LAMBDA_REF_J_KG) / max(
        denominator,
        EPS,
    )


def moist_air_density(temp_k: float, humidity_ratio: float, pressure_pa: float) -> float:
    pv = vapor_partial_pressure(humidity_ratio, pressure_pa)
    p_da = max(pressure_pa - pv, EPS)
    return p_da / max(R_DRY_AIR * temp_k, EPS) + pv / max(R_WATER_VAPOR * temp_k, EPS)


def water_vapor_density(temp_k: float, humidity_ratio: float, pressure_pa: float) -> float:
    pv = vapor_partial_pressure(humidity_ratio, pressure_pa)
    return pv / max(R_WATER_VAPOR * temp_k, EPS)


def saturated_vapor_density(temp_k: float) -> float:
    return saturation_vapor_pressure(temp_k) / max(R_WATER_VAPOR * temp_k, EPS)


def humid_air_mass_flow(dry_air_mass_flow_kg_s: float, humidity_ratio: float) -> float:
    return dry_air_mass_flow_kg_s * (1.0 + humidity_ratio)


def air_superficial_velocity(
    temp_k: float,
    humidity_ratio: float,
    pressure_pa: float,
    dry_air_mass_flow_kg_s: float,
    chamber_area_m2: float,
) -> float:
    rho = moist_air_density(temp_k, humidity_ratio, pressure_pa)
    return humid_air_mass_flow(dry_air_mass_flow_kg_s, humidity_ratio) / max(
        rho * chamber_area_m2,
        EPS,
    )


def water_vapor_diffusivity(temp_k: float, pressure_pa: float) -> float:
    return 1.17564e-9 * temp_k**1.75 * (101325.0 / pressure_pa)


def dynamic_viscosity_air(temp_k: float) -> float:
    return SUTHERLAND_MU0 * (temp_k / SUTHERLAND_T0) ** 1.5 * (
        (SUTHERLAND_T0 + SUTHERLAND_C) / (temp_k + SUTHERLAND_C)
    )


def thermal_conductivity_air(temp_k: float) -> float:
    # The planning docs fix the balance structure but not a dedicated k_a correlation.
    # This mild temperature law keeps Pr/Nu responsive without importing legacy logic.
    return 0.0241 * (temp_k / 273.15) ** 0.9


def latent_heat_evaporation(temp_k: float) -> float:
    value = 2.792e6 - 160.0 * temp_k - 3.43 * temp_k**2
    return max(value, 1.0e5)
