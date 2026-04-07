from __future__ import annotations

import pandas as pd
import streamlit as st


def render_equation(title: str, equation: str, explanation: str) -> None:
    st.markdown(f"**{title}**")
    st.latex(equation)
    st.caption(explanation)


st.title("Sprühtrockner REA")
st.write(
    "Die Anwendung bildet einen einfachen Sprühtrockner als Plug-Flow-System im Gleichstrom ab. "
    "Sie koppelt Partikel- und Luftzustand über ein steifes ODE-System und berechnet daraus "
    "Feuchteverlauf, Temperaturverlauf, Partikelgröße, Luftbeladung und Austrittswerte."
)
st.write(
    "Fachlich basiert das Modell auf einem REA-Ansatz für die gekoppelte Beschreibung von "
    "Feuchte-, Temperatur- und Bewegungsverlauf. Für SMP mit 20 % und 30 % TS wird zusätzlich "
    "eine sehr kurze wasserartige Anfangsphase berücksichtigt, bevor auf die kalibrierte "
    "REA-Materialfunktion umgeschaltet wird. SMP mit 50 % TS bleibt direkt auf REA."
)

st.divider()
st.subheader("A. Überblick")
st.markdown(
    "- Plug-Flow-Modell im Gleichstrom\n"
    "- Monodisperse Tropfen ohne Tropfenwechselwirkung\n"
    "- Gekoppelte Lösung von Produkt-, Luft- und Bewegungszustand\n"
    "- REA-basierte Trocknung mit materialabhängiger Schließung"
)

overview_left, overview_right = st.columns(2)
with overview_left:
    st.markdown("**Was berechnet wird**")
    st.markdown(
        "- Produktfeuchte `X`\n"
        "- Partikeltemperatur `T_p`\n"
        "- Lufttemperatur `T_b`\n"
        "- Luftfeuchte `Y`\n"
        "- Höhe `H` und Partikelgeschwindigkeit `v_p`"
    )
with overview_right:
    st.markdown("**Wofür die App gedacht ist**")
    st.markdown(
        "- Technische Vorstudien\n"
        "- Betriebspunktvergleiche\n"
        "- Sensitivitäts- und Szenarioanalysen\n"
        "- Schnelle Bewertung von Austrittsfeuchte und Trocknungshöhe"
    )

st.divider()
st.subheader("B. Berechnungsablauf")
st.markdown(
    "1. Eingaben normieren: Temperaturen, Massenströme und Feuchtegrößen werden in die Modellbasis überführt.\n"
    "2. Anfangszustand bilden: Aus TS-Gehalt, Tropfengröße und Materialdaten entstehen `X_0`, `m_s` und weitere Startwerte.\n"
    "3. Hilfsmodelle evaluieren: Relative Feuchte, Gleichgewichtsfeuchte, Schrumpfung, Nusselt-, Sherwood- und REA-Terme werden berechnet.\n"
    "4. ODE-System lösen: Der BDF-Solver integriert alle Zustandsgrößen gleichzeitig.\n"
    "5. Zeitreihen nachbearbeiten: Durchmesser, Trocknungszeit, Trocknungshöhe und Austrittswerte werden rekonstruiert.\n"
    "6. Ergebnisse bewerten: KPIs, Warnungen, Diagramme und Exporte werden aufbereitet."
)

st.divider()
st.subheader("C. Praktische Nutzung")
st.markdown(
    "1. Auf `Simulation` einen Basisfall oder ein Preset setzen.\n"
    "2. Optional Vergleichsszenarien über ausgewählte Overrides anlegen.\n"
    "3. Ein Bewertungsziel für die Austrittsfeuchte definieren.\n"
    "4. Auf `Ergebnisse` Trocknungshöhe, Austrittsfeuchte, Austritts-Temperatur und Kurven vergleichen."
)
st.caption(
    "Praxisregel: Wenn die berechnete Trocknungshöhe kleiner ist als die reale Trocknerhöhe, "
    "ist die gewählte Kombination aus Luftzustand, Tropfengröße und Feedbelastung im Modell "
    "grundsätzlich ausreichend."
)

st.divider()
st.subheader("D. Zustandsgrößen")
state_frame = pd.DataFrame(
    [
        {"Symbol": "X", "Bedeutung": "Produktfeuchte, kg Wasser pro kg Feststoff", "Einheit": "kg/kg"},
        {"Symbol": "T_p", "Bedeutung": "Partikeltemperatur", "Einheit": "K"},
        {"Symbol": "T_b", "Bedeutung": "Lufttemperatur im Trockner", "Einheit": "K"},
        {"Symbol": "Y", "Bedeutung": "Absolute Luftfeuchte", "Einheit": "kg/kg"},
        {"Symbol": "H", "Bedeutung": "Axiale Partikelposition", "Einheit": "m"},
        {"Symbol": "v_p", "Bedeutung": "Axiale Partikelgeschwindigkeit", "Einheit": "m/s"},
        {
            "Symbol": r"\rho_{p,crit}",
            "Bedeutung": "Kritische Partikeldichte nach Krustenbildung im Ballon-Bereich",
            "Einheit": "kg/m³",
        },
    ]
)
st.dataframe(state_frame, use_container_width=True, hide_index=True)
st.latex(r"\mathbf{z}(t) = \begin{bmatrix} X & T_p & T_b & Y & H & v_p & \rho_{p,\mathrm{crit}} \end{bmatrix}^{\mathsf{T}}")
st.caption(
    "Dieser Zustandsvektor wird vom ODE-Solver integriert. Die Anfangswerte werden direkt aus "
    "Zuluft, Feed, TS-Gehalt, Tropfengröße und Materialdaten abgeleitet."
)

