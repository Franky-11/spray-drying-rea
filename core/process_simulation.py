from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from .model import SimulationInput, run_simulation, summarize_input


TIME_VARIABLE_FIELDS = (
    "inlet_air_temp_c",
    "air_flow_m3_h",
    "inlet_abs_humidity_g_kg",
    "feed_rate_kg_h",
    "feed_total_solids",
)


@dataclass(frozen=True)
class ProcessEvent:
    time_s: float
    inlet_air_temp_c: float | None = None
    air_flow_m3_h: float | None = None
    inlet_abs_humidity_g_kg: float | None = None
    feed_rate_kg_h: float | None = None
    feed_total_solids: float | None = None
    label: str = ""


@dataclass(frozen=True)
class ProcessSimulationInput:
    base_input: SimulationInput
    events: list[ProcessEvent]
    duration_s: float
    time_step_s: float = 1.0
    target_outlet_x: float = 0.04

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.duration_s <= 0:
            errors.append("duration_s muss groesser als 0 sein.")
        if self.time_step_s <= 0:
            errors.append("time_step_s muss groesser als 0 sein.")
        for event in self.events:
            if event.time_s < 0:
                errors.append("event.time_s darf nicht negativ sein.")
        return errors


@dataclass
class ProcessSimulationResult:
    series: pd.DataFrame
    kpis: dict[str, float | None]
    warnings: list[str]


def build_stepwise_inputs(sim_input: ProcessSimulationInput) -> pd.DataFrame:
    errors = sim_input.validate()
    if errors:
        raise ValueError(" ".join(errors))

    times = np.arange(
        0.0,
        sim_input.duration_s + (0.5 * sim_input.time_step_s),
        sim_input.time_step_s,
        dtype=float,
    )
    base_values = {
        field: getattr(sim_input.base_input, field)
        for field in TIME_VARIABLE_FIELDS
    }
    current_values = dict(base_values)
    current_label = ""
    event_index = 0
    events = sorted(sim_input.events, key=lambda event: event.time_s)
    rows: list[dict[str, float | str]] = []

    for time_s in times:
        while event_index < len(events) and events[event_index].time_s <= time_s:
            event = events[event_index]
            for field in TIME_VARIABLE_FIELDS:
                value = getattr(event, field)
                if value is not None:
                    current_values[field] = value
            if event.label:
                current_label = event.label
            event_index += 1
        rows.append(
            {
                "t": float(time_s),
                **current_values,
                "event_label": current_label,
            }
        )

    return pd.DataFrame(rows)


def summarize_process_kpis(
    series: pd.DataFrame,
    *,
    target_outlet_x: float,
) -> dict[str, float | None]:
    if series.empty:
        return {
            "final_outlet_X": None,
            "final_outlet_Tb": None,
            "final_outlet_RH": None,
            "final_outlet_Y": None,
            "final_outlet_Tp": None,
            "max_outlet_X": None,
            "min_outlet_X": None,
            "mean_moisture_error": None,
            "max_moisture_error": None,
            "time_above_target_s": None,
            "final_target_outlet_time_s": None,
            "final_q_loss_w": None,
            "final_evaporation_rate_kg_s": None,
            "final_latent_load_w": None,
        }

    above_target = series["outlet_X"] > target_outlet_x
    dt_values = series["t"].diff().fillna(0.0)
    return {
        "final_outlet_X": float(series["outlet_X"].iloc[-1]),
        "final_outlet_Tb": float(series["outlet_Tb"].iloc[-1]),
        "final_outlet_RH": float(series["outlet_RH"].iloc[-1]),
        "final_outlet_Y": float(series["outlet_Y"].iloc[-1]),
        "final_outlet_Tp": float(series["outlet_Tp"].iloc[-1]),
        "max_outlet_X": float(series["outlet_X"].max()),
        "min_outlet_X": float(series["outlet_X"].min()),
        "mean_moisture_error": float(series["moisture_error"].mean()),
        "max_moisture_error": float(series["moisture_error"].max()),
        "time_above_target_s": float(dt_values.where(above_target, 0.0).sum()),
        "final_target_outlet_time_s": float(series["target_outlet_time_s"].iloc[-1]),
        "final_q_loss_w": float(series["q_loss_w"].iloc[-1]),
        "final_evaporation_rate_kg_s": float(series["evaporation_rate_kg_s"].iloc[-1]),
        "final_latent_load_w": float(series["latent_load_w"].iloc[-1]),
    }


