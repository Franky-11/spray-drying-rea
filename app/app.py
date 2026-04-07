from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model import (
    ScenarioConfig,
    SimulationInput,
    SimulationResult,
    results_to_excel_bytes,
    results_to_metrics_frame,
    results_to_timeseries_frame,
    run_batch,
    summarize_input,
)


st.set_page_config(page_title="Spruehtrockner REA", layout="wide")


DEFAULT_INPUT = SimulationInput()
BASE_FIELD_ORDER = [
    "dryer_height_m",
    "inlet_air_temp_c",
    "droplet_size_um",
    "feed_rate_kg_h",
    "air_flow_m3_h",
    "inlet_abs_humidity_g_kg",
    "ambient_temp_c",
    "feed_temp_c",
    "feed_total_solids",
    "material",
    "dryer_diameter_m",
    "heat_loss_coeff_w_m2k",
    "xcrit",
    "initial_droplet_velocity_ms",
    "simulation_end_s",
    "solid_density_kg_m3",
    "water_density_kg_m3",
    "protein_fraction",
    "lactose_fraction",
    "fat_fraction",
]

FIELD_LABELS = {
    "dryer_height_m": "Trocknerhoehe [m]",
    "inlet_air_temp_c": "Lufttemperatur [degC]",
    "droplet_size_um": "Tropfengroesse [um]",
    "feed_rate_kg_h": "Durchsatz [kg/h]",
    "air_flow_m3_h": "Luftmenge [m^3/h]",
    "inlet_abs_humidity_g_kg": "Absolute Zuluftfeuchte [g/kg]",
    "ambient_temp_c": "Umgebungstemperatur [degC]",
    "feed_temp_c": "Feedtemperatur [degC]",
    "feed_total_solids": "TS-Gehalt [-]",
    "material": "Material",
    "dryer_diameter_m": "Trocknerdurchmesser [m]",
    "heat_loss_coeff_w_m2k": "Waermeverlustkoeffizient Up [W/m^2K]",
    "xcrit": "Kritische Beladung Xcrit [-]",
    "initial_droplet_velocity_ms": "Anfangsgeschwindigkeit Tropfen [m/s]",
    "simulation_end_s": "Simulationsdauer [s]",
    "solid_density_kg_m3": "Feststoffdichte [kg/m^3]",
    "water_density_kg_m3": "Wasserdichte [kg/m^3]",
    "protein_fraction": "Proteinanteil [-]",
    "lactose_fraction": "Lactoseanteil [-]",
    "fat_fraction": "Fettanteil [-]",
}

PRESETS: dict[str, dict[str, Any]] = {
    "Standard": {},
    "Schonende Trocknung": {
        "inlet_air_temp_c": 165.0,
        "feed_rate_kg_h": 2.5,
        "air_flow_m3_h": 150.0,
        "droplet_size_um": 110.0,
        "feed_temp_c": 35.0,
    },
    "Schnelle Trocknung": {
        "inlet_air_temp_c": 205.0,
        "feed_rate_kg_h": 3.2,
        "air_flow_m3_h": 155.0,
        "droplet_size_um": 80.0,
        "feed_temp_c": 45.0,
    },
    "WPC 30 % TS": {
        "material": "WPC",
        "feed_total_solids": 0.3,
        "inlet_air_temp_c": 180.0,
        "droplet_size_um": 100.0,
    },
}

FIELD_GROUPS = {
    "Prozess": [
        "dryer_height_m",
        "inlet_air_temp_c",
        "droplet_size_um",
        "feed_rate_kg_h",
        "air_flow_m3_h",
        "inlet_abs_humidity_g_kg",
        "ambient_temp_c",
        "feed_temp_c",
        "feed_total_solids",
        "material",
    ],
    "Experten": [
        "dryer_diameter_m",
        "heat_loss_coeff_w_m2k",
        "xcrit",
        "initial_droplet_velocity_ms",
        "simulation_end_s",
        "solid_density_kg_m3",
        "water_density_kg_m3",
        "protein_fraction",
        "lactose_fraction",
        "fat_fraction",
    ],
}

STEP_MAP = {
    "dryer_height_m": 0.1,
    "inlet_air_temp_c": 1.0,
    "droplet_size_um": 1.0,
    "feed_rate_kg_h": 0.1,
    "air_flow_m3_h": 1.0,
    "inlet_abs_humidity_g_kg": 0.1,
    "ambient_temp_c": 1.0,
    "feed_temp_c": 1.0,
    "dryer_diameter_m": 0.05,
    "heat_loss_coeff_w_m2k": 0.1,
    "xcrit": 0.01,
    "initial_droplet_velocity_ms": 1.0,
    "simulation_end_s": 1.0,
    "solid_density_kg_m3": 10.0,
    "water_density_kg_m3": 10.0,
    "protein_fraction": 0.01,
    "lactose_fraction": 0.01,
    "fat_fraction": 0.01,
}

