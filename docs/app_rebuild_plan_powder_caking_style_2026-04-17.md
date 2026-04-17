# Implementierungsplan fuer den UI/UX-Neuaufbau der Spray-Drying-App

## Statusstand 2026-04-17

### Gesamtstatus

- `Phase 0` `done`
- `Phase 1` `done`
- `Phase 2` `in progress`
- `Phase 3` `planned`
- `Phase 4` `planned`
- `Phase 5` `planned`

### Bereits umgesetzt

- `frontend/` als eigenstaendiges `React + Vite + TypeScript`-Projekt angelegt
- technische App-Shell mit Top-Bar und Navigation `Start / Simulation / Modellgrundlagen`
- Python-API unter `src/spray_drying/` angelegt
- `health`, `model/defaults`, `presets/reference-cases` und `simulate` angebunden
- V1-Eingabestruktur fuer Basismodus und Expertenmodus im Frontend vorbereitet
- Einzel-Szenario fuer den stationaeren SMP-REA-Kern ueber die neue UI ausfuehrbar
- KPI-Band, Chart-Tabs, Reportpunkte und Ergebnisexport fuer den Einzel-Lauf angebunden
- API liefert nun strukturierte Resultate mit `summary`, `outlet`, `report_points`, `profile`, `warnings`, `provenance`
- lokale Python- und Frontend-Checks laufen erfolgreich

### Aktuell in Arbeit

- Phase 2 fachlich abschliessen und die Einzel-Szenario-Seite weiter in Richtung produktiver V1-Arbeitsseite haerten
- API-/Frontend-Struktur so stabilisieren, dass Vergleichsszenarien ohne Umbau anschliessbar sind

### Noch geplant

- serverseitiger Vergleichsmodus `compare` fuer mehrere Szenarien
- Delta- und Vergleichstabellen ueber mehrere Faelle
- Modellgrundlagen-Seite fachlich inhaltlich ausbauen
- moegliche CSS-Weiterstrukturierung in `frontend/src/styles/` gemaess Zielbild
- spaetere V1+-Themen wie Sweep-Modus, gespeicherte Szenariensets und groessere Prozesssimulation bewusst spaeter

## Zielbild

Die bestehende UI wird nicht weiterentwickelt. Die App wird neu aufgesetzt und soll sich in Stack,
Struktur und Tonalitaet klar am Referenzprojekt `powder-caking` orientieren:

- Frontend als `React + Vite + TypeScript`
- Backend als Python-API, die den Simulationskern kapselt
- Single-server-Betrieb fuer Produktion: API liefert auch das gebaute Frontend aus
- Vite-Dev-Modus fuer UI-Entwicklung
- technische, helle, datenorientierte UI statt Streamlit- oder Notebook-Charakter

Fuer die erste Ausbaustufe wird **nur** das Modul fuer die stationaere Trocknungskinetik aufgebaut.
Die groessere Prozesssimulation bleibt vorerst bewusst draussen.

## Referenz aus `powder-caking`

Die neue App soll folgende Grundprinzipien aus `powder-caking` uebernehmen:

- klares App-Shell-Konzept mit Top-Bar und einfacher Navigation
- getrennte Seiten statt einer einzigen langen UI
- Frontend als eigenstaendiges `frontend/`-Projekt
- API-Client im Frontend mit klaren Request-/Response-Typen
- technische Light-Theme-Gestaltung statt Marketing-Look
- KPI-Band, Charts, strukturierte Eingabepanels und eigene Seite fuer Modellgrundlagen

Relevante Referenzdateien:

- `powder-caking/README.md`
- `powder-caking/DESIGN.md`
- `powder-caking/preview.html`
- `powder-caking/frontend/package.json`
- `powder-caking/frontend/src/App.tsx`
- `powder-caking/frontend/src/apiClient.ts`
- `powder-caking/frontend/src/apiTypes.ts`

Verbindliche Umsetzungsregel:

- `DESIGN.md` aus `powder-caking` wird als primaere visuelle Referenz fuer Tokens, Panelstruktur,
  KPI-Band, Tabellen- und Chartanmutung uebernommen.
- `preview.html` aus `powder-caking` wird ebenfalls als konkrete Layout- und Interaktionsreferenz
  fuer das Frontend herangezogen.
- Vor dem eigentlichen Frontend-Bau soll deshalb eine projektspezifische Ableitung dieser beiden
  Dateien fuer `spray-drying` erstellt oder direkt in das neue Frontend-Tokensystem ueberfuehrt werden.

