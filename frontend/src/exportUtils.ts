import type { SimulationResponse } from './apiTypes'

export function downloadSimulationJson(result: SimulationResponse, filename = 'spray-drying-simulation.json') {
  downloadText(JSON.stringify(result, null, 2), filename, 'application/json;charset=utf-8')
}

export function downloadSimulationProfileCsv(
  result: SimulationResponse,
  filename = 'spray-drying-profile.csv',
) {
  const columns = [
    'h_m',
    'section',
    'tau_s',
    'moisture_wb_pct',
    'X',
    'T_a_c',
    'T_p_c',
    'RH_a_pct',
    'x_b',
    'psi',
    'U_a_ms',
    'U_p_ms',
  ] as const

  const lines = [
    columns.join(','),
    ...result.profile.series.map((row) =>
      columns
        .map((column) => escapeCsvValue(row[column]))
        .join(','),
    ),
  ]
  downloadText(lines.join('\n'), filename, 'text/csv;charset=utf-8')
}

function downloadText(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

function escapeCsvValue(value: string | number | null): string {
  if (value === null) {
    return ''
  }
  const text = String(value)
  if (!/[",\n]/.test(text)) {
    return text
  }
  return `"${text.replaceAll('"', '""')}"`
}
