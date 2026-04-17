# Stationary SMP REA Fine Model: Status 2026-04-17

## Zweck

Diese Notiz haelt den aktuellen Implementierungsstand des neuen Fine-Kerns unter `core/stationary_smp_rea/` fest, inklusive der wichtigsten Diagnoseerkenntnisse fuer den MS400-Fall `V2`.

## Implementierungsstand

- Aktiver Arbeitskern: `core/stationary_smp_rea/`
- Legacy-Kern und `core/model.py` dienen nur als Referenz und wurden nicht weiter umgebaut.
- Der V2-Builder in `core/stationary_smp_rea/ms400.py` nutzt aktuell standardmaessig:
  - `humid_air_mass_flow_kg_h = 304`
  - `x_b_model = "lin_gab"`
- Die Luftenthalpiebilanz im Fine-Kern enthaelt inzwischen den fehlenden Fluessigwasser-Anteil der Partikelenthalpie:
  - `cp_w * (T_p - T_ref) * dX/dh`
- Weiteres Verdampfen wird jetzt unterbunden, sobald das lokale Gleichgewicht erreicht oder unterschritten ist:
  - Falls `X <= x_b` und der berechnete Massenfluss weiter trocknen wuerde, wird `dm_p/dh = 0` gesetzt.

## Aktuelle Referenz fuer V2 mit Builder-Defaults

Experimentelle Referenz fuer `V2`:

- `Tout = 92.0 degC`
- Pulverfeuchte `= 3.2 wt% wb`

Aktuelle Fine-Modell-Ergebnisse fuer `304 kg/h` feuchte Luft:

- `baseline_dynamic`
  - `Tout_pre_cyclone = 61.82 degC`
  - Pulverfeuchte `= 2.695 wt% wb`
  - `RHout = 26.15 %`
  - Abweichung zu Experiment:
    - `dTout = -30.18 K`
    - `dFeuchte = -0.505 wt%-Punkte`
- `dynamic_no_heat_loss`
  - `Tout_pre_cyclone = 92.04 degC`
  - Pulverfeuchte `= 2.223 wt% wb`
  - `RHout = 7.62 %`
  - Abweichung zu Experiment:
    - `dTout = +0.043 K`
    - `dFeuchte = -0.977 wt%-Punkte`
- `fixed_velocities_from_baseline_pre_cyclone`
  - `Tout_pre_cyclone = 60.61 degC`
  - Pulverfeuchte `= 6.076 wt% wb`
  - `RHout = 27.12 %`

## Wichtigste Diagnoseerkenntnisse

### 1. Die fruehere Luftenthalpie-Inkonsistenz ist behoben

- Vor dem Fix war die Luftseite selbst bei `Qloss = 0` noch deutlich zu kalt.
- Nach dem Fix der Gasenthalpiebilanz trifft der Fall `dynamic_no_heat_loss` den Luft-Endzustand fast exakt.
- Der verbleibende Hauptfehler im Default-Fall ist deshalb nicht mehr primaer die Luftenthalpieformel.

### 2. Das Modell trocknet lokal weiterhin zu schnell

- Der aktuelle Kern erreicht im V2-Fall die niedrigen Feuchten zu frueh entlang der effektiven Trocknungsbahn.
- Das gilt besonders fuer den fruehen fallenden Trocknungsabschnitt nach dem Uebergang in die zweite Phase.
- Der spaete "Tail" ist nicht der Haupttaeter:
  - Nach Erreichen der niedrigen Feuchten laeuft das Modell in vielen Faellen nur noch lange mit kaum weiterer Trocknung weiter.

### 3. Das Problem sitzt nicht nur in der Verweilzeit

- Fuer `V2`, `14 kg/h`, `heat_loss_coeff_w_m2k = 2.0`, `304 kg/h` Luft ergibt der dynamische Fall:
  - `Tout_pre_cyclone = 87.41 degC`
  - Pulverfeuchte `= 1.206 wt% wb`
  - `RHout = 7.80 %`
  - `tau_out = 22.93 s`
