from __future__ import annotations

from math import inf
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go


APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from ui_state import (
    BASE_FIELD_ORDER,
    FIELD_LABELS,
    SimulationResult,
    results_to_metrics_frame,
    results_to_timeseries_frame,
)


CHART_SERIES_COLORS = ["#D46A2E", "#3D7A62", "#3E5C76", "#B88B4A", "#7A4E6D"]
CHART_GROUPS = {
    "Thermisch": [
        ("Tb_C", "Lufttemperatur", "degC"),
        ("Tp_C", "Partikeltemperatur", "degC"),
    ],
    "Feuchte": [
        ("X", "Produktfeuchte X", "-"),
        ("RH", "Relative Luftfeuchte", "-"),
        ("Y_gkg", "Absolute Luftfeuchte", "g/kg"),
    ],
    "Partikel": [
        ("dp_um", "Partikeldurchmesser", "um"),
        ("vp", "Tropfengeschwindigkeit", "m/s"),
    ],
}


def to_display_metrics(metrics_frame: pd.DataFrame) -> pd.DataFrame:
    display = metrics_frame.copy()
    for column in ("outlet_Tb", "outlet_Tp", "final_Tb", "final_Tp"):
        if column in display:
            display[column] = display[column] - 273.0
    return display


def chart_frame(results: list[SimulationResult]) -> pd.DataFrame:
    frame = results_to_timeseries_frame(results).copy()
    frame["Tb_C"] = frame["Tb"] - 273.0
    frame["Tp_C"] = frame["Tp"] - 273.0
    frame["dp_um"] = frame["dp"] * 1_000_000.0
    frame["Y_gkg"] = frame["Y"] * 1000.0
    return frame


def axis_label(axis_key: str) -> str:
    return "Höhe [m]" if axis_key == "height" else "Zeit [s]"


def field_display_name(field: str) -> str:
    return FIELD_LABELS[field].split(" [", 1)[0]


def _format_input_value(field: str, value: Any) -> str:
    if field == "material":
        return str(value)
    if field == "feed_total_solids":
        return f"{float(value):.2f}"
    if field == "droplet_size_um":
        return f"{float(value):.0f}"
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def _value_changed(values: list[Any]) -> bool:
    first = values[0]
    if isinstance(first, str):
        return any(value != first for value in values[1:])
    return any(abs(float(value) - float(first)) > 1e-9 for value in values[1:])


def scenario_display_map(results: list[SimulationResult]) -> dict[str, str]:
    if len(results) <= 1:
        return {result.label: result.label for result in results}

    varying_fields: list[str] = []
    for field in BASE_FIELD_ORDER:
        values = [getattr(result.inputs, field) for result in results]
        if _value_changed(values):
            varying_fields.append(field)

    if not varying_fields:
        return {result.label: result.label for result in results}

    display_map: dict[str, str] = {}
    max_fields = 3
    for result in results:
        parts = [
            f"{field_display_name(field)} {_format_input_value(field, getattr(result.inputs, field))}"
            for field in varying_fields[:max_fields]
        ]
        if len(varying_fields) > max_fields:
            parts.append(f"+{len(varying_fields) - max_fields} weitere")
        display_map[result.label] = f"{result.label} ({', '.join(parts)})"
    return display_map


def series_color_map(scenarios: list[str]) -> dict[str, str]:
    return {
        scenario: CHART_SERIES_COLORS[index % len(CHART_SERIES_COLORS)]
        for index, scenario in enumerate(scenarios)
    }


