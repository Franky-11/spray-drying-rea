import { useEffect, useMemo, useState } from 'react'
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
import LineChart from './LineChart'
import SprayTowerPreview from './SprayTowerPreview'

const BASE_SCENARIO_ID = 'base'
const MAX_SCENARIOS = 4
const SCENARIO_COLORS = ['#0f62fe', '#8a3ffc', '#009d9a', '#fa4d56']

const chartTabs: Array<{ id: ChartTab; label: string }> = [
  { id: 'moisture', label: 'Feuchte' },
  { id: 'temperature', label: 'Temperatur' },
  { id: 'equilibrium', label: 'Gleichgewicht und Material' },
  { id: 'particle', label: 'Partikelgroesse' },
  { id: 'velocity', label: 'Geschwindigkeit' },
  { id: 'comparison', label: 'Vergleichstabelle' },
]

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
            'Basisfall',
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
        setMessage(error instanceof Error ? error.message : 'API nicht erreichbar')
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
        name: 'Hoehe m',
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
            'Ziel',
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
          name: 'wt% wb',
        },
        series,
      }
    }

    if (activeChartTab === 'temperature') {
      return {
        ...common,
        yAxis: {
          ...common.yAxis,
          name: 'Temperatur C',
        },
        series: scenarioResults.flatMap((scenario, index) => {
          const color = SCENARIO_COLORS[index % SCENARIO_COLORS.length]
          return [
            buildLineSeries(
              `${scenario.label} Luft`,
              scenario.profile.series.map((row) => [row.h_m, row.T_a_c]),
              color,
            ),
            buildLineSeries(
              `${scenario.label} Partikel`,
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
          name: 'Modellgroessen',
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
          name: 'Partikelgroesse um',
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
        name: 'Geschwindigkeit m/s',
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
      `Variante ${scenarioNumber}`,
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
      setMessage(error instanceof Error ? error.message : 'Simulation fehlgeschlagen')
      setComparisonResult(null)
    } finally {
      setIsSimulating(false)
    }
  }

  return (
    <>
      <header className="top-bar">
        <div className="brand">
          <span className="brand-title">Spray Drying</span>
          <span className="brand-subtitle">Stationaere SMP-REA-Trocknung</span>
        </div>
        <nav className="top-nav" aria-label="Seiten">
          <button className={activeView === 'start' ? 'active' : ''} onClick={() => setActiveView('start')} type="button">
            Start
          </button>
          <button
            className={activeView === 'simulation' ? 'active' : ''}
            onClick={() => setActiveView('simulation')}
            type="button"
          >
            Simulation
          </button>
          <button className={activeView === 'model' ? 'active' : ''} onClick={() => setActiveView('model')} type="button">
            Modellgrundlagen
          </button>
        </nav>
        <div className={`api-status ${apiStatus}`}>
          <span className="status-label">API</span>
          <strong>{apiStatus === 'online' ? 'online' : apiStatus === 'offline' ? 'offline' : 'prueft'}</strong>
        </div>
      </header>

      <main className="page">
        {activeView === 'start' && (
          <section className="start-page">
            <div className="panel start-intro">
              <div className="panel-header">
                <p className="eyebrow">V1-Neuaufbau in Powder-Caking-Struktur</p>
                <h1 className="start-title">Technische Arbeitsoberflaeche fuer stationaere SMP-Trocknung</h1>
              </div>
              <div className="panel-body start-grid">
                <div>
                  <p className="lead">
                    Das neue Frontend kapselt den stabilisierten Fine-Kern aus
                    <code> core/stationary_smp_rea/</code> hinter einer klaren React- und API-Schicht.
                  </p>
                  <div className="button-row">
                    <button className="button-primary" onClick={() => setActiveView('simulation')} type="button">
                      Simulation oeffnen
                    </button>
                    <button className="button-secondary" onClick={() => setActiveView('model')} type="button">
                      Modellgrundlagen
                    </button>
                  </div>
                </div>
                <div className="start-points">
                  <div className="start-point">
                    <span className="point-index">01</span>
                    <p>Stationaerer REA-basierter Trocknungskern fuer SMP.</p>
                  </div>
                  <div className="start-point">
                    <span className="point-index">02</span>
                    <p>Ein Basisfall plus bis zu drei Vergleichsszenarien fuer gezielte Sensitivitaeten.</p>
                  </div>
                  <div className="start-point">
                    <span className="point-index">03</span>
                    <p>KPI-Band, Vergleichstabelle und ueberlagerte Profilplots in einer technischen Light-Theme-Shell.</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2 className="panel-title">Erste Ausbaugrenze</h2>
              </div>
              <div className="panel-body info-grid">
                <div>
                  <span className="label">In V1 enthalten</span>
                  <p>Nur das Modul fuer die stationaere Trocknungskinetik, ohne Prozesssimulation und ohne Legacy-Streamlit-UI.</p>
                </div>
                <div>
                  <span className="label">Vorbereitet</span>
                  <p>Basismodus, Expertenmodus, Vergleichsszenarien, KPI-Struktur sowie Chart-Tabs fuer die spaetere Erweiterung.</p>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeView === 'simulation' && activeScenario && (
          <section className="simulation-page">
            <div className="layout simulation-top-layout">
              <section className="panel">
                <div className="panel-header">
                  <h2 className="panel-title">Simulationseingaben</h2>
                </div>
                <div className="panel-body field-stack">
                  <section className="subsection scenario-section">
                    <div className="subsection-header">
                      <h3>Szenarien</h3>
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
                          <small>{scenario.scenario_id === BASE_SCENARIO_ID ? 'Basis' : 'Vergleich'}</small>
                        </button>
                      ))}
                    </div>
                    <div className="button-row">
                      <button className="button-secondary" disabled={!canAddScenario} onClick={() => addScenario(baseScenario ?? activeScenario)} type="button">
                        Vergleichsszenario anlegen
                      </button>
                      <button className="button-secondary" disabled={!canAddScenario} onClick={() => addScenario(activeScenario)} type="button">
                        Aktives duplizieren
                      </button>
                      <button className="button-secondary" disabled={!canDeleteScenario} onClick={removeActiveScenario} type="button">
                        Aktives entfernen
                      </button>
                    </div>
                    <span className="helper">Bis zu drei Vergleichsszenarien zusaetzlich zum Basisfall.</span>
                  </section>

                  <div className="field-row">
                    <div className="field">
                      <label htmlFor="scenario-label">Szenarioname</label>
                      <input
                        id="scenario-label"
                        onChange={(event) => updateScenarioLabel(event.target.value)}
                        type="text"
                        value={activeScenario.label}
                      />
                    </div>
                    <div className="field">
                      <label htmlFor="target-moisture">Ziel-Feuchte wt% wb</label>
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
                      <h3>Basismodus</h3>
                    </div>
                    <div className="field-stack">
                      <div className="field-row">
                        <NumberField id="Tin" label="Tin C" onChange={(value) => updateNumberField('Tin', value)} value={activeScenario.inputs.Tin} />
                        <NumberField
                          id="humid_air_mass_flow_kg_h"
                          label="Humid air mass flow kg/h"
                          onChange={(value) => updateNumberField('humid_air_mass_flow_kg_h', value)}
                          value={activeScenario.inputs.humid_air_mass_flow_kg_h}
                        />
                      </div>
                      <div className="field-row">
                        <NumberField
                          id="feed_rate_kg_h"
                          label="Feed rate kg/h"
                          onChange={(value) => updateNumberField('feed_rate_kg_h', value)}
                          value={activeScenario.inputs.feed_rate_kg_h}
                        />
                        <NumberField
                          id="droplet_size_um"
                          label="Droplet size um"
                          onChange={(value) => updateNumberField('droplet_size_um', value)}
                          value={activeScenario.inputs.droplet_size_um}
                        />
                      </div>
                      <div className="field-row">
                        <NumberField
                          id="inlet_abs_humidity_g_kg"
                          label="Yin g/kg"
                          onChange={(value) => updateNumberField('inlet_abs_humidity_g_kg', value)}
                          value={activeScenario.inputs.inlet_abs_humidity_g_kg}
                        />
                        <PercentageField
                          id="feed_total_solids"
                          label="Total feed solids %"
                          onChange={updateFeedTotalSolidsPercent}
                          value={activeScenario.inputs.feed_total_solids}
                        />
                      </div>
                    </div>
                  </section>

                  <section className="subsection">
                    <button className="section-toggle" onClick={() => setIsExpertOpen((current) => !current)} type="button">
                      Expertenmodus {isExpertOpen ? 'schliessen' : 'oeffnen'}
                    </button>
                    {isExpertOpen && (
                      <div className="field-stack expert-fields">
                        <div className="field-row">
                          <NumberField
                            id="heat_loss_coeff_w_m2k"
                            label="heat_loss_coeff_w_m2k"
                            onChange={(value) => updateNumberField('heat_loss_coeff_w_m2k', value)}
                            value={activeScenario.inputs.heat_loss_coeff_w_m2k}
                          />
                          <div className="field">
                            <label htmlFor="x_b_model">x_b_model</label>
                            <select
                              id="x_b_model"
                              onChange={(event) => updateXBModel(event.target.value as XBModel)}
                              value={activeScenario.inputs.x_b_model}
                            >
                              <option value="langrish">langrish</option>
                              <option value="lin_gab">lin_gab</option>
                            </select>
                          </div>
                        </div>
                        <div className="field-row">
                          <NumberField
                            id="nozzle_delta_p_bar"
                            label="nozzle_delta_p_bar"
                            onChange={(value) => updateNumberField('nozzle_delta_p_bar', value)}
                            value={activeScenario.inputs.nozzle_delta_p_bar}
                          />
                          <NumberField
                            id="nozzle_velocity_coefficient"
                            label="nozzle_velocity_coefficient"
                            onChange={(value) => updateNumberField('nozzle_velocity_coefficient', value)}
                            value={activeScenario.inputs.nozzle_velocity_coefficient}
                          />
                        </div>
                        <div className="field-row">
                          <NumberField
                            id="dryer_diameter_m"
                            label="dryer_diameter_m"
                            onChange={(value) => updateNumberField('dryer_diameter_m', value)}
                            value={activeScenario.inputs.dryer_diameter_m}
                          />
                          <NullableNumberField
                            id="cylinder_height_m"
                            label="cylinder_height_m"
                            onChange={(value) => updateNullableNumberField('cylinder_height_m', value)}
                            value={activeScenario.inputs.cylinder_height_m}
                          />
                        </div>
                        <div className="field-row">
                          <NumberField
                            id="cone_height_m"
                            label="cone_height_m"
                            onChange={(value) => updateNumberField('cone_height_m', value)}
                            value={activeScenario.inputs.cone_height_m}
                          />
                          <NumberField
                            id="outlet_duct_length_m"
                            label="outlet_duct_length_m"
                            onChange={(value) => updateNumberField('outlet_duct_length_m', value)}
                            value={activeScenario.inputs.outlet_duct_length_m}
                          />
                        </div>
                        <div className="field-row">
                          <NullableNumberField
                            id="outlet_duct_diameter_m"
                            label="outlet_duct_diameter_m"
                            onChange={(value) => updateNullableNumberField('outlet_duct_diameter_m', value)}
                            value={activeScenario.inputs.outlet_duct_diameter_m}
                          />
                          <div className="field">
                            <label>Geometriehinweis</label>
                            <div className="field-note">
                              Die segmentierte Geometrie wird direkt ueber Zylinderhoehe, Konushoehe und Abluftrohr beschrieben.
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </section>

                  <div className="button-row">
                    <button className="button-primary" disabled={!canSimulate} onClick={runComparison} type="button">
                      {isSimulating ? 'Simulation laeuft' : 'Vergleich rechnen'}
                    </button>
                    <button className="button-secondary" onClick={resetActiveScenario} type="button">
                      {activeScenario.scenario_id === BASE_SCENARIO_ID ? 'Basisfall zuruecksetzen' : 'Aktives Szenario zuruecksetzen'}
                    </button>
                  </div>
                </div>
              </section>

              <section className="result-band">
                <div className="kpi-grid">
                  <KpiTile
                    label="Endfeuchte"
                    value={formatKpi(activeScenarioResult?.summary.end_moisture_wb_pct)}
                    unit="wt% wb"
                    status={activeScenarioResult?.summary.target_reached ? 'success' : 'warning'}
                  />
                  <KpiTile label="Tout" value={formatKpi(activeScenarioResult?.summary.Tout_c)} unit="C" status="info" />
                  <KpiTile label="RHout" value={formatKpi(activeScenarioResult?.summary.RHout_pct)} unit="%" status="info" />
                  <KpiTile label="tau_out" value={formatKpi(activeScenarioResult?.summary.tau_out_s)} unit="s" status="info" />
                  <KpiTile
                    label="Ziel erreicht"
                    value={activeScenarioResult ? (activeScenarioResult.summary.target_reached ? 'ja' : 'nein') : 'offen'}
                    unit=""
                    status={activeScenarioResult?.summary.target_reached ? 'success' : 'warning'}
                  />
                  <KpiTile label="dmean_out" value={formatKpi(activeScenarioResult?.summary.dmean_out_um)} unit="um" status="info" />
                </div>

                <div className="panel">
                  <div className="panel-header">
                    <h2 className="panel-title">Aktives Szenario</h2>
                  </div>
                  <div className="panel-body parameter-summary-grid">
                    <ParameterItem label="Name" value={activeScenario.label} />
                    <ParameterItem label="Rolle" value={activeScenario.scenario_id === BASE_SCENARIO_ID ? 'Basisfall' : 'Vergleichsszenario'} />
                    <ParameterItem label="Tin" value={`${formatKpi(activeScenario.inputs.Tin)} C`} />
                    <ParameterItem label="Yin" value={`${formatKpi(activeScenario.inputs.inlet_abs_humidity_g_kg)} g/kg`} />
                    <ParameterItem label="Air flow" value={`${formatKpi(activeScenario.inputs.humid_air_mass_flow_kg_h)} kg/h`} />
                    <ParameterItem label="Feed rate" value={`${formatKpi(activeScenario.inputs.feed_rate_kg_h)} kg/h`} />
                    <ParameterItem label="Droplet size" value={`${formatKpi(activeScenario.inputs.droplet_size_um)} um`} />
                    <ParameterItem label="Feed solids" value={`${formatKpi(activeScenario.inputs.feed_total_solids * 100)} %`} />
                    <ParameterItem label="Target moisture" value={`${formatKpi(activeScenario.target_moisture_wb_pct)} wt% wb`} />
                    <ParameterItem
                      label="Zylinder"
                      value={`${formatKpi(activeScenario.inputs.cylinder_height_m)} m x ${formatKpi(activeScenario.inputs.dryer_diameter_m)} m`}
                    />
                    <ParameterItem
                      label="Konus / Duct"
                      value={`${formatKpi(activeScenario.inputs.cone_height_m)} m / ${formatKpi(activeScenario.inputs.outlet_duct_length_m)} m`}
                    />
                    <ParameterItem
                      label="Duct diameter"
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
                  <h2 className="panel-title">Result charts</h2>
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
                      Aktives Profil als CSV exportieren
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
                      Aktives Ergebnis als JSON exportieren
                    </button>
                    <button
                      className="button-secondary"
                      onClick={() => downloadComparisonJson(comparisonResult)}
                      type="button"
                    >
                      Vergleich als JSON exportieren
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
                    <p>Noch keine Ergebnisse.</p>
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
                            {scenario.scenario_id === comparisonResult.base_scenario_id ? ' (Basis)' : ''}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Endfeuchte wt% wb"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.end_moisture_wb_pct}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Tout C"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.Tout_c}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="RHout %"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.RHout_pct}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="tau_out s"
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
                        label="T_p,out C"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.T_p_out_c}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="dmean_out um"
                        scenarios={comparisonResult.scenarios}
                        selector={(scenario) => scenario.summary.dmean_out_um}
                      />
                      <ComparisonRow
                        baseScenario={baseScenarioResult}
                        label="Gesamt-Waermeverlust W"
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

        {activeView === 'model' && (
          <section className="model-page">
            <div className="panel">
              <div className="panel-header">
                <h1 className="panel-title">Modellgrundlagen</h1>
              </div>
              <div className="panel-body info-grid">
                <div>
                  <span className="label">Kern</span>
                  <p>Verwendet wird ausschliesslich der stationaere SMP-REA-Kern unter <code>core/stationary_smp_rea/</code>.</p>
                </div>
                <div>
                  <span className="label">Koordinate</span>
                  <p>Die Berechnung laeuft entlang einer effektiven 1D-Stroembahn ueber Zylinder, Konus und optionales Abluftrohr.</p>
                </div>
                <div>
                  <span className="label">V1-Fokus</span>
                  <p>Die Seite dokumentiert Inputs, KPI-Definitionen und Modellgrenzen, nicht die Prozesssimulation.</p>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2 className="panel-title">Eingaben und Outputs</h2>
              </div>
              <div className="panel-body basics-grid">
                <div>
                  <h3>Basismodus</h3>
                  <ul className="flat-list">
                    <li><code>Tin</code>, <code>humid_air_mass_flow_kg_h</code>, <code>feed_rate_kg_h</code></li>
                    <li><code>droplet_size_um</code>, <code>inlet_abs_humidity_g_kg</code>, <code>feed_total_solids</code></li>
                  </ul>
                </div>
                <div>
                  <h3>Expertenmodus</h3>
                  <ul className="flat-list">
                    <li><code>heat_loss_coeff_w_m2k</code>, <code>x_b_model</code></li>
                    <li><code>nozzle_delta_p_bar</code>, <code>nozzle_velocity_coefficient</code></li>
                    <li>Turm- und Geometriedaten fuer Zylinder, Konus und Abluftrohr</li>
                  </ul>
                </div>
                <div>
                  <h3>Pflicht-KPIs</h3>
                  <ul className="flat-list">
                    <li><code>Tout</code>, <code>RHout</code>, <code>tau_out</code></li>
                    <li>Endfeuchte, Zielerreichung, Zeit und Hoehe bis Ziel</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-header">
                <h2 className="panel-title">Technische Hinweise</h2>
              </div>
              <div className="panel-body">
                <ul className="flat-list">
                  <li>Der API-Layer konvertiert <code>humid_air_mass_flow_kg_h</code> intern in den fuer den Kern benoetigten Volumenstrom.</li>
                  <li><code>x_b_model</code> kann zwischen <code>langrish</code> und <code>lin_gab</code> umgeschaltet werden.</li>
                  <li>Die neue App-Struktur ist fuer Vergleichsszenarien, KPI-Matrix und ueberlagerte Profilplots ausgelegt.</li>
                </ul>
              </div>
            </div>
          </section>
        )}
      </main>
    </>
  )
}

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

interface SimpleNumberFieldProps {
  id: string
  label: string
  value: number
  onChange: (value: string) => void
}

function NumberField({ id, label, value, onChange }: SimpleNumberFieldProps) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input id={id} onChange={(event) => onChange(event.target.value)} step="any" type="number" value={value} />
    </div>
  )
}

interface NullableNumberFieldProps {
  id: string
  label: string
  value: number | null
  onChange: (value: string) => void
}

function NullableNumberField({ id, label, value, onChange }: NullableNumberFieldProps) {
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

function PercentageField({ id, label, value, onChange }: PercentageFieldProps) {
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        onChange={(event) => onChange(event.target.value)}
        step="0.1"
        type="number"
        value={(value * 100).toFixed(1)}
      />
    </div>
  )
}

export default App