## Produktumfang der ersten Version

Die neue App soll in V1 drei Seiten haben:

1. `Start`
2. `Simulation`
3. `Modellgrundlagen`

### 1. Start

Ziel:

- kurze Orientierung
- direkte Navigation in die Simulation
- knapper, technischer Produktkontext

Inhalt:

- App-Titel und kurze Einordnung
- 3 bis 5 Kernpunkte:
  - stationaerer REA-basierter Trocknungskern
  - Szenarienvergleich
  - sensitivitaetsartige Variation von Inputs
  - KPI- und Profilvergleich
- CTA `Simulation oeffnen`
- CTA `Modellgrundlagen`

### 2. Simulation

Ziel:

- produktive Arbeitsseite fuer den Fine-Kern
- ein Basisszenario plus Vergleichsszenarien
- schnelle Iteration ueber die wichtigsten Eingaben

Fokus der ersten Version:

- nur `core/stationary_smp_rea/`
- keine Legacy-UI
- keine Prozesssimulation

Pflichtfunktionen:

- Auswahl oder Vorgabe eines Referenzfalls, z. B. `V2`, `V3`
- Eingabemodus mit `Basismodus` und aufklappbarem `Expertenmodus`
- Definition von Vergleichsszenarien:
  - gleiche Basisparameter
  - gezielte Variation einzelner Parameter
  - zuerst manuell, spaeter komfortabler Preset-/Sweep-Modus

### Eingabestruktur der Simulation

#### Basismodus

Der Basismodus soll die wenigen Parameter enthalten, die man fuer einen sinnvollen Szenarienvergleich
wirklich oft veraendert. Diese Felder sollen mit gut nachvollziehbaren Default-Werten vorbelegt werden.

Pflichtfelder im Basismodus:

- `Tin`
- `humid_air_mass_flow_kg_h`
- `feed_rate_kg_h`
- `droplet_size_um`
- `inlet_abs_humidity_g_kg`
- `feed_total_solids`

Ergaenzende Empfehlung:

- `heat_loss_coeff_w_m2k` soll in V1 sichtbar bleiben, aber zunaechst im Expertenmodus liegen, damit
  der Basismodus nicht zu technisch wird.

#### Expertenmodus

Der Expertenmodus soll als aufklappbarer Bereich wie im `powder-caking`-Projekt aufgebaut werden.
Er dient nicht fuer den Standard-Workflow, sondern fuer Modellinspektion und Kalibrierung.

Pflichtkandidaten fuer V1:

- `heat_loss_coeff_w_m2k`
- `x_b_model`
- `nozzle_delta_p_bar`
- `nozzle_velocity_coefficient`
- `dryer_diameter_m`
- `dryer_height_m`
- `cylinder_height_m`
- `cone_height_m`
- `outlet_duct_length_m`
- `outlet_duct_diameter_m`

Optionale Kandidaten fuer spaeter:

- alternative Isotherm-Parameter bzw. GAB-nahe Parameter
- Schrumpfungsmodell
- Materialfunktions- oder REA-Schalter
- Solver-Optionen

Nicht fuer die erste sichtbare UI empfohlen:

- direkte Freigabe sehr detailreicher Materialfunktionsparameter
- Freigabe vieler interner REA-Kalibrierterme ohne klaren Nutzerfall

Pflichtoutputs:

- KPI fuer jedes Szenario:
  - `Tout_pre_cyclone`
  - Pulverfeuchte `wt% wb`
  - `RHout`
  - `tau_out`
- Profilvergleich:
  - `T_a(h)`
  - `T_p(h)`
  - `X(h)` bzw. `wt% wb(h)`
  - `x_b(h)`
  - `psi(h)`
  - optional `U_a(h)` und `U_p(h)`
- tabellarischer Szenarienvergleich
- Export der Resultate als CSV oder JSON

### KPI-Struktur fuer die Simulation

Die KPI-Reihe soll wie in `powder-caking` kompakt und direkt lesbar sein. Fuer die erste Version sind
die folgenden KPIs sinnvoll:

- `Endfeuchte`
- `Tout_pre_cyclone`
- `RHout`
- `tau_out`
- `Trocknungsziel erreicht` `ja/nein`
- `Zeit bis Ziel`
- `Hoehe bis Ziel`

Definition fuer zielbezogene KPIs:

- Das Trocknungsziel ist ein nutzerseitig definierbarer Zielwert fuer die Pulverfeuchte `wt% wb`.
- `Zeit bis Ziel` ist die erste `tau`, bei der das Ziel erreicht oder unterschritten wird.
- `Hoehe bis Ziel` ist die erste axiale Position `h`, bei der das Ziel erreicht oder unterschritten wird.

Weitere sinnvolle KPI-Kandidaten:

- `x_out - x_b,out` oder aequivalente Feuchtereserve zum Gleichgewicht
- `T_p,out`
- `U_p,out`

Empfehlung fuer V1:

- `x_out - x_b,out` als technische Zusatz-KPI im Expertenkontext ausgeben
- `T_p,out` und `U_p,out` erst spaeter sichtbar machen, wenn klar ist, dass sie fuer Nutzer wirklich
  interpretierbar sind

### Chart-Struktur

Die Diagramme sollen tabweise organisiert werden, analog zur Arbeitsweise in `powder-caking`.

Empfohlene Tabs in V1:

- `Feuchte`
- `Temperatur`
- `Gleichgewicht und Material`
- `Geschwindigkeit`
- `Vergleichstabelle`

Empfohlene Inhalte:

`Feuchte`

- `X(h)` oder `wt% wb(h)`
- Ziel-Feuchte als Referenzlinie

`Temperatur`

- `T_a(h)`
- `T_p(h)`

`Gleichgewicht und Material`

- `x_b(h)`
- `psi(h)`
- optional `activation_ratio`

`Geschwindigkeit`

- `U_a(h)`
- `U_p(h)`
- optional `tau(h)`

`Vergleichstabelle`

- KPI-Vergleich ueber alle Szenarien
- Export-Button

### 3. Modellgrundlagen

Ziel:

- kompakte, technisch lesbare Dokumentationsseite in der App
- keine Paper-Kopie, sondern klare Modelluebersicht

Inhalt:

- Prozessschema des stationaeren Kerns
- Bilanzgleichungen in knapper Form
- Materialmodell:
  - Chew-REA
  - weicher Zusatzterm im fruehen Falling-Rate-Bereich
- `x_b`-Modelle
- Schrumpfung
- Impuls-/Geschwindigkeitsmodell
- Druckduesen-Startgeschwindigkeit nach Walzel
- Geltungsbereich, Annahmen, aktuelle Einschraenkungen

## UX-Prinzipien fuer die neue App

Die App soll sich optisch und strukturell an `powder-caking` anlehnen, aber mit dem Produktfokus
`Spray Drying Kinetics`.

### Stilrichtung

- hell
- technisch
- ruhig
- wissenschaftlich
- datenorientiert
- wenig dekorativ

### Was explizit vermieden wird

- Streamlit-Anmutung
- dunkle Default-Dashboards
- marketinglastige Hero-Seiten
- verspielte Farben
- verschachtelte Card-in-Card-Layouts

### Empfohlene Gestaltung

- Top-Bar mit App-Name, Navigationspunkten und API-/Rechenstatus
- grosszuegige, flache Panels mit subtilen Linien
- klare KPI-Reihe
- ECharts fuer Zeit- und Profilkurven
- Tabellen fuer Szenarienvergleich und Export
- technische Sprache auf Deutsch

Verbindliche Design-Basis:

- Das Frontend soll nicht nur lose an `powder-caking` angelehnt sein, sondern die dortige
  Designlogik aus `DESIGN.md` und die visuelle Struktur aus `preview.html` konkret uebernehmen.
- Vor Implementierungsbeginn sollen deshalb fuer `spray-drying` mindestens folgende Artefakte angelegt werden:
  - `frontend/src/styles/tokens.css`
  - `frontend/src/styles/app.css`
  - optional eine eigene `preview.html` oder ein Frontend-Preview-Screen zur schnellen UI-Abnahme

## Ziel-Architektur

## 1. Frontend

Empfohlenes neues Verzeichnis:

- `frontend/`

Empfohlener Stack:

- `React`
- `TypeScript`
- `Vite`
- `ECharts`
- `ESLint`

Empfohlene erste Struktur:

```text
frontend/
  src/
    main.tsx
    App.tsx
    app/
      routes.tsx
      layout/
      navigation/
    pages/
      StartPage.tsx
      SimulationPage.tsx
      ModelBasisPage.tsx
    components/
      kpi/
      charts/
      forms/
      scenario/
      status/
      tables/
    api/
      client.ts
      types.ts
    styles/
      tokens.css
      app.css
```

### Frontend-Zustand in V1

Bewusst einfach halten:

- lokaler Seitenzustand plus wenige zentrale Hooks
- kein komplexes Global-State-System am Anfang
- Szenarien als klarer lokaler Array-State

## 2. Backend/API

Die neue App sollte wie `powder-caking` ueber eine saubere API-Schicht mit dem Kern sprechen.

Empfohlenes Ziel:

- FastAPI oder eine gleichwertige Python-API-Schicht
- Frontend nutzt nur diese API, nicht direkt Python-Module

Empfohlene Zielstruktur:

```text
src/
  spray_drying_app/
    api.py
    schemas.py
    services/
      stationary_smp_rea_service.py
      scenario_service.py
      export_service.py
```

Der Simulationskern selbst bleibt dort, wo er fachlich hingehort:

- `core/stationary_smp_rea/`

### Wichtige Regel

Der UI-Neuaufbau darf den neuen Kern nicht mit UI-Logik vermischen. Die API-Schicht adaptiert nur
Eingaben und Resultate.

## Erste API-Endpunkte

Empfohlene erste Endpunkte:

- `GET /api/health`
- `GET /api/stationary-smp-rea/defaults`
- `GET /api/stationary-smp-rea/ms400-cases`
- `POST /api/stationary-smp-rea/simulate`
- `POST /api/stationary-smp-rea/compare`
- `GET /api/stationary-smp-rea/model-basis`

### API-Aufgaben

`/defaults`

- liefert Frontend-Defaults
- liefert Modelloptionen
- liefert Builder-nahe Standardwerte

`/ms400-cases`

- liefert verfuegbare Referenzfaelle wie `V2`, `V3`
- liefert experimentelle Vergleichswerte

`/simulate`

- rechnet ein einzelnes Szenario

`/compare`

- rechnet mehrere Szenarien in einem Request
- liefert KPI-Block plus Profilzeitreihen pro Szenario

`/model-basis`

- liefert strukturierte Texte/Metadaten fuer die Modellgrundlagen-Seite

## Datenschnitt fuer die Simulation

Empfohlene erste Request-Struktur:

```text
SimulationRequest
  base_case_label?: string
  parameters:
    inlet_air_temp_c
    feed_rate_kg_h
    humid_air_mass_flow_kg_h
    inlet_abs_humidity_g_kg
    droplet_size_um
    feed_total_solids
    heat_loss_coeff_w_m2k
    x_b_model
    nozzle_delta_p_bar
    nozzle_velocity_coefficient
  compare_parameters?: []
```

Empfohlene Response-Struktur:

```text
SimulationResponse
  summary
  outlet
  report_points
  profile
  warnings
  provenance
```

## Szenarienvergleich in V1

Der Vergleichsmodus ist das wichtigste UI-Merkmal der neuen App.

### Startumfang

- 1 Basisszenario
- bis zu 3 Vergleichsszenarien
- Parameter-Kopie aus Basisszenario
- nur geaenderte Felder werden hervorgehoben

### Erste sinnvolle Vergleichsachsen

- Tropfengroesse
- `Tin`
- absolute Luftfeuchte
- Feedrate

### Ergebnisdarstellung

- KPI-Matrix ueber alle Szenarien
- ueberlagerte Profilplots
- Delta-Spalten gegen das Basisszenario

## Empfohlene Seitenstruktur im Frontend

## StartPage

- kurze Einfuehrung
- Navigationskarten
- technische Kernpunkte
- Hinweis auf aktuellen Modellstatus

## SimulationPage

Oberer Bereich:

- Seitenkopf
- API-Status
- Rechenstatus
- Aktion `Simulation starten`

Linke Spalte:

- Fallauswahl
- Inputformular Basismodus
- aufklappbarer Expertenmodus
- Szenarienverwaltung

Rechte Spalte:

- KPI-Band
- Warnungen
- Vergleichstabelle

Unterer Bereich:

- Profilcharts in Tabs
- Exportbereich

## ModelBasisPage

- Abschnitt `Bilanzstruktur`
- Abschnitt `Materialmodell`
- Abschnitt `Geschwindigkeiten und Drag`
- Abschnitt `Druckduesen-Startgeschwindigkeit`
- Abschnitt `Annahmen und Grenzen`

## Migration vom aktuellen Stand

## Phase 0: Dokumentation und Einfrieren des aktuellen Kerns

Status: `done`

Ziel:

- Fine-Kern fachlich nicht mehr aufbrechen
- UI-Neuaufbau davon entkoppeln

Aufgaben:

- Status des neuen Kerns kurz dokumentieren
- UI-Rebuild-Plan festziehen
- aktuelle Streamlit-/Alt-UI nicht mehr erweitern