def build_chart_figure(
    subset: pd.DataFrame,
    x_axis: str,
    y_column: str,
    title: str,
    unit: str,
    color_map: dict[str, str],
    display_map: dict[str, str],
    target_outlet_x: float,
) -> go.Figure:
    figure = go.Figure()
    x_label = axis_label(x_axis)
    y_label = f"{title} [{unit}]"

    for scenario in subset["scenario"].unique():
        scenario_frame = subset[subset["scenario"] == scenario]
        legend_label = display_map.get(scenario, scenario)
        figure.add_trace(
            go.Scatter(
                x=scenario_frame[x_axis],
                y=scenario_frame[y_column],
                mode="lines",
                name=legend_label,
                line=dict(color=color_map[scenario], width=3),
                hovertemplate=(
                    f"<b>{legend_label}</b><br>{x_label}: %{{x:.2f}}<br>{y_label}: %{{y:.3f}}<extra></extra>"
                ),
            )
        )

    if y_column == "X":
        figure.add_hline(
            y=target_outlet_x,
            line_dash="dash",
            line_color="#D46A2E",
            annotation_text=f"Ziel X = {target_outlet_x:.3f}",
            annotation_position="top left",
        )

    figure.update_layout(
        height=360,
        margin=dict(l=12, r=12, t=30, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    figure.update_xaxes(
        title=x_label,
        showline=True,
        linecolor="#D9D9D9",
        gridcolor="rgba(0,0,0,0.08)",
        zeroline=False,
    )
    figure.update_yaxes(
        title=y_label,
        showline=True,
        linecolor="#D9D9D9",
        gridcolor="rgba(0,0,0,0.08)",
        zeroline=False,
    )
    return figure


def assessment_rows(results: list[SimulationResult], target_outlet_x: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        outlet_x = result.metrics["outlet_X"]
        drying_height = result.metrics["drying_height"]
        outlet_tb = result.metrics["outlet_Tb"]
        target_met = outlet_x is not None and outlet_x <= target_outlet_x
        dried_in_tower = drying_height is not None and drying_height <= result.inputs.dryer_height_m
        rows.append(
            {
                "scenario": result.label,
                "target_met": target_met,
                "dried_in_tower": dried_in_tower,
                "outlet_X": outlet_x,
                "drying_height": drying_height,
                "outlet_Tb_C": outlet_tb - 273.0 if outlet_tb is not None else None,
                "drying_time": result.metrics["drying_time"],
            }
        )
    return rows


def build_executive_summary(results: list[SimulationResult], target_outlet_x: float) -> dict[str, str]:
    rows = assessment_rows(results, target_outlet_x)
    target_ok = [row["scenario"] for row in rows if row["target_met"]]
    dried_ok = [row["scenario"] for row in rows if row["dried_in_tower"]]
    best = choose_best_scenario(rows)

    target_text = ", ".join(target_ok) if target_ok else "Kein Szenario"
    dried_text = ", ".join(dried_ok) if dried_ok else "Kein Szenario"

    if best is None:
        best_text = "Keine belastbare Einordnung möglich."
    else:
        best_text = (
            f"{best['scenario']} mit X Austritt {best['outlet_X']:.4f}"
            if best["outlet_X"] is not None
            else best["scenario"]
        )

    return {
        "target": target_text,
        "drying": dried_text,
        "best": best_text,
        "method": (
            "Einordnung nach Ziel-X, Trocknung vor Austritt und danach nach niedrigerer "
            "Austrittsfeuchte sowie geringerer Trocknungshöhe."
        ),
    }


def choose_best_scenario(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None

    def rank(row: dict[str, Any]) -> tuple[float, float, float, float]:
        outlet_x = row["outlet_X"] if row["outlet_X"] is not None else inf
        drying_height = row["drying_height"] if row["drying_height"] is not None else inf
        drying_time = row["drying_time"] if row["drying_time"] is not None else inf
        status_rank = (
            0
            if row["target_met"] and row["dried_in_tower"]
            else 1
            if row["target_met"]
            else 2
            if row["dried_in_tower"]
            else 3
        )
        return (status_rank, outlet_x, drying_height, drying_time)

    return min(rows, key=rank)


def build_kpi_frame(results: list[SimulationResult], target_outlet_x: float) -> pd.DataFrame:
    rows = assessment_rows(results, target_outlet_x)
    base = rows[0]
    display_rows: list[dict[str, Any]] = []
    for row in rows:
        display_rows.append(
            {
                "Szenario": row["scenario"],
                "Ziel-X eingehalten": "Ja" if row["target_met"] else "Nein",
                "Trocknung vor Austritt": "Ja" if row["dried_in_tower"] else "Nein",
                "Austritts-X [-]": row["outlet_X"],
                "Austritts-Tb [degC]": row["outlet_Tb_C"],
                "Trocknungshöhe [m]": row["drying_height"],
                "Trocknungszeit [s]": row["drying_time"],
                "Delta X zur Basis": (
                    None
                    if row["outlet_X"] is None or base["outlet_X"] is None
                    else row["outlet_X"] - base["outlet_X"]
                ),
                "Delta Trocknungshöhe [m]": (
                    None
                    if row["drying_height"] is None or base["drying_height"] is None
                    else row["drying_height"] - base["drying_height"]
                ),
            }
        )
    return pd.DataFrame(display_rows)


def build_inputs_frame(results: list[SimulationResult]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"scenario": result.label, **result.inputs.to_dict()} for result in results]
    ).rename(columns={"scenario": "Szenario"})


def build_detailed_metrics_frame(results: list[SimulationResult]) -> pd.DataFrame:
    return to_display_metrics(results_to_metrics_frame(results)).rename(
        columns={
            "scenario": "Szenario",
            "drying_time": "Trocknungszeit [s]",
            "drying_height": "Trocknungshöhe [m]",
            "outlet_time": "Austrittszeit [s]",
            "outlet_X": "X am Austritt [-]",
            "outlet_Tb": "Tb am Austritt [degC]",
            "outlet_Tp": "Tp am Austritt [degC]",
            "outlet_RH": "RH am Austritt [-]",
            "final_X": "X Ende [-]",
            "final_Tb": "Tb Ende [degC]",
            "final_Tp": "Tp Ende [degC]",
            "final_RH": "RH Ende [-]",
        }
    )