def run_process_simulation(sim_input: ProcessSimulationInput) -> ProcessSimulationResult:
    schedule = build_stepwise_inputs(sim_input)
    warnings: list[str] = []
    cache: dict[SimulationInput, dict[str, float | None]] = {}

    baseline_summary = summarize_input(sim_input.base_input)
    air_dead_time_s = max(sim_input.time_step_s, baseline_summary["air_residence_time_s"])
    product_baseline = run_simulation(sim_input.base_input, label="process-baseline")
    warnings.extend(product_baseline.warnings)
    product_dead_time_s = max(
        air_dead_time_s,
        float(product_baseline.metrics["outlet_time"] or air_dead_time_s),
    )
    tau_air_s = max(sim_input.time_step_s, 2.0 * air_dead_time_s)
    tau_product_s = max(sim_input.time_step_s, 2.0 * product_dead_time_s)
    air_dead_steps = int(np.ceil(air_dead_time_s / sim_input.time_step_s))
    product_dead_steps = int(np.ceil(product_dead_time_s / sim_input.time_step_s))

    target_rows: list[dict[str, float | None]] = []

    for _, row in schedule.iterrows():
        step_input = replace(
            sim_input.base_input,
            inlet_air_temp_c=float(row["inlet_air_temp_c"]),
            air_flow_m3_h=float(row["air_flow_m3_h"]),
            inlet_abs_humidity_g_kg=float(row["inlet_abs_humidity_g_kg"]),
            feed_rate_kg_h=float(row["feed_rate_kg_h"]),
            feed_total_solids=float(row["feed_total_solids"]),
        )
        if step_input not in cache:
            step_result = run_simulation(step_input, label=f"t={row['t']:.1f}s")
            warnings.extend(step_result.warnings)
            cache[step_input] = _extract_target_outputs(step_result)
        target_rows.append(cache[step_input])

    target_frame = pd.DataFrame(target_rows)
    series = pd.concat([schedule.reset_index(drop=True), target_frame], axis=1)
    series["outlet_X"] = [
        float(target_rows[0]["target_outlet_X"]) if index == 0 else np.nan
        for index in range(len(series))
    ]
    series["outlet_Tb"] = [
        float(target_rows[0]["target_outlet_Tb"]) if index == 0 else np.nan
        for index in range(len(series))
    ]
    series["outlet_RH"] = [
        float(target_rows[0]["target_outlet_RH"]) if index == 0 else np.nan
        for index in range(len(series))
    ]
    series["outlet_Y"] = [
        float(target_rows[0]["target_outlet_Y"]) if index == 0 else np.nan
        for index in range(len(series))
    ]
    series["outlet_Tp"] = [
        float(target_rows[0]["target_outlet_Tp"]) if index == 0 else np.nan
        for index in range(len(series))
    ]

    actual_states = {
        "outlet_X": float(target_rows[0]["target_outlet_X"]),
        "outlet_Tb": float(target_rows[0]["target_outlet_Tb"]),
        "outlet_RH": float(target_rows[0]["target_outlet_RH"]),
        "outlet_Y": float(target_rows[0]["target_outlet_Y"]),
        "outlet_Tp": float(target_rows[0]["target_outlet_Tp"]),
    }
    for index in range(1, len(series)):
        delayed_air = target_rows[max(0, index - air_dead_steps)]
        delayed_product = target_rows[max(0, index - product_dead_steps)]
        actual_states["outlet_Tb"] = _lag_step(
            actual_states["outlet_Tb"],
            float(delayed_air["target_outlet_Tb"]),
            sim_input.time_step_s,
            tau_air_s,
        )
        actual_states["outlet_RH"] = _lag_step(
            actual_states["outlet_RH"],
            float(delayed_air["target_outlet_RH"]),
            sim_input.time_step_s,
            tau_air_s,
        )
        actual_states["outlet_Y"] = _lag_step(
            actual_states["outlet_Y"],
            float(delayed_air["target_outlet_Y"]),
            sim_input.time_step_s,
            tau_air_s,
        )
        actual_states["outlet_X"] = _lag_step(
            actual_states["outlet_X"],
            float(delayed_product["target_outlet_X"]),
            sim_input.time_step_s,
            tau_product_s,
        )
        actual_states["outlet_Tp"] = _lag_step(
            actual_states["outlet_Tp"],
            float(delayed_product["target_outlet_Tp"]),
            sim_input.time_step_s,
            tau_product_s,
        )
        for column, value in actual_states.items():
            series.at[index, column] = value

    _append_derived_process_quantities(series, sim_input.base_input)
    series["moisture_error"] = series["outlet_X"] - sim_input.target_outlet_x
    kpis = summarize_process_kpis(series, target_outlet_x=sim_input.target_outlet_x)
    kpis["air_dead_time_s"] = float(air_dead_steps * sim_input.time_step_s)
    kpis["product_dead_time_s"] = float(product_dead_steps * sim_input.time_step_s)
    kpis["tau_air_s"] = float(tau_air_s)
    kpis["tau_product_s"] = float(tau_product_s)

    return ProcessSimulationResult(series=series, kpis=kpis, warnings=_deduplicate_warnings(warnings))