MIN_MAP = {
    "dryer_height_m": 0.1,
    "droplet_size_um": 1.0,
    "feed_rate_kg_h": 0.1,
    "air_flow_m3_h": 1.0,
    "inlet_abs_humidity_g_kg": 0.0,
    "dryer_diameter_m": 0.1,
    "heat_loss_coeff_w_m2k": 0.0,
    "xcrit": 0.01,
    "initial_droplet_velocity_ms": 0.1,
    "simulation_end_s": 1.0,
    "solid_density_kg_m3": 100.0,
    "water_density_kg_m3": 100.0,
    "protein_fraction": 0.0,
    "lactose_fraction": 0.0,
    "fat_fraction": 0.0,
}

SUMMARY_LABELS = {
    "initial_moisture_content": "Startbeladung X0",
    "dryer_cross_section_m2": "Querschnitt",
    "dryer_surface_m2": "Turmflaeche",
    "air_superficial_velocity_ms": "Luftgeschwindigkeit",
    "humid_air_mass_flow_kg_s": "Luftmassenstrom",
    "initial_air_density_kg_m3": "Luftdichte",
    "droplet_volume_m3": "Tropfenvolumen",
    "droplet_surface_m2": "Tropfenoberflaeche",
    "solid_mass_per_droplet_kg": "TS-Masse je Tropfen",
    "droplets_per_s": "Tropfenstrom",
    "air_residence_time_s": "Hydraulische Verweilzeit",
}

CHART_SERIES_COLORS = [
    "#D46A2E",
    "#3D7A62",
    "#3E5C76",
    "#B88B4A",
    "#7A4E6D",
]

