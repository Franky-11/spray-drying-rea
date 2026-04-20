import type {
  CompareRequest,
  CompareResponse,
  HealthResponse,
  ModelDefaults,
  SimulationRequest,
  SimulationResponse,
} from './apiTypes'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').trim().replace(/\/$/, '')

function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  })

  if (!response.ok) {
    let message = `API request failed with status ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) {
        message = payload.detail
      }
    } catch {
      message = response.statusText || message
    }
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health')
}

export function getModelDefaults(): Promise<ModelDefaults> {
  return requestJson<ModelDefaults>('/model/defaults')
}

export function simulate(body: SimulationRequest): Promise<SimulationResponse> {
  return requestJson<SimulationResponse>('/simulate', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function compare(body: CompareRequest): Promise<CompareResponse> {
  return requestJson<CompareResponse>('/compare', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
