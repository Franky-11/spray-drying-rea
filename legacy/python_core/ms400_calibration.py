from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import OptimizeResult, least_squares

from .model import SimulationInput, air_density, run_simulation


_MS400_SUMMARY_ROWS = [
    {
        "label": "V1",
        "inlet_air_temp_c": 240.0,
        "measured_outlet_air_temp_c": 130.0,
        "nozzle_opening_mm": 0.34,
        "measured_d43_um": 78.0,
        "measured_powder_moisture_wb_pct": 1.4,
    },
    {
        "label": "V2",
        "inlet_air_temp_c": 180.0,
        "measured_outlet_air_temp_c": 92.0,
        "nozzle_opening_mm": 0.34,
        "measured_d43_um": 63.0,
        "measured_powder_moisture_wb_pct": 3.2,
    },
    {
        "label": "V3",
        "inlet_air_temp_c": 150.0,
        "measured_outlet_air_temp_c": 72.0,
        "nozzle_opening_mm": 0.34,
        "measured_d43_um": 78.0,
        "measured_powder_moisture_wb_pct": 6.2,
    },
    {
        "label": "V4",
        "inlet_air_temp_c": 250.0,
        "measured_outlet_air_temp_c": 134.0,
        "nozzle_opening_mm": 0.40,
        "measured_d43_um": 85.0,
        "measured_powder_moisture_wb_pct": 1.2,
    },
    {
        "label": "V5",
        "inlet_air_temp_c": 180.0,
        "measured_outlet_air_temp_c": 94.0,
        "nozzle_opening_mm": 0.40,
        "measured_d43_um": 76.0,
        "measured_powder_moisture_wb_pct": 3.2,
    },
    {
        "label": "V6",
        "inlet_air_temp_c": 150.0,
        "measured_outlet_air_temp_c": 72.0,
        "nozzle_opening_mm": 0.40,
        "measured_d43_um": 104.0,
        "measured_powder_moisture_wb_pct": 7.3,
    },
]


@dataclass(frozen=True)
class MS400CalibrationSettings:
    feed_rate_kg_h: float = 17.0
    feed_total_solids: float = 0.37
    feed_temp_c: float = 40.0
    inlet_abs_humidity_g_kg: float = 5.0
    ambient_temp_c: float = 20.0
    humid_air_mass_flow_kg_h: float = 200.0
    heater_power_kw: float = 35.0
    heater_nominal_air_mass_flow_kg_h: float = 400.0
    particle_metric: str = "d32"
    particle_backcalc_exponent: float = 1.0 / 3.0
    simulation_end_s: float = 30.0
    time_points: int = 600
    temp_weight_c: float = 10.0
    moisture_weight_wb_pct: float = 1.0
    excluded_labels: tuple[str, ...] = ("V1", "V4")

    @property
    def dry_particle_to_effective_input_factor(self) -> float:
        return 1.0 / (self.feed_total_solids ** self.particle_backcalc_exponent)


@dataclass(frozen=True)
class MS400CalibrationParameters:
    particle_scale: float = 1.0
    rea_transfer_scale: float = 1.0
    heat_loss_coeff_w_m2k: float = 4.5
    equilibrium_moisture_offset: float = 0.0


@dataclass(frozen=True)
class MS400CalibrationResult:
    parameters: MS400CalibrationParameters
    series: pd.DataFrame
    rmse_outlet_temp_c: float
    rmse_powder_moisture_wb_pct: float
    success: bool
    message: str
    nfev: int
    cost: float
    raw_result: OptimizeResult | None = None


def load_ms400_stationary_experiments(psd_path: str | Path | None = None) -> pd.DataFrame:
    summary = pd.DataFrame(_MS400_SUMMARY_ROWS)
    summary["label"] = summary["label"].astype(str)
    summary["measured_powder_moisture_wb_frac"] = (
        summary["measured_powder_moisture_wb_pct"] / 100.0
    )
    summary["target_X_db"] = (
        summary["measured_powder_moisture_wb_frac"]
        / (1.0 - summary["measured_powder_moisture_wb_frac"])
    )

    if psd_path is None:
        candidate = Path("ms400/psd.csv")
        psd_path = candidate if candidate.exists() else None
    elif not Path(psd_path).exists():
        psd_path = None

    if psd_path is None:
        summary["d10_um"] = np.nan
        summary["d50_um"] = np.nan
        summary["d90_um"] = np.nan
        summary["d32_um"] = summary["measured_d43_um"]
        summary["span"] = np.nan
        return summary

    psd_frame = pd.read_csv(psd_path).rename(
        columns={
            "Versuch": "label",
            "D10 [um]": "d10_um",
            "D50 [um]": "d50_um",
            "D90 [um]": "d90_um",
            "d32": "d32_um",
            "d43": "d43_um",
            "Span": "span",
        }
    )
    psd_frame = psd_frame.dropna(subset=["label"]).copy()
    psd_frame["label"] = psd_frame["label"].astype(str)
    merged = summary.merge(psd_frame, on="label", how="left", suffixes=("", "_psd"))
    merged["d32_um"] = merged["d32_um"].fillna(merged["measured_d43_um"])
    merged["d43_um"] = merged["d43_um"].fillna(merged["measured_d43_um"])
    return merged


