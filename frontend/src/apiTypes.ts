export type ApiStatus = 'checking' | 'online' | 'offline'
export type AppView = 'start' | 'simulation' | 'model'
export type ChartTab = 'moisture' | 'temperature' | 'equilibrium' | 'particle' | 'velocity' | 'comparison'
export type XBModel = 'kockel' | 'lin_gab' | 'lin_gab_kockel_blend' | 'lin_gab_kockel_blend_rh'

export interface HealthResponse {
  status: 'ok'
}

export interface StationaryInput {
  Tin: number
  humid_air_mass_flow_kg_h: number
  feed_rate_kg_h: number
  droplet_size_um: number
  inlet_abs_humidity_g_kg: number
  feed_total_solids: number
  heat_loss_coeff_w_m2k: number
  contact_efficiency: number
  atomization_zone_length_m: number
  atomization_zone_exposure_factor: number
  secondary_exposure_zone_length_m: number
  secondary_exposure_zone_factor: number
  effective_gas_humidity_mode: 'off' | 'target_rh'
  humidity_bias_zone_length_m: number
  humidity_bias_zone_target_rh: number
  humidity_bias_zone2_length_m: number
  humidity_bias_zone2_target_rh: number
  enable_material_retardation_add: boolean
  x_b_model: XBModel
  x_b_blend_kockel_weight: number
  x_b_blend_kockel_weight_base: number
  x_b_blend_kockel_weight_rh_coeff: number
  nozzle_delta_p_bar: number
  nozzle_velocity_coefficient: number
  dryer_diameter_m: number
  cylinder_height_m: number | null
  cone_height_m: number
  outlet_duct_length_m: number
  outlet_duct_diameter_m: number | null
  feed_temp_c: number
  ambient_temp_c: number
  pressure_pa: number
  axial_points: number
  solver_method: 'BDF' | 'RK45' | 'Radau'
  solver_rtol: number
  solver_atol: number
}

export interface ModelDefaults {
  default_target_moisture_wb_pct: number
  default_inputs: StationaryInput
  x_b_models: XBModel[]
  solver_methods: Array<'BDF' | 'RK45' | 'Radau'>
}

export interface SimulationRequest {
  inputs: StationaryInput
  target_moisture_wb_pct: number
}

export interface CompareScenarioRequest {
  scenario_id: string
  label: string
  inputs: StationaryInput
  target_moisture_wb_pct: number
}

export interface CompareRequest {
  scenarios: CompareScenarioRequest[]
  base_scenario_id?: string
}

export interface SimulationSeriesPoint {
  h_m: number
  section: string
  tau_s: number | null
  moisture_wb_pct: number
  X: number
  T_a_c: number
  T_p_c: number
  RH_a_pct: number
  x_b: number
  psi: number
  particle_diameter_um: number
  U_a_ms: number
  U_p_ms: number
}

export interface SimulationOutlet {
  h_m: number
  section: string
  tau_s: number | null
  moisture_wb_pct: number
  X: number
  x_b: number
  T_a_c: number
  T_p_c: number
  RH_a_pct: number
  U_p_ms: number
  dmean_out_um: number
  total_q_loss_w: number
}

export interface SimulationProfile {
  n_points: number
  axial_length_m: number
  dryer_exit_h_m: number
  pre_cyclone_h_m: number
  sections: string[]
  series: SimulationSeriesPoint[]
}

export interface SimulationSummary {
  end_moisture_wb_pct: number
  Tout_c: number
  RHout_pct: number
  tau_out_s: number | null
  target_moisture_wb_pct: number
  target_reached: boolean
  time_to_target_s: number | null
  height_to_target_m: number | null
  x_out_minus_x_b_out: number
  T_p_out_c: number
  U_p_out_ms: number
  dmean_out_um: number
  solver_success: boolean
  solver_message: string
}

export interface SimulationResponse {
  summary: SimulationSummary
  outlet: SimulationOutlet
  profile: SimulationProfile
  warnings: string[]
  inputs: StationaryInput
}

export interface CompareScenarioResponse extends SimulationResponse {
  scenario_id: string
  label: string
}

export interface CompareResponse {
  base_scenario_id: string
  scenarios: CompareScenarioResponse[]
}
