from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .air import moist_air_density
from .closures import XBModel
from .inputs import StationarySMPREAInput


@dataclass(frozen=True)
class MS400GeometryAssumption:
    cylinder_height_m: float = 2.2
    cone_height_m: float = 1.0
    cylinder_diameter_m: float = 1.15
    outlet_duct_length_m: float = 1.0
    outlet_duct_diameter_m: float = 0.20


def load_ms400_experiments(psd_path: str | Path | None = None) -> pd.DataFrame:
    if psd_path is None:
        psd_path = Path("ms400/psd.csv")
    frame = pd.read_csv(psd_path).rename(
        columns={
            "Versuch": "label",
            "Tin": "Tin_C",
            "Tout": "Tout_C",
            "Pulverfeuchte": "powder_moisture_wb_pct",
            "d32": "d32_um",
            "d43": "d43_um",
        }
    )
    frame = frame.dropna(subset=["label"]).copy()
    frame["label"] = frame["label"].astype(str)
    return frame


def _humid_air_mass_flow_to_volumetric_flow_m3_h(
    *,
    inlet_air_temp_c: float,
    inlet_abs_humidity_g_kg: float,
    humid_air_mass_flow_kg_h: float,
    pressure_pa: float,
) -> float:
    rho_air = moist_air_density(
        inlet_air_temp_c + 273.15,
        inlet_abs_humidity_g_kg / 1000.0,
        pressure_pa,
    )
    return humid_air_mass_flow_kg_h / max(rho_air, 1e-12)


def _default_humid_air_mass_flow_kg_h(label: str) -> float:
    if label == "V2":
        return 304.0
    return 200.0


def build_ms400_stationary_input(
    experiment: pd.Series,
    *,
    geometry: MS400GeometryAssumption | None = None,
    feed_rate_kg_h: float = 17.0,
    feed_total_solids: float = 0.37,
    inlet_abs_humidity_g_kg: float = 5.7,
    humid_air_mass_flow_kg_h: float | None = None,
    x_b_model: XBModel = "lin_gab",
    feed_temp_c: float = 40.0,
    ambient_temp_c: float = 20.0,
    heat_loss_coeff_w_m2k: float = 1.0,
    pressure_pa: float = 101325.0,
    particle_metric: str = "d32",
    particle_backcalc_exponent: float = 1.0 / 3.0,
    axial_points: int = 320,
) -> StationarySMPREAInput:
    geometry = MS400GeometryAssumption() if geometry is None else geometry
    if humid_air_mass_flow_kg_h is None:
        humid_air_mass_flow_kg_h = _default_humid_air_mass_flow_kg_h(
            str(experiment["label"])
        )
    particle_column = f"{particle_metric.lower()}_um"
    measured_particle_um = float(experiment[particle_column])
    effective_input_diameter_um = measured_particle_um / max(
        feed_total_solids**particle_backcalc_exponent,
        1e-12,
    )
    air_flow_m3_h = _humid_air_mass_flow_to_volumetric_flow_m3_h(
        inlet_air_temp_c=float(experiment["Tin_C"]),
        inlet_abs_humidity_g_kg=inlet_abs_humidity_g_kg,
        humid_air_mass_flow_kg_h=humid_air_mass_flow_kg_h,
        pressure_pa=pressure_pa,
    )
    return StationarySMPREAInput(
        dryer_height_m=geometry.cylinder_height_m,
        dryer_diameter_m=geometry.cylinder_diameter_m,
        cylinder_height_m=geometry.cylinder_height_m,
        cone_height_m=geometry.cone_height_m,
        cylinder_diameter_m=geometry.cylinder_diameter_m,
        outlet_duct_length_m=geometry.outlet_duct_length_m,
        outlet_duct_diameter_m=geometry.outlet_duct_diameter_m,
        inlet_air_temp_c=float(experiment["Tin_C"]),
        droplet_size_um=effective_input_diameter_um,
        feed_rate_kg_h=feed_rate_kg_h,
        air_flow_m3_h=air_flow_m3_h,
        inlet_abs_humidity_g_kg=inlet_abs_humidity_g_kg,
        ambient_temp_c=ambient_temp_c,
        feed_temp_c=feed_temp_c,
        feed_total_solids=feed_total_solids,
        x_b_model=x_b_model,
        pressure_pa=pressure_pa,
        heat_loss_coeff_w_m2k=heat_loss_coeff_w_m2k,
        axial_points=axial_points,
    )


def build_ms400_stationary_input_from_label(
    label: str,
    *,
    psd_path: str | Path | None = None,
    geometry: MS400GeometryAssumption | None = None,
    **kwargs: float,
) -> StationarySMPREAInput:
    experiments = load_ms400_experiments(psd_path=psd_path)
    experiment = experiments.loc[experiments["label"] == label]
    if experiment.empty:
        raise KeyError(f"MS400-Versuch '{label}' wurde in der PSD-Datei nicht gefunden.")
    return build_ms400_stationary_input(
        experiment.iloc[0],
        geometry=geometry,
        **kwargs,
    )


__all__ = [
    "MS400GeometryAssumption",
    "build_ms400_stationary_input",
    "build_ms400_stationary_input_from_label",
    "load_ms400_experiments",
]
