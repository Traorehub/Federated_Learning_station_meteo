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

export type FlParticipant = {
  node_id: number
  n_samples: number
  w: number[]
  rssi: number | null
  snr: number | null
}

export type FlRound = {
  id: number
  status: string
  started_at: string
  closed_at: string | null
  timeout_s: number
  w: number[] | null
  n_total: number | null
  n_nodes: number | null
  participants?: FlParticipant[]
}

export type FlAuto = {
  enabled: boolean
  interval_s: number
  min_interval_s: number
  rounds_started: number
  last_round_at: string | null
  next_in_s: number | null
  last_error: string | null
}

/** RMSE en °C, mesuré sur les lectures postérieures à la clôture du round. */
export type FlNodeError = {
  node_id: number
  n_eval: number
  participated: boolean
  rmse_persistence: number | null
  rmse_local: number | null
  rmse_global: number | null
}

export type FlRoundError = {
  round_id: number
  closed_at: string
  n_nodes: number | null
  nodes: FlNodeError[]
}

export type FlNodeErrorSummary = {
  node_id: number
  rmse_persistence: number | null
  rmse_local: number | null
  rmse_global_present: number | null
  rmse_global_absent: number | null
  penalty: number | null
  rounds_present: number
  rounds_absent: number
}

export type FlErrors = {
  horizon_min: number
  rounds: FlRoundError[]
  nodes: FlNodeErrorSummary[]
}
