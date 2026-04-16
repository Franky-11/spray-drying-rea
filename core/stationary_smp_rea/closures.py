from __future__ import annotations

from math import exp, log
from typing import Literal


EPS = 1e-12
XBModel = Literal["langrish", "lin_gab"]


def equilibrium_moisture_langrish(temp_k: float, rh: float) -> float:
    bounded_rh = min(max(rh, EPS), 0.999999)
    return 0.1499 * exp(-2.306e-3 * temp_k) * (log(1.0 / bounded_rh) ** 0.4)


def equilibrium_moisture_lin_gab(temp_k: float, rh: float) -> float:
    bounded_rh = min(max(rh, EPS), 0.999999)
    c_const = 0.001645 * exp(24831.0 / (8.314 * temp_k))
    k_const = 5.710 * exp(-5118.0 / (8.314 * temp_k))
    numerator = c_const * k_const * 0.06156 * bounded_rh
    denominator = (1.0 - k_const * bounded_rh) * (
        1.0 - k_const * bounded_rh + c_const * k_const * bounded_rh
    )
    return numerator / max(denominator, EPS)


def equilibrium_moisture(temp_k: float, rh: float, model: XBModel) -> float:
    if model == "langrish":
        return equilibrium_moisture_langrish(temp_k, rh)
    if model == "lin_gab":
        return equilibrium_moisture_lin_gab(temp_k, rh)
    raise ValueError(f"Unsupported X_b closure: {model}")
