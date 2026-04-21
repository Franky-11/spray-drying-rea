import { useEffect, useMemo, useRef, useState } from 'react'
import type { EChartsOption, SeriesOption } from 'echarts'
import './App.css'
import { compare, getHealth, getModelDefaults } from './apiClient'
import { downloadComparisonJson, downloadSimulationJson, downloadSimulationProfileCsv } from './exportUtils'
import type {
  ApiStatus,
  AppView,
  ChartTab,
  CompareResponse,
  CompareScenarioResponse,
  ModelDefaults,
  StationaryInput,
  XBModel,
} from './apiTypes'
import heroSprayDryer from './assets/start/start-hero-spray-dryer.jpg'
import labPowderAnalysis from './assets/start/start-lab-powder-analysis.jpg'
import LineChart from './LineChart'
import SprayTowerPreview from './SprayTowerPreview'

const BASE_SCENARIO_ID = 'base'
const MAX_SCENARIOS = 4
const SCENARIO_COLORS = ['#0f62fe', '#8a3ffc', '#009d9a', '#fa4d56']

const chartTabs: Array<{ id: ChartTab; label: string }> = [
  { id: 'moisture', label: 'Moisture' },
  { id: 'temperature', label: 'Temperature' },
  { id: 'equilibrium', label: 'Equilibrium and Material' },
  { id: 'particle', label: 'Particle Diameter' },
  { id: 'velocity', label: 'Velocity' },
  { id: 'comparison', label: 'Comparison Table' },
]

const XB_MODEL_DETAILS: Record<XBModel, { label: string; description: string }> = {
  lin_gab: {
    label: 'Temperature-dependent GAB (Lin et al., 2005)',
    description:
      'Uses the temperature-dependent GAB closure for skim milk powder and remains the recommended default for the active SMP workflow.',
  },
  langrish: {
    label: 'Langrish isotherm (2009)',
    description:
      'Uses the Langrish equilibrium isotherm as a sensitivity option for cross-checking outlet moisture and approach-to-equilibrium trends.',
  },
}