def _mark_calibration_rows(
    experiments: pd.DataFrame,
    excluded_labels: tuple[str, ...],
) -> pd.DataFrame:
    frame = experiments.copy()
    excluded = {label.upper() for label in excluded_labels}
    frame["use_for_calibration"] = ~frame["label"].astype(str).str.upper().isin(excluded)
    return frame


def default_ms400_calibration_parameters() -> MS400CalibrationParameters:
    return MS400CalibrationParameters()


def _measured_particle_size_um(experiment: pd.Series, metric: str) -> float:
    column = f"{metric.lower()}_um"
    if column in experiment.index and pd.notna(experiment[column]):
        return float(experiment[column])
    if metric.lower() == "d43":
        return float(experiment["measured_d43_um"])
    raise KeyError(f"Particle metric '{metric}' ist fuer {experiment['label']} nicht verfuegbar.")


def _humid_air_flow_to_volumetric_flow(
    inlet_air_temp_c: float,
    inlet_abs_humidity_g_kg: float,
    humid_air_mass_flow_kg_h: float,
) -> float:
    rho_air = air_density(
        inlet_air_temp_c + 273.15,
        inlet_abs_humidity_g_kg / 1000.0,
        101000.0,
        287.058,
        461.523,
    )
    return humid_air_mass_flow_kg_h / max(rho_air, 1e-12)


def build_ms400_simulation_input(
    experiment: pd.Series,
    settings: MS400CalibrationSettings,
    parameters: MS400CalibrationParameters,
) -> SimulationInput:
    particle_size_um = (
        _measured_particle_size_um(experiment, settings.particle_metric)
        * settings.dry_particle_to_effective_input_factor
        * parameters.particle_scale
    )
    air_flow_m3_h = _humid_air_flow_to_volumetric_flow(
        inlet_air_temp_c=float(experiment["inlet_air_temp_c"]),
        inlet_abs_humidity_g_kg=settings.inlet_abs_humidity_g_kg,
        humid_air_mass_flow_kg_h=settings.humid_air_mass_flow_kg_h,
    )
    return SimulationInput(
        inlet_air_temp_c=float(experiment["inlet_air_temp_c"]),
        droplet_size_um=float(particle_size_um),
        feed_rate_kg_h=settings.feed_rate_kg_h,
        air_flow_m3_h=float(air_flow_m3_h),
        inlet_abs_humidity_g_kg=settings.inlet_abs_humidity_g_kg,
        ambient_temp_c=settings.ambient_temp_c,
        feed_temp_c=settings.feed_temp_c,
        feed_total_solids=settings.feed_total_solids,
        material="SMP",
        heat_loss_coeff_w_m2k=parameters.heat_loss_coeff_w_m2k,
        simulation_end_s=settings.simulation_end_s,
        time_points=settings.time_points,
        rea_transfer_scale=parameters.rea_transfer_scale,
        equilibrium_moisture_offset=parameters.equilibrium_moisture_offset,
    )


