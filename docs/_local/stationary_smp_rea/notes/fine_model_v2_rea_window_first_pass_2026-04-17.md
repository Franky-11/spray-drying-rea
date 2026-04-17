# V2 REA Material Window: First Pass 2026-04-17

## Eingriff

- Datei:
  - `core/stationary_smp_rea/materials/smp_chew.py`
- Neue Form:
  - `reduced_ratio_total = reduced_ratio_base + reduced_ratio_add`
  - `DeltaE_v = reduced_ratio_total * DeltaE_v,max`
  - `psi = exp(-DeltaE_v / (R * T_p))`
- Zusatzterm:
  - `reduced_ratio_add = k_add * delta * sigmoid((center - delta_norm) / width)`
  - mit
    - `k_add = 1.29`
    - `delta_norm = delta / (X0 - x_b)`
    - `center = 0.12`
    - `width = 0.025`

Interpretation:

- Die Fensterung schaltet die Zusatzbremse erst im fruehen Falling-Rate-Bereich weich ein.
- Der lineare `delta`-Faktor laesst den Zusatzterm nahe `x_b` wieder auslaufen.
- Transport, `h_m`, Geschwindigkeiten und Legacy-Code bleiben unveraendert.

## V2 Referenzfall

Fall:

- `label = V2`
- `feed_rate_kg_h = 14`
- `humid_air_mass_flow_kg_h = 304`
- `heat_loss_coeff_w_m2k = 2.0`
- `x_b_model = "lin_gab"`

Vorher:

- `Tout_pre_cyclone = 87.413 degC`
- Pulverfeuchte `= 1.206 wt% wb`
- `RHout = 7.803 %`
- `tau_out = 22.927 s`

Nachher:

- `Tout_pre_cyclone = 87.847 degC`
- Pulverfeuchte `= 3.155 wt% wb`
- `RHout = 7.602 %`
- `tau_out = 22.645 s`

Delta:

- `dTout_pre_cyclone = +0.434 K`
- `dPowderMoisture = +1.948 wt%-Punkte`
- `dRHout = -0.201 %-Punkte`
- `dtau_out = -0.282 s`

## Profilverschiebung

- `~12.34 wt% wb`
  - vorher bei `h = 0.145 m`, `tau = 0.313 s`
  - nachher bei `h = 0.184 m`, `tau = 0.645 s`
- `~6.70 wt% wb`
  - vorher bei `h = 0.158 m`, `tau = 0.425 s`
  - nachher bei `h = 0.698 m`, `tau = 5.081 s`
- `~2.74 wt% wb`
  - vorher bei `h = 0.184 m`, `tau = 0.655 s`
  - nachher im Referenzfall nicht mehr erreicht; Austritt bei `3.155 wt% wb`

Schluss:

- Die kritische Uebertrocknung wird deutlich nach hinten verschoben.
- Der Effekt sitzt damit tatsaechlich im fruehen Falling-Rate-Bereich und nicht primaer im spaeten Tail.
- Die erste Materialanpassung trifft die Zielgroessenordnung der Endfeuchte bereits brauchbar, ist aber noch klar ein erster Kalibrierschritt.

## Diagnoseoutput

- Das lokale Diagnoseskript schreibt jetzt zusaetzlich:
  - `normalized_delta`
  - `activation_ratio_base`
  - `activation_ratio_add`
  - `activation_ratio_total`
- Script:
  - `docs/_local/stationary_smp_rea/scripts/generate_stationary_smp_rea_v2_material_retardation_diagnostics.py`
- CSV:
  - `docs/_local/stationary_smp_rea/data/stationary_smp_rea_v2_material_retardation_diagnostics.csv`
