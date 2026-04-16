from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt


EPS = 1e-12


@dataclass(frozen=True)
class EffectiveDryerGeometry:
    cylinder_height_m: float
    cone_height_m: float
    cylinder_diameter_m: float
    cone_exit_diameter_m: float
    outlet_duct_length_m: float
    outlet_duct_diameter_m: float

    @property
    def cylinder_end_h_m(self) -> float:
        return self.cylinder_height_m

    @property
    def cone_end_h_m(self) -> float:
        return self.cylinder_height_m + self.cone_height_m

    @property
    def total_length_m(self) -> float:
        return self.cylinder_height_m + self.cone_height_m + self.outlet_duct_length_m

    @property
    def pre_cyclone_h_m(self) -> float:
        return self.total_length_m

    @property
    def cone_radius_slope(self) -> float:
        if self.cone_height_m <= 0.0:
            return 0.0
        radius_delta = 0.5 * (self.cone_exit_diameter_m - self.cylinder_diameter_m)
        return radius_delta / self.cone_height_m

    @property
    def cone_slant_factor(self) -> float:
        return sqrt(1.0 + self.cone_radius_slope**2)

    @property
    def total_wall_area_m2(self) -> float:
        cylinder_area = pi * self.cylinder_diameter_m * self.cylinder_height_m
        if self.cone_height_m > 0.0:
            r1 = 0.5 * self.cylinder_diameter_m
            r2 = 0.5 * self.cone_exit_diameter_m
            cone_slant_height = sqrt((r1 - r2) ** 2 + self.cone_height_m**2)
            cone_area = pi * (r1 + r2) * cone_slant_height
        else:
            cone_area = 0.0
        duct_area = pi * self.outlet_duct_diameter_m * self.outlet_duct_length_m
        return cylinder_area + cone_area + duct_area

    def clamp_h(self, h_m: float) -> float:
        return min(max(h_m, 0.0), self.total_length_m)

    def section_at(self, h_m: float) -> str:
        h_m = self.clamp_h(h_m)
        if h_m < self.cylinder_end_h_m:
            return "cylinder"
        if h_m < self.cone_end_h_m:
            return "cone"
        return "outlet_duct"

    def diameter_at(self, h_m: float) -> float:
        h_m = self.clamp_h(h_m)
        if h_m <= self.cylinder_end_h_m:
            return self.cylinder_diameter_m
        if h_m <= self.cone_end_h_m and self.cone_height_m > 0.0:
            fraction = (h_m - self.cylinder_end_h_m) / self.cone_height_m
            return self.cylinder_diameter_m + fraction * (
                self.cone_exit_diameter_m - self.cylinder_diameter_m
            )
        return self.outlet_duct_diameter_m

    def cross_section_area_at(self, h_m: float) -> float:
        diameter_m = self.diameter_at(h_m)
        return pi * diameter_m**2 / 4.0

    def perimeter_at(self, h_m: float) -> float:
        return pi * self.diameter_at(h_m)

    def wall_area_density_at(self, h_m: float) -> float:
        if self.section_at(h_m) == "cone":
            return self.perimeter_at(h_m) * self.cone_slant_factor
        return self.perimeter_at(h_m)


def build_effective_dryer_geometry(
    *,
    dryer_height_m: float,
    dryer_diameter_m: float,
    cylinder_height_m: float | None,
    cone_height_m: float,
    cylinder_diameter_m: float | None,
    outlet_duct_length_m: float,
    outlet_duct_diameter_m: float | None,
) -> EffectiveDryerGeometry:
    resolved_cylinder_height_m = dryer_height_m if cylinder_height_m is None else cylinder_height_m
    resolved_cylinder_diameter_m = (
        dryer_diameter_m if cylinder_diameter_m is None else cylinder_diameter_m
    )
    resolved_outlet_duct_diameter_m = (
        resolved_cylinder_diameter_m
        if outlet_duct_diameter_m is None
        else outlet_duct_diameter_m
    )
    cone_exit_diameter_m = resolved_outlet_duct_diameter_m
    return EffectiveDryerGeometry(
        cylinder_height_m=resolved_cylinder_height_m,
        cone_height_m=cone_height_m,
        cylinder_diameter_m=resolved_cylinder_diameter_m,
        cone_exit_diameter_m=cone_exit_diameter_m,
        outlet_duct_length_m=outlet_duct_length_m,
        outlet_duct_diameter_m=resolved_outlet_duct_diameter_m,
    )
