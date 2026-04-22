from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Literal


EPS = 1e-12
XBModel = Literal[
    "langrish",
    "lin_gab",
    "lin_gab_langrish_blend",
    "lin_gab_langrish_blend_rh",
]


@dataclass(frozen=True)
class EquilibriumMoistureClosure:
    x_b: float
    x_b_lin_gab: float
    x_b_langrish: float
    x_b_langrish_weight: float


def _bounded_langrish_weight(weight: float) -> float:
    return min(max(weight, 0.0), 1.0)


def equilibrium_moisture_langrish(temp_k: float, rh: float) -> float:
    bounded_rh = min(max(rh, EPS), 0.999999)
    return 0.1499 * exp(-2.306e-3 * temp_k) * log(1.0 / bounded_rh)


def equilibrium_moisture_lin_gab(temp_k: float, rh: float) -> float:
    bounded_rh = min(max(rh, EPS), 0.999999)
    c_const = 0.001645 * exp(24831.0 / (8.314 * temp_k))
    k_const = 5.710 * exp(-5118.0 / (8.314 * temp_k))
    numerator = c_const * k_const * 0.06156 * bounded_rh
    denominator = (1.0 - k_const * bounded_rh) * (
        1.0 - k_const * bounded_rh + c_const * k_const * bounded_rh
    )
    return numerator / max(denominator, EPS)


def equilibrium_moisture_closure(
    temp_k: float,
    rh: float,
    model: XBModel,
    x_b_blend_langrish_weight: float = 0.5,
    x_b_blend_langrish_weight_base: float = 0.0,
    x_b_blend_langrish_weight_rh_coeff: float = 0.0,
) -> EquilibriumMoistureClosure:
    x_b_langrish = equilibrium_moisture_langrish(temp_k, rh)
    x_b_lin_gab = equilibrium_moisture_lin_gab(temp_k, rh)

    if model == "langrish":
        return EquilibriumMoistureClosure(
            x_b=x_b_langrish,
            x_b_lin_gab=x_b_lin_gab,
            x_b_langrish=x_b_langrish,
            x_b_langrish_weight=1.0,
        )
    if model == "lin_gab":
        return EquilibriumMoistureClosure(
            x_b=x_b_lin_gab,
            x_b_lin_gab=x_b_lin_gab,
            x_b_langrish=x_b_langrish,
            x_b_langrish_weight=0.0,
        )
    if model == "lin_gab_langrish_blend":
        bounded_weight = _bounded_langrish_weight(x_b_blend_langrish_weight)
        return EquilibriumMoistureClosure(
            x_b=(1.0 - bounded_weight) * x_b_lin_gab + bounded_weight * x_b_langrish,
            x_b_lin_gab=x_b_lin_gab,
            x_b_langrish=x_b_langrish,
            x_b_langrish_weight=bounded_weight,
        )
    if model == "lin_gab_langrish_blend_rh":
        bounded_weight = _bounded_langrish_weight(
            x_b_blend_langrish_weight_base + x_b_blend_langrish_weight_rh_coeff * rh
        )
        return EquilibriumMoistureClosure(
            x_b=(1.0 - bounded_weight) * x_b_lin_gab + bounded_weight * x_b_langrish,
            x_b_lin_gab=x_b_lin_gab,
            x_b_langrish=x_b_langrish,
            x_b_langrish_weight=bounded_weight,
        )
    raise ValueError(f"Unsupported X_b closure: {model}")


def equilibrium_moisture(
    temp_k: float,
    rh: float,
    model: XBModel,
    x_b_blend_langrish_weight: float = 0.5,
    x_b_blend_langrish_weight_base: float = 0.0,
    x_b_blend_langrish_weight_rh_coeff: float = 0.0,
) -> float:
    return equilibrium_moisture_closure(
        temp_k=temp_k,
        rh=rh,
        model=model,
        x_b_blend_langrish_weight=x_b_blend_langrish_weight,
        x_b_blend_langrish_weight_base=x_b_blend_langrish_weight_base,
        x_b_blend_langrish_weight_rh_coeff=x_b_blend_langrish_weight_rh_coeff,
    ).x_b
