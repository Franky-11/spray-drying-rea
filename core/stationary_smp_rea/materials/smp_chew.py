from __future__ import annotations

from dataclasses import dataclass
from math import exp, log


EPS = 1e-12
R_GAS = 8.314
POLY_COEFFS = (1.0, -1.305, 0.7097, -0.1721, 0.0151)
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


@dataclass(frozen=True)
class ChewMaterialState:
    delta: float
    x_b: float
    critical_delta: float
    critical_ratio: float
    activation_ratio: float
    delta_e_max_j_mol: float
    delta_e_j_mol: float
    psi: float
    shrinkage_ratio: float


def chew_validity_warnings(feed_total_solids: float) -> list[str]:
    warnings: list[str] = []
    if not 0.30 <= feed_total_solids <= 0.43:
        warnings.append(
            "Chew-REA interpolation ist nur im Bereich 30-43 wt% referenzbasiert."
        )
    if feed_total_solids < 0.37:
        warnings.append(
            "Chew-Schrumpfung ist nur fuer 37-43 wt% verankert; fuer 30-37 wt% wird auf den 37-wt%-Anker geklemmt."
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


def _common_polynomial(delta: float) -> float:
    bounded_delta = max(delta, 0.0)
    return (
        POLY_COEFFS[0]
        + POLY_COEFFS[1] * bounded_delta
        + POLY_COEFFS[2] * bounded_delta**2
        + POLY_COEFFS[3] * bounded_delta**3
        + POLY_COEFFS[4] * bounded_delta**4
    )


def activation_ratio(delta: float, feed_total_solids: float) -> tuple[float, float, float]:
    params = _piecewise_linear_interpolate(feed_total_solids, LINEAR_ANCHORS)
    bounded_delta = max(delta, 0.0)
    if bounded_delta >= params["critical_delta"]:
        ratio = params["critical_ratio"] - params["slope"] * (
            bounded_delta - params["critical_delta"]
        )
    else:
        ratio = _common_polynomial(bounded_delta)
    return (
        min(max(ratio, 0.0), 1.0),
        params["critical_delta"],
        params["critical_ratio"],
    )


def shrinkage_ratio(delta: float, feed_total_solids: float) -> float:
    bounded_total_solids = min(max(feed_total_solids, 0.37), 0.43)
    params = _piecewise_linear_interpolate(bounded_total_solids, SHRINKAGE_ANCHORS)
    ratio = params["intercept"] + params["slope"] * max(delta, 0.0)
    return min(max(ratio, 0.2), 1.0)


def equilibrium_activation_energy_max(temp_air_k: float, rh_air: float) -> float:
    bounded_rh = min(max(rh_air, EPS), 0.999999)
    return -R_GAS * temp_air_k * log(bounded_rh)


def chew_material_state(
    *,
    moisture_dry_basis: float,
    x_b: float,
    feed_total_solids: float,
    temp_particle_k: float,
    temp_air_k: float,
    rh_air: float,
) -> ChewMaterialState:
    delta = moisture_dry_basis - x_b
    reduced_ratio, critical_delta, critical_ratio = activation_ratio(
        delta,
        feed_total_solids,
    )
    delta_e_max = equilibrium_activation_energy_max(temp_air_k, rh_air)
    delta_e = reduced_ratio * delta_e_max
    psi = exp(-delta_e / max(R_GAS * temp_particle_k, EPS))
    return ChewMaterialState(
        delta=delta,
        x_b=x_b,
        critical_delta=critical_delta,
        critical_ratio=critical_ratio,
        activation_ratio=reduced_ratio,
        delta_e_max_j_mol=delta_e_max,
        delta_e_j_mol=delta_e,
        psi=min(max(psi, 0.0), 1.0),
        shrinkage_ratio=shrinkage_ratio(delta, feed_total_solids),
    )
