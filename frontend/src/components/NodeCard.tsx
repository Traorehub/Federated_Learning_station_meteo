import type { NodeStats } from '../types'

function ageSeconds(iso: string | null, now: number): number | null {
  if (!iso) return null
  return Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000))
}

function linkState(age: number | null): { label: string; className: string } {
  if (age === null) return { label: 'jamais vu', className: 'off' }
  if (age <= 30) return { label: 'en ligne', className: 'ok' }
  if (age <= 90) return { label: 'faible', className: 'warn' }
  return { label: 'hors ligne', className: 'off' }
}

function rssiQuality(rssi: number | null): string {
  if (rssi === null) return '-'
  if (rssi >= -70) return 'excellent'
  if (rssi >= -90) return 'bon'
  if (rssi >= -110) return 'faible'
  return 'critique'
}

function fmtAge(age: number | null): string {
  if (age === null) return 'aucun message'
  if (age < 5) return 'à l’instant'
  return `il y a ${age} s`
}

function pct(rate: number | null): string {
  if (rate === null) return '-'
  return `${(rate * 100).toFixed(1)} %`
}

type Props = { node: NodeStats; now: number }

export function NodeCard({ node, now }: Props) {
  const age = ageSeconds(node.last_seen_at, now)
  const state = linkState(age)

  return (
    <article className={`node-card ${state.className}`}>
      <header>
        <div>
          <p className="kicker">Nœud ESP32</p>
          <h2>Nœud {node.node_id}</h2>
        </div>
        <span className={`pill ${state.className}`}>
          <i />
          {state.label}
        </span>
      </header>

      <p className="age">{fmtAge(age)}</p>

      <div className="metrics">
        <div>
          <span>Température</span>
          <strong>{node.last_temperature?.toFixed(1) ?? '-'}<small>°C</small></strong>
        </div>
        <div>
          <span>Humidité</span>
          <strong>{node.last_humidity?.toFixed(1) ?? '-'}<small>%</small></strong>
        </div>
        <div>
          <span>RSSI</span>
          <strong>{node.last_rssi ?? '-'}<small>dBm</small></strong>
        </div>
        <div>
          <span>SNR</span>
          <strong>{node.last_snr?.toFixed(2) ?? '-'}<small>dB</small></strong>
        </div>
      </div>

      <dl className="meta">
        <div>
          <dt>Séquence</dt>
          <dd>{node.last_seq ?? '-'}</dd>
        </div>
        <div>
          <dt>Reçus</dt>
          <dd>{node.packets_received}</dd>
        </div>
        <div>
          <dt>Manquants</dt>
          <dd>{node.packets_missing}</dd>
        </div>
        <div>
          <dt>Perte</dt>
          <dd>{pct(node.loss_rate)}</dd>
        </div>
        <div>
          <dt>Corrompus</dt>
          <dd>{node.packets_corrupt}</dd>
        </div>
        <div>
          <dt>Lien</dt>
          <dd>{rssiQuality(node.last_rssi)}</dd>
        </div>
      </dl>
    </article>
  )
}
