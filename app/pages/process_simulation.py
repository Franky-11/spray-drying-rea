from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(APP_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from core import (
    ProcessEvent,
    ProcessSimulationInput,
    build_stepwise_inputs,
    run_process_simulation,
)
from ui_state import (
    DEFAULT_INPUT,
    MATERIAL_FIELDS,
    PROCESS_FIELDS,
    EXPERT_FIELDS,
    build_base_input,
    initialize_session_state,
    render_field_input,
)


PROCESS_SIM_RESULT_KEY = "process_simulation_result"
PROCESS_SIM_DURATION_KEY = "process_sim_duration_s"
PROCESS_SIM_DT_KEY = "process_sim_time_step_s"
PROCESS_SIM_TARGET_KEY = "process_sim_target_x"
PROCESS_SIM_PRESET_KEY = "process_sim_preset"
PROCESS_SIM_EVENTS_DATA_KEY = "process_sim_events_data"
PROCESS_SIM_EVENT_COUNT_KEY = "process_sim_event_count"

PROCESS_PRESETS: dict[str, dict[str, Any]] = {
    "Benutzerdefiniert": {
        "duration_s": 300.0,
        "time_step_s": 10.0,
        "target_outlet_x": 0.04,
        "events": [],
    },
    "Tin-Sprung": {
        "duration_s": 300.0,
        "time_step_s": 10.0,
        "target_outlet_x": 0.04,
        "events": [
            {"time_s": 60.0, "inlet_air_temp_c": 200.0, "label": "Tin hoch"},
            {"time_s": 180.0, "inlet_air_temp_c": 180.0, "label": "Tin zurück"},
        ],
    },
    "Feuchte Sommerluft": {
        "duration_s": 300.0,
        "time_step_s": 10.0,
        "target_outlet_x": 0.04,
        "events": [
            {
                "time_s": 120.0,
                "inlet_abs_humidity_g_kg": 12.0,
                "label": "Sommerregen",
            }
        ],
    },
    "TS-Schwankung": {
        "duration_s": 500.0,
        "time_step_s": 10.0,
        "target_outlet_x": 0.04,
        "events": [
            {"time_s": 200.0, "feed_total_solids": 0.3, "label": "TS runter"},
            {"time_s": 350.0, "feed_total_solids": 0.5, "label": "TS zurück"},
        ],
    },
}

EVENT_COLUMNS = [
    "time_s",
    "label",
    "inlet_air_temp_c",
    "air_flow_m3_h",
    "inlet_abs_humidity_g_kg",
    "feed_rate_kg_h",
    "feed_total_solids",
]


def initialize_process_sim_state() -> None:
    preset = PROCESS_PRESETS["Benutzerdefiniert"]
    st.session_state.setdefault(PROCESS_SIM_DURATION_KEY, preset["duration_s"])
    st.session_state.setdefault(PROCESS_SIM_DT_KEY, preset["time_step_s"])
    st.session_state.setdefault(PROCESS_SIM_TARGET_KEY, preset["target_outlet_x"])
    st.session_state.setdefault(PROCESS_SIM_PRESET_KEY, "Benutzerdefiniert")
    if PROCESS_SIM_EVENTS_DATA_KEY not in st.session_state:
        _set_event_widgets(preset["events"])


def render_field_grid(fields: list[str], key_prefix: str = "base") -> None:
    columns = st.columns(2)
    for index, field in enumerate(fields):
        with columns[index % 2]:
            render_field_input(field, f"{key_prefix}_{field}")


def apply_process_preset() -> None:
    preset_name = str(st.session_state[PROCESS_SIM_PRESET_KEY])
    preset = PROCESS_PRESETS[preset_name]
    st.session_state[PROCESS_SIM_DURATION_KEY] = preset["duration_s"]
    st.session_state[PROCESS_SIM_DT_KEY] = preset["time_step_s"]
    st.session_state[PROCESS_SIM_TARGET_KEY] = preset["target_outlet_x"]
    _set_event_widgets(preset["events"])
    st.session_state.pop(PROCESS_SIM_RESULT_KEY, None)


def ensure_base_defaults(fields: list[str]) -> None:
    for field in fields:
        key = f"base_{field}"
        if key not in st.session_state or st.session_state[key] is None:
            st.session_state[key] = getattr(DEFAULT_INPUT, field)


def _events_frame(events: list[dict[str, Any]]) -> pd.DataFrame:
    if not events:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    return pd.DataFrame(events, columns=EVENT_COLUMNS)


def _set_event_widgets(events: list[dict[str, Any]]) -> None:
    st.session_state[PROCESS_SIM_EVENTS_DATA_KEY] = list(events)
    st.session_state[PROCESS_SIM_EVENT_COUNT_KEY] = len(events)
    for index, event in enumerate(events):
        st.session_state[f"process_event_{index}_time_s"] = "" if event.get("time_s") is None else str(event["time_s"])
        st.session_state[f"process_event_{index}_label"] = str(event.get("label", ""))
        for field in EVENT_COLUMNS[2:]:
            value = event.get(field)
            st.session_state[f"process_event_{index}_{field}"] = "" if value is None else str(value)


def _collect_events_from_state() -> tuple[list[ProcessEvent], list[str]]:
    events: list[ProcessEvent] = []
    errors: list[str] = []
    event_count = int(st.session_state.get(PROCESS_SIM_EVENT_COUNT_KEY, 0))
    for index in range(event_count):
        time_raw = str(st.session_state.get(f"process_event_{index}_time_s", "")).strip()
        label = str(st.session_state.get(f"process_event_{index}_label", "")).strip()
        field_payload: dict[str, float | None] = {}
        any_payload = bool(label)
        for field in EVENT_COLUMNS[2:]:
            raw_value = str(st.session_state.get(f"process_event_{index}_{field}", "")).strip()
            if raw_value == "":
                field_payload[field] = None
                continue
            try:
                field_payload[field] = float(raw_value)
                any_payload = True
            except ValueError:
                errors.append(f"Event {index + 1}: `{field}` ist keine Zahl.")
                field_payload[field] = None

        if time_raw == "" and not any_payload:
            continue
        if time_raw == "":
            errors.append(f"Event {index + 1}: `time_s` fehlt.")
            continue
        try:
            time_value = float(time_raw)
        except ValueError:
            errors.append(f"Event {index + 1}: `time_s` ist keine Zahl.")
            continue

        events.append(
            ProcessEvent(
                time_s=time_value,
                label=label,
                **field_payload,
            )
        )
    return events, errors


def _add_event() -> None:
    event_count = int(st.session_state.get(PROCESS_SIM_EVENT_COUNT_KEY, 0))
    st.session_state[PROCESS_SIM_EVENT_COUNT_KEY] = event_count + 1
    st.session_state[f"process_event_{event_count}_time_s"] = ""
    st.session_state[f"process_event_{event_count}_label"] = ""
    for field in EVENT_COLUMNS[2:]:
        st.session_state[f"process_event_{event_count}_{field}"] = ""


def _remove_event(index: int) -> None:
    events, _ = _collect_events_from_state()
    if 0 <= index < len(events):
        events.pop(index)
    _set_event_widgets(
        [
            {
                "time_s": event.time_s,
                "label": event.label,
                **{field: getattr(event, field) for field in EVENT_COLUMNS[2:]},
            }
            for event in events
        ]
    )


def _single_axis_chart(
    frame: pd.DataFrame,
    columns: list[tuple[str, str, str]],
) -> go.Figure:
    figure = go.Figure()
    colors = ["#D46A2E", "#3D7A62", "#3E5C76", "#B88B4A", "#7A4E6D"]
    for index, (column, label, unit) in enumerate(columns):
        figure.add_trace(
            go.Scatter(
                x=frame["t"],
                y=frame[column],
                mode="lines",
                name=f"{label} [{unit}]",
                line=dict(color=colors[index % len(colors)], width=3),
                hovertemplate=(
                    f"<b>{label}</b><br>Zeit: %{{x:.1f}} s<br>Wert: %{{y:.3f}} {unit}<extra></extra>"
                ),
            )
        )
    figure.update_layout(
        height=320,
        margin=dict(l=12, r=12, t=12, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
    )
    figure.update_xaxes(title="Zeit [s]", showline=True, linecolor="#D9D9D9", gridcolor="rgba(0,0,0,0.08)")
    figure.update_yaxes(showline=True, linecolor="#D9D9D9", gridcolor="rgba(0,0,0,0.08)")
    return figure


def _dual_axis_chart(
    frame: pd.DataFrame,
    *,
    left: tuple[str, str, str],
    right: tuple[str, str, str],
    left_color: str = "#D46A2E",
    right_color: str = "#3D7A62",
    target_right_value: float | None = None,
    target_right_label: str | None = None,
    left_shape: str = "linear",
    right_shape: str = "linear",
    left_range_override: list[float] | None = None,
    right_range_override: list[float] | None = None,
) -> go.Figure:
    figure = make_subplots(specs=[[{"secondary_y": True}]])
    left_column, left_label, left_unit = left
    right_column, right_label, right_unit = right

    figure.add_trace(
        go.Scatter(
            x=frame["t"],
            y=frame[left_column],
            mode="lines",
            name=f"{left_label} [{left_unit}]",
            line=dict(color=left_color, width=3, shape=left_shape),
            hovertemplate=(
                f"<b>{left_label}</b><br>Zeit: %{{x:.1f}} s<br>Wert: %{{y:.3f}} {left_unit}<extra></extra>"
            ),
        ),
        secondary_y=False,
    )
    figure.add_trace(
        go.Scatter(
            x=frame["t"],
            y=frame[right_column],
            mode="lines",
            name=f"{right_label} [{right_unit}]",
            line=dict(color=right_color, width=3, dash="dot", shape=right_shape),
            hovertemplate=(
                f"<b>{right_label}</b><br>Zeit: %{{x:.1f}} s<br>Wert: %{{y:.3f}} {right_unit}<extra></extra>"
            ),
        ),
        secondary_y=True,
    )

    if target_right_value is not None:
        figure.add_hline(
            y=target_right_value,
            line_dash="dash",
            line_color=right_color,
            annotation_text=target_right_label or f"Ziel {target_right_value:.3f}",
            annotation_position="top left",
            secondary_y=True,
        )

    left_range = left_range_override or _axis_range(frame[left_column])
    right_values = frame[right_column]
    if target_right_value is not None:
        right_values = pd.concat([right_values, pd.Series([target_right_value])], ignore_index=True)
    right_range = right_range_override or _axis_range(right_values)

    figure.update_layout(
        height=320,
        margin=dict(l=12, r=12, t=12, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
    )
    figure.update_xaxes(title="Zeit [s]", showline=True, linecolor="#D9D9D9", gridcolor="rgba(0,0,0,0.08)")
    figure.update_yaxes(
        title=f"{left_label} [{left_unit}]",
        showline=True,
        linecolor=left_color,
        tickfont=dict(color=left_color),
        title_font=dict(color=left_color),
        gridcolor="rgba(0,0,0,0.08)",
        range=left_range,
        secondary_y=False,
    )
    figure.update_yaxes(
        title=f"{right_label} [{right_unit}]",
        showline=True,
        linecolor=right_color,
        tickfont=dict(color=right_color),
        title_font=dict(color=right_color),
        gridcolor="rgba(0,0,0,0.04)",
        range=right_range,
        secondary_y=True,
    )
    return figure


def _axis_range(
    values: pd.Series,
    *,
    lower_pad: float = 0.15,
    upper_pad: float = 0.15,
) -> list[float]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return [0.0, 1.0]

    minimum = float(numeric.min())
    maximum = float(numeric.max())
    if minimum == maximum:
        padding = max(abs(minimum) * 0.1, 1.0)
        return [minimum - padding, maximum + padding]

    span = maximum - minimum
    return [minimum - span * lower_pad, maximum + span * upper_pad]


def _display_frame(result_frame: pd.DataFrame) -> pd.DataFrame:
    frame = result_frame.copy()
    for column in ("target_outlet_Tb", "target_outlet_Tp", "outlet_Tb", "outlet_Tp"):
        frame[f"{column}_C"] = frame[column] - 273.0
    frame["target_outlet_Y_gkg"] = frame["target_outlet_Y"] * 1000.0
    frame["outlet_Y_gkg"] = frame["outlet_Y"] * 1000.0
    frame["target_outlet_RH_pct"] = frame["target_outlet_RH"] * 100.0
    frame["outlet_RH_pct"] = frame["outlet_RH"] * 100.0
    frame["target_outlet_X_pct"] = frame["target_outlet_X"] * 100.0
    frame["outlet_X_pct"] = frame["outlet_X"] * 100.0
    frame["moisture_error_pct"] = frame["moisture_error"] * 100.0
    frame["feed_total_solids_pct"] = frame["feed_total_solids"] * 100.0
    frame["outlet_powder_rate_kg_h"] = frame["feed_rate_kg_h"] * frame["feed_total_solids"] * (1.0 + frame["outlet_X"])
    return frame


def _segment_preview_frame(schedule: pd.DataFrame, duration_s: float) -> pd.DataFrame:
    if schedule.empty:
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for index, row in schedule.iterrows():
        start_s = float(row["t"])
        if index + 1 < len(schedule):
            end_s = float(schedule.iloc[index + 1]["t"])
        else:
            end_s = float(duration_s)
        if end_s <= start_s:
            continue
        rows.append(
            {
                "von [s]": start_s,
                "bis [s]": end_s,
                "Label": row["event_label"],
                "Tin [degC]": float(row["inlet_air_temp_c"]),
                "Luftstrom [m^3/h]": float(row["air_flow_m3_h"]),
                "Zuluftfeuchte [g/kg]": float(row["inlet_abs_humidity_g_kg"]),
                "Feedstrom [kg/h]": float(row["feed_rate_kg_h"]),
                "Feed-TS [-]": float(row["feed_total_solids"]),
            }
        )
    return pd.DataFrame(rows)


initialize_session_state()
initialize_process_sim_state()
ensure_base_defaults(EXPERT_FIELDS)

st.title("Prozesssimulation")
st.write(
    "Diese Seite erweitert den stationären REA-Kern um eine diskrete Open-Loop-Prozesssimulation "
    "mit stückkonstanten Störungen, Totzeit/Lag und diagnostischen Bilanzgrößen."
)

st.subheader("A. Basisfall")
st.caption(
    "Material, Tropfengröße und Feedtemperatur bleiben innerhalb einer Prozesssimulation konstant. "
    "Zeitabhängig sind nur Tin, Luftstrom, absolute Zuluftfeuchte, Feedstrom und Feed-TS."
)

with st.expander("Basisfall anpassen", expanded=True):
    st.markdown("**Material und Feed**")
    render_field_grid(MATERIAL_FIELDS)
    st.markdown("**Prozessparameter**")
    render_field_grid(PROCESS_FIELDS)
    with st.expander("Expertenparameter", expanded=False):
        st.caption(
            "Die Expertenfelder sind mit den Modell-Defaults vorbelegt. "
            "Nur ändern, wenn du gezielt Geometrie-, Stoffwert- oder Modellannahmen variieren willst."
        )
        render_field_grid(EXPERT_FIELDS)

st.divider()
st.subheader("B. Simulationsprofil")
left, middle, right = st.columns([1.1, 1.0, 1.0])
with left:
    st.selectbox(
        "Preset",
        options=tuple(PROCESS_PRESETS),
        key=PROCESS_SIM_PRESET_KEY,
        on_change=apply_process_preset,
    )
with middle:
    st.number_input(
        "Simulationsdauer [s]",
        min_value=10.0,
        step=10.0,
        key=PROCESS_SIM_DURATION_KEY,
    )
with right:
    st.number_input(
        "Zeitschritt [s]",
        min_value=1.0,
        step=1.0,
        key=PROCESS_SIM_DT_KEY,
    )

st.number_input(
    "Ziel-Austrittsfeuchte X [-]",
    min_value=0.0,
    step=0.005,
    key=PROCESS_SIM_TARGET_KEY,
)

st.divider()
st.subheader("C. Event-Schedule")
st.caption(
    "Jede Zeile startet ab `time_s` einen neuen Abschnitt. Leere Felder übernehmen den vorherigen Wert."
)
st.caption(
    "Ja, du kannst Abschnitte aneinanderhängen: einfach mehrere Zeilen mit steigenden Zeiten anlegen. "
    "Beispiel: 60 s Tin hoch, 120 s Feedstrom hoch, 180 s Tin zurück."
)
event_count = int(st.session_state.get(PROCESS_SIM_EVENT_COUNT_KEY, 0))
if event_count == 0:
    st.info("Noch keine Events angelegt. Mit `Event hinzufügen` kannst du einen neuen Abschnitt definieren.")

for index in range(event_count):
    title = f"Event {index + 1}"
    label_value = str(st.session_state.get(f"process_event_{index}_label", "")).strip()
    time_value = str(st.session_state.get(f"process_event_{index}_time_s", "")).strip()
    if label_value:
        title += f" · {label_value}"
    elif time_value:
        title += f" · ab {time_value} s"
    with st.expander(title, expanded=index == 0):
        top_left, top_right, top_remove = st.columns([1.0, 1.4, 0.8])
        with top_left:
            st.text_input("time_s [s]", key=f"process_event_{index}_time_s", placeholder="z. B. 60")
        with top_right:
            st.text_input("Label", key=f"process_event_{index}_label", placeholder="z. B. Tin hoch")
        with top_remove:
            st.write("")
            st.button(
                "Entfernen",
                key=f"remove_process_event_{index}",
                on_click=_remove_event,
                args=(index,),
                use_container_width=True,
            )

        row1 = st.columns(3)
        with row1[0]:
            st.text_input("Tin [degC]", key=f"process_event_{index}_inlet_air_temp_c", placeholder="leer = fortschreiben")
        with row1[1]:
            st.text_input("Zuluftfeuchte [g/kg]", key=f"process_event_{index}_inlet_abs_humidity_g_kg", placeholder="leer = fortschreiben")
        with row1[2]:
            st.text_input("Luftstrom [m^3/h]", key=f"process_event_{index}_air_flow_m3_h", placeholder="leer = fortschreiben")

        row2 = st.columns(2)
        with row2[0]:
            st.text_input("Feedstrom [kg/h]", key=f"process_event_{index}_feed_rate_kg_h", placeholder="leer = fortschreiben")
        with row2[1]:
            st.text_input("Feed-TS [-]", key=f"process_event_{index}_feed_total_solids", placeholder="leer = fortschreiben")

control_left, control_right = st.columns([1.0, 1.0])
with control_left:
    st.button("Event hinzufügen", on_click=_add_event, use_container_width=True)
with control_right:
    if st.button("Events aus Widgets übernehmen", use_container_width=True):
        current_events, current_errors = _collect_events_from_state()
        if current_errors:
            for error in current_errors:
                st.error(error)
        else:
            _set_event_widgets(
                [
                    {
                        "time_s": event.time_s,
                        "label": event.label,
                        **{field: getattr(event, field) for field in EVENT_COLUMNS[2:]},
                    }
                    for event in current_events
                ]
            )
            st.success("Events übernommen.")

collected_events, collected_errors = _collect_events_from_state()
if collected_errors:
    for error in collected_errors:
        st.warning(error)

preview_input = ProcessSimulationInput(
    base_input=build_base_input(),
    events=collected_events,
    duration_s=float(st.session_state[PROCESS_SIM_DURATION_KEY]),
    time_step_s=float(st.session_state[PROCESS_SIM_DT_KEY]),
    target_outlet_x=float(st.session_state[PROCESS_SIM_TARGET_KEY]),
)
schedule_preview = build_stepwise_inputs(preview_input)
segment_preview = _segment_preview_frame(schedule_preview, preview_input.duration_s)

with st.expander("Aufgelöste Abschnittsvorschau", expanded=True):
    st.caption(
        "Diese Tabelle zeigt, welche Werte in welchem Zeitabschnitt tatsächlich aktiv sind. "
        "Damit ist direkt sichtbar, wie Basisfall und Events zusammenwirken."
    )
    st.dataframe(segment_preview, use_container_width=True, hide_index=True)

st.divider()
if st.button("Prozesssimulation rechnen", type="primary", use_container_width=True):
    try:
        sim_input = preview_input
        st.session_state[PROCESS_SIM_RESULT_KEY] = run_process_simulation(sim_input)
        st.success("Prozesssimulation abgeschlossen.")
    except Exception as exc:
        st.session_state.pop(PROCESS_SIM_RESULT_KEY, None)
        st.error(str(exc))

result = st.session_state.get(PROCESS_SIM_RESULT_KEY)
if not result:
    st.info("Noch keine Prozesssimulation gerechnet.")
    st.stop()

if result.warnings:
    with st.expander("Warnungen und Modellgrenzen", expanded=True):
        for warning in result.warnings:
            st.warning(warning)

series = _display_frame(result.series)
kpis = result.kpis

st.divider()
st.subheader("D. KPI-Überblick")
kpi_left, kpi_mid, kpi_right, kpi_four = st.columns(4)
with kpi_left:
    st.metric("Finales Austritts-X", f"{kpis['final_outlet_X']:.4f}")
with kpi_mid:
    st.metric("Finale Austritts-Tb", f"{kpis['final_outlet_Tb'] - 273.0:.1f} degC")
with kpi_right:
    st.metric("Finale Abluftfeuchte", f"{kpis['final_outlet_Y'] * 1000.0:.2f} g/kg")
with kpi_four:
    st.metric("Finaler Wärmeverlust", f"{kpis['final_q_loss_w']:.0f} W")

st.divider()
st.subheader("E. Zeitreihen")
tab_process, tab_diagnostics = st.tabs(["Prozessbild", "Diagnostik"])

with tab_process:
    st.caption(
        "Oben stehen die vorgegebenen Eingangsprofile. Darunter folgen die dazu passenden Reaktionen des Prozesses."
    )
    input_left, input_mid, input_right = st.columns(3)
    with input_left:
        st.markdown("**Input: Tin und Zuluftfeuchte**")
        st.plotly_chart(
            _dual_axis_chart(
                series,
                left=("inlet_air_temp_c", "Tin", "degC"),
                right=("inlet_abs_humidity_g_kg", "Zuluftfeuchte", "g/kg"),
                left_shape="hv",
                right_shape="hv",
                left_range_override=[150.0, 230.0],
                right_range_override=[0.0, 30.0],
            ),
            use_container_width=True,
        )
    with input_mid:
        st.markdown("**Input: Feedstrom und Feed-TS**")
        st.plotly_chart(
            _dual_axis_chart(
                series,
                left=("feed_rate_kg_h", "Feedstrom", "kg/h"),
                right=("feed_total_solids_pct", "Feed-TS", "%"),
                left_color="#3E5C76",
                right_color="#B88B4A",
                left_shape="hv",
                right_shape="hv",
                right_range_override=[20.0, 60.0],
            ),
            use_container_width=True,
        )
    with input_right:
        st.markdown("**Input: Luftmenge**")
        st.plotly_chart(
            _single_axis_chart(
                series,
                [("air_flow_m3_h", "Luftstrom", "m^3/h")],
            ),
            use_container_width=True,
        )

    output_left, output_mid, output_right = st.columns(3)
    output_left, output_right = st.columns(2)
    with output_left:
        st.markdown("**Reaktion: Abluft auf Tin/Zuluftfeuchte**")
        st.plotly_chart(
            _dual_axis_chart(
                series,
                left=("outlet_Tb_C", "Ablufttemperatur", "degC"),
                right=("outlet_Y_gkg", "Abluftfeuchte", "g/kg"),
                left_range_override=[60.0, 120.0],
                right_range_override=[0.0, 30.0],
            ),
            use_container_width=True,
        )
    with output_right:
        st.markdown("**Reaktion: Produktzustand**")
        st.plotly_chart(
            _dual_axis_chart(
                series,
                left=("outlet_Tp_C", "Partikeltemperatur", "degC"),
                right=("outlet_X_pct", "Austrittsfeuchte X", "%"),
                left_range_override=[60.0, 120.0],
                right_range_override=[0.0, 6.0],
                target_right_value=float(st.session_state[PROCESS_SIM_TARGET_KEY]) * 100.0,
                target_right_label=f"Ziel X = {float(st.session_state[PROCESS_SIM_TARGET_KEY]) * 100.0:.1f} %",
            ),
            use_container_width=True,
        )

with tab_diagnostics:
    diag_left, diag_right = st.columns(2)
    with diag_left:
        st.markdown("**REA-Zielgrößen**")
        st.plotly_chart(
            _dual_axis_chart(
                series,
                left=("target_outlet_Tb_C", "Target Ablufttemperatur", "degC"),
                right=("target_outlet_Y_gkg", "Target Abluftfeuchte", "g/kg"),
            ),
            use_container_width=True,
        )
        st.plotly_chart(
            _dual_axis_chart(
                series,
                left=("target_outlet_time_s", "Target Austrittszeit", "s"),
                right=("target_outlet_X_pct", "Target Austrittsfeuchte X", "%"),
                left_color="#3E5C76",
                right_color="#B88B4A",
                right_range_override=[0.0, 6.0],
            ),
            use_container_width=True,
        )
    with diag_right:
        st.markdown("**Bilanz- und Lastgrößen**")
        st.plotly_chart(
            _single_axis_chart(
                series,
                [
                    ("q_loss_w", "Wärmeverlust", "W"),
                    ("latent_load_w", "Latentlast", "W"),
                    ("evaporation_rate_kg_s", "Verdampfungsrate", "kg/s"),
                ],
            ),
            use_container_width=True,
        )
        st.markdown("**Feuchtediagnostik**")
        st.plotly_chart(
            _dual_axis_chart(
                series,
                left=("moisture_error_pct", "Feuchteabweichung", "%-Pkt"),
                right=("outlet_X_pct", "Austrittsfeuchte X", "%"),
                left_color="#D46A2E",
                right_color="#B88B4A",
                target_right_value=float(st.session_state[PROCESS_SIM_TARGET_KEY]) * 100.0,
                target_right_label=f"Ziel X = {float(st.session_state[PROCESS_SIM_TARGET_KEY]) * 100.0:.1f} %",
                right_range_override=[0.0, 6.0],
            ),
            use_container_width=True,
        )

    st.markdown("**Zeitreihentabelle**")
    st.dataframe(series, use_container_width=True, hide_index=True, height=420)

st.divider()
st.subheader("F. Export")
csv_bytes = series.to_csv(index=False).encode("utf-8")
st.download_button(
    "Zeitreihen als CSV",
    csv_bytes,
    "spruehtrockner_process_timeseries.csv",
    "text/csv",
)