st.divider()
st.subheader("E. Differentialgleichungen des Modells")
st.write(
    "Im Kern löst die App ein gekoppeltes, steifes Anfangswertproblem. Die folgenden Gleichungen "
    "entsprechen der fachlichen Struktur der Implementierung."
)

ode_left, ode_right = st.columns(2)
with ode_left:
    render_equation(
        "1. Produktfeuchte",
        r"\frac{dX}{dt} = \frac{1}{m_s}\,\frac{dm_{p,w}}{dt}",
        "Die Feuchteänderung ergibt sich aus dem Wasserverlust des Partikels bezogen auf die Feststoffmasse.",
    )
    st.latex(
        r"\frac{dm_{p,w}}{dt} = \begin{cases} -\,h_m A_p \left(\rho_{v,s} - \rho_{v,b}\right), & X > X_e \\ 0, & X \leq X_e \end{cases}"
    )
    st.caption(
        "Verdunstet wird nur, solange die aktuelle Feuchte oberhalb der Gleichgewichtsfeuchte liegt. "
        "Dann treibt der Unterschied zwischen Oberflächen- und Luftdampfdichte den Stoffübergang."
    )

    render_equation(
        "2. Partikeltemperatur",
        r"\frac{dT_p}{dt} = \frac{\alpha A_p \left(T_b - T_p\right) + \left(H_v + q_{stn}\right)\frac{dX}{dt}m_s}{m_p c_p}",
        "Der erste Term beschreibt den konvektiven Wärmeeintrag aus der Luft, der zweite die energetische Wirkung der Verdunstung.",
    )

    render_equation(
        "3. Luftfeuchte",
        r"\frac{dY}{dt} = -\,\frac{N_p\,m_s\,\frac{dX}{dt}}{G}",
        "Das vom Partikel abgegebene Wasser erhöht die Beladung der Trocknungsluft.",
    )

    render_equation(
        "4. Lufttemperatur",
        r"\frac{dT_b}{dt} = \frac{\frac{dH_{\mathrm{air}}}{dt} - \frac{dY}{dt}\left(H_v + c_{pv}T_b\right)}{c_{p,\mathrm{air}} + c_{pv}Y}",
        "Die Luft kühlt ab, weil sie Wärme an Partikel und Verdunstung abgibt.",
    )
    st.latex(
        r"\frac{dH_{\mathrm{air}}}{dt} = -\,\frac{m_s\left(c_{ps} + X c_{pw}\right)\frac{dT_p}{dt}N_p + Q_{\mathrm{loss}}}{G}"
    )
    st.caption("Über diesen Enthalpieterm gehen auch Wärmeverluste an die Umgebung in die Luftbilanz ein.")

with ode_right:
    render_equation(
        "5. Höhe im Trockner",
        r"\frac{dH}{dt} = v_p",
        "Die Partikelhöhe folgt direkt aus der axialen Geschwindigkeit und liefert die Trocknungshöhe.",
    )

    render_equation(
        "6. Partikelgeschwindigkeit",
        r"\frac{dv_p}{dt} = \left(1 - \frac{\rho_{\mathrm{air}}}{\rho_p}\right)g - 0.75\,\frac{\rho_{\mathrm{air}} C_D U_{\mathrm{rel}}\left(v_p - v_b\right)}{\rho_p d_p}",
        "Die Bewegung wird durch Gewicht/Auftrieb und den aerodynamischen Widerstand bestimmt.",
    )

    render_equation(
        "7. Kritische Dichte nach Krustenbildung",
        r"\frac{d\rho_{p,\mathrm{crit}}}{dt} = \begin{cases} 0, & X \geq X_{\mathrm{crit}} \\ \dfrac{6\,\frac{dm_{p,w}}{dt}}{d_p A_p}, & X < X_{\mathrm{crit}} \end{cases}",
        "Dieser Term wird nur im Ballon-Schrumpfungsbereich aktiv und beschreibt die Dichteänderung nach Krustenbildung.",
    )

st.divider()
st.subheader("F. Hilfsmodelle und Schließungen")

with st.expander("Luftzustand und Gleichgewichtsfeuchte", expanded=True):
    st.latex(r"\mathrm{RH} = \left(\frac{p}{p_{\mathrm{sat}}(T_b)}\right)\frac{Y}{0.622 + Y}")
    st.latex(
        r"X_e = \frac{C K \cdot 0.06156 \cdot \mathrm{RH}}{\left(1 - K\,\mathrm{RH}\right)\left(1 - K\,\mathrm{RH} + C K\,\mathrm{RH}\right)}"
    )
    st.latex(r"C = 0.001645 \exp\left(\frac{24831}{R T_b}\right), \qquad K = 5.710 \exp\left(\frac{-5118}{R T_b}\right)")
    st.caption(
        "Die GAB-Schließung liefert die Gleichgewichtsfeuchte `X_e`. Sie definiert, ab wann die "
        "Verdunstungstriebkraft verschwindet."
    )

