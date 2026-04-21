from __future__ import annotations

from dataclasses import dataclass
from math import exp, log


EPS = 1e-12
R_GAS = 8.314
POLY_COEFFS = (1.0, -1.305, 0.7097, -0.1721, 0.0151)
EARLY_FALLING_RATE_ADD_GAIN = 1.29
EARLY_FALLING_RATE_WINDOW_CENTER = 0.12
EARLY_FALLING_RATE_WINDOW_WIDTH = 0.025
HIGH_SOLIDS_BLEND_START = 0.43
HIGH_SOLIDS_BLEND_END = 0.50
LEGACY_REA_50_DELTA_LIMIT = 1.0
FU_REA_50_CUBIC = {"a": -1.485, "b": 2.728, "c": -2.186}
FU_SHRINKAGE_50_TEMP_LOW_C = 70.0
FU_SHRINKAGE_50_TEMP_HIGH_C = 90.0
LINEAR_ANCHORS = {
    0.30: {"slope": 0.1617, "critical_delta": 1.362, "critical_ratio": 0.172},
    0.37: {"slope": 0.3595, "critical_delta": 0.969, "critical_ratio": 0.265},
    0.40: {"slope": 0.4779, "critical_delta": 0.788, "critical_ratio": 0.337},
    0.43: {"slope": 0.5927, "critical_delta": 0.640, "critical_ratio": 0.408},
}
SHRINKAGE_ANCHORS = {
    0.37: {"intercept": 0.8021, "slope": 0.1214},
    0.40: {"intercept": 0.8506, "slope": 0.0956},
    0.43: {"intercept": 0.87, "slope": 0.0933},
}
LOW_SOLIDS_LINEAR = {"slope": 0.1617, "critical_delta": 1.362, "critical_ratio": 0.172}
LEGACY_SHRINKAGE_20 = 0.67
LEGACY_SHRINKAGE_30 = 0.76


@dataclass(frozen=True)
class ChewMaterialState:
    delta: float
    x_b: float
    initial_moisture_dry_basis: float
    linear_slope: float
    linear_intercept: float
    critical_delta: float
    critical_ratio: float
    normalized_delta: float
    activation_ratio_base: float
    activation_ratio_add: float
    activation_ratio: float
    delta_e_max_j_mol: float
    delta_e_j_mol: float
    psi: float
    shrinkage_ratio: float
    shrinkage_mode: str


def chew_validity_warnings(feed_total_solids: float) -> list[str]:
    warnings: list[str] = []
    if not 0.20 <= feed_total_solids <= 0.50:
        warnings.append(
            "The current SMP core is enabled for 20-50 wt%; Chew Table 3 itself is directly anchored only for 30-43 wt%, while 43-50 wt% blends toward the legacy 50-wt% SMP branch."
        )
    if feed_total_solids < 0.37:
        warnings.append(
            "Chew shrinkage is directly anchored only for 37-43 wt%."
        )
    if feed_total_solids > HIGH_SOLIDS_BLEND_START:
        warnings.append(
            "Above 43 wt%, SMP REA smoothly blends the active high-solids law toward the Fu et al. 50-wt% function, and shrinkage blends from the 43-wt% anchor onto the temperature-dependent 50-wt% endpoint."
        )
    return warnings


def _piecewise_linear_interpolate(value: float, anchors: dict[float, dict[str, float]]) -> dict[str, float]:
    sorted_keys = sorted(anchors)
    if value <= sorted_keys[0]:
        return anchors[sorted_keys[0]].copy()
    if value >= sorted_keys[-1]:
        return anchors[sorted_keys[-1]].copy()
    for lower, upper in zip(sorted_keys[:-1], sorted_keys[1:], strict=True):
        if lower <= value <= upper:
            blend = (value - lower) / max(upper - lower, EPS)
            return {
                key: anchors[lower][key] + blend * (anchors[upper][key] - anchors[lower][key])
                for key in anchors[lower]
            }
    return anchors[sorted_keys[-1]].copy()


def initial_moisture_dry_basis(feed_total_solids: float) -> float:
    return (1.0 - feed_total_solids) / feed_total_solids