- Wenn die Geschwindigkeiten auf die dynamischen Pre-Cyclone-Werte fixiert werden, verschiebt sich derselbe Fall auf deutlich hoehere Endfeuchten:
  - nur `U_a` fix: `2.414 wt% wb`, `tau_out = 1.41 s`
  - nur `U_p` fix: `1.922 wt% wb`, `tau_out = 1.45 s`
  - `U_a` und `U_p` fix: `2.375 wt% wb`, praktisch auf lokalem `x_b`

Schluss daraus:

- Die dynamische Geschwindigkeits-/Verweilzeitkopplung treibt einen wichtigen Teil der Uebertrocknung.
- Aber selbst bei unrealistisch kurzer Verweilzeit von nur etwa `1.4-1.5 s` kommt das Modell schon sehr nah an das Gleichgewicht.
- Deshalb ist nicht nur `tau` das Problem; die lokale Trocknungskinetik selbst ist ebenfalls zu aggressiv.

### 4. Die spaete REA-Retardierung ist wahrscheinlich zu schwach

Fuer den Fall `V2`, `14 kg/h`, `heat_loss_coeff_w_m2k = 2.0` zeigt die Auswertung in Zeitkoordinaten:

- Die Trocknung von etwa `6-7 wt% wb` auf etwa `1-2 wt% wb` passiert im Modell in grob `1 s`.
- Danach wird wegen des neuen Guards praktisch nicht mehr weitergetrocknet.
- Der problematische Abschnitt ist damit der fruehe Falling-Rate-Bereich, nicht die allerletzte Endphase.

Das deutet auf zu schwache Retardierung in mindestens einem dieser Pfade hin:

- REA-`psi(delta)` im Bereich `X <= 0.08 db`
- Stoffuebergangskoeffizient `h_m`
- effektive Partikeloberflaeche bzw. Schrumpfung

## Feedrate-Sweep mit den aktuellen Defaults

V2 bei `304 kg/h` feuchter Luft:

- `12 kg/h`, `Qloss = 0`
  - `Tout = 115.73 degC`
  - Pulverfeuchte `= 0.630 wt% wb`
  - `RHout = 2.57 %`
- `14 kg/h`, `Qloss = 0`
  - `Tout = 105.98 degC`
  - Pulverfeuchte `= 1.083 wt% wb`
  - `RHout = 4.00 %`
- `16 kg/h`, `Qloss = 0`
  - `Tout = 96.59 degC`
  - Pulverfeuchte `= 1.777 wt% wb`
  - `RHout = 6.16 %`
- `12 kg/h`, `heat_loss_coeff_w_m2k = 2.0`
  - `Tout = 94.96 degC`
  - Pulverfeuchte `= 0.704 wt% wb`
  - `RHout = 5.23 %`
- `14 kg/h`, `heat_loss_coeff_w_m2k = 2.0`
  - `Tout = 87.41 degC`
  - Pulverfeuchte `= 1.206 wt% wb`
  - `RHout = 7.80 %`
- `16 kg/h`, `heat_loss_coeff_w_m2k = 2.0`
  - `Tout = 80.12 degC`
  - Pulverfeuchte `= 1.959 wt% wb`
  - `RHout = 11.49 %`

## Abweichung zur praktischen Erwartung

- Die modellierten Endfeuchten sind fuer mehrere V2-Faelle zu niedrig.
- Die Kombination aus niedriger Endfeuchte und sehr frueher Austrocknung ist nicht plausibel fuer eine Pilotturmanlage mit Partikelverweilzeiten im Bereich grob `10-17 s`.
- Literaturhinweise zu Pilotanlagen und RTD sprechen eher fuer deutlich laengere Partikelverweilzeiten und Partikel/Gas-Residence-Time-Verhaeltnisse nahe `1.0-1.6`, nicht fuer einen fast vollstaendigen Endfeuchteabfall in rund `1-1.5 s`.

## Zusaetzliche Materialdiagnose mit `xi_eff` und `DeltaE_add`

Zur besseren Einordnung wurde fuer den Fall `V2`, `14 kg/h`, `304 kg/h` Luft, `heat_loss_coeff_w_m2k = 2.0`, `x_b_model = "lin_gab"` ein lokaler Materialdiagnosepfad aufgebaut:

- Script:
  - `docs/_local/stationary_smp_rea/scripts/generate_stationary_smp_rea_v2_material_retardation_diagnostics.py`
