from __future__ import annotations

import streamlit as st


st.title("Sprühtrockner REA")
st.write(
    "Diese Anwendung berechnet die Trocknung einzelner Tropfen in einem vereinfachten "
    "Sprühtrockner-Modell. Sie ist für technische Vorstudien, Betriebspunktvergleiche "
    "und Szenarioanalysen gedacht."
)

st.subheader("Modellannahmen")
st.markdown(
    "- Monodisperse Tropfen\n"
    "- Keine Tropfenwechselwirkung\n"
    "- Gleichstrombetrieb\n"
    "- Plug-Flow-Modell"
)

st.info(
    "Modellzusammenfassung: REA-basierte Tropfentrocknung mit bewusst reduziertem "
    "Prozessbild. Die App dient der ingenieurmäßigen Einordnung, nicht der CFD-nahen Detailanalyse."
)

st.subheader("Einsatzbereich und Grenzen")
st.write(
    "Die Ergebnisse eignen sich zur schnellen Bewertung von Einflussgrößen wie "
    "Zulufttemperatur, Tropfengröße, Luftstrom oder Feed-Trockensubstanz. "
    "Materialgültigkeit und Randbedingungen bleiben auf den im Modell hinterlegten Bereich begrenzt."
)

st.subheader("Arbeitsablauf")
st.markdown(
    "1. Eingaben und optional einen sinnvollen Startpunkt auf der Seite `Simulation` festlegen.\n"
    "2. Einen Basisfall und bei Bedarf weitere Vergleichsszenarien berechnen.\n"
    "3. Auf der Seite `Ergebnisse` die technische Bewertung, Kennzahlen und Kurven vergleichen."
)

st.caption("Navigation über die Seitenleiste: Überblick, Simulation, Ergebnisse.")
