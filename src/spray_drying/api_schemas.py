from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


X_B_MODELS = (
    "kockel",
    "lin_gab",
    "lin_gab_kockel_blend",
    "lin_gab_kockel_blend_rh",
)


class HealthDTO(BaseModel):
    status: Literal["ok"] = "ok"


class StationaryInputDTO(BaseModel):
    Tin: float = Field(gt=-273.15)
    humid_air_mass_flow_kg_h: float = Field(gt=0)
    feed_rate_kg_h: float = Field(gt=0)
    droplet_size_um: float = Field(gt=0)
    inlet_abs_humidity_g_kg: float = Field(ge=0)
    feed_total_solids: float = Field(gt=0, le=1)
    heat_loss_coeff_w_m2k: float = Field(ge=0)
    contact_efficiency: float = Field(default=1.0, gt=0, le=1)
    atomization_zone_length_m: float = Field(default=0.0, ge=0)
    atomization_zone_exposure_factor: float = Field(default=1.0, gt=0, le=1)
    secondary_exposure_zone_length_m: float = Field(default=0.0, ge=0)
    secondary_exposure_zone_factor: float = Field(default=1.0, gt=0, le=1)
    effective_gas_humidity_mode: Literal["off", "target_rh"] = "off"
    humidity_bias_zone_length_m: float = Field(default=0.0, ge=0)
    humidity_bias_zone_target_rh: float = Field(default=0.0, ge=0, lt=1)
    humidity_bias_zone2_length_m: float = Field(default=0.0, ge=0)
    humidity_bias_zone2_target_rh: float = Field(default=0.0, ge=0, lt=1)
    enable_material_retardation_add: bool = True
    x_b_model: Literal[
        "kockel",
        "lin_gab",
        "lin_gab_kockel_blend",
        "lin_gab_kockel_blend_rh",
    ] = "lin_gab"
    x_b_blend_kockel_weight: float = Field(default=0.5, ge=0, le=1)
    x_b_blend_kockel_weight_base: float = 0.0
    x_b_blend_kockel_weight_rh_coeff: float = 0.0
    nozzle_delta_p_bar: float = Field(gt=0)
    nozzle_velocity_coefficient: float = Field(gt=0)
    dryer_diameter_m: float = Field(gt=0)
    cylinder_height_m: float | None = Field(default=None, gt=0)
    cone_height_m: float = Field(ge=0)
    outlet_duct_length_m: float = Field(ge=0)
    outlet_duct_diameter_m: float | None = Field(default=None, gt=0)
    feed_temp_c: float = 40.0
    ambient_temp_c: float = 20.0
    pressure_pa: float = Field(default=101325.0, gt=0)
    axial_points: int = Field(default=250, ge=25)
    solver_method: Literal["BDF", "RK45", "Radau"] = "BDF"
    solver_rtol: float = Field(default=1e-6, gt=0)
    solver_atol: float = Field(default=1e-8, gt=0)

    model_config = ConfigDict(extra="forbid")


class ModelDefaultsDTO(BaseModel):
    default_target_moisture_wb_pct: float
    default_inputs: StationaryInputDTO
    x_b_models: list[str]
    solver_methods: list[str]


class SimulationRequestDTO(BaseModel):
    inputs: StationaryInputDTO
    target_moisture_wb_pct: float = Field(default=4.0, gt=0)

    model_config = ConfigDict(extra="forbid")


class CompareScenarioRequestDTO(BaseModel):
    scenario_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    inputs: StationaryInputDTO
    target_moisture_wb_pct: float = Field(default=4.0, gt=0)

    model_config = ConfigDict(extra="forbid")


class CompareRequestDTO(BaseModel):
    scenarios: list[CompareScenarioRequestDTO] = Field(min_length=1, max_length=4)
    base_scenario_id: str | None = None

    model_config = ConfigDict(extra="forbid")


class SimulationSeriesPointDTO(BaseModel):
    h_m: float
    section: str
    tau_s: float | None
    moisture_wb_pct: float
    X: float
    T_a_c: float
    T_p_c: float
    RH_a_pct: float
    x_b: float
    psi: float
    axial_exposure_factor: float
    combined_contact_exposure_factor: float
    RH_eff_pct: float
    Y_eff: float
    humidity_bias_active: bool
    delta_t_air_particle_c: float
    rho_v_driving_force_kg_m3: float
    q_conv_w: float
    q_latent_w: float
    q_sorption_w: float
    q_evap_total_w: float
    q_evap_to_conv_ratio: float
    particle_diameter_um: float
    U_a_ms: float
    U_p_ms: float

    model_config = ConfigDict(protected_namespaces=())


class SimulationOutletDTO(BaseModel):
    h_m: float
    section: str
    tau_s: float | None
    moisture_wb_pct: float
    X: float
    x_b: float
    T_a_c: float
    T_p_c: float
    RH_a_pct: float
    U_p_ms: float
    dmean_out_um: float
    total_q_loss_w: float

    model_config = ConfigDict(protected_namespaces=())


class SimulationProfileDTO(BaseModel):
    n_points: int
    axial_length_m: float
    dryer_exit_h_m: float
    pre_cyclone_h_m: float
    sections: list[str]
    series: list[SimulationSeriesPointDTO]

    model_config = ConfigDict(protected_namespaces=())


class SimulationSummaryDTO(BaseModel):
    end_moisture_wb_pct: float
    Tout_c: float
    RHout_pct: float
    tau_out_s: float | None
    target_moisture_wb_pct: float
    target_reached: bool
    time_to_target_s: float | None
    height_to_target_m: float | None
    x_out_minus_x_b_out: float
    T_p_out_c: float
    U_p_out_ms: float
    dmean_out_um: float
    solver_success: bool
    solver_message: str


class SimulationResponseDTO(BaseModel):
    summary: SimulationSummaryDTO
    outlet: SimulationOutletDTO
    profile: SimulationProfileDTO
    warnings: list[str]
    inputs: StationaryInputDTO

    model_config = ConfigDict(protected_namespaces=())


class CompareScenarioResponseDTO(SimulationResponseDTO):
    scenario_id: str
    label: str


class CompareResponseDTO(BaseModel):
    base_scenario_id: str
    scenarios: list[CompareScenarioResponseDTO]

    model_config = ConfigDict(protected_namespaces=())
