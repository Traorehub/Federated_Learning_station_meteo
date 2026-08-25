import type { Overview, Reading } from './types'

export async function fetchOverview(): Promise<Overview> {
  const res = await fetch('/api/overview')
  if (!res.ok) throw new Error(`overview ${res.status}`)
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