def _common_polynomial(delta: float) -> float:
    bounded_delta = max(delta, 0.0)
    return (
        POLY_COEFFS[0]
        + POLY_COEFFS[1] * bounded_delta
        + POLY_COEFFS[2] * bounded_delta**2
        + POLY_COEFFS[3] * bounded_delta**3
        + POLY_COEFFS[4] * bounded_delta**4
    )


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exp_term = exp(-value)
        return 1.0 / (1.0 + exp_term)
    exp_term = exp(value)
    return exp_term / (1.0 + exp_term)


def _lerp(lower: float, upper: float, blend: float) -> float:
    bounded_blend = min(max(blend, 0.0), 1.0)
    return lower + bounded_blend * (upper - lower)


def _smoothstep(value: float, start: float, end: float) -> float:
    if value <= start:
        return 0.0
    if value >= end:
        return 1.0
    blend = (value - start) / max(end - start, EPS)
    return blend * blend * (3.0 - 2.0 * blend)


def linear_parameters_from_initial_moisture(
    initial_moisture_dry_basis_value: float,
) -> tuple[float, float, float, float]:
    bounded_initial_moisture = max(initial_moisture_dry_basis_value, EPS)
    slope = exp(1.202 - 1.299 * bounded_initial_moisture)
    intercept = exp(0.3192 - 0.3628 * bounded_initial_moisture**1.5)
    critical_delta = exp(0.8799 - 2.035 / max(bounded_initial_moisture**1.5, EPS))
    critical_ratio = exp(-2.252 + 5.131 * exp(-bounded_initial_moisture))
    return slope, intercept, critical_delta, critical_ratio


def low_solids_activation_parameters() -> tuple[float, float, float, float]:
    slope = LOW_SOLIDS_LINEAR["slope"]
    critical_delta = LOW_SOLIDS_LINEAR["critical_delta"]
    critical_ratio = LOW_SOLIDS_LINEAR["critical_ratio"]
    intercept = critical_ratio + slope * critical_delta
    return slope, intercept, critical_delta, critical_ratio


def table2_anchor_parameters(feed_total_solids: float) -> tuple[float, float, float, float]:
    params = _piecewise_linear_interpolate(feed_total_solids, LINEAR_ANCHORS)
    slope = params["slope"]
    critical_delta = params["critical_delta"]
    critical_ratio = params["critical_ratio"]
    intercept = critical_ratio + slope * critical_delta
    return slope, intercept, critical_delta, critical_ratio


def _continuous_activation_ratio(
    delta: float,
    feed_total_solids: float,
) -> tuple[float, float, float, float, float]:
    if feed_total_solids < 0.30:
        slope, intercept, critical_delta, critical_ratio = low_solids_activation_parameters()
    else:
        initial_moisture = initial_moisture_dry_basis(feed_total_solids)
        slope, intercept, critical_delta, critical_ratio = linear_parameters_from_initial_moisture(
            initial_moisture
        )
    bounded_delta = max(delta, 0.0)
    if bounded_delta >= critical_delta:
        ratio = -slope * bounded_delta + intercept
    else:
        ratio = _common_polynomial(bounded_delta)
    return (
        min(max(ratio, 0.0), 1.0),
        slope,
        intercept,
        critical_delta,
        critical_ratio,
    )


def fu_50_activation_ratio(
    delta: float,
) -> float:
    # Fu et al. (2012) report a dedicated 50-wt% REA cubic in delta = X - x_b.
    # It stays positive up to delta = 1.0 and turns negative beyond that, so
    # the active kernel saturates the delta input at that last positive boundary.
    bounded_delta = min(max(delta, 0.0), LEGACY_REA_50_DELTA_LIMIT)
    ratio = (
        FU_REA_50_CUBIC["a"] * bounded_delta**3
        + FU_REA_50_CUBIC["b"] * bounded_delta**2
        + FU_REA_50_CUBIC["c"] * bounded_delta
        + 1.0
    )
    return min(max(ratio, 0.0), 1.0)


