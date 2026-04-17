# Sprühtrockner REA

Neuer technischer App-Neuaufbau fuer die stationaere SMP-REA-Trocknung. Der fachliche Kern unter
`core/stationary_smp_rea/` bleibt bestehen und wird nun ueber ein React-Frontend und eine Python-API
im Stil von `powder-caking` gekapselt.

## Projektstruktur

- `core/stationary_smp_rea/`: fachlicher stationaerer SMP-REA-Kern
- `src/spray_drying/api.py`: FastAPI-App inklusive statischem Frontend-Serving
- `src/spray_drying/api_service.py`: Uebersetzung zwischen API-Datenmodellen und Kern
- `src/spray_drying/api_schemas.py`: Pydantic-DTOs fuer Defaults, Referenzfaelle und Simulation
- `frontend/`: React + Vite + TypeScript Frontend
- `tests/test_stationary_smp_rea.py`: Kernregressionen
- `tests/test_api.py`: API-Shell-Tests fuer Defaults, Referenzfaelle und Simulation

## Funktionen

- Frontend-App-Shell mit den Seiten `Start`, `Simulation` und `Modellgrundlagen`
- Top-Bar, KPI-Band, Chart-Tabs und technische Light-Theme-Gestaltung nach `powder-caking`
- Python-API fuer Referenzfaelle, Defaultwerte und Simulation des stationaeren SMP-Kerns
- Referenzfaelle `V1` bis `V6` aus `ms400/psd.csv` als Ausgangspunkt fuer V1
- Basismodus plus aufklappbarer Expertenmodus fuer zentrale Eingaben und Geometriedaten
- KPI- und Profilstruktur fuer spaetere Vergleichsszenarien

## Voraussetzungen

- Python 3.12 oder kompatibel
- Node.js 24 oder kompatibel
- Python-Abhaengigkeiten in `.venv`
- Frontend-Abhaengigkeiten im Projektordner `frontend/`

## Schnellstart

```bash
git clone https://github.com/Franky-11/spray-drying-rea.git
cd spray-drying-rea
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend
npm install
cd ..
PYTHONPATH=src:. uvicorn spray_drying.api:app --reload
```

Im Entwicklungsmodus kann das Frontend separat gestartet werden:

```bash
cd frontend
npm run dev
```

## Tests ausführen

```bash
source .venv/bin/activate
PYTHONPATH=src:. python -m unittest tests.test_stationary_smp_rea tests.test_api
```

## Verwendete Pakete

- Python: `numpy`, `scipy`, `pandas`, `fastapi`, `pydantic`, `uvicorn`
- Frontend: `react`, `vite`, `typescript`, `echarts`

## Modellgrenzen

- `SMP` ist nur für `TS < 0.2` sowie für die diskreten Werte `0.2`, `0.3` und `0.5` vorgesehen.
- `WPC` ist in diesem Modell nur für `TS = 0.3` validiert.
- Für `SMP` mit `TS = 0.2` und `0.3` wird nach Chen (2008) eine kurze initiale Nassphase modelliert. `TS = 0.5` nutzt weiterhin die hinterlegte REA-Korrelation direkt ab Start.
- Die Standardzusammensetzung der Expertenparameter ist materialabhängig: `SMP` startet mit Protein `0.35`, Lactose `0.55`, Fett `0.01`; `WPC` mit Protein `0.80`, Lactose `0.074`, Fett `0.056`.
- Das Modell gibt Warnungen aus, wenn typische Arbeitsbereiche für Zulufttemperatur oder Tropfengröße verlassen werden.
- Ein formaler Modellabgleich sollte später mit geeigneten Messdaten für ausgewählte Fälle erfolgen.