## Phase 1: Technisches Grundgeruest

Status: `done`

Ziel:

- neues Frontend-Verzeichnis
- neue API-Schicht
- einfacher Health-Check

Aufgaben:

- `frontend/` mit Vite/React/TS anlegen
- Python-API fuer neue App anlegen
- Build-/Run-Pfade wie in `powder-caking` festlegen
- `DESIGN.md` und `preview.html` aus `powder-caking` systematisch in das neue Frontend ueberfuehren
- lokale Dev-Anleitung in `README` ergaenzen

Akzeptanz:

- Frontend startet lokal
- API startet lokal
- Frontend kann `health` lesen

## Phase 2: Einzel-Szenario fuer Trocknungskinetik

Status: `in progress`

Ziel:

- ein Simulationslauf reproduzierbar ueber die neue UI

Aufgaben:

- `defaults`-Endpoint
- `simulate`-Endpoint
- Formular fuer Einzel-Szenario
- KPI-Ausgabe
- Profilplot
- Reportpunkte, strukturierte Ergebnisdaten und Export fuer den Einzel-Lauf
- fachliche Abnahme gegen Referenzlaeufe fuer `V2` und weitere MS400-Faelle

Akzeptanz:

- `V2` kann ueber die UI gerechnet werden
- Resultate stimmen mit Python-Referenzlauf des neuen Kerns ueberein

## Phase 3: Vergleichsszenarien

Status: `planned`

Ziel:

- produktiver Kernnutzen der neuen App

Aufgaben:

- Szenario-Duplikation
- Mehrfachlauf `compare`
- KPI-Vergleich
- ueberlagerte Charts
- Export

Akzeptanz:

- mindestens 3 Vergleichsszenarien nebeneinander
- unterschiedliche Tropfengroessen, `Tin`, Luftfeuchten oder Feedraten darstellbar

## Phase 4: Modellgrundlagen-Seite

Status: `planned`

Ziel:

- wissenschaftlich saubere, knappe In-App-Dokumentation

Aufgaben:

- Inhalte aus den lokalen Referenzen und dem Kern zusammenziehen
- Formeln, Annahmen und Modellpfade in lesbarer Form aufbereiten

Akzeptanz:

- Modellseite ist fuer fachliche Einordnung ausreichend
- keine externe Dokumentensuche fuer die Kernlogik noetig

## Phase 5: Verfeinerung

Status: `planned`

Erst nach stabiler V1:

- section-wise heat loss
- komfortabler Sweep-Modus
- gespeicherte Szenariensets
- Download von Profil-CSV/JSON
- spaetere Erweiterung um groessere Prozesssimulation

## Inhalte, die bewusst noch nicht in V1 sollen

- komplette Prozesssimulation
- Legacy-Kern als UI-Option
- Optimierer oder automatische Kalibrierung in der UI
- Nutzerverwaltung
- Datenbank
- dark mode

## Konkrete offene Architekturentscheidungen

Status heute:

1. Python-API-Paketname: `done` als `spray_drying`
2. Frontend lebt unter `frontend/`: `done`
3. Fuer V1 wird einfache View-Navigation genutzt, kein React Router: `done`
4. `compare`-Strategie: `planned`, aktuell noch nicht umgesetzt

Empfehlung:

1. `frontend/` direkt im Repo
2. einfache View-Navigation bis zum Vergleichsmodus beibehalten
3. Batch-Endpoint `compare` serverseitig in Phase 3 anbieten

## Erste Umsetzungsreihenfolge

Empfohlene konkrete Reihenfolge:

1. neues Frontend-Geruest wie `powder-caking` anlegen
2. neue API-Schicht fuer `stationary_smp_rea` anlegen
3. Startseite und App-Shell bauen
4. Einzel-Szenario-Endpunkt und Formular anbinden
5. KPI- und Chartbereich anbinden
6. Vergleichsszenarien bauen
7. Modellgrundlagen-Seite ergaenzen

## Empfehlung zum naechsten Arbeitsschritt

Der naechste sinnvolle Schritt nach dem aktuellen Stand ist **Phase 3 vorbereiten**:

- Szenariozustand im Frontend von Einzelfall auf Basisszenario plus Vergleichsarray erweitern
- serverseitigen `compare`-Endpoint definieren
- KPI-Matrix und ueberlagerte Profilplots fuer mehrere Szenarien aufbauen
- Delta-Darstellung gegen das Basisszenario einziehen
