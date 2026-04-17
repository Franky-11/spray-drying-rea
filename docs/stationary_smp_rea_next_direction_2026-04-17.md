# Stationary SMP REA: Naechste Modellrichtung am 2026-04-17

## Kurzfazit

Empfohlen wird kein harter Wechsel auf einen CDC-Kern. Die sinnvollste Richtung ist ein `REA`-Kern mit einem vorgeschalteten `REA+CDC`-Diagnosevergleich:

- `REA` bleibt das eigentliche Modell.
- `CDC` dient als Referenz- und Plausibilitaetsdiagnose fuer die Form der notwendigen Retardierung.
- Die naechste Implementierung sollte die `REA`-Retardierung im fruehen Falling-Rate-Bereich staerker machen, ohne die Massentriebkraft auf ein anderes physikalisches Konzept umzustellen.

## Warum kein expliziter CDC-Wechsel

Die vorhandenen Referenzen im Repo sprechen nicht dafuer, dass ein reiner `CDC`-Wechsel das aktuelle Problem sauber loest:

- `Langrish_2001.md` bewertet fuer Milchpulver eine lineare Falling-Rate-Curve als brauchbare Vereinfachung und kommt fuer spray-dryer-typische Partikelgroessen auf Trocknungszeiten in der Groessenordnung von `~1 s`.
- `Langrish (2009).md` fasst zusammen, dass `REA` fuer Milch zwar etwas naeher an den Experimenten lag als `CDC`, der Unterschied aber klein blieb.
- `Edrisi.md` nutzt zwar ein `xi`-basiertes `CDC`, aber fuer ein anderes System mit `WPI`-bedingtem sofortigem Falling-Rate-Verhalten; das ist keine tragfaehige SMP-Kalibration.

Damit ist `CDC` fachlich eher ein guter Vergleichsrahmen als ein stark begruendeter Ersatz fuer den SMP-Kern.

## Was der aktuelle Kern wahrscheinlich nicht trifft

### 1. Hauptverdacht: zu schwache REA-Retardierung im fruehen Falling-Rate-Bereich

Die problematische Strecke liegt nicht im spaeten End-Tail, sondern direkt nach dem Uebergang in den zweiten Trocknungsabschnitt.

Fuer `V2`, `14 kg/h`, `304 kg/h` Luft und `heat_loss_coeff_w_m2k = 2.0` zeigt das aktuelle Profil:

- bei `~12.34 wt% wb`: `psi ~ 0.053`, `Sh ~ 2.12`, `h_m ~ 1.57e-3 m/s`
- bei `~6.70 wt% wb`: `psi ~ 0.047`, `rho_v,s / rho_v,a ~ 1.05`
- bei `~2.00 wt% wb`: `psi ~ 0.043`, `rho_v,s / rho_v,a ~ 1.007`

Das bedeutet:

- Die Oberflaeche ist im kritischen Bereich bereits fast im Gleichgewicht mit der Luft.
- Trotzdem faellt die Feuchte noch zu schnell.
- Wenn trotz schon stark retardierter Oberflaechenbedingung noch zu schnell getrocknet wird, ist die wahrscheinlichste Luecke die Form von `psi(delta)` bzw. der zugrunde liegenden Aktivierungsenergie im fruehen Falling-Rate-Bereich.

### 2. Transportseite ist eher nicht der primaere Taeter

Im kritischen Bereich ist die Transportseite schon stark eingebrochen:

- `Re ~ 0.05`
- `Sh ~ 2.11`, also fast beim diffusionsnahen Minimum von `2`
- `h_m` ist nur noch etwa `1.56e-3 m/s`

Das ist keine uebertrieben aggressive Transportseite. Wenn das Modell dort noch zu schnell trocknet, liegt das primaer nicht an zu hoher `Ranz-Marshall`-Verstaerkung.

### 3. Schrumpfung/Flaeche wirken eher bremsend als treibend

Der Partikeldurchmesser faellt im kritischen Bereich bereits auf etwa `51-52 um`. Gegenueber dem groesseren Eintrittsdurchmesser sinkt die Flaeche deutlich. Diese Schrumpfung beschleunigt die Trocknung nicht, sondern reduziert die aeussere Austauschflaeche bereits merklich.

Deshalb ist eine "zu grosse effektive Oberflaeche" aktuell nicht die naheliegendste Hauptursache.

### 4. Geschwindigkeitskopplung bleibt wichtig, ist aber nicht die Wurzel

Die vorhandenen Velocity-Diagnosen zeigen klar:

- dynamische `U_a/U_p`-Kopplung verlaengert `tau` stark und treibt damit einen relevanten Anteil der Uebertrocknung
- selbst bei stark verkuerzter Verweilzeit trocknet der Kern aber schon fast bis ans lokale Gleichgewicht

Damit ist die Geschwindigkeitskopplung ein Verstaerker, aber nicht die primaere fehlende Physik.

## Fachliche Interpretation der Literatur fuer SMP

