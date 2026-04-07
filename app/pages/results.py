from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from results_helpers import (
    CHART_GROUPS,
    axis_label,
    build_chart_figure,
    build_detailed_metrics_frame,
    build_executive_summary,
    build_inputs_frame,
    build_kpi_frame,
    chart_frame,
    scenario_display_map,
    series_color_map,
)
from ui_state import (
    RESULTS_STATE_KEY,
    TARGET_STATE_KEY,
    initialize_session_state,
    results_to_excel_bytes,
    results_to_timeseries_frame,
)


initialize_session_state()

st.title("Ergebnisse")
st.write(
    "Die Ergebnisse sind in einer festen Reihenfolge aufgebaut: zuerst die technische Einordnung, "
    "danach Kennzahlen, Kurven, Detailtabellen und Export."
)

results = st.session_state.get(RESULTS_STATE_KEY)
if not results:
    st.info("Noch keine Berechnung vorhanden. Bitte zuerst auf der Seite `Simulation` rechnen.")
    st.stop()

target_outlet_x = float(st.session_state[TARGET_STATE_KEY])
warnings = [warning for result in results for warning in result.warnings]
if warnings:
    with st.expander("Warnungen und Modellgrenzen", expanded=True):
        for warning in warnings:
            st.warning(warning)

st.subheader("A. Executive Engineering Summary")
summary = build_executive_summary(results, target_outlet_x)
st.markdown(f"**Ziel-Austrittsfeuchte erreicht:** {summary['target']}")
st.markdown(f"**Trocknung vor Trockneraustritt abgeschlossen:** {summary['drying']}")
st.markdown(f"**Im Vergleich am günstigsten:** {summary['best']}")
st.caption(summary["method"])

st.divider()
st.subheader("B. Szenariovergleich")
st.dataframe(
    build_kpi_frame(results, target_outlet_x),
    use_container_width=True,
    hide_index=True,
)

st.divider()
st.subheader("C. Charts")
plot_frame = chart_frame(results)
available_scenarios = plot_frame["scenario"].unique().tolist()
control_left, control_middle, control_right = st.columns([1.0, 1.1, 1.6])
with control_left:
    chart_group = st.selectbox("Diagrammgruppe", tuple(CHART_GROUPS), index=0)
with control_middle:
    x_axis = st.radio("x-Achse", ("height", "t"), horizontal=True, format_func=axis_label)
with control_right:
    selected_scenarios = st.multiselect(
        "Szenarien",
        options=available_scenarios,
        default=available_scenarios,
    )

subset = plot_frame[plot_frame["scenario"].isin(selected_scenarios)]
if subset.empty:
    st.info("Mindestens ein Szenario für die Diagramme auswählen.")
else:
    selected_results = [result for result in results if result.label in selected_scenarios]
    display_map = scenario_display_map(selected_results)
    color_map = series_color_map(available_scenarios)
    for column, title, unit in CHART_GROUPS[chart_group]:
        st.markdown(f"**{title}**")
        st.plotly_chart(
            build_chart_figure(
                subset=subset,
                x_axis=x_axis,
                y_column=column,
                title=title,
                unit=unit,
                color_map=color_map,
                display_map=display_map,
                target_outlet_x=target_outlet_x,
            ),
            use_container_width=True,
            key=f"{chart_group}_{column}_{x_axis}_{'-'.join(selected_scenarios)}",
        )

st.divider()
st.subheader("D. Detaillierte Tabellen")
with st.expander("Kennzahlen", expanded=False):
    st.dataframe(build_detailed_metrics_frame(results), use_container_width=True, hide_index=True)
with st.expander("Zeitreihen", expanded=False):
    timeseries_frame = chart_frame(results)
    st.dataframe(timeseries_frame, use_container_width=True, hide_index=True, height=420)
with st.expander("Verwendete Eingaben", expanded=False):
    st.dataframe(build_inputs_frame(results), use_container_width=True, hide_index=True)

st.divider()
st.subheader("E. Export")
metrics_csv = build_detailed_metrics_frame(results).to_csv(index=False).encode("utf-8")
timeseries_csv = results_to_timeseries_frame(results).to_csv(index=False).encode("utf-8")
excel_bytes = results_to_excel_bytes(results)

export_left, export_middle, export_right = st.columns(3)
with export_left:
    st.download_button("Kennzahlen als CSV", metrics_csv, "spruehtrockner_metrics.csv", "text/csv")
with export_middle:
    st.download_button("Zeitreihen als CSV", timeseries_csv, "spruehtrockner_timeseries.csv", "text/csv")
with export_right:
    st.download_button(
        "Ergebnisse als XLSX",
        excel_bytes,
        "spruehtrockner_results.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
