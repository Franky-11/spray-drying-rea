from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from results_helpers import (
    CHART_GROUPS,
    assessment_rows,
    axis_label,
    build_chart_figure,
    build_detailed_metrics_frame,
    build_executive_summary,
    build_inputs_frame,
    build_kpi_frame,
    chart_frame,
    choose_best_scenario,
    scenario_display_map,
    series_color_map,
)
from ui_state import (
    BASE_FIELD_ORDER,
    COMPARISON_COUNT_KEY,
    COMPARISON_ENABLED_KEY,
    EXPERT_FIELDS,
    MAX_COMPARISONS,
    MATERIAL_FIELDS,
    PRESETS,
    PRESET_WIDGET_KEY,
    PROCESS_FIELDS,
    RESULTS_STATE_KEY,
    TARGET_STATE_KEY,
    apply_selected_preset,
    build_base_input,
    build_comparison_input,
    build_operating_point_frame,
    build_override_summary_frame,
    clear_results,
    field_display_name,
    format_input_value,
    initialize_session_state,
    render_field_input,
    run_batch,
    results_to_excel_bytes,
    results_to_timeseries_frame,
)


def render_field_grid(fields: list[str], key_prefix: str = "base") -> None:
    columns = st.columns(2)
    for index, field in enumerate(fields):
        with columns[index % 2]:
            render_field_input(field, f"{key_prefix}_{field}")