def _extract_target_outputs(result: Any) -> dict[str, float | None]:
    outlet_mask = result.series["height"] >= result.inputs.dryer_height_m
    if outlet_mask.any():
        outlet_row = result.series.loc[outlet_mask].iloc[0]
    else:
        outlet_row = result.series.iloc[-1]

    return {
        "target_outlet_X": float(outlet_row["X"]),
        "target_outlet_Tb": float(outlet_row["Tb"]),
        "target_outlet_RH": float(outlet_row["RH"]),
        "target_outlet_Y": float(outlet_row["Y"]),
        "target_outlet_Tp": float(outlet_row["Tp"]),
        "target_outlet_time_s": float(result.metrics["outlet_time"] or outlet_row["t"]),
    }


def _lag_step(current: float, target: float, time_step_s: float, tau_s: float) -> float:
    alpha = min(1.0, time_step_s / max(tau_s, time_step_s))
    return current + alpha * (target - current)


def _append_derived_process_quantities(series: pd.DataFrame, base_input: SimulationInput) -> None:
    ambient_temp_k = base_input.ambient_temp_c + 273.0
    dryer_shell_area_m2 = np.pi * base_input.dryer_diameter_m * base_input.dryer_height_m
    dry_solids_rate_kg_s = (series["feed_rate_kg_h"] * series["feed_total_solids"]) / 3600.0
    inlet_water_dry_basis = (1.0 - series["feed_total_solids"]) / series["feed_total_solids"]
    evaporation_rate_kg_s = dry_solids_rate_kg_s * (inlet_water_dry_basis - series["outlet_X"])
    vaporization_enthalpy_j_kg = 2.792e6 - 160.0 * series["outlet_Tb"] - 3.43 * series["outlet_Tb"] ** 2

    series["q_loss_w"] = (
        base_input.heat_loss_coeff_w_m2k
        * dryer_shell_area_m2
        * (series["outlet_Tb"] - ambient_temp_k)
    )
    series["evaporation_rate_kg_s"] = evaporation_rate_kg_s.clip(lower=0.0)
    series["latent_load_w"] = series["evaporation_rate_kg_s"] * vaporization_enthalpy_j_kg


def _deduplicate_warnings(warnings: list[str]) -> list[str]:
    unique: list[str] = []
    for warning in warnings:
        if warning not in unique:
            unique.append(warning)
    return unique