CHART_GROUPS = {
    "Thermisch": [
        ("Tb_C", "Lufttemperatur", "degC"),
        ("Tp_C", "Partikeltemperatur", "degC"),
    ],
    "Feuchte": [
        ("X", "Produktfeuchte X", "-"),
        ("Xe", "Gleichgewichtsfeuchte Xe", "-"),
        ("RH", "Relative Luftfeuchte", "-"),
        ("Y_gkg", "Absolute Luftfeuchte", "g/kg"),
    ],
    "Partikel": [
        ("dp_um", "Partikeldurchmesser", "um"),
        ("vp", "Tropfengeschwindigkeit", "m/s"),
    ],
}


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --bg: #ffffff;
            --surface: #ffffff;
            --surface-soft: #fafafa;
            --ink: #171717;
            --muted: #4d4d4d;
            --muted-soft: #666666;
            --line: #ebebeb;
            --accent: #0a72ef;
            --accent-soft: rgba(10, 114, 239, 0.08);
            --good: #0f766e;
            --bad: #b42318;
            --shadow-ring: rgba(0, 0, 0, 0.08) 0px 0px 0px 1px;
            --shadow-card: rgba(0, 0, 0, 0.08) 0px 0px 0px 1px, rgba(0, 0, 0, 0.04) 0px 2px 2px 0px,
                rgba(0, 0, 0, 0.04) 0px 8px 8px -8px;
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(10,114,239,0.06), transparent 22%),
                linear-gradient(180deg, #ffffff 0%, #fcfcfc 100%);
            color: var(--ink);
        }
        .block-container {
            max-width: 1380px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        h1, h2, h3, h4 {
            color: var(--ink);
            letter-spacing: -0.03em;
        }
        .app-hero {
            display: grid;
            grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.8fr);
            gap: 1rem;
            margin-bottom: 1rem;
        }
        .hero-panel, .summary-panel, .section-panel, .metric-panel, .toolbar-panel {
            background: var(--surface);
            border-radius: 12px;
            box-shadow: var(--shadow-card);
            padding: 1rem 1.1rem;
        }
        .hero-kicker, .section-kicker, .meta-kicker {
            text-transform: uppercase;
            letter-spacing: 0.14em;
            font-size: 0.72rem;
            color: var(--accent);
            font-weight: 600;
        }
        .hero-title {
            font-size: 2.55rem;
            line-height: 0.98;
            margin: 0.35rem 0 0.7rem;
            color: var(--ink);
            font-weight: 600;
        }
        .hero-copy {
            color: var(--muted);
            margin: 0;
            max-width: 60ch;
        }
        .hero-meta-copy {
            color: var(--muted);
            margin-top: 0.45rem;
            line-height: 1.6;
        }
        .section-title {
            font-size: 1.35rem;
            margin: 0.35rem 0 0.2rem;
            font-weight: 600;
            color: var(--ink);
        }
        .section-copy, .summary-note, .toolbar-note, .meta-note {
            color: var(--muted-soft);
            font-size: 0.92rem;
            line-height: 1.55;
            margin: 0;
        }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.65rem 1rem;
            margin-top: 0.9rem;
        }
        .summary-item {
            padding-top: 0.65rem;
            border-top: 1px solid var(--line);
        }
        .summary-label {
            font-size: 0.78rem;
            color: var(--muted-soft);
            margin-bottom: 0.2rem;
        }
        .summary-value {
            font-size: 1.02rem;
            color: var(--ink);
            font-weight: 600;
        }
        .summary-meta {
            margin-top: 0.95rem;
            padding-top: 0.8rem;
            border-top: 1px solid var(--line);
        }
        .status-good {
            color: var(--good);
            font-weight: 700;
        }
        .status-bad {
            color: var(--bad);
            font-weight: 700;
        }
        .status-neutral {
            color: var(--muted-soft);
            font-weight: 700;
        }
        .chart-note {
            color: var(--muted);
            font-size: 0.92rem;
            margin: -0.15rem 0 0.8rem;
        }
        .section-panel {
            margin-bottom: 1rem;
        }
        .toolbar-panel {
            margin-bottom: 0.95rem;
        }
        .scenario-card, .decision-card {
            background: var(--surface);
            border-radius: 12px;
            box-shadow: var(--shadow-card);
            padding: 1rem 1.05rem;
            margin-bottom: 0.9rem;
        }
        .scenario-list {
            display: grid;
            gap: 0.55rem;
            margin-top: 0.85rem;
        }
        .scenario-row {
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 0.75rem;
            align-items: start;
            padding-top: 0.55rem;
            border-top: 1px solid var(--line);
        }
        .scenario-name {
            font-size: 0.98rem;
            color: var(--ink);
            font-weight: 600;
        }
        .scenario-copy {
            color: var(--muted);
            font-size: 0.9rem;
            line-height: 1.5;
        }
        .scenario-badge {
            font-size: 0.75rem;
            color: var(--accent);
            background: var(--accent-soft);
            border-radius: 9999px;
            padding: 0.2rem 0.55rem;
            font-weight: 600;
            white-space: nowrap;
        }
        .decision-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 0.9rem;
            margin-bottom: 1rem;
        }
        .decision-card {
            margin-bottom: 0;
        }
        .decision-scenario {
            font-size: 0.78rem;
            color: var(--muted-soft);
            margin-bottom: 0.35rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }
        .decision-status {
            font-size: 1.1rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
        }
        .decision-main {
            font-size: 1.8rem;
            color: var(--ink);
            font-weight: 600;
            margin-bottom: 0.5rem;
            letter-spacing: -0.04em;
        }
        .decision-detail {
            color: var(--muted);
            font-size: 0.92rem;
            line-height: 1.55;
        }
        .decision-note {
            color: var(--muted-soft);
            font-size: 0.82rem;
            margin-top: 0.65rem;
            padding-top: 0.65rem;
            border-top: 1px solid var(--line);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }
        .stTabs [data-baseweb="tab"] {
            border-radius: 9999px;
            box-shadow: var(--shadow-ring);
            padding-inline: 0.95rem;
            color: var(--muted);
            background: var(--surface);
        }
        .stTabs [aria-selected="true"] {
            background: var(--ink);
            color: #ffffff;
        }
        .stTabs [data-baseweb="tab-panel"] {
            padding-top: 1rem;
        }
        @media (max-width: 980px) {
            .app-hero {
                grid-template-columns: 1fr;
            }
            .summary-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _ensure_base_state() -> None:
    defaults = asdict(DEFAULT_INPUT)
    for field in BASE_FIELD_ORDER:
        key = f"base_{field}"
        if key not in st.session_state:
            st.session_state[key] = defaults[field]
    if "selected_preset" not in st.session_state:
        st.session_state["selected_preset"] = "Standard"


def _apply_preset(preset_name: str) -> None:
    values = asdict(DEFAULT_INPUT)
    values.update(PRESETS[preset_name])
    for field in BASE_FIELD_ORDER:
        st.session_state[f"base_{field}"] = values[field]
    st.session_state["selected_preset"] = preset_name


def _get_widget_default(key: str, fallback: Any) -> Any:
    return st.session_state.get(key, fallback)


def _number_input(
    label: str,
    key: str,
    fallback: float,
    step: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    kwargs: dict[str, Any] = {
        "label": label,
        "key": key,
        "value": float(_get_widget_default(key, fallback)),
        "step": float(step),
    }
    if minimum is not None:
        kwargs["min_value"] = float(minimum)
    if maximum is not None:
        kwargs["max_value"] = float(maximum)
    return float(st.number_input(**kwargs))


def _selectbox(
    label: str,
    key: str,
    options: tuple[Any, ...],
    fallback: Any,
    help_text: str | None = None,
) -> Any:
    value = _get_widget_default(key, fallback)
    index = options.index(value) if value in options else 0
    return st.selectbox(label, options, index=index, key=key, help=help_text)


def _render_header() -> None:
    st.markdown(
        """
        <div class="app-hero">
            <div class="hero-panel">
                <div class="hero-kicker">Prozessmodell</div>
                <div class="hero-title">Spruehtrockner REA</div>
                <p class="hero-copy">
                    Prozessdaten eingeben, Varianten gegeneinander rechnen und schnell beurteilen,
                    ob die Trocknung vor dem Trockneraustritt abgeschlossen wird.
                </p>
            </div>
            <div class="summary-panel">
                <div class="meta-kicker">Modellrahmen</div>
                <div class="section-title">Plug-Flow, Gleichstrom, REA</div>
                <p class="hero-meta-copy">
                    Materialmodelle: SMP fuer TS &lt; 0.2 sowie 0.2 / 0.3 / 0.5, WPC fuer TS = 0.3.
                    Die App dient fuer Betriebspunktvergleich und Vorstudien, nicht fuer CFD-Details.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_preset_toolbar() -> None:
    st.markdown(
        """
        <div class="toolbar-panel">
            <div class="section-kicker">Preset und Startpunkt</div>
            <div class="section-title">Basiseingaben vorbereiten</div>
            <p class="toolbar-note">
                Presets laden einen sinnvollen Ausgangspunkt. Danach koennen einzelne Parameter gezielt angepasst werden.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bar1, bar2 = st.columns([1.6, 0.9])
    with bar1:
        selected_preset = st.selectbox(
            "Preset",
            tuple(PRESETS),
            index=tuple(PRESETS).index(st.session_state["selected_preset"]),
            key="preset_picker",
        )
    with bar2:
        if st.button("Preset laden", use_container_width=True):
            _apply_preset(selected_preset)
            st.rerun()


def _render_section_intro(kicker: str, title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="section-panel">
            <div class="section-kicker">{kicker}</div>
            <div class="section-title">{title}</div>
            <p class="section-copy">{copy}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_process_group() -> None:
    _render_section_intro(
        "Basisparameter",
        "Prozessdaten",
        "Diese Eingaben beschreiben den Betriebspunkt des Trockners und sollten zuerst gesetzt werden.",
    )
    cols = st.columns(2)
    process_fields = FIELD_GROUPS["Prozess"]
    for index, field in enumerate(process_fields):
        with cols[index % 2]:
            key = f"base_{field}"
            if field == "material":
                _selectbox(FIELD_LABELS[field], key, ("SMP", "WPC"), DEFAULT_INPUT.material)
            elif field == "feed_total_solids":
                _selectbox(
                    FIELD_LABELS[field],
                    key,
                    (0.15, 0.2, 0.3, 0.5),
                    DEFAULT_INPUT.feed_total_solids,
                    "SMP: TS < 0.2 oder 0.2/0.3/0.5, WPC: nur 0.3",
                )
            else:
                _number_input(
                    FIELD_LABELS[field],
                    key,
                    getattr(DEFAULT_INPUT, field),
                    STEP_MAP[field],
                    MIN_MAP.get(field),
                )


def _render_expert_group() -> None:
    _render_section_intro(
        "Erweiterte Parameter",
        "Modellannahmen feinjustieren",
        "Nur anpassen, wenn gezielt Material- oder Simulationsparameter untersucht werden sollen.",
    )
    cols = st.columns(2)
    expert_fields = FIELD_GROUPS["Experten"]
    for index, field in enumerate(expert_fields):
        with cols[index % 2]:
            _number_input(
                FIELD_LABELS[field],
                f"base_{field}",
                getattr(DEFAULT_INPUT, field),
                STEP_MAP[field],
                MIN_MAP.get(field),
            )


def _gather_base_input() -> SimulationInput:
    values = {field: st.session_state[f"base_{field}"] for field in BASE_FIELD_ORDER}
    return SimulationInput(**values)


def _format_summary_value(key: str, value: float) -> str:
    if key in {"droplet_volume_m3", "droplet_surface_m2", "solid_mass_per_droplet_kg"}:
        return f"{value:.3e}"
    if key in {"droplets_per_s"}:
        return f"{value:,.0f}".replace(",", " ")
    return f"{value:.3f}"


def _render_base_summary(base_input: SimulationInput) -> None:
    summary = summarize_input(base_input)
    primary_keys = [
        "initial_moisture_content",
        "air_superficial_velocity_ms",
        "humid_air_mass_flow_kg_s",
        "droplets_per_s",
        "air_residence_time_s",
        "solid_mass_per_droplet_kg",
    ]
    rows = "".join(
        f"""
        <div class="summary-item">
            <div class="summary-label">{SUMMARY_LABELS[key]}</div>
            <div class="summary-value">{_format_summary_value(key, summary[key])}</div>
        </div>
        """
        for key in primary_keys
    )
    st.markdown(
        f"""
        <div class="summary-panel">
            <div class="meta-kicker">Betriebspunkt</div>
            <div class="section-title">Kompakte Zusammenfassung</div>
            <p class="summary-note">
                Die wichtigsten abgeleiteten Kennwerte werden live aus den Basiseingaben berechnet.
            </p>
            <div class="summary-grid">{rows}</div>
            <div class="summary-meta">
                <div class="summary-label">Modellgrenze</div>
                <div class="summary-value" style="font-size:0.96rem;font-weight:500;">
                    SMP fuer TS &lt; 0.2 sowie 0.2 / 0.3 / 0.5, WPC fuer TS = 0.3
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Weitere abgeleitete Kennwerte", expanded=False):
        extra_keys = [key for key in SUMMARY_LABELS if key not in primary_keys]
        extra_rows = pd.DataFrame(
            [
                {"Kennwert": SUMMARY_LABELS[key], "Wert": _format_summary_value(key, summary[key])}
                for key in extra_keys
            ]
        )
        st.dataframe(extra_rows, use_container_width=True, hide_index=True)


def _render_override_input(field: str, base_input: SimulationInput, key_prefix: str) -> Any:
    base_value = getattr(base_input, field)
    key = f"{key_prefix}_{field}"
    if field == "material":
        return _selectbox(FIELD_LABELS[field], key, ("SMP", "WPC"), base_value)
    if field == "feed_total_solids":
        return float(
            _selectbox(
                FIELD_LABELS[field],
                key,
                (0.15, 0.2, 0.3, 0.5),
                base_value,
                "SMP: TS < 0.2 oder 0.2/0.3/0.5, WPC: nur 0.3",
            )
        )
    return _number_input(
        FIELD_LABELS[field],
        key,
        float(base_value),
        STEP_MAP.get(field, 0.1),
        MIN_MAP.get(field, 0.0),
    )


def _render_variants(base_input: SimulationInput) -> list[SimulationInput]:
    _render_section_intro(
        "Szenarien",
        "Varianten gezielt gegen die Basis rechnen",
        "Die Basis bleibt unveraendert. Zusaetzliche Szenarien enthalten nur die bewusst geaenderten Eingaben.",
    )
    scenario_total = int(st.slider("Anzahl Szenarien", min_value=1, max_value=3, value=1))

    inputs = [base_input]
    labels = ["Basis"]
    override_fields = list(FIELD_LABELS)
    st.markdown(
        """
        <div class="scenario-card">
            <div class="meta-kicker">Referenz</div>
            <div class="section-title">Basisfall</div>
            <p class="section-copy">
                Alle weiteren Szenarien werden als Abweichung gegen diese Eingaben aufgebaut.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for variant_index in range(2, scenario_total + 1):
        with st.expander(f"Szenario {variant_index}", expanded=True):
            header_col, text_col = st.columns([1.0, 1.8])
            with header_col:
                label = st.text_input(
                    "Szenariobezeichnung",
                    value=st.session_state.get(f"scenario_label_{variant_index}", f"Szenario {variant_index}"),
                    key=f"variant_label_{variant_index}",
                )
            with text_col:
                selected_fields = st.multiselect(
                    "Abweichende Eingaben",
                    options=override_fields,
                    default=st.session_state.get(f"variant_fields_{variant_index}", []),
                    format_func=lambda field: FIELD_LABELS[field],
                    key=f"variant_fields_{variant_index}",
                    help="Nur diese Felder werden gegen die Basis geaendert.",
                )

            overrides: dict[str, Any] = {}
            if selected_fields:
                st.markdown(
                    f"""
                    <div class="scenario-card">
                        <div class="meta-kicker">Overrides</div>
                        <div class="section-title">{label or f"Szenario {variant_index}"}</div>
                        <p class="section-copy">
                            Es werden nur {len(selected_fields)} Eingaben angepasst. Alle anderen Werte kommen aus dem Basisfall.
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                columns = st.columns(2)
                for index, field in enumerate(selected_fields):
                    with columns[index % 2]:
                        overrides[field] = _render_override_input(field, base_input, f"variant_{variant_index}")
            else:
                st.info("Noch keine Abweichungen ausgewaehlt. Dieses Szenario entspricht aktuell der Basis.")
        config = ScenarioConfig(label=label, overrides=overrides)
        inputs.append(config.apply(base_input))
        labels.append(label)

    st.session_state["scenario_labels"] = labels
    return inputs


def _to_display_metrics(metrics_frame: pd.DataFrame) -> pd.DataFrame:
    display = metrics_frame.copy()
    for column in ("outlet_Tb", "outlet_Tp", "final_Tb", "final_Tp"):
        if column in display:
            display[column] = display[column] - 273.0
    return display


def _render_kpi_cards(results: list[SimulationResult], target_outlet_x: float) -> None:
    cards_markup: list[str] = []
    base_result = results[0]
    base_outlet_x = base_result.metrics["outlet_X"]
    base_drying_height = base_result.metrics["drying_height"]
    for result in results:
        metrics = result.metrics
        outlet_x = metrics["outlet_X"]
        outlet_tb = metrics["outlet_Tb"]
        drying_height = metrics["drying_height"]
        reached_target = outlet_x is not None and outlet_x <= target_outlet_x
        dried_in_tower = drying_height is not None and drying_height <= result.inputs.dryer_height_m
        status_class = "status-good" if reached_target and dried_in_tower else "status-bad"
        status_text = "prozesstauglich" if reached_target and dried_in_tower else "kritisch"
        outlet_x_text = f"{outlet_x:.4f}" if outlet_x is not None else "n/a"
        outlet_tb_text = f"{(outlet_tb - 273.0):.1f}" if outlet_tb is not None else "n/a"
        note = "Referenzfall"
        if result is not base_result:
            delta_parts: list[str] = []
            if outlet_x is not None and base_outlet_x is not None:
                delta_parts.append(f"Delta X {outlet_x - base_outlet_x:+.4f}")
            if drying_height is not None and base_drying_height is not None:
                delta_parts.append(f"Delta Trocknungshoehe {drying_height - base_drying_height:+.3f} m")
            if delta_parts:
                note = " | ".join(delta_parts)
        cards_markup.append(
            f"""
            <div class="decision-card">
                <div class="decision-scenario">{result.label}</div>
                <div class="decision-status {status_class}">{status_text}</div>
                <div class="decision-main">X Austritt {outlet_x_text}</div>
                <div class="decision-detail">
                    Tb Austritt: {outlet_tb_text} degC<br>
                    Trocknung vor Austritt: {"Ja" if dried_in_tower else "Nein"}<br>
                    Ziel-X eingehalten: {"Ja" if reached_target else "Nein"}
                </div>
                <div class="decision-note">{note}</div>
            </div>
            """
        )
    st.markdown(f"""<div class="decision-grid">{''.join(cards_markup)}</div>""", unsafe_allow_html=True)


def _build_assessment_frame(results: list[SimulationResult], target_outlet_x: float) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for result in results:
        metrics = result.metrics
        outlet_x = metrics["outlet_X"]
        drying_height = metrics["drying_height"]
        rows.append(
            {
                "Szenario": result.label,
                "Ziel-X eingehalten": "Ja" if outlet_x is not None and outlet_x <= target_outlet_x else "Nein",
                "Trocknung vor Austritt": (
                    "Ja"
                    if drying_height is not None and drying_height <= result.inputs.dryer_height_m
                    else "Nein"
                ),
                "Trocknungshoehe [m]": drying_height,
                "Austritts-X [-]": outlet_x,
                "Austritts-Tb [degC]": (
                    metrics["outlet_Tb"] - 273.0 if metrics["outlet_Tb"] is not None else None
                ),
                "Austritts-RH [-]": metrics["outlet_RH"],
            }
        )
    return pd.DataFrame(rows)


def _build_delta_frame(metrics_frame: pd.DataFrame) -> pd.DataFrame:
    if len(metrics_frame) < 2:
        return pd.DataFrame()
    base = metrics_frame.iloc[0]
    delta_rows: list[dict[str, Any]] = []
    for _, row in metrics_frame.iloc[1:].iterrows():
        delta_rows.append(
            {
                "Szenario": row["scenario"],
                "Delta outlet_X": (
                    None if pd.isna(row["outlet_X"]) or pd.isna(base["outlet_X"]) else row["outlet_X"] - base["outlet_X"]
                ),
                "Delta outlet_Tb [K]": (
                    None
                    if pd.isna(row["outlet_Tb"]) or pd.isna(base["outlet_Tb"])
                    else row["outlet_Tb"] - base["outlet_Tb"]
                ),
                "Delta drying_time [s]": (
                    None
                    if pd.isna(row["drying_time"]) or pd.isna(base["drying_time"])
                    else row["drying_time"] - base["drying_time"]
                ),
                "Delta drying_height [m]": (
                    None
                    if pd.isna(row["drying_height"]) or pd.isna(base["drying_height"])
                    else row["drying_height"] - base["drying_height"]
                ),
            }
        )
    return pd.DataFrame(delta_rows)


def _render_metrics(results: list[SimulationResult], target_outlet_x: float) -> None:
    metrics_frame = results_to_metrics_frame(results)
    display_metrics = _to_display_metrics(metrics_frame).rename(
        columns={
            "scenario": "Szenario",
            "drying_time": "Trocknungszeit [s]",
            "drying_height": "Trocknungshoehe [m]",
            "outlet_time": "Austrittszeit [s]",
            "outlet_X": "X am Austritt [-]",
            "outlet_Tb": "Tb am Austritt [degC]",
            "outlet_Tp": "Tp am Austritt [degC]",
            "outlet_RH": "RH am Austritt [-]",
            "final_X": "X Ende [-]",
            "final_Tb": "Tb Ende [degC]",
            "final_Tp": "Tp Ende [degC]",
            "final_RH": "RH Ende [-]",
        }
    )
    _render_section_intro(
        "Entscheidung",
        "Szenarien fachlich einordnen",
        "Zuerst zaehlt, ob das Ziel-X eingehalten wird und ob die Trocknung vor dem Austritt abgeschlossen ist.",
    )
    _render_kpi_cards(results, target_outlet_x)

    assessment = _build_assessment_frame(results, target_outlet_x)
    delta_frame = _build_delta_frame(metrics_frame)
    lower_left, lower_right = st.columns([1.25, 1.0])
    with lower_left:
        _render_section_intro(
            "Bewertung",
            "Kernaussagen pro Szenario",
            "Diese Tabelle zeigt nur die entscheidenden Kriterien fuer die Einordnung des Betriebspunkts.",
        )
        st.dataframe(assessment, use_container_width=True, hide_index=True)
    with lower_right:
        if not delta_frame.empty:
            _render_section_intro(
                "Basisvergleich",
                "Abweichung gegen den Referenzfall",
                "Positive oder negative Deltas helfen bei der Einordnung der Wirkung jeder Aenderung.",
            )
            st.dataframe(delta_frame, use_container_width=True, hide_index=True)
    with st.expander("Vollstaendige Kennzahlen", expanded=False):
        st.dataframe(display_metrics, use_container_width=True, hide_index=True)


def _chart_frame(results: list[SimulationResult]) -> pd.DataFrame:
    frame = results_to_timeseries_frame(results).copy()
    frame["Tb_C"] = frame["Tb"] - 273.0
    frame["Tp_C"] = frame["Tp"] - 273.0
    frame["dp_um"] = frame["dp"] * 1_000_000.0
    frame["Y_gkg"] = frame["Y"] * 1000.0
    return frame


def _axis_label(axis_key: str) -> str:
    return "Hoehe [m]" if axis_key == "height" else "Zeit [s]"


def _field_display_name(field: str) -> str:
    return FIELD_LABELS[field].split(" [", 1)[0]


def _format_input_value(field: str, value: Any) -> str:
    if field == "material":
        return str(value)
    if field == "feed_total_solids":
        return f"{float(value):.2f}"
    if field in {
        "dryer_height_m",
        "feed_rate_kg_h",
        "air_flow_m3_h",
        "inlet_abs_humidity_g_kg",
        "ambient_temp_c",
        "feed_temp_c",
        "dryer_diameter_m",
        "heat_loss_coeff_w_m2k",
        "xcrit",
        "initial_droplet_velocity_ms",
        "simulation_end_s",
        "solid_density_kg_m3",
        "water_density_kg_m3",
        "protein_fraction",
        "lactose_fraction",
        "fat_fraction",
    }:
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    return f"{float(value):.0f}"


def _value_changed(values: list[Any]) -> bool:
    first = values[0]
    if isinstance(first, str):
        return any(value != first for value in values[1:])
    return any(abs(float(value) - float(first)) > 1e-9 for value in values[1:])


def _scenario_display_map(results: list[SimulationResult]) -> dict[str, str]:
    if len(results) <= 1:
        return {result.label: result.label for result in results}

    varying_fields: list[str] = []
    for field in BASE_FIELD_ORDER:
        values = [getattr(result.inputs, field) for result in results]
        if _value_changed(values):
            varying_fields.append(field)

    if not varying_fields:
        return {result.label: result.label for result in results}

    display_map: dict[str, str] = {}
    max_fields = 3
    for result in results:
        parts = [
            f"{_field_display_name(field)} {_format_input_value(field, getattr(result.inputs, field))}"
            for field in varying_fields[:max_fields]
        ]
        if len(varying_fields) > max_fields:
            parts.append(f"+{len(varying_fields) - max_fields} weitere")
        display_map[result.label] = f"{result.label} ({', '.join(parts)})"
    return display_map


def _series_color_map(scenarios: list[str]) -> dict[str, str]:
    return {
        scenario: CHART_SERIES_COLORS[index % len(CHART_SERIES_COLORS)]
        for index, scenario in enumerate(scenarios)
    }


def _build_chart_figure(
    subset: pd.DataFrame,
    x_axis: str,
    y_column: str,
    title: str,
    unit: str,
    color_map: dict[str, str],
    scenario_display_map: dict[str, str],
    target_outlet_x: float,
) -> go.Figure:
    figure = go.Figure()
    x_label = _axis_label(x_axis)
    y_label = f"{title} [{unit}]"

    for scenario in subset["scenario"].unique():
        scenario_frame = subset[subset["scenario"] == scenario]
        display_name = scenario_display_map.get(scenario, scenario)
        figure.add_trace(
            go.Scatter(
                x=scenario_frame[x_axis],
                y=scenario_frame[y_column],
                mode="lines",
                name=display_name,
                line=dict(color=color_map[scenario], width=3, shape="spline", smoothing=0.55),
                hovertemplate=(
                    f"<b>{display_name}</b><br>{x_label}: %{{x:.2f}}<br>{y_label}: %{{y:.3f}}<extra></extra>"
                ),
            )
        )

    if y_column == "X":
        figure.add_hrect(
            y0=0,
            y1=target_outlet_x,
            fillcolor="rgba(61,122,98,0.10)",
            line_width=0,
            layer="below",
        )
        figure.add_hline(
            y=target_outlet_x,
            line_dash="dash",
            line_color="#D46A2E",
            annotation_text=f"Ziel X = {target_outlet_x:.3f}",
            annotation_position="top left",
        )

    figure.update_layout(
        title=dict(text=title, x=0.02, xanchor="left", font=dict(size=20, color="#20332A")),
        height=390,
        margin=dict(l=18, r=18, t=56, b=18),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#FFFDF8",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    figure.update_xaxes(
        title=x_label,
        showline=True,
        linecolor="#CFC5B4",
        linewidth=1.1,
        gridcolor="rgba(95, 86, 73, 0.10)",
        zeroline=False,
        tickfont=dict(color="#42564A"),
        title_font=dict(color="#42564A"),
    )
    figure.update_yaxes(
        title=y_label,
        showline=True,
        linecolor="#CFC5B4",
        linewidth=1.1,
        gridcolor="rgba(95, 86, 73, 0.12)",
        zeroline=False,
        tickfont=dict(color="#42564A"),
        title_font=dict(color="#42564A"),
    )
    return figure


def _render_charts(results: list[SimulationResult], target_outlet_x: float) -> None:
    plot_frame = _chart_frame(results)
    control1, control2, control3 = st.columns([1.0, 1.0, 1.5])
    with control1:
        x_axis = st.radio("x-Achse", ("height", "t"), format_func=_axis_label, horizontal=True)
    with control2:
        available = plot_frame["scenario"].unique().tolist()
        selected_scenarios = st.multiselect("Szenarien", available, default=available)
    with control3:
        chart_family = st.selectbox(
            "Diagrammgruppe",
            ("Thermisch", "Feuchte", "Partikel"),
            index=0,
        )

    subset = plot_frame[plot_frame["scenario"].isin(selected_scenarios)]
    if subset.empty:
        st.info("Mindestens ein Szenario fuer die Diagrammansicht auswaehlen.")
        return

    st.markdown(
        """
        <div class="chart-note">
            Ruhige Achsen, konsistente Farben und ein gemeinsamer Hover-Fokus erleichtern den direkten Szenariovergleich.
        </div>
        """,
        unsafe_allow_html=True,
    )

    color_map = _series_color_map(available)
    selected_results = [result for result in results if result.label in selected_scenarios]
    scenario_display_map = _scenario_display_map(selected_results)

    if len(selected_results) > 1:
        summary_text = " | ".join(
            scenario_display_map[result.label] for result in selected_results
        )
        st.caption(f"Szenario-Parameter: {summary_text}")

    cols = st.columns(2)
    for index, (column, title, unit) in enumerate(CHART_GROUPS[chart_family]):
        with cols[index % 2]:
            chart_box = st.container(border=True)
            with chart_box:
                st.caption(f"{chart_family} | {title}")
                fig = _build_chart_figure(
                    subset=subset,
                    x_axis=x_axis,
                    y_column=column,
                    title=title,
                    unit=unit,
                    color_map=color_map,
                    scenario_display_map=scenario_display_map,
                    target_outlet_x=target_outlet_x,
                )
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"chart_{chart_family}_{column}_{x_axis}_{'-'.join(selected_scenarios)}",
                )


def _render_data_tabs(results: list[SimulationResult]) -> None:
    metrics_frame = _to_display_metrics(results_to_metrics_frame(results))
    timeseries_frame = _chart_frame(results)
    tabs = st.tabs(["Kennzahlen", "Zeitreihen", "Eingaben"])
    with tabs[0]:
        st.dataframe(metrics_frame, use_container_width=True)
    with tabs[1]:
        st.dataframe(timeseries_frame, use_container_width=True, height=420)
    with tabs[2]:
        inputs_df = pd.DataFrame(
            [{"scenario": result.label, **asdict(result.inputs)} for result in results]
        )
        st.dataframe(inputs_df, use_container_width=True)


def _render_exports(results: list[SimulationResult]) -> None:
    metrics_csv = results_to_metrics_frame(results).to_csv(index=False).encode("utf-8")
    timeseries_csv = results_to_timeseries_frame(results).to_csv(index=False).encode("utf-8")
    excel_bytes = results_to_excel_bytes(results)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button("Kennzahlen als CSV", metrics_csv, "spruehtrockner_metrics.csv", "text/csv")
    with col2:
        st.download_button("Zeitreihen als CSV", timeseries_csv, "spruehtrockner_timeseries.csv", "text/csv")
    with col3:
        st.download_button(
            "Ergebnisse als XLSX",
            excel_bytes,
            "spruehtrockner_results.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _render_evaluation_settings() -> None:
    _render_section_intro(
        "Bewertung",
        "Zielwert fuer die Einordnung",
        "Das Ziel wird nur fuer Bewertung und Visualisierung genutzt, nicht als Solver-Abbruch.",
    )
    st.number_input(
        "Bewertungsziel fuer Austrittsfeuchte X [-]",
        value=float(st.session_state.get("target_outlet_x", 0.04)),
        min_value=0.0,
        step=0.005,
        key="target_outlet_x",
    )


def _render_warning_box(results: list[SimulationResult]) -> None:
    warnings = [warning for result in results for warning in result.warnings]
    if warnings:
        with st.expander("Warnungen und Modellgrenzen", expanded=True):
            for warning in warnings:
                st.warning(warning)


def main() -> None:
    _ensure_base_state()
    _inject_styles()
    _render_header()

    left, right = st.columns([1.5, 1.0], vertical_alignment="top")
    with left:
        _render_preset_toolbar()
        with st.form("simulation_form"):
            _render_process_group()
            with st.expander("Expertenmodus", expanded=False):
                _render_expert_group()
            base_input = _gather_base_input()
            scenario_inputs = _render_variants(base_input)
            _render_evaluation_settings()
            submitted = st.form_submit_button("Berechnen", use_container_width=True)

    with right:
        base_input_preview = _gather_base_input()
        _render_base_summary(base_input_preview)

    if submitted:
        labels = st.session_state.get("scenario_labels", ["Basis"])
        try:
            results = run_batch(scenario_inputs, labels=labels)
        except Exception as exc:
            st.error(str(exc))
            return
        st.session_state["results"] = results

    results: list[SimulationResult] | None = st.session_state.get("results")
    if not results:
        st.info("Preset oder Eingaben festlegen und danach Berechnen waehlen.")
        return

    target_outlet_x = float(st.session_state.get("target_outlet_x", 0.04))
    _render_warning_box(results)

    overview_tab, charts_tab, data_export_tab = st.tabs(
        ["Ergebnis", "Diagramme", "Daten & Export"]
    )
    with overview_tab:
        _render_metrics(results, target_outlet_x)
    with charts_tab:
        _render_charts(results, target_outlet_x)
    with data_export_tab:
        _render_data_tabs(results)
        st.markdown("")
        _render_exports(results)


if __name__ == "__main__":
    main()
