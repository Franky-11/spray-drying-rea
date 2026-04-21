from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from .model import (
    SimulationInput,
    _build_derived,
    _latent_heat_vaporization,
    _rea_snapshot,
    run_simulation,
    summarize_input,
)


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


@dataclass
class _StageState:
    x: float
    tp: float
    tb: float
    y: float


@dataclass(frozen=True)
class _StageSettings:
    product_tau_s: float
    air_tau_s: float
    transfer_scale: float
    heat_loss_share: float


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
    target_cache: dict[SimulationInput, dict[str, float | None]] = {}

    nominal_times = _build_nominal_stage_times(sim_input.base_input)
    air_dead_time_s = nominal_times["stage1"].air_tau_s + nominal_times["stage2"].air_tau_s
    product_dead_time_s = nominal_times["stage1"].product_tau_s + nominal_times["stage2"].product_tau_s

    stage1, stage2 = _warm_start_states(sim_input.base_input, nominal_times)
    rows: list[dict[str, float | str | None]] = []

    for index, row in schedule.iterrows():
        step_input = replace(
            sim_input.base_input,
            inlet_air_temp_c=float(row["inlet_air_temp_c"]),
            air_flow_m3_h=float(row["air_flow_m3_h"]),
            inlet_abs_humidity_g_kg=float(row["inlet_abs_humidity_g_kg"]),
            feed_rate_kg_h=float(row["feed_rate_kg_h"]),
            feed_total_solids=float(row["feed_total_solids"]),
        )
        if step_input not in target_cache:
            step_result = run_simulation(step_input, label=f"t={row['t']:.1f}s")
            warnings.extend(step_result.warnings)
            target_cache[step_input] = _extract_target_outputs(step_result)
        target = target_cache[step_input]

        stage_metrics = _current_stage_metrics(stage1, stage2, step_input, nominal_times)
        rows.append(
            {
                "t": float(row["t"]),
                "event_label": str(row["event_label"]),
                "inlet_air_temp_c": float(row["inlet_air_temp_c"]),
                "air_flow_m3_h": float(row["air_flow_m3_h"]),
                "inlet_abs_humidity_g_kg": float(row["inlet_abs_humidity_g_kg"]),
                "feed_rate_kg_h": float(row["feed_rate_kg_h"]),
                "feed_total_solids": float(row["feed_total_solids"]),
                "target_outlet_X": float(target["target_outlet_X"]),
                "target_outlet_Tb": float(target["target_outlet_Tb"]),
                "target_outlet_RH": float(target["target_outlet_RH"]),
                "target_outlet_Y": float(target["target_outlet_Y"]),
                "target_outlet_Tp": float(target["target_outlet_Tp"]),
                "target_outlet_time_s": float(target["target_outlet_time_s"]),
                "outlet_X": float(stage2.x),
                "outlet_Tb": float(stage2.tb),
                "outlet_RH": float(stage_metrics["outlet_RH"]),
                "outlet_Y": float(stage2.y),
                "outlet_Tp": float(stage2.tp),
                "stage1_X": float(stage1.x),
                "stage1_Tb": float(stage1.tb),
                "stage1_Y": float(stage1.y),
                "stage1_Tp": float(stage1.tp),
                "q_loss_w": float(stage_metrics["q_loss_w"]),
                "evaporation_rate_kg_s": float(stage_metrics["evaporation_rate_kg_s"]),
                "latent_load_w": float(stage_metrics["latent_load_w"]),
                "dry_solids_rate_kg_s": float(stage_metrics["dry_solids_rate_kg_s"]),
                "air_mass_flow_rate_kg_s": float(stage_metrics["air_mass_flow_rate_kg_s"]),
                "stage1_product_tau_s": float(nominal_times["stage1"].product_tau_s),
                "stage2_product_tau_s": float(nominal_times["stage2"].product_tau_s),
                "stage1_air_tau_s": float(nominal_times["stage1"].air_tau_s),
                "stage2_air_tau_s": float(nominal_times["stage2"].air_tau_s),
            }
        )

        if index + 1 < len(schedule):
            dt = float(schedule.iloc[index + 1]["t"] - row["t"])
            if dt > 0:
                stage1, stage2 = _advance_process_states(
                    stage1,
                    stage2,
                    step_input,
                    nominal_times,
                    dt,
                )

    series = pd.DataFrame(rows)
    series["moisture_error"] = series["outlet_X"] - sim_input.target_outlet_x
    kpis = summarize_process_kpis(series, target_outlet_x=sim_input.target_outlet_x)
    kpis["air_dead_time_s"] = float(air_dead_time_s)
    kpis["product_dead_time_s"] = float(product_dead_time_s)
    kpis["tau_air_s"] = float(air_dead_time_s)
    kpis["tau_product_s"] = float(product_dead_time_s)

    return ProcessSimulationResult(series=series, kpis=kpis, warnings=_deduplicate_warnings(warnings))


