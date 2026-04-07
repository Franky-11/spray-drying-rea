# Sprühtrockner REA

Lokale Streamlit-Anwendung zur Simulation der Tropfentrocknung in einem einfachen Sprühtrockner. Das Projekt kombiniert ein REA-basiertes Trocknungsmodell mit einem testbaren Python-Rechenkern und einer interaktiven Browser-Oberfläche.

## Projektstruktur

- `app/app.py`: Streamlit-Startpunkt und Navigation zwischen den drei Seiten
- `app/pages/overview.py`: kurze Modell- und Workflow-Einführung
- `app/pages/simulation.py`: lineare Eingabeseite für Basisfall, Expertenparameter und Vergleichsszenarien
- `app/pages/results.py`: technische Bewertung, Kennzahlen, Charts, Detailtabellen und Export
- `app/ui_state.py`: gemeinsame Eingabedefinitionen, Session-State-Handling und Simulationsaufruf
- `app/results_helpers.py`: Aufbereitung für Bewertungstabellen und Diagramme
- `core/model.py`: Rechenkern mit Eingabevalidierung, ODE-Simulation, Batch-Lauf und Datenexport
- `tests/test_regression.py`: Regressions- und Validierungstests fuer Standardfall, Batch-Lauf und Eingaben
- `docs/spray_dryer_guide.html`: begleitende HTML-Dokumentation

## Funktionen

- Geführte App-Struktur mit den Seiten `Überblick`, `Simulation` und `Ergebnisse`
- Simulation eines Basisfalls mit REA-basiertem Trocknungsmodell
- Presets für typische Betriebspunkte wie `Standard`, `Schonende Trocknung`, `Schnelle Trocknung` und `WPC 30 % TS`
- Optionaler Variantenvergleich mehrerer Szenarien in einem Lauf
- Technische Bewertung vor Detailtabellen und Diagrammen
- Export der Ergebnisse als CSV und Excel
- Eingabevalidierung mit Fehlern und Warnhinweisen zu Modellgrenzen
- Frühphasen-Korrektur für `SMP` mit `TS = 0.2` und `0.3`: sehr kurze wasserartige Oberflächenphase vor dem Übergang auf die Literatur-REA-Korrelation

## Voraussetzungen

- Python 3.12 oder kompatibel
- Die Abhängigkeiten aus `requirements.txt`

## Schnellstart

```bash
git clone https://github.com/Franky-11/spray-drying-rea.git
cd spray-drying-rea
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/app.py
```

Danach ist die Anwendung lokal im Browser verfügbar.

Als begleitende Dokumentation zur App steht zusätzlich der HTML-Guide unter
`docs/spray_dryer_guide.html` bereit. Er erläutert Bedienung, Modellannahmen,
Gleichungen und die fachliche Einordnung der Ergebnisse.

## Tests ausführen

```bash
python3 -m unittest tests.test_regression
```

## Verwendete Pakete

- `numpy`
- `scipy`
- `pandas`
- `plotly`
- `streamlit`
- `openpyxl`

## Modellgrenzen

- `SMP` ist nur für `TS < 0.2` sowie für die diskreten Werte `0.2`, `0.3` und `0.5` vorgesehen.
- `WPC` ist in diesem Modell nur für `TS = 0.3` validiert.
- Für `SMP` mit `TS = 0.2` und `0.3` wird nach Chen (2008) eine kurze initiale Nassphase modelliert. `TS = 0.5` nutzt weiterhin die hinterlegte REA-Korrelation direkt ab Start.
- Die Standardzusammensetzung der Expertenparameter ist materialabhängig: `SMP` startet mit Protein `0.35`, Lactose `0.55`, Fett `0.01`; `WPC` mit Protein `0.80`, Lactose `0.074`, Fett `0.056`.
- Das Modell gibt Warnungen aus, wenn typische Arbeitsbereiche für Zulufttemperatur oder Tropfengröße verlassen werden.
- Ein formaler Modellabgleich sollte später mit geeigneten Messdaten für ausgewählte Fälle erfolgen.
