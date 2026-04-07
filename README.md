# Spruehtrockner REA App

Kleine lokale Browser-Anwendung zur Berechnung der Tropfentrocknung in einem einfachen Spruehtrockner. Die fachliche Grundlage ist das MATLAB-Skript `Dryingkinetic_REA.m`, dessen REA-Modell in Python portiert wurde.

## Bestandteile

- `core/model.py`: Rechenkern mit ODE-System, Eingabemodell, Batch-Lauf und Exportfunktionen
- `app/app.py`: Streamlit-Oberflaeche fuer Eingaben, Variantenvergleich, Kennzahlen, Diagramme und Export
- `tests/test_regression.py`: Grundlegende Regressions- und Validierungstests

## Lokaler Start

1. Virtuelle Umgebung anlegen:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. App starten:

```bash
streamlit run app/app.py
```

## Modellgrenzen

- `SMP` ist fuer `TS < 0.2` sowie `TS = 0.2`, `0.3`, `0.5` abgebildet.
- `WPC` ist in diesem Modell nur fuer `TS = 0.3` validiert.
- Das Modell bildet die Logik des Ausgangsskripts nach, einschliesslich gekoppelter Stoff-, Energie- und Geschwindigkeitsbilanz.
- Ein exakter numerischer MATLAB-Abgleich ist noch sinnvoll, sobald eine MATLAB- oder Octave-Referenzumgebung verfuegbar ist.
