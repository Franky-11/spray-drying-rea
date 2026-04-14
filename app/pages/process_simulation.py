from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parents[2]
APP_DIR = Path(__file__).resolve().parents[1]
for candidate in (str(ROOT), str(APP_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from core import ProcessEvent, ProcessSimulationInput, run_process_simulation
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
PROCESS_SIM_EVENTS_EDITOR_KEY = "process_sim_events_editor"

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
    st.session_state.setdefault(PROCESS_SIM_EVENTS_DATA_KEY, _events_frame(preset["events"]))


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
    st.session_state[PROCESS_SIM_EVENTS_DATA_KEY] = _events_frame(preset["events"])
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


def _events_from_frame(frame: pd.DataFrame) -> list[ProcessEvent]:
    events: list[ProcessEvent] = []
    if frame.empty:
        return events

    sanitized = frame.copy()
    sanitized = sanitized.dropna(how="all")
    for _, row in sanitized.iterrows():
        time_value = row.get("time_s")
        if pd.isna(time_value):
            continue
        payload: dict[str, Any] = {"time_s": float(time_value)}
        label = row.get("label", "")
        payload["label"] = "" if pd.isna(label) else str(label)
        for field in EVENT_COLUMNS[2:]:
            value = row.get(field)
            payload[field] = None if pd.isna(value) else float(value)
        events.append(ProcessEvent(**payload))
    return events


def _process_chart(
    frame: pd.DataFrame,
    columns: list[tuple[str, str, str]],
    *,
    title: str,
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
        title=title,
        height=360,
        margin=dict(l=12, r=12, t=44, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFFFF",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    figure.update_xaxes(title="Zeit [s]", showline=True, linecolor="#D9D9D9", gridcolor="rgba(0,0,0,0.08)")
    figure.update_yaxes(showline=True, linecolor="#D9D9D9", gridcolor="rgba(0,0,0,0.08)")
    return figure


def _display_frame(result_frame: pd.DataFrame) -> pd.DataFrame:
    frame = result_frame.copy()
    for column in ("target_outlet_Tb", "target_outlet_Tp", "outlet_Tb", "outlet_Tp"):
        frame[f"{column}_C"] = frame[column] - 273.0
    frame["target_outlet_Y_gkg"] = frame["target_outlet_Y"] * 1000.0
    frame["outlet_Y_gkg"] = frame["outlet_Y"] * 1000.0
    return frame


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

event_frame = st.data_editor(
    st.session_state[PROCESS_SIM_EVENTS_DATA_KEY],
    key=PROCESS_SIM_EVENTS_EDITOR_KEY,
    use_container_width=True,
    num_rows="dynamic",
    hide_index=True,
    column_config={
        "time_s": st.column_config.NumberColumn("time_s [s]", min_value=0.0, step=10.0),
        "label": st.column_config.TextColumn("Label"),
        "inlet_air_temp_c": st.column_config.NumberColumn("Tin [degC]", step=1.0),
        "air_flow_m3_h": st.column_config.NumberColumn("Luftstrom [m^3/h]", step=1.0),
        "inlet_abs_humidity_g_kg": st.column_config.NumberColumn("Zuluftfeuchte [g/kg]", step=0.1),
        "feed_rate_kg_h": st.column_config.NumberColumn("Feedstrom [kg/h]", step=0.1),
        "feed_total_solids": st.column_config.NumberColumn("Feed-TS [-]", step=0.01),
    },
)
st.session_state[PROCESS_SIM_EVENTS_DATA_KEY] = event_frame

st.divider()
if st.button("Prozesssimulation rechnen", type="primary", use_container_width=True):
    try:
        sim_input = ProcessSimulationInput(
            base_input=build_base_input(),
            events=_events_from_frame(event_frame),
            duration_s=float(st.session_state[PROCESS_SIM_DURATION_KEY]),
            time_step_s=float(st.session_state[PROCESS_SIM_DT_KEY]),
            target_outlet_x=float(st.session_state[PROCESS_SIM_TARGET_KEY]),
        )
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
tab_outputs, tab_targets, tab_balances, tab_table = st.tabs(
    ["Ausgänge", "Zielgrößen", "Bilanzgrößen", "Tabelle"]
)

with tab_outputs:
    st.plotly_chart(
        _process_chart(
            series,
            [
                ("outlet_Tb_C", "Ablufttemperatur", "degC"),
                ("outlet_Tp_C", "Partikeltemperatur", "degC"),
                ("outlet_X", "Austrittsfeuchte X", "-"),
            ],
            title="Geglättete Prozessantwort",
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        _process_chart(
            series,
            [
                ("outlet_Y_gkg", "Abluftfeuchte", "g/kg"),
                ("outlet_RH", "Abluft-RH", "-"),
                ("moisture_error", "Feuchteabweichung", "-"),
            ],
            title="Feuchtebezogene Ausgangsgrößen",
        ),
        use_container_width=True,
    )

with tab_targets:
    st.plotly_chart(
        _process_chart(
            series,
            [
                ("target_outlet_Tb_C", "Target Ablufttemperatur", "degC"),
                ("target_outlet_Tp_C", "Target Partikeltemperatur", "degC"),
                ("target_outlet_X", "Target Austrittsfeuchte X", "-"),
            ],
            title="REA-Zielgrößen je Betriebspunkt",
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        _process_chart(
            series,
            [
                ("target_outlet_Y_gkg", "Target Abluftfeuchte", "g/kg"),
                ("target_outlet_RH", "Target Abluft-RH", "-"),
                ("target_outlet_time_s", "Target Austrittszeit", "s"),
            ],
            title="REA-abgeleitete Zusatzgrößen",
        ),
        use_container_width=True,
    )

with tab_balances:
    st.plotly_chart(
        _process_chart(
            series,
            [
                ("q_loss_w", "Wärmeverlust", "W"),
                ("latent_load_w", "Latentlast", "W"),
                ("evaporation_rate_kg_s", "Verdampfungsrate", "kg/s"),
            ],
            title="Bilanz- und Lastgrößen",
        ),
        use_container_width=True,
    )

with tab_table:
    st.dataframe(series, use_container_width=True, hide_index=True, height=480)

st.divider()
st.subheader("F. Export")
csv_bytes = series.to_csv(index=False).encode("utf-8")
st.download_button(
    "Zeitreihen als CSV",
    csv_bytes,
    "spruehtrockner_process_timeseries.csv",
    "text/csv",
)