interface ScenarioDraft {
  scenario_id: string
  label: string
  inputs: StationaryInput
  target_moisture_wb_pct: number
}

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const [defaults, setDefaults] = useState<ModelDefaults | null>(null)
  const [activeView, setActiveView] = useState<AppView>('start')
  const [scenarios, setScenarios] = useState<ScenarioDraft[]>([])
  const [activeScenarioId, setActiveScenarioId] = useState(BASE_SCENARIO_ID)
  const [nextScenarioNumber, setNextScenarioNumber] = useState(1)
  const [isExpertOpen, setIsExpertOpen] = useState(false)
  const [activeChartTab, setActiveChartTab] = useState<ChartTab>('moisture')
  const [hoveredHeightM, setHoveredHeightM] = useState<number | null>(null)
  const [isSimulating, setIsSimulating] = useState(false)
  const [comparisonResult, setComparisonResult] = useState<CompareResponse | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true

    Promise.all([getHealth(), getModelDefaults()])
      .then(([, modelDefaults]) => {
        if (!isMounted) {
          return
        }
        setDefaults(modelDefaults)
        setApiStatus('online')
        setScenarios([
          buildScenario(
            BASE_SCENARIO_ID,
            'Base case',
            modelDefaults.default_inputs,
            modelDefaults.default_target_moisture_wb_pct,
          ),
        ])
      })
      .catch((error: unknown) => {
        if (!isMounted) {
          return
        }
        setApiStatus('offline')
        setMessage(error instanceof Error ? error.message : 'API unavailable')
      })

    return () => {
      isMounted = false
    }
  }, [])

  const activeScenario = useMemo(
    () => scenarios.find((scenario) => scenario.scenario_id === activeScenarioId) ?? null,
    [activeScenarioId, scenarios],
  )
  const baseScenario = useMemo(
    () => scenarios.find((scenario) => scenario.scenario_id === BASE_SCENARIO_ID) ?? null,
    [scenarios],
  )
  const activeScenarioResult = useMemo(
    () => comparisonResult?.scenarios.find((scenario) => scenario.scenario_id === activeScenarioId) ?? null,
    [activeScenarioId, comparisonResult],
  )
  const baseScenarioResult = useMemo(
    () =>
      comparisonResult?.scenarios.find((scenario) => scenario.scenario_id === comparisonResult.base_scenario_id) ?? null,
    [comparisonResult],
  )

  const canSimulate = apiStatus === 'online' && scenarios.length > 0 && !isSimulating
  const canAddScenario = scenarios.length < MAX_SCENARIOS && baseScenario !== null
  const canDeleteScenario = activeScenarioId !== BASE_SCENARIO_ID

  const chartOption = useMemo<EChartsOption | null>(() => {
    if (!comparisonResult || activeChartTab === 'comparison') {
      return null
    }

    const scenarioResults = comparisonResult.scenarios
    const sameTarget = scenarioResults.every(
      (scenario) =>
        Math.abs(scenario.summary.target_moisture_wb_pct - scenarioResults[0].summary.target_moisture_wb_pct) < 1e-9,
    )
    const baseProfile = baseScenarioResult?.profile.series ?? scenarioResults[0].profile.series

    const common = {
      animation: false,
      grid: { left: 56, right: 24, top: 64, bottom: 48 },
      legend: {
        top: 12,
        type: 'scroll' as const,
        textStyle: { color: '#525252', fontSize: 12 },
      },
      tooltip: { trigger: 'axis' as const },
      xAxis: {
        type: 'value' as const,
        name: 'Axial position (m)',
        nameLocation: 'middle' as const,
        nameGap: 30,
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
      yAxis: {
        type: 'value' as const,
        axisLabel: { color: '#525252', fontSize: 12 },
        splitLine: { lineStyle: { color: '#e0e0e0' } },
      },
    }

    if (activeChartTab === 'moisture') {
      const series = scenarioResults.map((scenario, index) =>
        buildLineSeries(
          scenario.label,
          scenario.profile.series.map((row) => [row.h_m, row.moisture_wb_pct]),
          SCENARIO_COLORS[index % SCENARIO_COLORS.length],
        ),
      )
      if (sameTarget) {
        series.push(
          buildLineSeries(
            'Target',
            baseProfile.map((row) => [row.h_m, scenarioResults[0].summary.target_moisture_wb_pct]),
            '#525252',
            'dashed',
          ),
        )
      }
      return {
        ...common,
        yAxis: {
          ...common.yAxis,
          name: 'Powder moisture (wt% wb)',
        },
        series,
      }
    }

    if (activeChartTab === 'temperature') {
      return {
        ...common,
        yAxis: {
          ...common.yAxis,
          name: 'Temperature (degC)',
        },
        series: scenarioResults.flatMap((scenario, index) => {
          const color = SCENARIO_COLORS[index % SCENARIO_COLORS.length]
          return [
            buildLineSeries(
              `${scenario.label} air`,
              scenario.profile.series.map((row) => [row.h_m, row.T_a_c]),
              color,
            ),
            buildLineSeries(
              `${scenario.label} particle`,
              scenario.profile.series.map((row) => [row.h_m, row.T_p_c]),
              color,
              'dashed',
            ),
          ]
        }),
      }
    }

    if (activeChartTab === 'equilibrium') {
      return {
        ...common,
        yAxis: {
          ...common.yAxis,
          name: 'x_b / psi',
        },
        series: scenarioResults.flatMap((scenario, index) => {
          const color = SCENARIO_COLORS[index % SCENARIO_COLORS.length]
          return [
            buildLineSeries(
              `${scenario.label} x_b`,
              scenario.profile.series.map((row) => [row.h_m, row.x_b]),
              color,
            ),
            buildLineSeries(
              `${scenario.label} psi`,
              scenario.profile.series.map((row) => [row.h_m, row.psi]),
              color,
              'dashed',
            ),
          ]
        }),
      }
    }

    if (activeChartTab === 'particle') {
      return {
        ...common,
        yAxis: {
          ...common.yAxis,
          name: 'Particle diameter (um)',
        },
        series: scenarioResults.map((scenario, index) =>
          buildLineSeries(
            scenario.label,
            scenario.profile.series.map((row) => [row.h_m, row.particle_diameter_um]),
            SCENARIO_COLORS[index % SCENARIO_COLORS.length],
          ),
        ),
      }
    }

    return {
      ...common,
      yAxis: {
        ...common.yAxis,
        name: 'Velocity (m/s)',
      },
      series: scenarioResults.flatMap((scenario, index) => {
        const color = SCENARIO_COLORS[index % SCENARIO_COLORS.length]
        return [
          buildLineSeries(
            `${scenario.label} U_a`,
            scenario.profile.series.map((row) => [row.h_m, row.U_a_ms]),
            color,
          ),
          buildLineSeries(
            `${scenario.label} U_p`,
            scenario.profile.series.map((row) => [row.h_m, row.U_p_ms]),
            color,
            'dashed',
          ),
        ]
      }),
    }
  }, [activeChartTab, baseScenarioResult, comparisonResult])

  const activeScenarioWarnings = activeScenarioResult?.warnings ?? []
  const activeXBModelDetails = activeScenario ? XB_MODEL_DETAILS[activeScenario.inputs.x_b_model] : null

  function invalidateResults() {
    setComparisonResult(null)
  }

  function activateScenario(scenarioId: string) {
    setHoveredHeightM(null)
    setActiveScenarioId(scenarioId)
  }

  function activateChartTab(tab: ChartTab) {
    setHoveredHeightM(null)
    setActiveChartTab(tab)
  }

  function updateActiveScenario(update: (scenario: ScenarioDraft) => ScenarioDraft) {
    setScenarios((current) =>
      current.map((scenario) => (scenario.scenario_id === activeScenarioId ? update(scenario) : scenario)),
    )
    invalidateResults()
  }

  function updateNumberField<Key extends NumberFieldKey>(key: Key, value: string) {
    if (!activeScenario || value === '') {
      return
    }
    updateActiveScenario((scenario) => ({
      ...scenario,
      inputs: {
        ...scenario.inputs,
        [key]: Number(value),
      },
    }))
  }

  function updateNullableNumberField<Key extends NullableNumberFieldKey>(key: Key, value: string) {
    if (!activeScenario) {
      return
    }
    updateActiveScenario((scenario) => ({
      ...scenario,
      inputs: {
        ...scenario.inputs,
        [key]: value === '' ? null : Number(value),
      },
    }))
  }

  function updateXBModel(value: XBModel) {
    if (!activeScenario) {
      return
    }
    updateActiveScenario((scenario) => ({
      ...scenario,
      inputs: {
        ...scenario.inputs,
        x_b_model: value,
      },
    }))
  }

  function updateFeedTotalSolidsPercent(value: string) {
    if (!activeScenario || value === '') {
      return
    }
    updateActiveScenario((scenario) => ({
      ...scenario,
      inputs: {
        ...scenario.inputs,
        feed_total_solids: Number(value) / 100,
      },
    }))
  }

  function updateScenarioLabel(value: string) {
    if (!activeScenario) {
      return
    }
    updateActiveScenario((scenario) => ({
      ...scenario,
      label: value,
    }))
  }

  function updateTargetMoisture(value: string) {
    if (!activeScenario || value === '') {
      return
    }
    updateActiveScenario((scenario) => ({
      ...scenario,
      target_moisture_wb_pct: Number(value),
    }))
  }

  function addScenario(copyFrom: ScenarioDraft) {
    if (!canAddScenario) {
      return
    }
    const scenarioNumber = nextScenarioNumber
    const nextScenario = buildScenario(
      `scenario-${scenarioNumber}`,
      `Scenario ${scenarioNumber}`,
      copyFrom.inputs,
      copyFrom.target_moisture_wb_pct,
    )
    setScenarios((current) => [...current, nextScenario])
    activateScenario(nextScenario.scenario_id)
    setNextScenarioNumber((current) => current + 1)
    invalidateResults()
  }

  function removeActiveScenario() {
    if (!canDeleteScenario) {
      return
    }
    const scenarioIdToRemove = activeScenarioId
    setScenarios((current) => current.filter((scenario) => scenario.scenario_id !== scenarioIdToRemove))
    activateScenario(BASE_SCENARIO_ID)
    setComparisonResult((current) =>
      current
        ? {
            ...current,
            scenarios: current.scenarios.filter((scenario) => scenario.scenario_id !== scenarioIdToRemove),
          }
        : null,
    )
  }

  function resetActiveScenario() {
    if (!defaults || !activeScenario) {
      return
    }
    const resetSource =
      activeScenario.scenario_id === BASE_SCENARIO_ID
        ? buildScenario(
            BASE_SCENARIO_ID,
            activeScenario.label,
            defaults.default_inputs,
            defaults.default_target_moisture_wb_pct,
          )
        : buildScenario(activeScenario.scenario_id, activeScenario.label, baseScenario?.inputs ?? defaults.default_inputs, baseScenario?.target_moisture_wb_pct ?? defaults.default_target_moisture_wb_pct)
    updateActiveScenario(() => resetSource)
  }

  async function runComparison() {
    if (scenarios.length === 0) {
      return
    }

    setIsSimulating(true)
    setMessage(null)
    setHoveredHeightM(null)
    try {
      const response = await compare({
        base_scenario_id: BASE_SCENARIO_ID,
        scenarios,
      })
      setComparisonResult(response)
      setActiveView('simulation')
      activateChartTab('moisture')
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Simulation failed')
      setComparisonResult(null)
    } finally {
      setIsSimulating(false)
    }
  }

  return (
    <>
      <header className="top-bar">
        <div className="brand">
          <span className="brand-title">Spray Drying REA</span>
        </div>
        <nav className="top-nav" aria-label="Pages">
          <button className={activeView === 'start' ? 'active' : ''} onClick={() => setActiveView('start')} type="button">
            Get started
          </button>
          <button
            className={activeView === 'simulation' ? 'active' : ''}
            onClick={() => setActiveView('simulation')}
            type="button"
          >
            Simulation
          </button>
          <button className={activeView === 'model' ? 'active' : ''} onClick={() => setActiveView('model')} type="button">
            Model Foundations
          </button>
        </nav>
        {message && (
          <div className={`api-status ${apiStatus === 'offline' ? 'offline' : 'error'}`}>
            <span className="status-label">Error</span>
            <strong>{message}</strong>
          </div>
        )}
      </header>

      <main className="page">
        {activeView === 'start' && <StartView onNavigate={setActiveView} />}

        {activeView === 'simulation' && activeScenario && (
          <section className="simulation-page">
            <div className="layout simulation-top-layout">
              <section className="panel">
                <div className="panel-header">
                  <h2 className="panel-title">Simulation Inputs</h2>
                </div>
                <div className="panel-body field-stack">
                  <section className="subsection scenario-section">
                    <div className="subsection-header">
                      <h3>Scenarios</h3>
                    </div>
                    <div className="scenario-list">
                      {scenarios.map((scenario) => (
                        <button
                          key={scenario.scenario_id}
                          className={activeScenarioId === scenario.scenario_id ? 'scenario-chip active' : 'scenario-chip'}
                          onClick={() => activateScenario(scenario.scenario_id)}
                          type="button"
                        >
                          <span>{scenario.label}</span>
                          <small>{scenario.scenario_id === BASE_SCENARIO_ID ? 'Base' : 'Comparison'}</small>
                        </button>
                      ))}
                    </div>
                    <div className="button-row">
                      <button className="button-secondary" disabled={!canAddScenario} onClick={() => addScenario(baseScenario ?? activeScenario)} type="button">
                        Add Comparison Scenario
                      </button>
                      <button className="button-secondary" disabled={!canAddScenario} onClick={() => addScenario(activeScenario)} type="button">
                        Duplicate Active
                      </button>
                      <button className="button-secondary" disabled={!canDeleteScenario} onClick={removeActiveScenario} type="button">
                        Remove Active
                      </button>
                    </div>
                    <span className="helper">Up to three comparison scenarios in addition to the base case.</span>
                  </section>

                  <div className="field-row">
                    <div className="field">
                      <label htmlFor="scenario-label">Scenario Name</label>
                      <input
                        id="scenario-label"
                        onChange={(event) => updateScenarioLabel(event.target.value)}
                        type="text"
                        value={activeScenario.label}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="target-moisture">Target Powder Moisture (wt% wb)</label>
                      <input
                        id="target-moisture"
                        min="0"
                        onChange={(event) => updateTargetMoisture(event.target.value)}
                        step="0.1"
                        type="number"
                        value={activeScenario.target_moisture_wb_pct}
                      />
                    </div>
                  </div>

                  <section className="subsection">
                    <div className="subsection-header">
                      <h3>Core Inputs</h3>
                    </div>
                    <div className="field-stack">
                      <div className="field-row">
                        <NumberField
                          id="Tin"
                          label="Inlet Air Temperature Tin (degC)"
                          onChange={(value) => updateNumberField('Tin', value)}
                          value={activeScenario.inputs.Tin}
                        />
                        <NumberField
                          id="humid_air_mass_flow_kg_h"
                          label="Humid Air Mass Flow (kg/h)"
                          onChange={(value) => updateNumberField('humid_air_mass_flow_kg_h', value)}
                          value={activeScenario.inputs.humid_air_mass_flow_kg_h}
                        />
                      </div>
                      <div className="field-row">
                        <NumberField
                          id="feed_rate_kg_h"
                          label="Feed Rate (kg/h)"
                          onChange={(value) => updateNumberField('feed_rate_kg_h', value)}
                          value={activeScenario.inputs.feed_rate_kg_h}
                        />
                        <NumberField
                          id="droplet_size_um"
                          label="Droplet Diameter (um)"
                          onChange={(value) => updateNumberField('droplet_size_um', value)}
                          value={activeScenario.inputs.droplet_size_um}
                        />
                      </div>
                      <div className="field-row">
                        <NumberField
                          id="inlet_abs_humidity_g_kg"
                          label="Inlet Absolute Humidity Yin (g/kg)"
                          onChange={(value) => updateNumberField('inlet_abs_humidity_g_kg', value)}
                          value={activeScenario.inputs.inlet_abs_humidity_g_kg}
                        />
                        <PercentageField
                          id="feed_total_solids"
                          label="Feed Total Solids (wt%)"
                          onChange={updateFeedTotalSolidsPercent}
                          value={activeScenario.inputs.feed_total_solids}
                        />
                      </div>
                    </div>
                  </section>

                  <section className="subsection">
                    <button className="section-toggle" onClick={() => setIsExpertOpen((current) => !current)} type="button">
                      {isExpertOpen ? 'Close Expert Inputs' : 'Open Expert Inputs'}
                    </button>
                    {isExpertOpen && (
                      <div className="field-stack expert-fields">
                        <section className="expert-group" aria-labelledby="expert-equilibrium-title">
                          <div className="expert-group-header">
                            <h3 id="expert-equilibrium-title">Equilibrium Moisture</h3>
                            <p>Select the `x_b` closure used by the REA core to evaluate local approach to equilibrium.</p>
                          </div>
                          <div className="field">
                            <label htmlFor="x_b_model">Equilibrium Moisture Closure</label>
                            <select
                              id="x_b_model"
                              onChange={(event) => updateXBModel(event.target.value as XBModel)}
                              value={activeScenario.inputs.x_b_model}
                            >
                              {(defaults?.x_b_models ?? []).map((model) => (
                                <option key={model} value={model}>
                                  {XB_MODEL_DETAILS[model].label}
                                </option>
                              ))}
                            </select>
                            {activeXBModelDetails && <div className="field-note field-note-compact">{activeXBModelDetails.description}</div>}
                          </div>
                        </section>
                        <section className="expert-group" aria-labelledby="expert-nozzle-title">
                          <div className="expert-group-header">
                            <h3 id="expert-nozzle-title">Pressure-Nozzle Entry</h3>
                            <p>
                              The active API derives inlet droplet velocity from pressure drop and the velocity coefficient. No nozzle orifice geometry is exposed in the current product path.
                            </p>
                          </div>
                          <div className="field-row">
                            <NumberField
                              id="nozzle_delta_p_bar"
                              label="Nozzle Liquid Pressure Drop Delta p (bar)"
                              note="Applied in the pressure-nozzle entry velocity relation together with feed density."
                              onChange={(value) => updateNumberField('nozzle_delta_p_bar', value)}
                              value={activeScenario.inputs.nozzle_delta_p_bar}
                            />
                            <NumberField
                              id="nozzle_velocity_coefficient"
                              label="Nozzle Velocity Coefficient Cv (-)"
                              note="Dimensionless discharge factor in U_p,0 = Cv * sqrt(2 * Delta p / rho_l)."
                              onChange={(value) => updateNumberField('nozzle_velocity_coefficient', value)}
                              value={activeScenario.inputs.nozzle_velocity_coefficient}
                            />
                          </div>
                        </section>
                        <section className="expert-group" aria-labelledby="expert-thermal-title">
                          <div className="expert-group-header">
                            <h3 id="expert-thermal-title">Thermal Loss</h3>
                            <p>
                              The wall-loss term uses a single overall coefficient over the effective cylinder, cone, and outlet-duct surface area.
                            </p>
                          </div>
                          <div className="field-row">
                            <NumberField
                              id="heat_loss_coeff_w_m2k"
                              label="Overall Heat Loss Coefficient (W/m2/K)"
                              note="Higher values increase wall heat loss from the air-side enthalpy balance."
                              onChange={(value) => updateNumberField('heat_loss_coeff_w_m2k', value)}
                              value={activeScenario.inputs.heat_loss_coeff_w_m2k}
                            />
                          </div>
                        </section>
                        <section className="expert-group" aria-labelledby="expert-geometry-title">
                          <div className="expert-group-header">
                            <h3 id="expert-geometry-title">Segmented Geometry</h3>
                            <p>
                              The active core resolves an effective 1D path through cylinder, cone, and outlet duct. Back-mixing and flow redirection are not modeled separately.
                            </p>
                          </div>
                          <div className="field-row">
                            <NumberField
                              id="dryer_diameter_m"
                              label="Cylinder Diameter (m)"
                              onChange={(value) => updateNumberField('dryer_diameter_m', value)}
                              value={activeScenario.inputs.dryer_diameter_m}
                            />
                            <NullableNumberField
                              id="cylinder_height_m"
                              label="Cylinder Height (m)"
                              note="This height defines the main vertical section before the cone starts."
                              onChange={(value) => updateNullableNumberField('cylinder_height_m', value)}
                              value={activeScenario.inputs.cylinder_height_m}
                            />
                          </div>
                          <div className="field-row">
                            <NumberField
                              id="cone_height_m"
                              label="Cone Height (m)"
                              onChange={(value) => updateNumberField('cone_height_m', value)}
                              value={activeScenario.inputs.cone_height_m}
                            />
                            <NumberField
                              id="outlet_duct_length_m"
                              label="Outlet Duct Length (m)"
                              onChange={(value) => updateNumberField('outlet_duct_length_m', value)}
                              value={activeScenario.inputs.outlet_duct_length_m}
                            />
                          </div>
                          <div className="field-row">
                            <NullableNumberField
                              id="outlet_duct_diameter_m"
                              label="Outlet Duct Diameter (m)"
                              note="Leave empty only if the backend default should provide the duct diameter."
                              onChange={(value) => updateNullableNumberField('outlet_duct_diameter_m', value)}
                              value={activeScenario.inputs.outlet_duct_diameter_m}
                            />
                          </div>
                        </section>
                      </div>
                    )}
                  </section>

                  <div className="button-row">
                    <button className="button-primary" disabled={!canSimulate} onClick={runComparison} type="button">
                      {isSimulating ? 'Simulation Running' : 'Run Comparison'}
                    </button>
                    <button className="button-secondary" onClick={resetActiveScenario} type="button">
                      {activeScenario.scenario_id === BASE_SCENARIO_ID ? 'Reset Base Case' : 'Reset Active Scenario'}
                    </button>
                  </div>
                </div>
              </section>

              <section className="result-band">
                <div className="kpi-grid">
                  <KpiTile
                    label="Final Powder Moisture"
                    value={formatKpi(activeScenarioResult?.summary.end_moisture_wb_pct)}
                    unit="wt% wb"
                    status={activeScenarioResult?.summary.target_reached ? 'success' : 'warning'}
                  />
                  <KpiTile label="Outlet Air Temperature" value={formatKpi(activeScenarioResult?.summary.Tout_c)} unit="degC" status="info" />
                  <KpiTile label="Outlet Relative Humidity" value={formatKpi(activeScenarioResult?.summary.RHout_pct)} unit="%" status="info" />
                  <KpiTile label="Residence Time" value={formatKpi(activeScenarioResult?.summary.tau_out_s)} unit="s" status="info" />
                  <KpiTile
                    label="Target Reached"
                    value={activeScenarioResult ? (activeScenarioResult.summary.target_reached ? 'yes' : 'no') : 'pending'}
                    unit=""
                    status={activeScenarioResult?.summary.target_reached ? 'success' : 'warning'}
                  />
                  <KpiTile label="Mean Particle Diameter" value={formatKpi(activeScenarioResult?.summary.dmean_out_um)} unit="um" status="info" />
                </div>

                <div className="panel">
                  <div className="panel-header">
                    <h2 className="panel-title">Active Scenario</h2>
                  </div>
                  <div className="panel-body parameter-summary-grid">
                    <ParameterItem label="Name" value={activeScenario.label} />
                    <ParameterItem label="Role" value={activeScenario.scenario_id === BASE_SCENARIO_ID ? 'Base case' : 'Comparison case'} />
                    <ParameterItem label="Tin" value={`${formatKpi(activeScenario.inputs.Tin)} degC`} />
                    <ParameterItem label="Yin" value={`${formatKpi(activeScenario.inputs.inlet_abs_humidity_g_kg)} g/kg`} />
                    <ParameterItem label="Air Mass Flow" value={`${formatKpi(activeScenario.inputs.humid_air_mass_flow_kg_h)} kg/h`} />
                    <ParameterItem label="Feed Rate" value={`${formatKpi(activeScenario.inputs.feed_rate_kg_h)} kg/h`} />
                    <ParameterItem label="Droplet Diameter" value={`${formatKpi(activeScenario.inputs.droplet_size_um)} um`} />
                    <ParameterItem label="Feed Solids" value={`${formatKpi(activeScenario.inputs.feed_total_solids * 100)} wt%`} />
                    <ParameterItem label="Target Moisture" value={`${formatKpi(activeScenario.target_moisture_wb_pct)} wt% wb`} />
                    <ParameterItem label="Equilibrium x_b Model" value={XB_MODEL_DETAILS[activeScenario.inputs.x_b_model].label} />
                    <ParameterItem
                      label="Pressure-Nozzle Entry"
                      value={`${formatKpi(activeScenario.inputs.nozzle_delta_p_bar)} bar / Cv ${formatKpi(activeScenario.inputs.nozzle_velocity_coefficient)}`}
                    />
                    <ParameterItem
                      label="Heat Loss Coefficient"
                      value={`${formatKpi(activeScenario.inputs.heat_loss_coeff_w_m2k)} W/m2/K`}
                    />
                    <ParameterItem
                      label="Cylinder"
                      value={`${formatKpi(activeScenario.inputs.cylinder_height_m)} m x ${formatKpi(activeScenario.inputs.dryer_diameter_m)} m`}
                    />
                    <ParameterItem
                      label="Cone / Outlet duct"
                      value={`${formatKpi(activeScenario.inputs.cone_height_m)} m / ${formatKpi(activeScenario.inputs.outlet_duct_length_m)} m`}
                    />
                    <ParameterItem
                      label="Outlet Duct Diameter"
                      value={`${formatKpi(activeScenario.inputs.outlet_duct_diameter_m)} m`}
                    />
                  </div>
                </div>

                {message && <Banner tone="danger" text={message} />}
                {activeScenarioWarnings.map((warning) => (
                  <Banner key={`${activeScenarioId}-${warning}`} tone="warning" text={warning} />
                ))}
              </section>
            </div>

            <section className="panel chart-panel">
              <div className="panel-header panel-header-split">
                <div>
                  <h2 className="panel-title">Result Charts</h2>
                </div>
                {comparisonResult && activeScenarioResult && (
                  <div className="panel-actions">
                    <button
                      className="button-secondary"
                      onClick={() =>
                        downloadSimulationProfileCsv(
                          activeScenarioResult,
                          `spray-drying-${slugify(activeScenarioResult.label)}-profile.csv`,
                        )
                      }
                      type="button"
                    >
                      Export Active Profile as CSV
                    </button>
                    <button
                      className="button-secondary"
                      onClick={() =>
                        downloadSimulationJson(
                          activeScenarioResult,
                          `spray-drying-${slugify(activeScenarioResult.label)}.json`,
                        )
                      }
                      type="button"
                    >
                      Export Active Result as JSON
                    </button>
                    <button
                      className="button-secondary"
                      onClick={() => downloadComparisonJson(comparisonResult)}
                      type="button"
                    >
                      Export Comparison as JSON
                    </button>
                  </div>
                )}
              </div>
              <div className="panel-body">
                <div className="chart-tabs" role="tablist" aria-label="Result chart tabs">
                  {chartTabs.map((tab) => (
                    <button
                      key={tab.id}
                      className={activeChartTab === tab.id ? 'active' : ''}
                      onClick={() => activateChartTab(tab.id)}
                      role="tab"
                      aria-selected={activeChartTab === tab.id}
                      type="button"
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                {!comparisonResult && (
                  <div className="empty-state">
                    <p>No results yet.</p>
                  </div>
                )}
                {comparisonResult && activeChartTab !== 'comparison' && chartOption && activeScenarioResult && (
                  <div className="chart-with-tower">
                    <LineChart option={chartOption} onAxisValueChange={setHoveredHeightM} />
                    <SprayTowerPreview hoveredHeightM={hoveredHeightM} scenario={activeScenarioResult} />
                  </div>
                )}
                {comparisonResult && activeChartTab === 'comparison' && (
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th>KPI</th>
                        {comparisonResult.scenarios.map((scenario) => (
                          <th key={scenario.scenario_id}>
                            {scenario.label}
                            {scenario.scenario_id === comparisonResult.base_scenario_id ? ' (Base)' : ''}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Final Powder Moisture (wt% wb)"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.end_moisture_wb_pct}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Outlet Air Temperature (degC)"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.Tout_c}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Outlet Relative Humidity (%)"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.RHout_pct}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Residence Time (s)"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.tau_out_s}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="x_out - x_b,out"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.x_out_minus_x_b_out}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Particle Outlet Temperature (degC)"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.T_p_out_c}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Mean Particle Diameter (um)"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.dmean_out_um}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Total Heat Loss (W)"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.outlet.total_q_loss_w}
                      />
                    </tbody>
                  </table>
                )}
              </div>
            </section>
          </section>
        )}

        {activeView === 'model' && <ModelFoundationView />}
      </main>
    </>
  )
}

function StartView({ onNavigate }: { onNavigate: (view: AppView) => void }) {
  return (
    <section className="start-page">
      <section className="start-hero" aria-labelledby="start-title">
        <img
          className="start-hero-image"
          src={heroSprayDryer}
          alt="Spray dryer tower in a clean pilot plant"
        />
        <div className="start-hero-copy">
          <p className="eyebrow">Plug-flow drying kinetics simulation</p>
          <h1 id="start-title">Simulate skim milk powder spray drying across operating scenarios</h1>
          <p>Assess powder moisture and outlet air conditions</p>
          <div className="start-hero-actions">
            <button className="button-primary start-cta" onClick={() => onNavigate('simulation')} type="button">
              Open Simulation
            </button>
            <button className="button-secondary start-cta" onClick={() => onNavigate('model')} type="button">
              Model Foundations
            </button>
          </div>
        </div>
      </section>

      <section className="start-orientation" aria-labelledby="orientation-title">
        <div className="panel start-orientation-panel">
          <div className="panel-header">
            <h2 id="orientation-title" className="panel-title">
              Get started
            </h2>
            <p className="panel-meta">Technical workflow</p>
          </div>
          <div className="start-points">
            {startOrientationPoints.map((point) => (
              <article className="start-point" key={point.title}>
                <span className="label">{point.title}</span>
                <p>{point.description}</p>
              </article>
            ))}
          </div>
        </div>
        <figure className="start-secondary-image">
          <img src={labPowderAnalysis} alt="Skim milk powder sample in pilot plant analysis setup" />
        </figure>
      </section>
    </section>
  )
}

function ModelFoundationView() {
  return (
    <section className="model-page">
      <section className="panel model-intro" aria-labelledby="model-title">
        <div className="panel-body model-intro-body">
          <div>
            <p className="eyebrow">Model Foundations</p>
            <h1 id="model-title" className="start-title">
              Steady-state SMP REA drying
            </h1>
          </div>
        </div>
      </section>

      <section className="panel model-section" aria-labelledby="process-title">
        <div className="panel-header">
          <h2 id="process-title" className="panel-title">
            Computation Workflow
          </h2>
        </div>
        <div className="panel-body">
          <ol className="process-chain">
            {modelProcessSteps.map((step) => (
              <li key={step.title}>
                <span className="process-index">{step.index}</span>
                <div>
                  <h3>{step.title}</h3>
                  <p>{step.description}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="panel model-section" aria-labelledby="state-title">
        <div className="panel-header">
          <h2 id="state-title" className="panel-title">
            State Vector and Outlet
          </h2>
        </div>
        <div className="panel-body model-card-grid">
          <article className="model-card">
            <h3>Axial Coordinate</h3>
            <div className="formula-rendered">
              <MathBlock tex={'h = 0 \\dots h_{\\mathrm{out}}'} />
            </div>
            <p>
              The equations are solved along the effective 1D flow path. Cylinder, cone, and outlet duct
              define the local cross-sectional area <code>A(h)</code>.
            </p>
          </article>
          <article className="model-card">
            <h3>State Vector</h3>
            <div className="formula-rendered">
              <MathBlock tex={'y(h) = [X, T_p, Y, H_h, U_p, \\tau]'} />
            </div>
            <p>
              The solved states are particle moisture, particle temperature, air humidity, air enthalpy,
              particle velocity, and residence time.
            </p>
          </article>
          <article className="model-card">
            <h3>Outlet at Cyclone Inlet</h3>
            <div className="formula-rendered">
              <MathBlock tex={'h_{\\mathrm{out}} = h_{\\mathrm{pre\\text{-}cyclone}}'} />
            </div>
            <p>
              The outlet is defined as the end of the effective outlet duct directly upstream of the cyclone
              inlet. Outlet air temperature, outlet humidity, residence time, final moisture, and mean
              particle diameter are evaluated there.
            </p>
          </article>
        </div>
      </section>

      <section className="panel model-section" aria-labelledby="equations-title">
        <div className="panel-header">
          <h2 id="equations-title" className="panel-title">
            Equations by Section
          </h2>
        </div>
        <div className="panel-body formula-section-grid">
          <article className="formula-section">
            <h3>Inputs and Derived Initial Conditions</h3>
            <div className="formula-rendered">
              <MathBlock tex={'X_0 = \\frac{1 - w_{\\mathrm{TS}}}{w_{\\mathrm{TS}}}'} />
              <MathBlock tex={'H_{h,\\mathrm{in}} = c_{p,da}(T_{\\mathrm{in}} - T_{\\mathrm{ref}}) + Y_{\\mathrm{in}}\\left[\\lambda_{\\mathrm{ref}} + c_{p,v}(T_{\\mathrm{in}} - T_{\\mathrm{ref}})\\right]'} />
              <MathBlock tex={'U_{p,0} = C_v \\sqrt{\\frac{2\\Delta p}{\\rho_l}}'} />
            </div>
            <p className="equation-note">
              The UI inputs are first converted into dry-basis moisture, air enthalpy, and a nozzle-based
              initial droplet velocity.
            </p>
          </article>

          <article className="formula-section">
            <h3>Local Air State and Geometry</h3>
            <div className="formula-rendered">
              <MathBlock tex={'U_a(h) = \\frac{\\dot{m}_{ha}}{\\rho_a(h) A(h)}'} />
              <MathBlock tex={'RH_a = \\frac{p_v(Y,p)}{p_{\\mathrm{sat}}(T_a)}'} />
              <MathBlock tex={'x_{b,\\mathrm{GAB}} = \\frac{C(T) K(T) m_0 RH_a}{\\left(1-K(T)RH_a\\right)\\left(1-K(T)RH_a + C(T)K(T)RH_a\\right)}'} />
              <MathBlock tex={'m_0 = 0.06156, \\quad C(T) = 0.001645 \\, \\exp\\!\\left(\\frac{24831}{RT}\\right), \\quad K(T) = 5.710 \\, \\exp\\!\\left(-\\frac{5118}{RT}\\right)'} />
              <MathBlock tex={'x_{b,\\mathrm{Langrish}} = 0.1499 \\, \\exp\\!\\left(-2.306 \\times 10^{-3} T_{a,K}\\right)\\left[\\ln\\!\\left(\\frac{1}{RH_a}\\right)\\right]^{0.4}'} />
            </div>
            <p className="equation-note">
              The local cross section from cylinder, cone, and outlet duct determines the air velocity. The
              default closure for equilibrium moisture in the core is the temperature-dependent GAB variant;
              the Langrish isotherm remains available for cross-checking.
            </p>
            <div className="equation-sources">
              <span className="label">Sources</span>
              <p>Lin, Chen, Pearce, 2005. Journal of Food Engineering 68, 257-264.</p>
              <p>Langrish, 2009. Journal of Food Engineering 93, 218-228.</p>
            </div>
          </article>

          <article className="formula-section">
            <h3>REA and Material Closure</h3>
            <div className="formula-rendered">
              <MathBlock tex={'\\delta = X - x_b'} />
              <MathBlock tex={'\\psi = \\exp\\!\\left(-\\frac{\\Delta E}{R T_p}\\right)'} />
              <MathBlock tex={'\\rho_{v,s} = \\psi \\, \\rho_{v,\\mathrm{sat}}(T_p)'} />
              <MathBlock tex={'r_{\\mathrm{REA}} = \\min\\!\\left(1, \\max\\!\\left(0, r_{\\mathrm{base}} + r_{\\mathrm{add}}\\right)\\right)'} />
              <MathBlock tex={'r_{\\mathrm{add}} = G \\, \\delta \\, \\sigma\\!\\left(\\frac{c - \\delta^{\\ast}}{w}\\right), \\qquad \\delta^{\\ast} = \\frac{\\max(\\delta,0)}{\\max(X_0 - x_b, \\varepsilon)}'} />
              <MathBlock tex={'d_p = d_{p,0} \\, s(\\delta, x_b, w_{\\mathrm{TS}})'} />
            </div>
            <p className="equation-note">
              REA denotes the Reaction Engineering Approach. The REA term retards surface evaporation through
              the activation energy. In parallel, the particle diameter is updated through the selected
              shrinkage model.
            </p>
            <div className="equation-sources">
              <span className="label">Sources</span>
              <p>Chen, 2008. Drying Technology 26, 627-639.</p>
              <p>Chew et al., 2013. Dairy Science &amp; Technology 93, 415-430.</p>
              <p>
                In the current core, REA retardation in the early falling-rate period is augmented by an
                additional material-specific term. This project-specific implementation adjustment was tuned
                against powder moisture and outlet air temperature data from an SPX MS400 pilot tower and is
                not a direct literature equation.
              </p>
            </div>
          </article>

          <article className="formula-section">
            <h3>Particle Mass Balance</h3>
            <div className="formula-rendered">
              <MathBlock tex={'\\frac{d m_p}{d h} = -\\frac{k_m A_p}{U_p}\\left(\\rho_{v,s} - \\rho_{v,a}\\right)'} />
              <MathBlock tex={'\\frac{dX}{dh} = \\frac{1}{m_{s,\\mathrm{dry}}}\\frac{d m_p}{d h}'} />
              <MathBlock tex={'X \\le x_b \\;\\Rightarrow\\; \\frac{d m_p}{d h} = 0'} />
            </div>
            <p className="equation-note">
              Once the local equilibrium moisture is reached, the drying flux is limited to zero in the core
              so that no unphysical further evaporation occurs.
            </p>
            <div className="equation-sources">
              <span className="label">Sources</span>
              <p>Chew et al., 2013. Dairy Science &amp; Technology 93, 415-430.</p>
              <p>Langrish, 2009. Journal of Food Engineering 93, 218-228.</p>
            </div>
          </article>

          <article className="formula-section">
            <h3>Energy Balances</h3>
            <div className="formula-rendered">
              <MathBlock tex={'\\frac{dT_p}{dh} = \\frac{\\pi d_p k_a Nu (T_a - T_p) + \\frac{dm_p}{dh} U_p (h_{fg} + q_{\\mathrm{sorp}})}{m_{s,\\mathrm{dry}} c_{p,p} U_p}'} />
              <MathBlock tex={'\\frac{dY}{dh} = -\\frac{\\dot{m}_{s,\\mathrm{dry}}}{\\dot{m}_{da}}\\frac{dX}{dh}'} />
              <MathBlock tex={'\\frac{dH_h}{dh} = -\\frac{\\dot{m}_{s,\\mathrm{dry}}}{\\dot{m}_{da}}\\left(c_{p,p}\\frac{dT_p}{dh} + c_{p,w}(T_p - T_{\\mathrm{ref}})\\frac{dX}{dh}\\right) - \\frac{q^{\\prime}_{\\mathrm{loss}}}{\\dot{m}_{da}}'} />
            </div>
            <p className="equation-note">
              The particle balance couples convective heat transfer and latent heat of evaporation. The air
              side is updated through humidity and enthalpy balances.
            </p>
            <div className="equation-sources">
              <span className="label">Sources</span>
              <p>Langrish, 2009. Journal of Food Engineering 93, 218-228.</p>
            </div>
          </article>

          <article className="formula-section">
            <h3>Transport, Motion, and Residence Time</h3>
            <div className="formula-rendered">
              <MathBlock tex={'Re = \\frac{\\rho_a \\left|U_p - U_a\\right| d_p}{\\mu_a}'} />
              <MathBlock tex={'Sh = 2 + 0.6 Re^{0.5} Sc^{1/3}, \\qquad Nu = 2 + 0.6 Re^{0.5} Pr^{1/3}'} />
              <MathBlock tex={'k_m = \\frac{Sh D_v}{d_p}'} />
              <MathBlock tex={'\\frac{dU_p}{dh} = \\frac{\\left(1 - \\frac{\\rho_a}{\\rho_p}\\right) g - F_D}{U_p}'} />
              <MathBlock tex={'\\frac{d\\tau}{dh} = \\frac{1}{U_p}'} />
            </div>
            <p className="equation-note">
              Mass and heat transfer are closed through Sherwood and Nusselt correlations. The particle
              velocity simultaneously drives residence time accumulation.
            </p>
            <div className="equation-sources">
              <span className="label">Sources</span>
              <p>Langrish, 2009. Journal of Food Engineering 93, 218-228.</p>
            </div>
          </article>
        </div>
      </section>

      <section className="panel model-section" aria-labelledby="assumptions-title">
        <div className="panel-header">
          <h2 id="assumptions-title" className="panel-title">
            Assumptions and Limits
          </h2>
        </div>
        <div className="panel-body model-assumptions">
          {modelAssumptions.map((item) => (
            <article className="model-assumption" key={item.title}>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </section>
    </section>
  )
}

const modelProcessSteps = [
  {
    index: '01',
    title: 'UI Inputs and Initial Conditions',
    description:
      'Tin, air mass flow, feed rate, droplet diameter, Yin, feed solids, and geometry define the initial moisture, air enthalpy, density, and nozzle-based droplet velocity.',
  },
  {
    index: '02',
    title: 'Local Geometry Along h',
    description:
      'Cylinder, cone, and outlet duct define the local cross section A(h), wall area per length, and therefore local air velocity and heat loss.',
  },
  {
    index: '03',
    title: 'Air State and Equilibrium Moisture',
    description:
      'Local T_a is calculated from Y and H_h. This determines RH_a and the equilibrium moisture x_b through the selected isotherm model.',
  },
  {
    index: '04',
    title: 'REA and Shrinkage',
    description:
      'The local difference delta = X - x_b determines the surface retardation psi through the REA activation energy and the current particle diameter through the shrinkage model.',
  },
  {
    index: '05',
    title: 'Mass, Energy, and Momentum Balances',
    description:
      'Using the local transport coefficients, dX/dh, dT_p/dh, dY/dh, dH_h/dh, dU_p/dh, and dtau/dh are formulated and integrated along h.',
  },
  {
    index: '06',
    title: 'Outlet and KPI Evaluation',
    description:
      'At the end of the effective outlet duct directly upstream of the cyclone, Tout, RHout, tau_out, final moisture, target attainment, and dmean_out are evaluated.',
  },
]

const startOrientationPoints = [
  {
    title: 'Set up the base case',
    description:
      'Inlet air temperature, air mass flow, feed rate, droplet diameter, inlet absolute humidity, total solids, and geometry define the axial reference case for the tower.',
  },
  {
    title: 'Run the axial profile',
    description:
      'The core integrates moisture, temperature, equilibrium moisture, particle motion, and residence time along the cylinder, cone, and outlet duct.',
  },
  {
    title: 'Apply the material model',
    description:
      'REA retardation, local equilibrium moisture x_b, and the selected shrinkage model couple evaporation and particle state.',
  },
  {
    title: 'Compare scenarios',
    description:
      'One base case plus up to three comparison scenarios show the sensitivity of final moisture, outlet air temperature, outlet relative humidity, residence time, and mean particle diameter.',
  },
]

const modelAssumptions = [
  {
    title: 'Effective 1D flow path',
    description:
      'Cylinder, cone, and outlet duct are treated as a section-wise 1D flow path with local cross section. Back-mixing, redirection, and true 3D structure are not resolved separately.',
  },
  {
    title: 'Steady-state operation',
    description:
      'The calculation is formulated as steady-state in h. Dynamic system changes, disturbances, or time-varying operation are outside the current V1 core.',
  },
  {
    title: 'REA only on the drying branch',
    description:
      'Once X locally falls to x_b, further drying flux is cut off. Rewetting or a symmetric REA branch is not calibrated in the current core.',
  },
  {
    title: 'SMP material closure',
    description:
      'The REA and shrinkage closures are parameterized for the current SMP context over 20-50 wt% feed solids. Above 43 wt%, REA blends toward the legacy 50-wt% material function and shrinkage blends onto the temperature-dependent 50-wt% endpoint; below 37 wt%, the legacy extended shrinkage path is used.',
  },
  {
    title: 'No Tg or stickiness model in V1',
    description:
      'The current app does not yet assess glass-transition or stickiness risk. The tower preview currently shows only the position along h, not critical deposition zones.',
  },
]

type NumberFieldKey =
  | 'Tin'
  | 'humid_air_mass_flow_kg_h'
  | 'feed_rate_kg_h'
  | 'droplet_size_um'
  | 'inlet_abs_humidity_g_kg'
  | 'feed_total_solids'
  | 'heat_loss_coeff_w_m2k'
  | 'nozzle_delta_p_bar'
  | 'nozzle_velocity_coefficient'
  | 'dryer_diameter_m'
  | 'cone_height_m'
  | 'outlet_duct_length_m'

type NullableNumberFieldKey = 'cylinder_height_m' | 'outlet_duct_diameter_m'

function buildScenario(
  scenario_id: string,
  label: string,
  inputs: StationaryInput,
  target_moisture_wb_pct: number,
): ScenarioDraft {
  return {
    scenario_id,
    label,
    inputs: { ...inputs },
    target_moisture_wb_pct,
  }
}

function buildLineSeries(
  name: string,
  data: Array<[number, number | null]>,
  color: string,
  lineType: 'solid' | 'dashed' = 'solid',
): SeriesOption {
  return {
    name,
    type: 'line',
    showSymbol: false,
    lineStyle: {
      color,
      type: lineType,
      width: 2,
    },
    itemStyle: {
      color,
    },
    data,
  }
}

interface ComparisonRowProps {
  label: string
  scenarios: CompareScenarioResponse[]
  baseScenario: CompareScenarioResponse | null
  selector: (scenario: CompareScenarioResponse) => number | null
}

function ComparisonRow({ label, scenarios, baseScenario, selector }: ComparisonRowProps) {
  const baseValue = baseScenario ? selector(baseScenario) : null
  return (
    <tr>
      <td>{label}</td>
      {scenarios.map((scenario) => {
        const value = selector(scenario)
        const delta = baseValue !== null && value !== null ? value - baseValue : null
        return (
          <td key={`${label}-${scenario.scenario_id}`}>
            <div className="comparison-cell">
              <span>{formatKpi(value)}</span>
              {scenario.scenario_id !== baseScenario?.scenario_id && delta !== null && (
                <span className={`comparison-delta ${delta > 0 ? 'positive' : delta < 0 ? 'negative' : ''}`}>
                  {formatSignedDelta(delta)}
                </span>
              )}
            </div>
          </td>
        )
      })}
    </tr>
  )
}

declare global {
  interface Window {
    MathJax?: {
      typesetPromise?: (elements?: HTMLElement[]) => Promise<void>
    }
  }
}

function MathBlock({ tex }: { tex: string }) {
  return <MathFormula display tex={tex} />
}

function MathFormula({ tex, display }: { tex: string; display: boolean }) {
  const elementRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!elementRef.current || !window.MathJax?.typesetPromise) {
      return
    }
    void window.MathJax.typesetPromise([elementRef.current])
  }, [display, tex])

  if (display) {
    return (
      <div
        className="math-block"
        ref={(node) => {
          elementRef.current = node
        }}
      >
        {`\\[${tex}\\]`}
      </div>
    )
  }

  return (
    <span
      className="math-inline"
      ref={(node) => {
        elementRef.current = node
      }}
    >
      {`\\(${tex}\\)`}
    </span>
  )
}

interface SimpleNumberFieldProps {
  id: string
  label: string
  note?: string
  value: number
  onChange: (value: string) => void
}

function NumberField({ id, label, note, value, onChange }: SimpleNumberFieldProps) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} onChange={(event) => onChange(event.target.value)} step="any" type="number" value={value} />
      {note && <div className="field-note field-note-compact">{note}</div>}
    </div>
  )
}

interface NullableNumberFieldProps {
  id: string
  label: string
  note?: string
  value: number | null
  onChange: (value: string) => void
}

function NullableNumberField({ id, label, note, value, onChange }: NullableNumberFieldProps) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        onChange={(event) => onChange(event.target.value)}
        placeholder="auto"
        step="any"
        type="number"
        value={value ?? ''}
      />
      {note && <div className="field-note field-note-compact">{note}</div>}
    </div>
  )
}