- CSV:
  - `docs/_local/stationary_smp_rea/data/stationary_smp_rea_v2_material_retardation_diagnostics.csv`

### 1. Bedeutung von `xi_eff`

`xi_eff` ist hier **keine** neue CDC-Modellgleichung im Kern, sondern eine reine Diagnosegroesse:

- Sie beschreibt, welcher Anteil der lokalen unbehinderten Dampfdichte-Triebkraft im aktuellen REA-Zustand noch wirksam ist.
- Mit
  - `rho_v_surface = psi * rho_v_sat(T_p)`
  - `rho_v_air =` Dampfdichte der Luft
  - `rho_v_sat =` Saettigungsdampfdichte bei `T_p`
  ergibt sich diagnostisch:
  - `xi_eff = (rho_v_surface - rho_v_air) / (rho_v_sat - rho_v_air)`

Interpretation:

- `xi_eff = 1`: lokal praktisch unbehinderte Trocknung
- `xi_eff -> 0`: lokal stark behinderte Trocknung bzw. fast Gleichgewicht

### 2. Bedeutung von `DeltaE_add`

`DeltaE_add` ist ebenfalls nur eine Diagnosegroesse:

- Es ist die zusaetzliche Aktivierungsenergie, die der aktuelle REA-Zustand lokal noch braeuchte, um von dort aus im Mittel nur bis zur experimentellen Ziel-Endfeuchte weiterzutrocknen.
- Das ist **kein** exakter inverser Solver, sondern eine heuristische "average-to-target"-Groesse entlang der verbleibenden Zeit bis zum Austritt.

### 3. Ergebnis der `xi_eff`-Diagnose

Fuer den kritischen Bereich ergibt sich:

- bei `~12.34 wt% wb`
  - `psi_current ~ 0.05335`
  - `xi_eff_current ~ 6.65e-3`
  - `DeltaE_add_avg_to_target ~ 389 J/mol`
- bei `~6.70 wt% wb`
  - `psi_current ~ 0.04705`
  - `xi_eff_current ~ 2.33e-3`
  - `DeltaE_add_avg_to_target ~ 150 J/mol`
- bei `~4.13 wt% wb`
  - `psi_current ~ 0.04484`
  - `xi_eff_current ~ 1.17e-3`
  - `DeltaE_add_avg_to_target ~ 79 J/mol`
- bei `~2.74 wt% wb`
  - `psi_current ~ 0.04379`
  - `xi_eff_current ~ 5.96e-4`
  - `DeltaE_add_avg_to_target ~ 41 J/mol`

Schluss daraus:

- Die aktuelle Materialbremse ist im relevanten Bereich bereits stark.
- Die wirksame lokale Triebkraft ist dort schon winzig.
- Trotzdem trocknet das Modell noch zu schnell weiter.
- Das spricht **nicht** primaer fuer einen weiteren Transportfix, sondern fuer eine zu schwache Form der Materialfunktion genau im fruehen Falling-Rate-Bereich.

### 4. Folgerung fuer die Modellrichtung

Die `xi_eff`-Auswertung stuetzt damit die folgende fachliche Richtung:

- `REA` bleibt das produktive Modell.
- `CDC` bleibt, wenn ueberhaupt, nur Diagnose- und Vergleichssprache.
- Die naechste produktive Aenderung sollte an der **Materialfunktion** erfolgen, nicht an `h_m`, nicht an der Gasenthalpiebilanz und nicht als pauschaler Geschwindigkeitsfix.

## Vorschlag fuer die naechste REA-Anpassung

### 1. Wo die Aenderung sitzen sollte

Die Aenderung sollte in der Materialclosure unter

- `core/stationary_smp_rea/materials/smp_chew.py`

erfolgen, nicht in:

- `core/stationary_smp_rea/transport.py`
- `core/stationary_smp_rea/balances.py`

### 2. Bevorzugte Form der Anpassung

Die sauberste REA-konforme Form ist ein **zusaetzlicher materialseitiger Anteil auf die normalisierte Aktivierungsenergie**:

- aktuell:
  - `DeltaE_v = reduced_ratio_base * DeltaE_v,max`
- vorgeschlagen:
  - `DeltaE_v = reduced_ratio_total * DeltaE_v,max`
  - mit
    - `reduced_ratio_total = reduced_ratio_base + reduced_ratio_add`