def evaluate_ms400_stationary_model(
    experiments: pd.DataFrame,
    settings: MS400CalibrationSettings,
    parameters: MS400CalibrationParameters,
) -> pd.DataFrame:
    experiments = _mark_calibration_rows(experiments, settings.excluded_labels)
    rows: list[dict[str, float | str]] = []
    for _, experiment in experiments.iterrows():
        sim_input = build_ms400_simulation_input(experiment, settings, parameters)
        result = run_simulation(sim_input, label=str(experiment["label"]))

        predicted_x_db = float(result.metrics["outlet_X"])
        predicted_wb_frac = predicted_x_db / (1.0 + predicted_x_db)
        predicted_wb_pct = 100.0 * predicted_wb_frac
        predicted_outlet_temp_c = float(result.metrics["outlet_Tb"]) - 273.15
        measured_wb_pct = float(experiment["measured_powder_moisture_wb_pct"])
        measured_outlet_temp_c = float(experiment["measured_outlet_air_temp_c"])
        measured_particle_um = _measured_particle_size_um(experiment, settings.particle_metric)

        rows.append(
            {
                "label": str(experiment["label"]),
                "Tin_C": float(experiment["inlet_air_temp_c"]),
                "Tout_measured_C": measured_outlet_temp_c,
                "Tout_predicted_C": predicted_outlet_temp_c,
                "Tout_error_C": predicted_outlet_temp_c - measured_outlet_temp_c,
                "moisture_measured_wb_pct": measured_wb_pct,
                "moisture_predicted_wb_pct": predicted_wb_pct,
                "moisture_error_wb_pct": predicted_wb_pct - measured_wb_pct,
                "target_X_db": float(experiment["target_X_db"]),
                "predicted_X_db": predicted_x_db,
                "particle_metric_um": measured_particle_um,
                "effective_input_diameter_um": float(sim_input.droplet_size_um),
                "air_flow_m3_h": float(sim_input.air_flow_m3_h),
                "humid_air_mass_flow_kg_h": settings.humid_air_mass_flow_kg_h,
                "use_for_calibration": bool(experiment["use_for_calibration"]),
            }
        )

    return pd.DataFrame(rows)


def _parameter_vector(parameters: MS400CalibrationParameters) -> np.ndarray:
    return np.array(
        [
            parameters.particle_scale,
            parameters.rea_transfer_scale,
            parameters.heat_loss_coeff_w_m2k,
            parameters.equilibrium_moisture_offset,
        ],
        dtype=float,
    )


def _parameters_from_vector(vector: np.ndarray) -> MS400CalibrationParameters:
    return MS400CalibrationParameters(
        particle_scale=float(vector[0]),
        rea_transfer_scale=float(vector[1]),
        heat_loss_coeff_w_m2k=float(vector[2]),
        equilibrium_moisture_offset=float(vector[3]),
    )


def ms400_calibration_residuals(
    vector: np.ndarray,
    experiments: pd.DataFrame,
    settings: MS400CalibrationSettings,
) -> np.ndarray:
    parameters = _parameters_from_vector(vector)
    evaluation = evaluate_ms400_stationary_model(experiments, settings, parameters)
    active = evaluation[evaluation["use_for_calibration"]]
    temp_residuals = active["Tout_error_C"].to_numpy(dtype=float) / settings.temp_weight_c
    moisture_residuals = (
        active["moisture_error_wb_pct"].to_numpy(dtype=float) / settings.moisture_weight_wb_pct
    )
    return np.concatenate([temp_residuals, moisture_residuals])


def fit_ms400_stationary_calibration(
    experiments: pd.DataFrame | None = None,
    settings: MS400CalibrationSettings | None = None,
    initial_parameters: MS400CalibrationParameters | None = None,
    *,
    max_nfev: int = 80,
) -> MS400CalibrationResult:
    if settings is None:
        settings = MS400CalibrationSettings()
    if experiments is None:
        experiments = load_ms400_stationary_experiments()
    if initial_parameters is None:
        initial_parameters = default_ms400_calibration_parameters()

    initial_vector = _parameter_vector(initial_parameters)
    lower = np.array([0.6, 0.4, 0.0, -0.02], dtype=float)
    upper = np.array([1.8, 3.0, 30.0, 0.05], dtype=float)
    result = least_squares(
        ms400_calibration_residuals,
        initial_vector,
        bounds=(lower, upper),
        args=(experiments, settings),
        max_nfev=max_nfev,
    )
    parameters = _parameters_from_vector(result.x)
    evaluation = evaluate_ms400_stationary_model(experiments, settings, parameters)
    return MS400CalibrationResult(
        parameters=parameters,
        series=evaluation,
        rmse_outlet_temp_c=float(np.sqrt(np.mean(np.square(evaluation["Tout_error_C"])))),
        rmse_powder_moisture_wb_pct=float(
            np.sqrt(np.mean(np.square(evaluation["moisture_error_wb_pct"])))
        ),
        success=bool(result.success),
        message=str(result.message),
        nfev=int(result.nfev),
        cost=float(result.cost),
        raw_result=result,
    )


__all__ = [
    "MS400CalibrationParameters",
    "MS400CalibrationResult",
    "MS400CalibrationSettings",
    "build_ms400_simulation_input",
    "default_ms400_calibration_parameters",
    "evaluate_ms400_stationary_model",
    "fit_ms400_stationary_calibration",
    "load_ms400_stationary_experiments",
    "ms400_calibration_residuals",
]
