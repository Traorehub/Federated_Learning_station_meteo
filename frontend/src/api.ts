import type {
  FlAuto,
  FlErrors,
  FlRound,
  LatencyHistory,
  LinkHistory,
  Overview,
  Reading,
} from './types'

export async function fetchOverview(): Promise<Overview> {
  const res = await fetch('/api/overview')
  if (!res.ok) throw new Error(`overview ${res.status}`)
  return res.json()
}

export async function fetchRounds(): Promise<FlRound[]> {
  const res = await fetch('/api/fl/rounds')
  if (!res.ok) throw new Error(`rounds ${res.status}`)
  const data: { rounds: FlRound[] } = await res.json()
  return data.rounds ?? []
}

export async function fetchRoundErrors(): Promise<FlErrors> {
  const res = await fetch('/api/fl/errors')
  if (!res.ok) throw new Error(`errors ${res.status}`)
  return res.json()
}

export async function fetchLinkHistory(hours: number, bucketMin: number): Promise<LinkHistory> {
  const res = await fetch(`/api/network/history?hours=${hours}&bucket_min=${bucketMin}`)
  if (!res.ok) throw new Error(`history ${res.status}`)
  return res.json()
}

export async function fetchLatency(): Promise<LatencyHistory> {
  const res = await fetch('/api/network/latency')
  if (!res.ok) throw new Error(`latency ${res.status}`)
  return res.json()
}

export async function fetchAuto(): Promise<FlAuto> {
  const res = await fetch('/api/fl/auto')
  if (!res.ok) throw new Error(`auto ${res.status}`)
  return res.json()
}

export async function setAuto(enabled: boolean, intervalS?: number): Promise<FlAuto> {
  const params = new URLSearchParams({ enabled: String(enabled) })
  if (intervalS != null) params.set('interval_s', String(intervalS))
  const res = await fetch(`/api/fl/auto?${params}`, { method: 'POST' })
  if (!res.ok) throw new Error(`auto ${res.status}`)
  return res.json()
}

export async function startRound(): Promise<FlRound> {
  const res = await fetch('/api/fl/rounds', { method: 'POST' })
  if (!res.ok) throw new Error(`start ${res.status}`)
  return res.json()
}

export function liveSocket(): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return new WebSocket(`${proto}://${window.location.host}/ws/live`)
}

export function isReadingEvent(data: unknown): data is { type: 'reading'; data: Reading } {
  return (
    typeof data === 'object' &&
    data !== null &&
    'type' in data &&
    (data as { type: string }).type === 'reading'
  )
}
