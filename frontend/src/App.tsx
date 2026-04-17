import { useEffect, useMemo, useState } from 'react'
import type { EChartsOption } from 'echarts'
import './App.css'
import { getHealth, getModelDefaults, simulate } from './apiClient'
import { downloadSimulationJson, downloadSimulationProfileCsv } from './exportUtils'
import type {
  ApiStatus,
  AppView,
  ChartTab,
  ModelDefaults,
  SimulationResponse,
  StationaryInput,
  XBModel,
} from './apiTypes'
import LineChart from './LineChart'

const chartTabs: Array<{ id: ChartTab; label: string }> = [
  { id: 'moisture', label: 'Feuchte' },
  { id: 'temperature', label: 'Temperatur' },
  { id: 'equilibrium', label: 'Gleichgewicht und Material' },
  { id: 'velocity', label: 'Geschwindigkeit' },
  { id: 'comparison', label: 'Vergleichstabelle' },
]

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>('checking')
  const [defaults, setDefaults] = useState<ModelDefaults | null>(null)
  const [activeView, setActiveView] = useState<AppView>('start')
  const [inputs, setInputs] = useState<StationaryInput | null>(null)
  const [targetMoistureWbPct, setTargetMoistureWbPct] = useState(4)
  const [isExpertOpen, setIsExpertOpen] = useState(false)
  const [activeChartTab, setActiveChartTab] = useState<ChartTab>('moisture')
  const [isSimulating, setIsSimulating] = useState(false)
  const [result, setResult] = useState<SimulationResponse | null>(null)
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
        setInputs(modelDefaults.default_inputs)
        setTargetMoistureWbPct(modelDefaults.default_target_moisture_wb_pct)
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

  const canSimulate = apiStatus === 'online' && inputs !== null && !isSimulating

  const chartOption = useMemo<EChartsOption | null>(() => {
    if (!result) {
      return null
    }
    const profileSeries = result.profile.series

    const common = {
      animation: false,
      grid: { left: 56, right: 24, top: 48, bottom: 48 },
      legend: { top: 8, textStyle: { color: '#525252', fontSize: 12 } },
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
      return {
        ...common,
        color: ['#8a3ffc', '#0f62fe'],
        yAxis: {
          ...common.yAxis,
          name: 'wt% wb',
        },
        series: [
          {
            name: 'Pulverfeuchte',
            type: 'line',
            showSymbol: false,
            lineStyle: { width: 2 },
            data: profileSeries.map((row) => [row.h_m, row.moisture_wb_pct]),
          },
          {
            name: 'Ziel',
            type: 'line',
            showSymbol: false,
            lineStyle: { width: 2, type: 'dashed' },
            data: profileSeries.map((row) => [row.h_m, result.summary.target_moisture_wb_pct]),
          },
        ],
      }
    }

    if (activeChartTab === 'temperature') {
      return {
        ...common,
        color: ['#0f62fe', '#fa4d56'],
        yAxis: {
          ...common.yAxis,
          name: 'Temperatur C',
        },
        series: [
          {
            name: 'Luft',
            type: 'line',
            showSymbol: false,
            lineStyle: { width: 2 },
            data: profileSeries.map((row) => [row.h_m, row.T_a_c]),
          },
          {
            name: 'Partikel',
            type: 'line',
            showSymbol: false,
            lineStyle: { width: 2 },
            data: profileSeries.map((row) => [row.h_m, row.T_p_c]),
          },
        ],
      }
    }

    if (activeChartTab === 'equilibrium') {
      return {
        ...common,
        color: ['#009d9a', '#8a3ffc'],
        yAxis: {
          ...common.yAxis,
          name: 'Modellgroessen',
        },
        series: [
          {
            name: 'x_b',
            type: 'line',
            showSymbol: false,
            lineStyle: { width: 2 },
            data: profileSeries.map((row) => [row.h_m, row.x_b]),
          },
          {
            name: 'psi',
            type: 'line',
            showSymbol: false,
            lineStyle: { width: 2 },
            data: profileSeries.map((row) => [row.h_m, row.psi]),
          },
        ],
      }
    }

    return {
      ...common,
      color: ['#0f62fe', '#525252'],
      yAxis: {
        ...common.yAxis,
        name: 'Geschwindigkeit m/s',
      },
      series: [
        {
          name: 'U_a',
          type: 'line',
          showSymbol: false,
          lineStyle: { width: 2 },
          data: profileSeries.map((row) => [row.h_m, row.U_a_ms]),
        },
        {
          name: 'U_p',
          type: 'line',
          showSymbol: false,
          lineStyle: { width: 2 },
          data: profileSeries.map((row) => [row.h_m, row.U_p_ms]),
        },
      ],
    }
  }, [activeChartTab, result])

  function updateNumberField<Key extends NumberFieldKey>(key: Key, value: string) {
    if (!inputs || value === '') {
      return
    }
    setInputs({
      ...inputs,
      [key]: Number(value),
    })
  }

  function updateNullableNumberField<Key extends NullableNumberFieldKey>(key: Key, value: string) {
    if (!inputs) {
      return
    }
    setInputs({
      ...inputs,
      [key]: value === '' ? null : Number(value),
    })
  }

  function updateXBModel(value: XBModel) {
    if (!inputs) {
      return
    }
    setInputs({
      ...inputs,
      x_b_model: value,
    })
  }

  function updateFeedTotalSolidsPercent(value: string) {
    if (!inputs || value === '') {
      return
    }
    setInputs({
      ...inputs,
      feed_total_solids: Number(value) / 100,
    })
  }

  async function runSimulation() {
    if (!inputs) {
      return
    }

    setIsSimulating(true)
    setMessage(null)
    try {
      const response = await simulate({
        inputs,
        target_moisture_wb_pct: targetMoistureWbPct,
      })
      setResult(response)
      setActiveView('simulation')
      setActiveChartTab('moisture')
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : 'Simulation fehlgeschlagen')
      setResult(null)
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
          <button
            className={activeView === 'start' ? 'active' : ''}
            onClick={() => setActiveView('start')}
            type="button"
          >
            Start
          </button>
          <button
            className={activeView === 'simulation' ? 'active' : ''}
            onClick={() => setActiveView('simulation')}
            type="button"
          >
            Simulation
          </button>
          <button
            className={activeView === 'model' ? 'active' : ''}
            onClick={() => setActiveView('model')}
            type="button"
          >
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
                    <p>Ein technischer Basisfall mit klaren Defaultwerten fuer schnelle Iteration.</p>
                  </div>
                  <div className="start-point">
                    <span className="point-index">03</span>
                    <p>KPI-Band, Profilplots und Expertenparameter in einer technischen Light-Theme-Shell.</p>
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
                  <p>Basismodus, Expertenmodus, KPI-Struktur sowie Chart-Tabs fuer die spaetere Erweiterung.</p>
                </div>
              </div>
            </div>
          </section>
        )}

        {activeView === 'simulation' && inputs && (
          <section className="simulation-page">
            <div className="layout">
              <section className="panel">
                <div className="panel-header">
                  <h2 className="panel-title">Simulationseingaben</h2>
                  <p className="panel-meta">Struktur gemaess Implementierungsplan, im Stil von powder-caking.</p>
                </div>
                <div className="panel-body field-stack">
                  <div className="field">
                    <label htmlFor="target-moisture">Ziel-Feuchte wt% wb</label>
                    <input
                      id="target-moisture"
                      min="0"
                      onChange={(event) => setTargetMoistureWbPct(Number(event.target.value))}
                      step="0.1"
                      type="number"
                      value={targetMoistureWbPct}
                    />
                    <span className="helper">Wird fuer die KPI-Bewertung und Zielerreichung verwendet.</span>
                  </div>

                  <section className="subsection">
                    <div className="subsection-header">
                      <h3>Basismodus</h3>
                    </div>
                    <div className="field-stack">
                      <div className="field-row">
                        <NumberField
                          id="Tin"
                          label="Tin C"
                          onChange={(value) => updateNumberField('Tin', value)}
                          value={inputs.Tin}
                        />
                        <NumberField
                          id="humid_air_mass_flow_kg_h"
                          label="Humid air mass flow kg/h"
                          onChange={(value) => updateNumberField('humid_air_mass_flow_kg_h', value)}
                          value={inputs.humid_air_mass_flow_kg_h}
                        />
                      </div>
                      <div className="field-row">
                        <NumberField
                          id="feed_rate_kg_h"
                          label="Feed rate kg/h"
                          onChange={(value) => updateNumberField('feed_rate_kg_h', value)}
                          value={inputs.feed_rate_kg_h}
                        />
                        <NumberField
                          id="droplet_size_um"
                          label="Droplet size um"
                          onChange={(value) => updateNumberField('droplet_size_um', value)}
                          value={inputs.droplet_size_um}
                        />
                      </div>
                      <div className="field-row">
                        <NumberField
                          id="inlet_abs_humidity_g_kg"
                          label="Yin g/kg"
                          onChange={(value) => updateNumberField('inlet_abs_humidity_g_kg', value)}
                          value={inputs.inlet_abs_humidity_g_kg}
                        />
                        <PercentageField
                          id="feed_total_solids"
                          label="Total feed solids %"
                          onChange={updateFeedTotalSolidsPercent}
                          value={inputs.feed_total_solids}
                        />
                      </div>
                    </div>
                  </section>

                  <section className="subsection">
                    <button
                      className="section-toggle"
                      onClick={() => setIsExpertOpen((current) => !current)}
                      type="button"
                    >
                      Expertenmodus {isExpertOpen ? 'schliessen' : 'oeffnen'}
                    </button>
                    {isExpertOpen && (
                      <div className="field-stack expert-fields">
                        <div className="field-row">
                          <NumberField
                            id="heat_loss_coeff_w_m2k"
                            label="heat_loss_coeff_w_m2k"
                            onChange={(value) => updateNumberField('heat_loss_coeff_w_m2k', value)}
                            value={inputs.heat_loss_coeff_w_m2k}
                          />
                          <div className="field">
                            <label htmlFor="x_b_model">x_b_model</label>
                            <select
                              id="x_b_model"
                              onChange={(event) => updateXBModel(event.target.value as XBModel)}
                              value={inputs.x_b_model}
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
                            value={inputs.nozzle_delta_p_bar}
                          />
                          <NumberField
                            id="nozzle_velocity_coefficient"
                            label="nozzle_velocity_coefficient"
                            onChange={(value) => updateNumberField('nozzle_velocity_coefficient', value)}
                            value={inputs.nozzle_velocity_coefficient}
                          />
                        </div>
                        <div className="field-row">
                          <NumberField
                            id="dryer_diameter_m"
                            label="dryer_diameter_m"
                            onChange={(value) => updateNumberField('dryer_diameter_m', value)}
                            value={inputs.dryer_diameter_m}
                          />
                          <NullableNumberField
                            id="cylinder_height_m"
                            label="cylinder_height_m"
                            onChange={(value) => updateNullableNumberField('cylinder_height_m', value)}
                            value={inputs.cylinder_height_m}
                          />
                        </div>
                        <div className="field-row">
                          <NumberField
                            id="cone_height_m"
                            label="cone_height_m"
                            onChange={(value) => updateNumberField('cone_height_m', value)}
                            value={inputs.cone_height_m}
                          />
                          <NumberField
                            id="outlet_duct_length_m"
                            label="outlet_duct_length_m"
                            onChange={(value) => updateNumberField('outlet_duct_length_m', value)}
                            value={inputs.outlet_duct_length_m}
                          />
                        </div>
                        <div className="field-row">
                          <NullableNumberField
                            id="outlet_duct_diameter_m"
                            label="outlet_duct_diameter_m"
                            onChange={(value) => updateNullableNumberField('outlet_duct_diameter_m', value)}
                            value={inputs.outlet_duct_diameter_m}
                          />
                          <div className="field">
                            <label>Geometriehinweis</label>
                            <div className="field-note">
                              Fuer die UI wird die segmentierte Geometrie direkt ueber Zylinderhoehe,
                              Konushoehe und Abluftrohr beschrieben. Eine separate Gesamt-Turmhoehe
                              wird in der App nicht mehr gepflegt.
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </section>

                  <div className="button-row">
                    <button className="button-primary" disabled={!canSimulate} onClick={runSimulation} type="button">
                      {isSimulating ? 'Simulation laeuft' : 'Simulation starten'}
                    </button>
                    <button
                      className="button-secondary"
                      onClick={() => {
                        if (!defaults) {
                          return
                        }
                        setInputs(defaults.default_inputs)
                        setResult(null)
                        setMessage(null)
                      }}
                      type="button"
                    >
                      Basisfall zuruecksetzen
                    </button>
                  </div>
                </div>
              </section>

              <section className="result-band">
                <div className="kpi-grid">
                  <KpiTile
                    label="Endfeuchte"
                    value={formatKpi(result?.summary.end_moisture_wb_pct)}
                    unit="wt% wb"
                    status={result?.summary.target_reached ? 'success' : 'warning'}
                  />
                  <KpiTile
                    label="Tout"
                    value={formatKpi(result?.summary.Tout_c)}
                    unit="C"
                    status="info"
                  />
                  <KpiTile
                    label="RHout"
                    value={formatKpi(result?.summary.RHout_pct)}
                    unit="%"
                    status="info"
                  />
                  <KpiTile
                    label="tau_out"
                    value={formatKpi(result?.summary.tau_out_s)}
                    unit="s"
                    status="info"
                  />
                  <KpiTile
                    label="Ziel erreicht"
                    value={result ? (result.summary.target_reached ? 'ja' : 'nein') : 'offen'}
                    unit=""
                    status={result?.summary.target_reached ? 'success' : 'warning'}
                  />
                  <KpiTile
                    label="dmean_out"
                    value={formatKpi(result?.summary.dmean_out_um)}
                    unit="um"
                    status="info"
                  />
                </div>

                <div className="panel">
                  <div className="panel-header">
                    <h2 className="panel-title">Aktuelle Simulation</h2>
                  </div>
                  <div className="panel-body parameter-summary-grid">
                    <ParameterItem label="Tin" value={`${formatKpi(inputs.Tin)} C`} />
                    <ParameterItem label="Yin" value={`${formatKpi(inputs.inlet_abs_humidity_g_kg)} g/kg`} />
                    <ParameterItem label="Feed rate" value={`${formatKpi(inputs.feed_rate_kg_h)} kg/h`} />
                    <ParameterItem label="Droplet size" value={`${formatKpi(inputs.droplet_size_um)} um`} />
                    <ParameterItem label="Feed solids" value={`${formatKpi(inputs.feed_total_solids * 100)} %`} />
                    <ParameterItem label="Target moisture" value={`${formatKpi(targetMoistureWbPct)} wt% wb`} />
                    <ParameterItem
                      label="Zylinder"
                      value={`${formatKpi(inputs.cylinder_height_m)} m x ${formatKpi(inputs.dryer_diameter_m)} m`}
                    />
                    <ParameterItem
                      label="Konus / Duct"
                      value={`${formatKpi(inputs.cone_height_m)} m / ${formatKpi(inputs.outlet_duct_length_m)} m`}
                    />
                  </div>
                </div>

                {message && <Banner tone="danger" text={message} />}
                {result?.warnings.map((warning) => (
                  <Banner key={warning} tone="warning" text={warning} />
                ))}

                <div className="panel chart-panel">
                  <div className="panel-header">
                    <h2 className="panel-title">Profile und Vergleich</h2>
                  </div>
                  <div className="panel-body">
                    <div className="tab-row">
                      {chartTabs.map((tab) => (
                        <button
                          key={tab.id}
                          className={activeChartTab === tab.id ? 'tab active' : 'tab'}
                          onClick={() => setActiveChartTab(tab.id)}
                          type="button"
                        >
                          {tab.label}
                        </button>
                      ))}
                    </div>
                    {result && (
                      <div className="button-row export-row">
                        <button
                          className="button-secondary"
                          onClick={() => downloadSimulationProfileCsv(result)}
                          type="button"
                        >
                          Profil als CSV exportieren
                        </button>
                        <button
                          className="button-secondary"
                          onClick={() => downloadSimulationJson(result)}
                          type="button"
                        >
                          Ergebnis als JSON exportieren
                        </button>
                      </div>
                    )}
                    {!result && (
                      <div className="empty-state">
                        <p>Die Chart-Struktur ist angelegt. Nach dem ersten Lauf erscheinen hier KPI-, Profil- und Vergleichsdaten.</p>
                      </div>
                    )}
                    {result && activeChartTab !== 'comparison' && chartOption && <LineChart option={chartOption} />}
                    {result && activeChartTab === 'comparison' && (
                      <table className="comparison-table">
                        <thead>
                          <tr>
                            <th>KPI</th>
                            <th>Basisfall</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td>Endfeuchte wt% wb</td>
                            <td>{formatKpi(result.summary.end_moisture_wb_pct)}</td>
                          </tr>
                          <tr>
                            <td>Tout C</td>
                            <td>{formatKpi(result.summary.Tout_c)}</td>
                          </tr>
                          <tr>
                            <td>x_out - x_b,out</td>
                            <td>{formatKpi(result.summary.x_out_minus_x_b_out)}</td>
                          </tr>
                          <tr>
                            <td>T_p,out C</td>
                            <td>{formatKpi(result.summary.T_p_out_c)}</td>
                          </tr>
                          <tr>
                            <td>U_p,out m/s</td>
                            <td>{formatKpi(result.summary.U_p_out_ms)}</td>
                          </tr>
                          <tr>
                            <td>dmean_out um</td>
                            <td>{formatKpi(result.summary.dmean_out_um)}</td>
                          </tr>
                          <tr>
                            <td>Gesamt-Waermeverlust W</td>
                            <td>{formatKpi(result.outlet.total_q_loss_w)}</td>
                          </tr>
                        </tbody>
                      </table>
                    )}
                    {result && activeChartTab === 'comparison' && (
                      <p className="helper comparison-note">
                        Diese Tabelle zeigt aktuell nur den Basisfall. Mehrere Szenarien werden im naechsten Schritt hier gegenuebergestellt.
                      </p>
                    )}
                  </div>
                </div>
              </section>
            </div>
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
                  <li>Die neue App-Struktur ist bewusst fuer spaetere Vergleichsszenarien und Exportfunktionen vorbereitet.</li>
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