`Chew2013.md` ist fuer die aktuelle Frage zentral:

- die Master-Aktivierungskurve ist material- und konzentrationsspezifisch
- hoehere Anfangsfeststoffe trocknen frueh langsamer
- als Ursache wird explizit fruehere Krusten-/Skin-Bildung genannt
- der gemeinsame Polynomialast beschreibt eher die spaetere niedrigere Feuchte-Region
- der fruehe hoehere Feuchtebereich braucht den konzentrationsspezifischen linearen Ast

Das passt sehr gut zur aktuellen Beobachtung:

- der spaete Tail ist nicht das Hauptproblem
- es fehlt eher eine fruehere, staerkere Behinderung nach Beginn des Falling-Rate-Bereichs

## Empfohlene Modellrichtung

Empfohlen wird `Option 2: hybrider REA+CDC-Diagnoseansatz`, aber mit klarer Rollentrennung:

- `REA` bleibt der produktive Modellkern.
- `CDC` wird nur als Diagnosewerkzeug benutzt.
- Ein expliziter Wechsel auf `CDC` wird vorerst nicht empfohlen.

Der Grund ist pragmatisch:

- reines Weiterdrehen an `REA` ohne Vergleichsdiagnose ist zu blind
- reiner `CDC` ist fuer SMP im Repo nicht besser belegt als `REA`
- ein Diagnosevergleich sagt schnell, ob die fehlende Retardierung eher wie ein einfacher `xi(X)`-Faktor aussieht oder ob die `REA`-Kurve selbst umgeformt werden muss

## Konkrete naechste Implementierungsstrategie

### Schritt 1: REA-konforme Diagnose vor Verhaltensaenderung

Zuerst sollte diagnostisch aus dem bestehenden Profil ein "erforderlicher Zusatz-Retardierungsfaktor" im kritischen Bereich rekonstruiert werden, z. B. fuer:

- `6-15 wt% wb`
- `X - X_b`
- Zeitkoordinate `t`

Zwei hilfreiche Sichtweisen:

- ein aequivalenter `xi_eff(X)` im CDC-Sinn
- eine erforderliche Zusatz-Aktivierungsenergie `DeltaE_add(X)` im REA-Sinn

Wenn `xi_eff(X)` glatt und einfach aussieht, ist `CDC` als Diagnose nuetzlich. Implementiert werden sollte danach aber vorzugsweise `DeltaE_add(X)`, nicht `xi` selbst.

### Schritt 2: REA staerker bremsen, aber REA bleiben

Wenn die Diagnose bestaetigt, dass der fruehe Falling-Rate-Bereich zu schnell ist, sollte die erste Verhaltensaenderung REA-konform sein:

- optionaler Zusatzterm auf `DeltaE_v / DeltaE_v,max` oder direkt auf `DeltaE_v`
- nur aktiv fuer kleinen `delta = X - X_b`
- bevorzugt weich und differenzierbar, kein harter Kippschalter

Geeignete Kandidaten:

- fruehe "skin onset"-Verstaerkung fuer `delta` unter einem kalibrierbaren Schwellwert
- solids-abhaengige Verschaerfung des linearen Asts
- interpolation zwischen der `37 wt%`- und einer staerker retardierten Kurve fuer den fruehen Falling-Rate-Bereich

Weniger attraktiv als erster Schritt:

- pauschales Absenken von `h_m`
- pauschales Vergroessern des Partikels
- globales Manipulieren der Geschwindigkeiten

Diese Hebel sind unspezifischer und verschmieren die Modellursache.

## Erste Diagnosen/Literaturchecks

Als naechstes sollten zuerst diese vier Checks gemacht werden:

1. Aus dem V2-Profil ein `xi_eff(X)` und `DeltaE_add(X)` rueckrechnen.
2. Gegen `Langrish_2001` pruefen, ob die benoetigte Retardierung ueberhaupt mit einer einfachen linearen/potenzfoermigen `CDC`-Form darstellbar waere.
3. `Chew2013` gezielt darauf abklopfen, wie weit eine staerkere fruehe Behinderung noch durch die vorhandenen 37/40/43-wt%-Kurven motiviert werden kann.
4. `Zhu et al. 2011` beziehungsweise den im Repo referenzierten "modified desorption method"-Pfad sichten, ob dort fuer Dairy bereits eine saubere REA-nahe Zusatzretardierung existiert, die nicht in einen reinen CDC-Wechsel umkippt.

## Arbeitsurteil

Wenn nur eine Richtung gewaehlt werden soll:

- nicht `CDC` als neuer Hauptkern
- nicht blindes Weiterkalibrieren ohne Vergleichsrahmen
- sondern `REA` beibehalten und mit einem kurzen `CDC`-Diagnoseabgleich die fehlende Retardierungsform identifizieren

Das ist fachlich am saubersten und minimiert das Risiko, zwei verschiedene Trocknungskonzepte unbewusst zu vermischen.