wobei `reduced_ratio_add`:

- weich ist
- nur im fruehen Falling-Rate-Bereich aktiv ist
- Richtung Gleichgewicht wieder abklingt

### 3. Qualitative Zielform

Die zusaetzliche REA-Retardierung sollte kein globales "alles trocknet langsamer" sein, sondern eher ein Fenster:

- bei hoher Feuchte:
  - nahezu kein Zusatzterm
- kurz nach Beginn des Falling-Rate-Bereichs:
  - merkliche zusaetzliche Bremsung
- im spaeten Tail nahe `x_b`:
  - Zusatzterm wieder klein bis auslaufend

Das entspricht eher einem fruehen `skin onset`-/Struktur-Effekt als einer pauschalen globalen Korrektur.

### 4. Warum nicht zuerst Transport oder Basis-Chew global aendern

Weniger attraktiv als erster Schritt sind:

- pauschales Absenken von `h_m`
- pauschales Vergroessern der Partikelflaeche/-groesse
- globales Ueberschreiben der Geschwindigkeiten
- globales Umformen der gesamten Basis-Chew-Kurve ohne lokale Begrenzung

Grund:

- Diese Hebel sind weniger selektiv.
- Sie wuerden auch Abschnitte veraendern, die aktuell nicht als Hauptfehlerbild auffallen.
- Die Diagnose spricht staerker fuer eine lokale materialseitige Zusatzbremse als fuer einen globalen Transferfehler.

### 5. Praktischer naechster Implementierungsschritt

Wenn die REA-Anpassung produktiv umgesetzt wird, sollte zuerst ein kleiner, parametrisierter Zusatzterm in `smp_chew.py` erprobt werden:

- neue Hilfsfunktion, z. B. fuer einen fruehen Falling-Rate-Zusatzterm
- Addition auf `reduced_ratio_base`
- zunaechst nur lokal aktiv fuer den kritischen `delta`-Bereich
- anschliessend Diagnose-Sweep gegen
  - V2-Endfeuchte
  - V2-Tout
  - Lage und Dauer des kritischen Trocknungsabschnitts

Arbeitsurteil:

- Ja, die naechste sinnvolle Stellschraube ist die **Materialfunktion**.
- `xi_eff` und `DeltaE_add` sind nuetzliche Diagnosegroessen, um diese Anpassung gezielt zu formen.
- Die wahrscheinlich beste erste produktive Aenderung ist ein **weicher frueher Zusatzterm auf die REA-Aktivierungsenergie**, nicht ein Wechsel des Massenmodells.

## Naechste sinnvolle Schritte

1. Den post-`X <= 0.08 db`-Abschnitt gezielt nachkalibrieren.
   - REA-`psi(delta)` im Falling-Rate-Bereich diagnostisch verschaerfen.
   - Optional einen expliziten spaeten Diffusions-/Shell-Faktor einfuehren.

2. `h_m` und die Transportseite im Spaetbereich isoliert pruefen.
   - Sherwood-Niveau
   - Re-Abfall
   - Einfluss der kleinen Relativgeschwindigkeit

3. Schrumpfung und effektive Oberflaeche gegen Plausibilitaet pruefen.
   - `D/D0`
   - `A_p`
   - `A_p / m_s`

4. Die Geschwindigkeitsseite fachlich einordnen.
   - Warum faellt `U_p_mean` im dynamischen Fall so stark ab?
   - Ist `tau_out ~ 23 s` fuer die effektive 1D-Bahn plausibel?
   - Welche Teile davon repraesentieren reale RTD und welche nur Modellartefakte?

5. Fuer den relevanten Spaetabschnitt Diagnoseplots bzw. CSVs in Zeitkoordinaten behalten.
   - `dX/dt`
   - `psi`
   - `h_m`
   - `A_p`
   - Dampfdichte-Triebkraft

## Lokale Ablage

Diese Notiz sowie die aktuellen V2-Diagnosegeneratoren und CSVs liegen bewusst unter:

- `docs/_local/stationary_smp_rea/`

Sie sind in `.gitignore` aufgenommen und sollen lokal bleiben, bis klar ist, welche Diagnoseartefakte dauerhaft ins Repo gehoeren.