def activation_ratio(
    delta: float,
    feed_total_solids: float,
) -> tuple[float, float, float, float, float]:
    ratio, slope, intercept, critical_delta, critical_ratio = _continuous_activation_ratio(
        delta,
        feed_total_solids,
    )
    if feed_total_solids <= HIGH_SOLIDS_BLEND_START:
        return ratio, slope, intercept, critical_delta, critical_ratio

    fu_ratio = fu_50_activation_ratio(
        delta,
    )
    # Above 43 wt%, keep the active continuous Chew-based branch as the lower
    # endpoint and blend it smoothly onto the Fu et al. 50-wt% REA function.
    blend = _smoothstep(feed_total_solids, HIGH_SOLIDS_BLEND_START, HIGH_SOLIDS_BLEND_END)
    blended_ratio = _lerp(ratio, fu_ratio, blend)
    return (
        min(max(blended_ratio, 0.0), 1.0),
        slope,
        intercept,
        critical_delta,
        critical_ratio,
    )


def _early_falling_rate_activation_ratio_add(
    delta: float,
    x_b: float,
    initial_moisture_dry_basis_value: float,
) -> tuple[float, float]:
    bounded_delta = max(delta, 0.0)
    moisture_span = max(initial_moisture_dry_basis_value - x_b, EPS)
    normalized_delta = min(max(bounded_delta / moisture_span, 0.0), 1.0)
    # Switch on a material-side REA penalty only after the early falling-rate
    # regime is entered; the linear delta factor makes it fade back out near x_b.
    early_falling_rate_window = _sigmoid(
        (EARLY_FALLING_RATE_WINDOW_CENTER - normalized_delta)
        / EARLY_FALLING_RATE_WINDOW_WIDTH
    )
    activation_ratio_add = (
        EARLY_FALLING_RATE_ADD_GAIN
        * bounded_delta
        * early_falling_rate_window
    )
    return min(max(activation_ratio_add, 0.0), 1.0), normalized_delta


def _anchored_high_solids_shrinkage_ratio(delta: float, feed_total_solids: float) -> float:
    bounded_total_solids = min(max(feed_total_solids, 0.37), 0.43)
    params = _piecewise_linear_interpolate(bounded_total_solids, SHRINKAGE_ANCHORS)
    ratio = params["intercept"] + params["slope"] * max(delta, 0.0)
    return min(max(ratio, 0.2), 1.0)


def _fu_50_shrinkage_ratio_70c(delta: float) -> float:
    bounded_delta = max(delta, 0.0)
    if bounded_delta <= 0.30:
        ratio = 0.0301 * bounded_delta + 0.9238
    else:
        ratio = 0.0866 * bounded_delta + 0.9061
    return min(max(ratio, 0.2), 1.0)


def _fu_50_shrinkage_ratio_90c(delta: float) -> float:
    ratio = 0.0447 * max(delta, 0.0) + 0.959
    return min(max(ratio, 0.2), 1.0)


def fu_50_shrinkage_ratio(delta: float, temp_air_k: float) -> float:
    temp_air_c = temp_air_k - 273.15
    ratio_70 = _fu_50_shrinkage_ratio_70c(delta)
    ratio_90 = _fu_50_shrinkage_ratio_90c(delta)
    # Fu et al. (2012) report 70 and 90 degC endpoints for 50-wt% SMP.
    # The active kernel maps the local air temperature onto those endpoints.
    if temp_air_c <= FU_SHRINKAGE_50_TEMP_LOW_C:
        return ratio_70
    if temp_air_c >= FU_SHRINKAGE_50_TEMP_HIGH_C:
        return ratio_90
    blend = (
        (temp_air_c - FU_SHRINKAGE_50_TEMP_LOW_C)
        / max(FU_SHRINKAGE_50_TEMP_HIGH_C - FU_SHRINKAGE_50_TEMP_LOW_C, EPS)
    )
    return min(max(_lerp(ratio_70, ratio_90, blend), 0.2), 1.0)


def chew_shrinkage_ratio(delta: float, feed_total_solids: float, temp_air_k: float) -> float:
    if feed_total_solids <= HIGH_SOLIDS_BLEND_START:
        return _anchored_high_solids_shrinkage_ratio(delta, feed_total_solids)
    ratio_43 = _anchored_high_solids_shrinkage_ratio(delta, HIGH_SOLIDS_BLEND_START)
    ratio_50 = fu_50_shrinkage_ratio(delta, temp_air_k)
    blend = _smoothstep(feed_total_solids, HIGH_SOLIDS_BLEND_START, HIGH_SOLIDS_BLEND_END)
    return min(max(_lerp(ratio_43, ratio_50, blend), 0.2), 1.0)


