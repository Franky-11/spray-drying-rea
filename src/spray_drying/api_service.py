from __future__ import annotations

import pandas as pd

from core.stationary_smp_rea import (
    MS400GeometryAssumption,
    StationarySMPREAInput,
    derive_inputs,
    solve_stationary_smp_profile,
)
from core.stationary_smp_rea.air import moist_air_density

from .api_schemas import (
    CompareRequestDTO,
    CompareResponseDTO,
    CompareScenarioResponseDTO,
    ModelDefaultsDTO,
    SimulationOutletDTO,
    SimulationProfileDTO,
    SimulationRequestDTO,
    SimulationResponseDTO,
    SimulationSeriesPointDTO,
    SimulationSummaryDTO,
    StationaryInputDTO,
    X_B_MODELS,
)


DEFAULT_TARGET_MOISTURE_WB_PCT = 4.0
SOLVER_METHODS = ["BDF", "RK45", "Radau"]
SUPPRESSED_UI_WARNINGS = {
    "The section-wise geometry treats cylinder, cone, and outlet duct as an effective 1D flow path with local cross section; redirection, back-mixing, and changes in flow direction are not resolved separately.",
    "The report point 'pre_cyclone' is located at the end of the effective outlet duct section directly upstream of the cyclone inlet.",
}


def get_model_defaults() -> ModelDefaultsDTO:
    return ModelDefaultsDTO(
        default_target_moisture_wb_pct=DEFAULT_TARGET_MOISTURE_WB_PCT,
        default_inputs=build_default_input_dto(),
        x_b_models=list(X_B_MODELS),
        solver_methods=SOLVER_METHODS,
    )


def run_simulation(request: SimulationRequestDTO) -> SimulationResponseDTO:
    return _run_single_simulation(request.inputs, request.target_moisture_wb_pct)


def run_compare(request: CompareRequestDTO) -> CompareResponseDTO:
    seen_ids: set[str] = set()
    scenario_results: list[CompareScenarioResponseDTO] = []
    for scenario in request.scenarios:
        if scenario.scenario_id in seen_ids:
            raise ValueError(f"Duplicate scenario_id: {scenario.scenario_id}")
        seen_ids.add(scenario.scenario_id)
        simulation = _run_single_simulation(scenario.inputs, scenario.target_moisture_wb_pct)
        scenario_results.append(
            CompareScenarioResponseDTO(
                scenario_id=scenario.scenario_id,
                label=scenario.label,
                summary=simulation.summary,
                outlet=simulation.outlet,
                profile=simulation.profile,
                warnings=simulation.warnings,
                inputs=simulation.inputs,
            )
        )

    base_scenario_id = request.base_scenario_id or request.scenarios[0].scenario_id
    if base_scenario_id not in seen_ids:
        raise ValueError(f"Unknown base_scenario_id: {base_scenario_id}")

    return CompareResponseDTO(
        base_scenario_id=base_scenario_id,
        scenarios=scenario_results,
    )


