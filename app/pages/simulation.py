from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

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


initialize_session_state()

st.title("Simulation")
st.write(
    "Die Eingaben folgen einer linearen Reihenfolge: Startpunkt wählen, Basisfall definieren, "
    "optional Expertenparameter und Vergleichsszenarien ergänzen und danach einmal rechnen."
)

st.subheader("A. Preset und Startpunkt")
st.selectbox(
    "Startpunkt",
    options=tuple(PRESETS),
    key=PRESET_WIDGET_KEY,
    on_change=apply_selected_preset,
)
st.caption("Ein Preset setzt den Basisfall neu. Danach können alle Eingaben frei angepasst werden.")

st.divider()
st.subheader("B. Materialspezifische Parameter")
st.caption("Material, Partikel und Feed-Zustand des Basisfalls.")
st.info(
    "Hinweis: Fuer SMP mit 20 % oder 30 % TS nutzt das Modell eine sehr kurze wasserartige "
    "Anfangsphase und schaltet danach auf die REA-Korrelation. SMP mit 50 % TS bleibt direkt "
    "auf REA. Beim Materialwechsel werden die Expertenparameter fuer Protein, Lactose und Fett "
    "auf materialtypische Standardwerte gesetzt."
)
render_field_grid(MATERIAL_FIELDS)

st.divider()
st.subheader("C. Prozessparameter")
st.caption("Betriebsbedingungen des Trockners für den Basisfall.")
render_field_grid(PROCESS_FIELDS)

base_input = build_base_input()
st.dataframe(build_operating_point_frame(base_input), use_container_width=True, hide_index=True)

st.divider()
st.subheader("D. Optionale Expertenparameter")
with st.expander("Expertenparameter anzeigen", expanded=False):
    st.caption(
        "Nur anpassen, wenn Materialannahmen oder Simulationsgrenzen gezielt untersucht werden sollen."
    )
    st.caption(
        "Standardwerte sind materialabhaengig: SMP 0.35 / 0.55 / 0.01 fuer Protein / Lactose / Fett, "
        "WPC 0.80 / 0.074 / 0.056."
    )
    render_field_grid(EXPERT_FIELDS)

base_input = build_base_input()

st.divider()
st.subheader("E. Optionale Vergleichsszenarien")
comparison_inputs, comparison_labels = render_comparison_scenarios(base_input)

st.divider()
st.subheader("F. Bewertungsziel")
st.number_input(
    "Ziel für Austrittsfeuchte X [-]",
    min_value=0.0,
    step=0.005,
    key=TARGET_STATE_KEY,
    help="Dieser Wert dient nur der Bewertung auf der Ergebnisseite, nicht als Solver-Abbruch.",
)

st.divider()
if st.button("Berechnen", type="primary", use_container_width=True):
    labels = ["Basis", *comparison_labels]
    inputs = [base_input, *comparison_inputs]
    try:
        st.session_state[RESULTS_STATE_KEY] = run_batch(inputs, labels=labels)
        st.success("Berechnung abgeschlossen. Die Ergebnisse stehen auf der Seite `Ergebnisse` bereit.")
    except Exception as exc:
        clear_results()
        st.error(str(exc))

elif RESULTS_STATE_KEY in st.session_state:
    st.caption("Die Ergebnisseite zeigt den letzten erfolgreich berechneten Lauf.")