def legacy_extended_shrinkage_ratio(
    delta: float,
    x_b: float,
    feed_total_solids: float,
) -> float:
    initial_moisture = initial_moisture_dry_basis(feed_total_solids)
    normalized_delta = max(delta, 0.0) / max(initial_moisture - x_b, EPS)
    normalized_delta = min(max(normalized_delta, 0.0), 1.0)
    factor_20 = LEGACY_SHRINKAGE_20 + (1.0 - LEGACY_SHRINKAGE_20) * normalized_delta
    factor_30 = LEGACY_SHRINKAGE_30 + (1.0 - LEGACY_SHRINKAGE_30) * normalized_delta
    factor_37 = _anchored_high_solids_shrinkage_ratio(delta, 0.37)

    if feed_total_solids <= 0.20:
        return factor_20
    if feed_total_solids <= 0.30:
        blend = (feed_total_solids - 0.20) / 0.10
        return factor_20 + blend * (factor_30 - factor_20)
    if feed_total_solids < 0.37:
        blend = (feed_total_solids - 0.30) / 0.07
        return factor_30 + blend * (factor_37 - factor_30)
    return factor_37


def shrinkage_ratio(
    delta: float,
    x_b: float,
    feed_total_solids: float,
    shrinkage_model: str,
    temp_air_k: float,
) -> tuple[float, str]:
    if shrinkage_model == "chew":
        return chew_shrinkage_ratio(delta, feed_total_solids, temp_air_k), "chew"
    if shrinkage_model == "legacy_extended":
        return legacy_extended_shrinkage_ratio(delta, x_b, feed_total_solids), "legacy_extended"
    if shrinkage_model == "auto":
        if feed_total_solids < 0.37:
            return legacy_extended_shrinkage_ratio(delta, x_b, feed_total_solids), "legacy_extended"
        return chew_shrinkage_ratio(delta, feed_total_solids, temp_air_k), "chew"
    raise ValueError(f"Unsupported shrinkage model: {shrinkage_model}")


def equilibrium_activation_energy_max(temp_air_k: float, rh_air: float) -> float:
    bounded_rh = min(max(rh_air, EPS), 0.999999)
    return -R_GAS * temp_air_k * log(bounded_rh)


def chew_material_state(
    *,
    moisture_dry_basis: float,
    x_b: float,
    feed_total_solids: float,
    shrinkage_model: str,
    temp_particle_k: float,
    temp_air_k: float,
    rh_air: float,
) -> ChewMaterialState:
    delta = moisture_dry_basis - x_b
    initial_moisture = initial_moisture_dry_basis(feed_total_solids)
    reduced_ratio_base, slope, intercept, critical_delta, critical_ratio = activation_ratio(
        delta,
        feed_total_solids,
    )
    reduced_ratio_add, normalized_delta = _early_falling_rate_activation_ratio_add(
        delta,
        x_b,
        initial_moisture,
    )
    reduced_ratio_total = min(max(reduced_ratio_base + reduced_ratio_add, 0.0), 1.0)
    delta_e_max = equilibrium_activation_energy_max(temp_air_k, rh_air)
    delta_e = reduced_ratio_total * delta_e_max
    psi = exp(-delta_e / max(R_GAS * temp_particle_k, EPS))
    shrinkage_value, shrinkage_mode = shrinkage_ratio(
        delta,
        x_b,
        feed_total_solids,
        shrinkage_model,
        temp_air_k,
    )
    return ChewMaterialState(
        delta=delta,
        x_b=x_b,
        initial_moisture_dry_basis=initial_moisture,
        linear_slope=slope,
        linear_intercept=intercept,
        critical_delta=critical_delta,
        critical_ratio=critical_ratio,
        normalized_delta=normalized_delta,
        activation_ratio_base=reduced_ratio_base,
        activation_ratio_add=reduced_ratio_add,
        activation_ratio=reduced_ratio_total,
        delta_e_max_j_mol=delta_e_max,
        delta_e_j_mol=delta_e,
        psi=min(max(psi, 0.0), 1.0),
        shrinkage_ratio=shrinkage_value,
        shrinkage_mode=shrinkage_mode,
    )