def _run_single_simulation(inputs: StationaryInputDTO, target_moisture_wb_pct: float) -> SimulationResponseDTO:
    model_input = _dto_to_stationary_input(inputs)
    result = solve_stationary_smp_profile(model_input)
    frame = result.series.copy()
    frame["moisture_wb_pct"] = 100.0 * frame["X"] / (1.0 + frame["X"])
    frame["RH_a_pct"] = 100.0 * frame["RH_a"]

    target_row = _first_target_row(frame, target_moisture_wb_pct)
    outlet_row = frame.iloc[-1]
    profile_series = [_series_point_from_row(row) for _, row in frame.iterrows()]
    derived = derive_inputs(model_input)
    dmean_out_um = float(outlet_row["d_p_m"]) * 1_000_000.0

    summary = SimulationSummaryDTO(
        end_moisture_wb_pct=float(outlet_row["moisture_wb_pct"]),
        Tout_c=float(outlet_row["T_a_c"]),
        RHout_pct=float(outlet_row["RH_a_pct"]),
        tau_out_s=float(outlet_row["tau_s"]) if pd.notna(outlet_row["tau_s"]) else None,
        target_moisture_wb_pct=target_moisture_wb_pct,
        target_reached=target_row is not None,
        time_to_target_s=_optional_series_float(target_row, "tau_s"),
        height_to_target_m=_optional_series_float(target_row, "h"),
        x_out_minus_x_b_out=float(outlet_row["X"] - outlet_row["x_b"]),
        T_p_out_c=float(outlet_row["T_p_c"]),
        U_p_out_ms=float(outlet_row["U_p_ms"]),
        dmean_out_um=dmean_out_um,
        solver_success=bool(result.success),
        solver_message=str(result.solver_message),
    )

    outlet = SimulationOutletDTO(
        h_m=float(outlet_row["h"]),
        section=str(outlet_row["section"]),
        tau_s=float(outlet_row["tau_s"]) if pd.notna(outlet_row["tau_s"]) else None,
        moisture_wb_pct=float(outlet_row["moisture_wb_pct"]),
        X=float(outlet_row["X"]),
        x_b=float(outlet_row["x_b"]),
        T_a_c=float(outlet_row["T_a_c"]),
        T_p_c=float(outlet_row["T_p_c"]),
        RH_a_pct=float(outlet_row["RH_a_pct"]),
        U_p_ms=float(outlet_row["U_p_ms"]),
        dmean_out_um=dmean_out_um,
        total_q_loss_w=float(result.outlet["total_q_loss_w"]),
    )

    profile = SimulationProfileDTO(
        n_points=len(profile_series),
        axial_length_m=float(derived.total_axial_length_m),
        dryer_exit_h_m=float(derived.dryer_exit_h_m),
        pre_cyclone_h_m=float(derived.pre_cyclone_h_m),
        sections=[str(section) for section in frame["section"].drop_duplicates().tolist()],
        series=profile_series,
    )

    return SimulationResponseDTO(
        summary=summary,
        outlet=outlet,
        profile=profile,
        warnings=[warning for warning in result.warnings if warning not in SUPPRESSED_UI_WARNINGS],
        inputs=inputs,
    )


def build_default_input_dto() -> StationaryInputDTO:
    geometry = MS400GeometryAssumption()
    return StationaryInputDTO(
        Tin=190.0,
        humid_air_mass_flow_kg_h=300.0,
        feed_rate_kg_h=15.0,
        droplet_size_um=65.0,
        inlet_abs_humidity_g_kg=6.0,
        feed_total_solids=0.37,
        heat_loss_coeff_w_m2k=1.4,
        contact_efficiency=1.0,
        enable_material_retardation_add=True,
        x_b_model="lin_gab",
        nozzle_delta_p_bar=47.0,
        nozzle_velocity_coefficient=0.60,
        dryer_diameter_m=geometry.cylinder_diameter_m,
        cylinder_height_m=geometry.cylinder_height_m,
        cone_height_m=geometry.cone_height_m,
        outlet_duct_length_m=geometry.outlet_duct_length_m,
        outlet_duct_diameter_m=geometry.outlet_duct_diameter_m,
        feed_temp_c=40.0,
        ambient_temp_c=20.0,
        pressure_pa=101325.0,
        axial_points=320,
        solver_method="BDF",
        solver_rtol=1e-6,
        solver_atol=1e-8,
    )


def _dto_from_stationary_input(model_input: StationarySMPREAInput) -> StationaryInputDTO:
    derived = derive_inputs(model_input)
    return StationaryInputDTO(
        Tin=model_input.inlet_air_temp_c,
        humid_air_mass_flow_kg_h=derived.humid_air_mass_flow_kg_s * 3600.0,
        feed_rate_kg_h=model_input.feed_rate_kg_h,
        droplet_size_um=model_input.droplet_size_um,
        inlet_abs_humidity_g_kg=model_input.inlet_abs_humidity_g_kg,
        feed_total_solids=model_input.feed_total_solids,
        heat_loss_coeff_w_m2k=model_input.heat_loss_coeff_w_m2k,
        contact_efficiency=model_input.contact_efficiency,
        enable_material_retardation_add=model_input.enable_material_retardation_add,
        x_b_model=model_input.x_b_model,
        nozzle_delta_p_bar=model_input.nozzle_delta_p_bar,
        nozzle_velocity_coefficient=model_input.nozzle_velocity_coefficient,
        dryer_diameter_m=model_input.dryer_diameter_m,
        cylinder_height_m=model_input.cylinder_height_m,
        cone_height_m=model_input.cone_height_m,
        outlet_duct_length_m=model_input.outlet_duct_length_m,
        outlet_duct_diameter_m=model_input.outlet_duct_diameter_m,
        feed_temp_c=model_input.feed_temp_c,
        ambient_temp_c=model_input.ambient_temp_c,
        pressure_pa=model_input.pressure_pa,
        axial_points=model_input.axial_points,
        solver_method=model_input.solver_method,
        solver_rtol=model_input.solver_rtol,
        solver_atol=model_input.solver_atol,
    )


