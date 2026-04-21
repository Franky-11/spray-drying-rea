from __future__ import annotations

import pandas as pd
import streamlit as st


st.title("Sprühtrockner REA")
st.write(
    "Die Anwendung besteht aus einem minimalen stationaeren REA-Kern und einer darauf "
    "aufbauenden, zeitabhaengigen Prozesssimulation. Beide Teile koppeln Produkt- und "
    "Luftzustand ueber Gesamtstroeme sowie einfache Stoff- und Energiebilanzen."
)
st.write(
    "Der bisherige Fokus auf explizite Tropfenanzahl, Flugbahn und Trocknerhoehe wurde "
    "zurueckgenommen. Fuer SMP mit 20 % und 30 % TS bleibt die kurze wasserartige "
    "Anfangsphase erhalten; anschliessend greift die REA-Materialfunktion."
)

st.divider()
st.subheader("A. Architektur")
architecture = pd.DataFrame(
    [
        {
            "Baustein": "REA-Trocknungskinetik",
            "Rolle": "Stationaerer Material- und Bilanzkern",
            "Kernidee": "Produktfeuchte, Produkttemperatur, Lufttemperatur und Luftfeuchte entlang einer effektiven Verweilzeit",
        },
        {
            "Baustein": "Prozesssimulation",
            "Rolle": "Zeitabhaengige Anlagen- und Stoerungslogik",
            "Kernidee": "Zweistufiges lumped Modell mit Luft-/Produktinventaren und Stage-Bilanzen",
        },
    ]
)
st.dataframe(architecture, use_container_width=True, hide_index=True)

st.divider()
st.subheader("B. Was Berechnet Wird")
st.markdown(
    "- Produktfeuchte `X`\n"
    "- Produkttemperatur `T_p`\n"
    "- Lufttemperatur `T_b`\n"
    "- Luftfeuchte `Y`\n"
    "- Materialabhaengiger REA-Faktor und Gleichgewichtsfeuchte `X_e`\n"
    "- KPI-gerechte Austrittswerte und Stoerungsreaktionen"
)

st.divider()
st.subheader("C. Fachliche Leitidee")
st.markdown(
    "1. Eingaben werden auf Gesamtstroeme gebracht: Feedstrom, Feststoffstrom und Luftmassenstrom.\n"
    "2. Die Gleichgewichtsfeuchte wird ueber eine GAB-Schliessung aus Luftzustand und Temperatur berechnet.\n"
    "3. Die REA-Materialfunktion bildet die sinkende Trocknungstreibkraft bei abnehmender Produktfeuchte ab.\n"
    "4. Ein einfacher Schrumpfungsansatz liefert weiter einen effektiven Partikeldurchmesser fuer die Kinetik.\n"
    "5. Die Prozesssimulation verwendet danach getrennte Stage-Bilanzen statt einer kuenstlichen Delay-Huelle."
)

st.divider()
st.subheader("D. Wichtige Vereinfachungen")
st.markdown(
    "- Keine explizite Tropfenanzahl `np_droplets`\n"
    "- Keine verpflichtende Flugbahn- oder Geschwindigkeitsberechnung im Kern\n"
    "- Keine zwingende Abhaengigkeit von Trocknerhoehe oder -durchmesser\n"
    "- Effektiver Verlustterm statt geometriegebundener Verlustrechnung\n"
    "- Stationaere und dynamische Modelle nutzen dieselbe REA-Kinetikbasis"
)

st.divider()
st.subheader("E. Nutzung")
st.markdown(
    "1. In `REA-Trocknungskinetik` einen Basisfall oder ein Preset aufbauen.\n"
    "2. Die stationaeren Austrittswerte und Profile gegen das Ziel-X pruefen.\n"
    "3. In `Prozesssimulation` Stoerungen als Event-Schedule hinterlegen.\n"
    "4. Die zeitliche Reaktion von Luft, Produkt und KPI-Werten auswerten."
)

st.divider()
st.subheader("F. Modellgrenzen")
st.markdown(
    "- Lumped und stage-basiert, nicht CFD-basiert\n"
    "- Materialfunktionen nur im hinterlegten Gueltigkeitsbereich\n"
    "- Tropfenspektren, Wandanhaftung und Mehrstufen-Detailapparate werden nicht explizit aufgeloest\n"
    "- Ziel-Austrittsfeuchte dient der Bewertung, nicht als harter Solver-Abbruch"
)

st.caption("Navigation über die Seitenleiste: Überblick, REA-Trocknungskinetik und Prozesssimulation.")