interface KpiTileProps {
  label: string
  value: string
  unit: string
  status: 'success' | 'warning' | 'info'
}

function KpiTile({ label, value, unit, status }: KpiTileProps) {
  return (
    <div className={`kpi ${status}`}>
      <span className="kpi-label">{label}</span>
      <strong className="kpi-value">{value}</strong>
      <span className="kpi-unit">{unit}</span>
    </div>
  )
}

function Banner({ text, tone }: { text: string; tone: 'warning' | 'danger' }) {
  return <div className={`banner ${tone}`}>{text}</div>
}

function formatKpi(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'n/a'
  }
  return value.toFixed(Math.abs(value) >= 10 ? 1 : 2)
}

function formatSignedDelta(value: number): string {
  const prefix = value > 0 ? '+' : ''
  return `${prefix}${formatKpi(value)}`
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function ParameterItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="parameter-item">
      <span className="label">{label}</span>
      <p>{value}</p>
    </div>
  )
}

interface PercentageFieldProps {
  id: string
  label: string
  value: number
  onChange: (value: string) => void
}

function formatPercentageInput(value: number): string {
  return (value * 100).toFixed(1)
}

function PercentageField({ id, label, value, onChange }: PercentageFieldProps) {
  const [displayValue, setDisplayValue] = useState(() => formatPercentageInput(value))
  const [isEditing, setIsEditing] = useState(false)
  const renderedValue = isEditing ? displayValue : formatPercentageInput(value)

  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        onBlur={() => {
          setIsEditing(false)
          if (displayValue === '') {
            setDisplayValue(formatPercentageInput(value))
            return
          }
          setDisplayValue(formatPercentageInput(value))
        }}
        onChange={(event) => {
          const nextValue = event.target.value
          setDisplayValue(nextValue)
          onChange(nextValue)
        }}
        onFocus={() => {
          setDisplayValue(formatPercentageInput(value))
          setIsEditing(true)
        }}
        step="0.1"
        type="number"
        value={renderedValue}
      />
    </div>
  )
}

export default App
