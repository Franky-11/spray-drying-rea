from __future__ import annotations

import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model import (  # noqa: E402
    ScenarioConfig,
    SimulationInput,
    SimulationResult,
    results_to_excel_bytes,
    results_to_metrics_frame,
    results_to_timeseries_frame,
    run_batch,
    summarize_input,
)


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
MATERIAL_FIELDS = [
    "material",
    "droplet_size_um",
    "feed_temp_c",
    "feed_total_solids",
]
PROCESS_FIELDS = [
    "dryer_height_m",
    "inlet_air_temp_c",
    "feed_rate_kg_h",
    "air_flow_m3_h",
    "inlet_abs_humidity_g_kg",
    "ambient_temp_c",
]
EXPERT_FIELDS = [
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
    "dryer_height_m": "Trocknerhöhe [m]",
    "inlet_air_temp_c": "Zulufttemperatur [degC]",
    "droplet_size_um": "Tropfengröße [um]",
    "feed_rate_kg_h": "Feedstrom [kg/h]",
    "air_flow_m3_h": "Luftstrom [m^3/h]",
    "inlet_abs_humidity_g_kg": "Absolute Zuluftfeuchte [g/kg]",
    "ambient_temp_c": "Umgebungstemperatur [degC]",
    "feed_temp_c": "Feedtemperatur [degC]",
    "feed_total_solids": "Feed-Trockensubstanz [-]",
    "material": "Material",
    "dryer_diameter_m": "Trocknerdurchmesser [m]",
    "heat_loss_coeff_w_m2k": "Wärmeverlustkoeffizient Up [W/m^2K]",
    "xcrit": "Kritische Beladung Xcrit [-]",
    "initial_droplet_velocity_ms": "Anfangsgeschwindigkeit Tropfen [m/s]",
    "simulation_end_s": "Simulationsdauer [s]",
    "solid_density_kg_m3": "Feststoffdichte [kg/m^3]",
    "water_density_kg_m3": "Wasserdichte [kg/m^3]",
    "protein_fraction": "Proteinanteil [-]",
    "lactose_fraction": "Lactoseanteil [-]",
    "fat_fraction": "Fettanteil [-]",
}

FIELD_HELP = {
    "feed_total_solids": "SMP: TS < 0.2 sowie 0.2 / 0.3 / 0.5. WPC: nur 0.3.",
}

MATERIAL_COMPOSITION_DEFAULTS: dict[str, dict[str, float]] = {
    "SMP": {
        "protein_fraction": 0.35,
        "lactose_fraction": 0.55,
        "fat_fraction": 0.01,
    },
    "WPC": {
        "protein_fraction": 0.80,
        "lactose_fraction": 0.074,
        "fat_fraction": 0.056,
    },
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
        **MATERIAL_COMPOSITION_DEFAULTS["WPC"],
    },
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
    "air_superficial_velocity_ms": "Luftgeschwindigkeit [m/s]",
    "humid_air_mass_flow_kg_s": "Luftmassenstrom [kg/s]",
    "droplets_per_s": "Tropfenstrom [1/s]",
    "air_residence_time_s": "Hydraulische Verweilzeit [s]",
}

RESULTS_STATE_KEY = "results"
PRESET_STATE_KEY = "selected_preset"
PRESET_WIDGET_KEY = "preset_choice"
TARGET_STATE_KEY = "target_outlet_x"
COMPARISON_ENABLED_KEY = "comparison_enabled"
COMPARISON_COUNT_KEY = "comparison_count"
DEFAULT_TARGET_OUTLET_X = 0.04
MAX_COMPARISONS = 3


def initialize_session_state() -> None:
    defaults = asdict(DEFAULT_INPUT)
    for field in BASE_FIELD_ORDER:
        st.session_state.setdefault(f"base_{field}", defaults[field])

    st.session_state.setdefault(PRESET_STATE_KEY, "Standard")
    st.session_state.setdefault(PRESET_WIDGET_KEY, st.session_state[PRESET_STATE_KEY])
    st.session_state.setdefault(TARGET_STATE_KEY, DEFAULT_TARGET_OUTLET_X)
    st.session_state.setdefault(COMPARISON_ENABLED_KEY, False)
    st.session_state.setdefault(COMPARISON_COUNT_KEY, 1)