with st.expander("Schrumpfung und Partikeldurchmesser", expanded=False):
    st.latex(r"\text{SMP, } TS = 0.3: \qquad d_p = d_{p,i}\left(0.76 + (1-0.76)\frac{X-X_e}{X_i-X_e}\right)")
    st.latex(r"\text{SMP, } TS = 0.2: \qquad d_p = d_{p,i}\left(0.67 + (1-0.67)\frac{X-X_e}{X_i-X_e}\right)")
    st.latex(r"\text{SMP, } TS = 0.5: \qquad d_p = d_{p,i}\left(0.0447\,(X-X_e) + 0.959\right)")
    st.latex(r"\text{WPC, } TS = 0.3: \qquad d_p = d_{p,i}\left(0.873 + (1-0.873)\frac{X-X_e}{X_i-X_e}\right)")
    st.latex(
        r"\text{TS} < 0.2: \qquad d_p = d_{p,i}\left(\frac{\rho_{\mathrm{milk}} - 1000}{\rho_{p,\mathrm{ballon}} - 1000}\right)^{1/3}"
    )
    st.caption(
        "Der Partikeldurchmesser wird materialspezifisch geschlossen. Damit beeinflusst die "
        "Schrumpfung direkt Oberfläche, Stoffübergang und Partikelbewegung."
    )

with st.expander("Wärme- und Stoffübergang", expanded=False):
    st.latex(
        r"\mathrm{Re} = \frac{d_p U_{\mathrm{rel}} \rho_{\mathrm{air}}}{\nu}, \qquad \mathrm{Pr} = \frac{c_{p,\mathrm{air}} \nu}{k_b}, \qquad \mathrm{Sc} = \frac{\nu}{D_m \rho_{\mathrm{air}}}"
    )
    st.latex(
        r"\mathrm{Nu} = 2.04 + 0.62\,\mathrm{Re}^{1/2}\,\mathrm{Pr}^{1/3}, \qquad \mathrm{Sh} = 1.54 + 0.54\,\mathrm{Re}^{1/2}\,\mathrm{Sc}^{1/3}"
    )
    st.latex(r"\alpha = \frac{\mathrm{Nu}\,k_b}{d_p}, \qquad h_m = \frac{\mathrm{Sh}\,D_{wm}\,M_w}{d_p\,\rho_{\mathrm{air}}}")
    st.caption(
        "Die Kopplung zwischen Luft und Partikel erfolgt über Nu- und Sh-Korrelationen. "
        "Daraus entstehen Wärmeübergangskoeffizient `α` und Stoffübergangskoeffizient `h_m`."
    )

with st.expander("REA-Modell der Trocknung", expanded=False):
    st.latex(r"E_{v,b} = - R T_b \ln\left(\frac{\rho_{v,b}}{\rho_{v,\mathrm{sat}}(T_b)}\right)")
    st.latex(r"E_v = f_{\mathrm{mat}}(X, X_e)\,E_{v,b}, \qquad \psi = \exp\left(\frac{-E_v}{R T_p}\right)")
    st.latex(r"\rho_{v,s} = \psi\,\rho_{v,\mathrm{sat}}(T_p)")
    st.caption(
        "Das REA-Modell beschreibt, wie die Trocknung mit sinkender Feuchte schwieriger wird. "
        "Damit wird die zweite Trocknungsphase realistisch abgebildet."
    )
    st.caption(
        "Für SMP mit 20 % und 30 % TS wird in der App zusätzlich eine sehr kurze Anfangsphase "
        "mit wasserartiger Oberflächenaktivität berücksichtigt."
    )

st.divider()
st.subheader("G. Numerische Lösung und Grenzen")
num_left, num_right = st.columns(2)
with num_left:
    st.markdown("**Warum BDF verwendet wird**")
    st.write(
        "Wärmeübergang, Stoffübergang und Geschwindigkeitsanpassung laufen auf deutlich "
        "schnelleren Zeitskalen ab als der spätere Feuchteabbau. Dadurch entsteht ein steifes "
        "ODE-System, das mit einem BDF-Solver robust integriert werden kann."
    )
with num_right:
    st.markdown("**Bewusst vereinfachte Modellgrenzen**")
    st.markdown(
        "- Keine Tropfenwechselwirkung und kein Tropfenspektrum\n"
        "- Eindimensionales Plug-Flow-Bild statt CFD-Auflösung\n"
        "- Materialfunktionen nur im hinterlegten Gültigkeitsbereich\n"
        "- Bewertungsziel für Austrittsfeuchte dient der Interpretation, nicht als Solver-Abbruch"
    )

st.caption("Navigation über die Seitenleiste: Überblick, Simulation, Ergebnisse.")