def render_comparison_scenarios(base_input) -> tuple[list[Any], list[str]]:
    comparison_inputs: list[Any] = []
    comparison_labels: list[str] = []

    enabled = st.checkbox(
        "Vergleichsszenarien hinzufügen",
        key=COMPARISON_ENABLED_KEY,
        help="Vergleichsszenarien übernehmen alle Basiswerte und ändern nur ausgewählte Parameter.",
    )
    if not enabled:
        return comparison_inputs, comparison_labels

    st.number_input(
        "Anzahl Vergleichsszenarien",
        min_value=1,
        max_value=MAX_COMPARISONS,
        step=1,
        key=COMPARISON_COUNT_KEY,
    )

    scenario_count = int(st.session_state[COMPARISON_COUNT_KEY])
    st.caption("Der Basisfall bleibt die Referenz. Vergleichsszenarien zeigen nur ihre Overrides.")

    for index in range(1, scenario_count + 1):
        with st.expander(f"Vergleichsszenario {index}", expanded=index == 1):
            label_key = f"comparison_label_{index}"
            fields_key = f"comparison_fields_{index}"
            st.session_state.setdefault(label_key, f"Vergleich {index}")
            st.session_state.setdefault(fields_key, [])
            label = st.text_input("Bezeichnung", key=label_key)
            selected_fields = st.multiselect(
                "Abweichende Parameter",
                options=BASE_FIELD_ORDER,
                key=fields_key,
                format_func=field_display_name,
                help="Nur diese Eingaben werden gegen den Basisfall geändert.",
            )

            overrides: dict[str, Any] = {}
            columns = st.columns(2)
            for field_index, field in enumerate(selected_fields):
                with columns[field_index % 2]:
                    widget_key = f"comparison_{index}_{field}"
                    base_value = getattr(base_input, field)
                    overrides[field] = render_field_input(field, widget_key, value=base_value)
                    st.caption(
                        f"Basiswert {field_display_name(field)}: {format_input_value(field, base_value)}"
                    )

            if overrides:
                st.dataframe(
                    build_override_summary_frame(base_input, overrides),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.caption("Noch keine Overrides gesetzt. Dieses Szenario entspricht aktuell dem Basisfall.")

            comparison_inputs.append(build_comparison_input(label or f"Vergleich {index}", base_input, overrides))
            comparison_labels.append(label or f"Vergleich {index}")

    return comparison_inputs, comparison_labels


def render_stationary_results(target_outlet_x: float) -> None:
    results = st.session_state.get(RESULTS_STATE_KEY)

    st.divider()
    st.subheader("4. KPI-Überblick")
    if not results:
        st.info(
            "Noch keine REA-Berechnung vorhanden. Nach `Berechnen` erscheinen hier Kennzahlen, "
            "Diagramme, Detailtabellen und Exporte des letzten erfolgreichen Laufs."
        )
        st.divider()
        st.subheader("5. Hauptdiagramme")
        st.caption("Die Hauptdiagramme werden nach der ersten Berechnung eingeblendet.")
        st.divider()
        st.subheader("6. Detailtabellen")
        st.caption("Kennzahlen, Zeitreihen und Eingabeübersichten folgen nach der Berechnung.")
        st.divider()
        st.subheader("7. Export")
        st.caption("CSV- und XLSX-Exporte werden nach der Berechnung aktiviert.")
        return

    warnings = [warning for result in results for warning in result.warnings]
    if warnings:
        with st.expander("Warnungen und Modellgrenzen", expanded=True):
            for warning in warnings:
                st.warning(warning)

    summary = build_executive_summary(results, target_outlet_x)
    assessment = assessment_rows(results, target_outlet_x)
    best = choose_best_scenario(assessment)
    target_hits = sum(1 for row in assessment if row["target_met"])
    dried_hits = sum(1 for row in assessment if row["dried_in_tower"])

    kpi_left, kpi_mid, kpi_right, kpi_far = st.columns(4)
    with kpi_left:
        st.metric("Szenarien", f"{len(results)}")
    with kpi_mid:
        st.metric("Ziel-X eingehalten", f"{target_hits}/{len(results)}")
    with kpi_right:
        st.metric("Vor Austritt getrocknet", f"{dried_hits}/{len(results)}")
    with kpi_far:
        best_x = best["outlet_X"] if best else None
        st.metric("Beste Austritts-X", "-" if best_x is None else f"{best_x:.4f}")

    st.markdown(f"**Ziel-Austrittsfeuchte erreicht:** {summary['target']}")
    st.markdown(f"**Trocknung vor effektivem Austritt abgeschlossen:** {summary['drying']}")
    st.markdown(f"**Im Vergleich am günstigsten:** {summary['best']}")
    st.caption(summary["method"])
    st.dataframe(
        build_kpi_frame(results, target_outlet_x),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("5. Hauptdiagramme")
    plot_frame = chart_frame(results)
    available_scenarios = plot_frame["scenario"].unique().tolist()
    control_left, control_middle, control_right = st.columns([1.0, 1.1, 1.6])
    with control_left:
        chart_group = st.selectbox("Diagrammgruppe", tuple(CHART_GROUPS), index=0)
    with control_middle:
        x_axis = st.radio("x-Achse", ("progress", "t"), horizontal=True, format_func=axis_label)
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
    st.subheader("6. Detailtabellen")
    with st.expander("Kennzahlen", expanded=False):
        st.dataframe(build_detailed_metrics_frame(results), use_container_width=True, hide_index=True)
    with st.expander("Zeitreihen", expanded=False):
        st.dataframe(plot_frame, use_container_width=True, hide_index=True, height=420)
    with st.expander("Verwendete Eingaben", expanded=False):
        st.dataframe(build_inputs_frame(results), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("7. Export")
    metrics_csv = build_detailed_metrics_frame(results).to_csv(index=False).encode("utf-8")
    timeseries_csv = results_to_timeseries_frame(results).to_csv(index=False).encode("utf-8")
    excel_bytes = results_to_excel_bytes(results)

    export_left, export_middle, export_right = st.columns(3)
    with export_left:
        st.download_button("Kennzahlen als CSV", metrics_csv, "spruehtrockner_metrics.csv", "text/csv")
    with export_middle:
        st.download_button(
            "Zeitreihen als CSV",
            timeseries_csv,
            "spruehtrockner_timeseries.csv",
            "text/csv",
        )
    with export_right:
        st.download_button(
            "Ergebnisse als XLSX",
            excel_bytes,
            "spruehtrockner_results.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


initialize_session_state()

st.title("REA-Trocknungskinetik")
st.subheader("1. Kurzbeschreibung")
st.write(
    "Dieses Werkzeug bildet einen stationären Minimal-REA-Kern mit gekoppelten Stoff- und "
    "Energiebilanzen fuer Produkt und Luft ab. Intern wird direkt mit Feststoff- und Luftstroemen "
    "gerechnet; Tropfenanzahl, Flugbahn und Trocknergeometrie sind nicht mehr kernbestimmend."
)

st.divider()
st.subheader("2. Eingaben")
st.markdown("**Preset und Startpunkt**")
st.selectbox(
    "Startpunkt",
    options=tuple(PRESETS),
    key=PRESET_WIDGET_KEY,
    on_change=apply_selected_preset,
)
st.caption("Ein Preset setzt den Basisfall neu. Danach können alle Eingaben frei angepasst werden.")

st.markdown("**Material und Feed**")
st.caption("Material, Partikelcharakteristik und Feed-Zustand des Basisfalls.")
st.info(
    "Hinweis: Fuer SMP mit 20 % oder 30 % TS nutzt das Modell eine sehr kurze wasserartige "
    "Anfangsphase und schaltet danach auf die REA-Korrelation. SMP mit 50 % TS bleibt direkt "
    "auf REA. Beim Materialwechsel werden die Expertenparameter fuer Protein, Lactose und Fett "
    "auf materialtypische Standardwerte gesetzt."
)
render_field_grid(MATERIAL_FIELDS)

st.markdown("**Prozessparameter**")
st.caption("Betriebsbedingungen fuer den Basisfall. Die Kopplung erfolgt ueber Gesamtstroeme.")
render_field_grid(PROCESS_FIELDS)

base_input = build_base_input()
st.dataframe(build_operating_point_frame(base_input), use_container_width=True, hide_index=True)

st.markdown("**Optionale Expertenparameter**")
with st.expander("Expertenparameter anzeigen", expanded=False):
    st.caption(
        "Nur anpassen, wenn Materialannahmen, Verluste oder Simulationsgrenzen gezielt untersucht werden sollen."
    )
    st.caption(
        "Standardwerte sind materialabhaengig: SMP 0.35 / 0.55 / 0.01 fuer Protein / Lactose / Fett, "
        "WPC 0.80 / 0.074 / 0.056."
    )
    render_field_grid(EXPERT_FIELDS)

base_input = build_base_input()

st.markdown("**Optionale Vergleichsszenarien**")
comparison_inputs, comparison_labels = render_comparison_scenarios(base_input)

st.markdown("**Bewertungsziel**")
st.number_input(
    "Ziel für Austrittsfeuchte X [-]",
    min_value=0.0,
    step=0.005,
    key=TARGET_STATE_KEY,
    help="Dieser Wert dient nur der Bewertung im KPI-Block und in den Diagrammen, nicht als Solver-Abbruch.",
)

st.divider()
st.subheader("3. Berechnen")
if st.button("Berechnen", type="primary", use_container_width=True):
    labels = ["Basis", *comparison_labels]
    inputs = [base_input, *comparison_inputs]
    try:
        st.session_state[RESULTS_STATE_KEY] = run_batch(inputs, labels=labels)
        st.success(
            "Berechnung abgeschlossen. KPI-Überblick, Hauptdiagramme, Detailtabellen und Export "
            "wurden unten aktualisiert."
        )
    except Exception as exc:
        clear_results()
        st.error(str(exc))
elif RESULTS_STATE_KEY in st.session_state:
    st.caption("Angezeigt wird der letzte erfolgreich berechnete REA-Lauf.")

render_stationary_results(float(st.session_state[TARGET_STATE_KEY]))