def clear_results() -> None:
    st.session_state.pop(RESULTS_STATE_KEY, None)


def material_composition_defaults(material: str) -> dict[str, float]:
    return MATERIAL_COMPOSITION_DEFAULTS[material].copy()


def apply_material_defaults_for_key(material_key: str = "base_material") -> None:
    material = str(st.session_state[material_key])
    prefix = material_key[: -len("material")]
    for field, value in material_composition_defaults(material).items():
        st.session_state[f"{prefix}{field}"] = value
    clear_results()


def apply_preset(preset_name: str) -> None:
    values = asdict(DEFAULT_INPUT)
    values.update(PRESETS[preset_name])
    values.update(material_composition_defaults(str(values["material"])))
    values.update(PRESETS[preset_name])
    for field in BASE_FIELD_ORDER:
        st.session_state[f"base_{field}"] = values[field]
    st.session_state[PRESET_STATE_KEY] = preset_name
    st.session_state[PRESET_WIDGET_KEY] = preset_name
    clear_results()


def apply_selected_preset() -> None:
    apply_preset(st.session_state[PRESET_WIDGET_KEY])


def build_base_input() -> SimulationInput:
    values = {field: st.session_state[f"base_{field}"] for field in BASE_FIELD_ORDER}
    return SimulationInput(**values)


def render_field_input(field: str, key: str, value: Any | None = None) -> Any:
    fallback = getattr(DEFAULT_INPUT, field) if value is None else value
    if key not in st.session_state:
        st.session_state[key] = fallback
    label = FIELD_LABELS[field]
    help_text = FIELD_HELP.get(field)

    if field == "material":
        options = ("SMP", "WPC")
        selectbox_kwargs: dict[str, Any] = {
            "label": label,
            "options": options,
            "key": key,
            "help": help_text,
        }
        if key == "base_material":
            selectbox_kwargs["on_change"] = apply_material_defaults_for_key
            selectbox_kwargs["kwargs"] = {"material_key": key}
        return st.selectbox(**selectbox_kwargs)

    if field == "feed_total_solids":
        return float(st.selectbox(label, (0.15, 0.2, 0.3, 0.5), key=key, help=help_text))

    kwargs: dict[str, Any] = {
        "label": label,
        "step": float(STEP_MAP[field]),
        "key": key,
    }
    minimum = MIN_MAP.get(field)
    if minimum is not None:
        kwargs["min_value"] = float(minimum)
    return float(st.number_input(**kwargs))


def format_input_value(field: str, value: Any) -> str:
    if field == "material":
        return str(value)
    if field == "feed_total_solids":
        return f"{float(value):.2f}"
    if field in {"droplet_size_um"}:
        return f"{float(value):.0f}"
    return f"{float(value):.2f}".rstrip("0").rstrip(".")


def field_display_name(field: str) -> str:
    return FIELD_LABELS[field].split(" [", 1)[0]


def build_override_summary_frame(base_input: SimulationInput, overrides: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "Parameter": field_display_name(field),
            "Basis": format_input_value(field, getattr(base_input, field)),
            "Szenario": format_input_value(field, value),
        }
        for field, value in overrides.items()
    ]
    return pd.DataFrame(rows)


def build_operating_point_frame(base_input: SimulationInput) -> pd.DataFrame:
    summary = summarize_input(base_input)
    return pd.DataFrame(
        [
            {
                "Kennwert": SUMMARY_LABELS[key],
                "Wert": (
                    f"{summary[key]:,.0f}".replace(",", " ")
                    if key == "droplets_per_s"
                    else f"{summary[key]:.3f}"
                ),
            }
            for key in SUMMARY_LABELS
        ]
    )


def build_comparison_input(
    label: str,
    base_input: SimulationInput,
    overrides: dict[str, Any],
) -> SimulationInput:
    config = ScenarioConfig(label=label, overrides=overrides)
    return config.apply(base_input)