def _build_nominal_stage_times(base_input: SimulationInput) -> dict[str, _StageSettings]:
    base_summary = summarize_input(base_input)
    product_total_s = max(base_summary["effective_residence_time_s"] * 1.5, 8.0)
    air_total_s = max(product_total_s * 0.22, 1.5)
    return {
        "stage1": _StageSettings(
            product_tau_s=0.62 * product_total_s,
            air_tau_s=0.58 * air_total_s,
            transfer_scale=1.0,
            heat_loss_share=0.65,
        ),
        "stage2": _StageSettings(
            product_tau_s=0.38 * product_total_s,
            air_tau_s=0.42 * air_total_s,
            transfer_scale=0.55,
            heat_loss_share=0.35,
        ),
    }


def _stage_hold_ups(
    step_input: SimulationInput,
    setting: _StageSettings,
) -> tuple[float, float]:
    d = _build_derived(step_input)
    product_hold_up = max(d.solids_rate_kg_s * setting.product_tau_s, 1e-6)
    air_hold_up = max(d.dry_air_mass_flow_kg_s * setting.air_tau_s, 1e-6)
    return product_hold_up, air_hold_up


def _warm_start_states(
    base_input: SimulationInput,
    nominal_times: dict[str, _StageSettings],
) -> tuple[_StageState, _StageState]:
    base = _build_derived(base_input)
    stage1 = _StageState(x=base.x0, tp=base.tp0_k, tb=base.tb0_k, y=base.y0)
    stage2 = _StageState(x=base.x0, tp=base.tp0_k, tb=base.tb0_k, y=base.y0)
    warmup_s = max(
        60.0,
        6.0
        * (
            nominal_times["stage1"].product_tau_s
            + nominal_times["stage2"].product_tau_s
        ),
    )
    return _advance_process_states(stage1, stage2, base_input, nominal_times, warmup_s)


def _advance_process_states(
    stage1: _StageState,
    stage2: _StageState,
    step_input: SimulationInput,
    nominal_times: dict[str, _StageSettings],
    duration_s: float,
) -> tuple[_StageState, _StageState]:
    substep_s = min(0.5, max(duration_s / 20.0, 0.05))
    elapsed = 0.0
    while elapsed < duration_s - 1e-12:
        dt = min(substep_s, duration_s - elapsed)
        stage1, stage2 = _advance_pair_once(stage1, stage2, step_input, nominal_times, dt)
        elapsed += dt
    return stage1, stage2


def _advance_pair_once(
    stage1: _StageState,
    stage2: _StageState,
    step_input: SimulationInput,
    nominal_times: dict[str, _StageSettings],
    dt: float,
) -> tuple[_StageState, _StageState]:
    d = _build_derived(step_input)
    stage1_next = _advance_stage(
        current=stage1,
        inlet_x=d.x0,
        inlet_tp=d.tp0_k,
        inlet_tb=d.tb0_k,
        inlet_y=d.y0,
        step_input=step_input,
        d=d,
        setting=nominal_times["stage1"],
        dt=dt,
    )
    stage2_next = _advance_stage(
        current=stage2,
        inlet_x=stage1_next.x,
        inlet_tp=stage1_next.tp,
        inlet_tb=stage1_next.tb,
        inlet_y=stage1_next.y,
        step_input=step_input,
        d=d,
        setting=nominal_times["stage2"],
        dt=dt,
    )
    return stage1_next, stage2_next


