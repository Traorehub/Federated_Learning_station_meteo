import { useEffect, useRef, useState } from 'react'
import { fetchOverview, isReadingEvent, liveSocket } from '../api'
import type { NodeStats, Overview, Reading } from '../types'

const POLL_MS = 8000
const MAX_READINGS = 80

function mergeReading(prev: Overview | null, reading: Reading): Overview {
  const base: Overview = prev ?? { stage: 'v1', nodes: [], readings: [] }
  const readings = [reading, ...base.readings.filter((r) => r.id !== reading.id)].slice(0, MAX_READINGS)

  const nodes = [...base.nodes]
  const idx = nodes.findIndex((n) => n.node_id === reading.node_id)
  const next: NodeStats = {
    node_id: reading.node_id,
    last_seq: reading.seq,
    last_seen_at: reading.received_at,
    last_rssi: reading.rssi,
    last_snr: reading.snr,
    last_temperature: reading.temperature,
    last_humidity: reading.humidity,
    packets_received: reading.packets_received ?? (idx >= 0 ? nodes[idx].packets_received : 0),
    packets_missing: reading.packets_missing ?? (idx >= 0 ? nodes[idx].packets_missing : 0),
    packets_corrupt: reading.packets_corrupt ?? (idx >= 0 ? nodes[idx].packets_corrupt : 0),
    loss_rate: reading.loss_rate ?? (idx >= 0 ? nodes[idx].loss_rate : null),
  }
  if (idx >= 0) nodes[idx] = next
  else nodes.push(next)
  nodes.sort((a, b) => a.node_id - b.node_id)

  return { ...base, nodes, readings }
}

export function useLiveData() {
  const [data, setData] = useState<Overview | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [live, setLive] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(tick)
  }, [])

  useEffect(() => {
    let stopped = false
    let retry: number | undefined

    const load = async () => {
      try {
        const overview = await fetchOverview()
        if (!stopped) {
          setData(overview)
          setError(null)
        }
      } catch (err) {
        if (!stopped) setError(err instanceof Error ? err.message : 'réseau')
      }
    }

    const connect = () => {
      const ws = liveSocket()
      wsRef.current = ws
      ws.onopen = () => {
        if (!stopped) setLive(true)
      }
      ws.onmessage = (ev) => {
        try {
          const parsed: unknown = JSON.parse(ev.data as string)
          if (isReadingEvent(parsed)) {
            setData((prev) => mergeReading(prev, parsed.data))
            setError(null)
          }
        } catch {
          /* ignore */
        }
      }
      ws.onclose = () => {
        if (stopped) return
        setLive(false)
        retry = window.setTimeout(connect, 2000)
      }
      ws.onerror = () => ws.close()
    }

    void load()
    connect()
    const poll = window.setInterval(() => { void load() }, POLL_MS)

    return () => {
      stopped = true
      window.clearInterval(poll)
      if (retry) window.clearTimeout(retry)
      wsRef.current?.close()
    }
  }, [])

  return { data, error, live, now }
}
