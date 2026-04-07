# Spruehtrockner REA

Lokale Streamlit-Anwendung zur Simulation der Tropfentrocknung in einem einfachen Spruehtrockner. Das Projekt kombiniert ein REA-basiertes Trocknungsmodell mit einem testbaren Python-Rechenkern und einer interaktiven Browser-Oberflaeche.

## Projektstruktur

- `app/app.py`: Streamlit-Oberflaeche fuer Eingaben, Presets, Variantenvergleich, Diagramme und Export
- `core/model.py`: Rechenkern mit Eingabevalidierung, ODE-Simulation, Batch-Lauf und Datenexport
- `tests/test_regression.py`: Regressions- und Validierungstests fuer Standardfall, Batch-Lauf und Eingaben
- `docs/spray_dryer_guide.html`: begleitende HTML-Dokumentation

## Funktionen

- Simulation eines Basisfalls mit REA-basiertem Trocknungsmodell
- Presets fuer typische Betriebspunkte wie `Standard`, `Schonende Trocknung`, `Schnelle Trocknung` und `WPC 30 % TS`
- Variantenvergleich mehrerer Szenarien in einem Lauf
- Kennzahlen, Zeitreihen und Eingabeuebersicht in der App
- Export der Ergebnisse als CSV und Excel
- Eingabevalidierung mit Fehlern und Warnhinweisen zu Modellgrenzen

## Voraussetzungen

- Python 3.12 oder kompatibel
- Die Abhaengigkeiten aus `requirements.txt`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## App starten

```bash
streamlit run app/app.py
```

Danach ist die Anwendung lokal im Browser verfuegbar.

## Tests ausfuehren

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

- `SMP` ist nur fuer `TS < 0.2` sowie fuer die diskreten Werte `0.2`, `0.3` und `0.5` vorgesehen.
- `WPC` ist in diesem Modell nur fuer `TS = 0.3` validiert.
- Das Modell gibt Warnungen aus, wenn typische Arbeitsbereiche fuer Zulufttemperatur oder Tropfengroesse verlassen werden.
- Ein formaler Modellabgleich sollte spaeter mit geeigneten Messdaten fuer ausgewaehlte Faelle erfolgen.
