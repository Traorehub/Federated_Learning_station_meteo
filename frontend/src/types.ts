export type NodeStats = {
  node_id: number
  last_seq: number | null
  last_seen_at: string | null
  last_rssi: number | null
  last_snr: number | null
  last_temperature: number | null
  last_humidity: number | null
  packets_received: number
  packets_missing: number
  packets_corrupt: number
  loss_rate: number | null
}

export type Reading = {
  id: number
  node_id: number
  seq: number
  temperature: number | null
  humidity: number | null
  rssi: number | null
  snr: number | null
  uptime_s: number | null
  checksum_ok: boolean
  error?: string | null
  received_at: string
  packets_received?: number
  packets_missing?: number
  packets_corrupt?: number
  loss_rate?: number | null
}

export type Overview = {
  stage: string
  nodes: NodeStats[]
  readings: Reading[]
}