def _advance_stage(
    *,
    current: _StageState,
    inlet_x: float,
    inlet_tp: float,
    inlet_tb: float,
    inlet_y: float,
    step_input: SimulationInput,
    d: Any,
    setting: _StageSettings,
    dt: float,
) -> _StageState:
    product_hold_up, air_hold_up = _stage_hold_ups(step_input, setting)
    air_to_solid_ratio = air_hold_up / product_hold_up
    snap = _rea_snapshot(
        current.x,
        current.tp,
        current.tb,
        current.y,
        step_input.material,
        d,
        air_to_solid_ratio=air_to_solid_ratio,
        heat_loss_factor_w_kgk=d.heat_loss_factor_w_kgk * setting.heat_loss_share,
        transfer_scale=setting.transfer_scale,
    )

    dx_dt = (d.solids_rate_kg_s / product_hold_up) * (inlet_x - current.x) + snap["dXdt"]
    dtp_dt = (d.solids_rate_kg_s / product_hold_up) * (inlet_tp - current.tp) + snap["dTpdt_K_s"]
    dy_dt = (d.dry_air_mass_flow_kg_s / air_hold_up) * (inlet_y - current.y) + snap["dYdt"]
    dtb_dt = (d.dry_air_mass_flow_kg_s / air_hold_up) * (inlet_tb - current.tb) + snap["dTbdt_K_s"]

    next_x = max(snap["Xe"], current.x + dx_dt * dt)
    next_tp = float(np.clip(current.tp + dtp_dt * dt, 273.15, 473.15))
    next_y = float(max(current.y + dy_dt * dt, d.y0))
    next_tb = float(np.clip(current.tb + dtb_dt * dt, d.tu_k, d.tb0_k + 15.0))
    return _StageState(x=float(next_x), tp=next_tp, tb=next_tb, y=next_y)


def _current_stage_metrics(
    stage1: _StageState,
    stage2: _StageState,
    step_input: SimulationInput,
    nominal_times: dict[str, _StageSettings],
) -> dict[str, float]:
    d = _build_derived(step_input)
    product_hold_up_1, air_hold_up_1 = _stage_hold_ups(step_input, nominal_times["stage1"])
    product_hold_up_2, air_hold_up_2 = _stage_hold_ups(step_input, nominal_times["stage2"])
    snap1 = _rea_snapshot(
        stage1.x,
        stage1.tp,
        stage1.tb,
        stage1.y,
        step_input.material,
        d,
        air_to_solid_ratio=air_hold_up_1 / product_hold_up_1,
        heat_loss_factor_w_kgk=d.heat_loss_factor_w_kgk * nominal_times["stage1"].heat_loss_share,
        transfer_scale=nominal_times["stage1"].transfer_scale,
    )
    snap2 = _rea_snapshot(
        stage2.x,
        stage2.tp,
        stage2.tb,
        stage2.y,
        step_input.material,
        d,
        air_to_solid_ratio=air_hold_up_2 / product_hold_up_2,
        heat_loss_factor_w_kgk=d.heat_loss_factor_w_kgk * nominal_times["stage2"].heat_loss_share,
        transfer_scale=nominal_times["stage2"].transfer_scale,
    )
    evap1 = snap1["evap_rate_kg_per_kg_s"] * product_hold_up_1
    evap2 = snap2["evap_rate_kg_per_kg_s"] * product_hold_up_2
    latent1 = evap1 * _latent_heat_vaporization(stage1.tb)
    latent2 = evap2 * _latent_heat_vaporization(stage2.tb)
    return {
        "outlet_RH": snap2["RH"],
        "q_loss_w": snap1["q_loss_w"] * product_hold_up_1 + snap2["q_loss_w"] * product_hold_up_2,
        "evaporation_rate_kg_s": evap1 + evap2,
        "latent_load_w": latent1 + latent2,
        "dry_solids_rate_kg_s": d.solids_rate_kg_s,
        "air_mass_flow_rate_kg_s": d.humid_air_mass_flow_kg_s,
    }


def _extract_target_outputs(result: Any) -> dict[str, float | None]:
    outlet_time = result.metrics["outlet_time"]
    if outlet_time is not None:
        outlet_row = result.series.loc[result.series["t"] >= outlet_time].iloc[0]
    else:
        outlet_row = result.series.iloc[-1]

    return {
        "target_outlet_X": float(result.metrics["outlet_X"] or outlet_row["X"]),
        "target_outlet_Tb": float(result.metrics["outlet_Tb"] or outlet_row["Tb"]),
        "target_outlet_RH": float(result.metrics["outlet_RH"] or outlet_row["RH"]),
        "target_outlet_Y": float(result.metrics.get("outlet_Y") or outlet_row["Y"]),
        "target_outlet_Tp": float(result.metrics["outlet_Tp"] or outlet_row["Tp"]),
        "target_outlet_time_s": float(result.metrics["outlet_time"] or outlet_row["t"]),
    }


def _deduplicate_warnings(warnings: list[str]) -> list[str]:
    unique: list[str] = []
    for warning in warnings:
        if warning not in unique:
            unique.append(warning)
    return unique
