export type ApiStatus = 'checking' | 'online' | 'offline'
export type AppView = 'start' | 'simulation' | 'model'
export type ChartTab = 'moisture' | 'temperature' | 'equilibrium' | 'velocity' | 'comparison'
export type XBModel = 'langrish' | 'lin_gab'

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
  x_b_model: XBModel
  nozzle_delta_p_bar: number
  nozzle_velocity_coefficient: number
  dryer_diameter_m: number
  dryer_height_m: number
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

export interface ReferenceCasePreset {
  label: string
  title: string
  measured_Tout_c: number | null
  measured_powder_moisture_wb_pct: number | null
  measured_d32_um: number | null
  inputs: StationaryInput
}

export interface ModelDefaults {
  default_reference_case_label: string
  default_target_moisture_wb_pct: number
  x_b_models: XBModel[]
  solver_methods: Array<'BDF' | 'RK45' | 'Radau'>
  reference_cases: ReferenceCasePreset[]
}

export interface SimulationRequest {
  inputs: StationaryInput
  target_moisture_wb_pct: number
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
  U_a_ms: number
  U_p_ms: number
}

export interface SimulationSummary {
  end_moisture_wb_pct: number
  Tout_pre_cyclone_c: number
  RHout_pct: number
  tau_out_s: number | null
  target_moisture_wb_pct: number
  target_reached: boolean
  time_to_target_s: number | null
  height_to_target_m: number | null
  x_out_minus_x_b_out: number
  T_p_out_c: number
  U_p_out_ms: number
  solver_success: boolean
  solver_message: string
}

export interface SimulationResponse {
  summary: SimulationSummary
  series: SimulationSeriesPoint[]
  warnings: string[]
  inputs: StationaryInput
}