def _dto_to_stationary_input(input_dto: StationaryInputDTO) -> StationarySMPREAInput:
    humidity_ratio = input_dto.inlet_abs_humidity_g_kg / 1000.0
    density = moist_air_density(
        input_dto.Tin + 273.15,
        humidity_ratio,
        input_dto.pressure_pa,
    )
    air_flow_m3_h = input_dto.humid_air_mass_flow_kg_h / max(density, 1e-12)
    cylinder_height_m = input_dto.cylinder_height_m
    if cylinder_height_m is None:
        raise ValueError("cylinder_height_m must be set for segmented geometry.")
    return StationarySMPREAInput(
        dryer_height_m=cylinder_height_m,
        dryer_diameter_m=input_dto.dryer_diameter_m,
        cylinder_height_m=cylinder_height_m,
        cone_height_m=input_dto.cone_height_m,
        outlet_duct_length_m=input_dto.outlet_duct_length_m,
        outlet_duct_diameter_m=input_dto.outlet_duct_diameter_m,
        inlet_air_temp_c=input_dto.Tin,
        droplet_size_um=input_dto.droplet_size_um,
        feed_rate_kg_h=input_dto.feed_rate_kg_h,
        air_flow_m3_h=air_flow_m3_h,
        inlet_abs_humidity_g_kg=input_dto.inlet_abs_humidity_g_kg,
        ambient_temp_c=input_dto.ambient_temp_c,
        feed_temp_c=input_dto.feed_temp_c,
        feed_total_solids=input_dto.feed_total_solids,
        nozzle_delta_p_bar=input_dto.nozzle_delta_p_bar,
        nozzle_velocity_coefficient=input_dto.nozzle_velocity_coefficient,
        pressure_pa=input_dto.pressure_pa,
        heat_loss_coeff_w_m2k=input_dto.heat_loss_coeff_w_m2k,
        contact_efficiency=input_dto.contact_efficiency,
        enable_material_retardation_add=input_dto.enable_material_retardation_add,
        x_b_model=input_dto.x_b_model,
        axial_points=input_dto.axial_points,
        solver_method=input_dto.solver_method,
        solver_rtol=input_dto.solver_rtol,
        solver_atol=input_dto.solver_atol,
    )


def _first_target_row(frame: pd.DataFrame, target_moisture_wb_pct: float) -> pd.Series | None:
    target_rows = frame.loc[frame["moisture_wb_pct"] <= target_moisture_wb_pct]
    if target_rows.empty:
        return None
    return target_rows.iloc[0]


def _series_point_from_row(row: pd.Series) -> SimulationSeriesPointDTO:
    return SimulationSeriesPointDTO(
        h_m=float(row["h"]),
        section=str(row["section"]),
        tau_s=float(row["tau_s"]) if pd.notna(row["tau_s"]) else None,
        moisture_wb_pct=float(row["moisture_wb_pct"]),
        X=float(row["X"]),
        T_a_c=float(row["T_a_c"]),
        T_p_c=float(row["T_p_c"]),
        RH_a_pct=float(row["RH_a_pct"]),
        x_b=float(row["x_b"]),
        psi=float(row["psi"]),
        delta_t_air_particle_c=float(row["delta_t_air_particle_k"]),
        rho_v_driving_force_kg_m3=float(row["rho_v_driving_force_kg_m3"]),
        q_conv_w=float(row["q_conv_w"]),
        q_latent_w=float(row["q_latent_w"]),
        q_sorption_w=float(row["q_sorption_w"]),
        q_evap_total_w=float(row["q_evap_total_w"]),
        q_evap_to_conv_ratio=float(row["q_evap_to_conv_ratio"]),
        particle_diameter_um=float(row["d_p_m"]) * 1_000_000.0,
        U_a_ms=float(row["U_a_ms"]),
        U_p_ms=float(row["U_p_ms"]),
    )


def _optional_series_float(row: pd.Series | None, key: str) -> float | None:
    if row is None:
        return None
    value = row[key]
    if pd.isna(value):
        return None
    return float(value)


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)
