import { useEffect, useState } from 'react'
import { fetchLatency, fetchLinkHistory } from '../api'
import { nodeColor } from '../nodeColor'
import type { LatencyHistory, LinkHistory, RoundLatency } from '../types'
import { ViewNav } from './ViewNav'

const POLL_MS = 20000
const FENETRES = [
  { hours: 1, bucket: 2, label: '1 h' },
  { hours: 3, bucket: 5, label: '3 h' },
  { hours: 12, bucket: 15, label: '12 h' },
  { hours: 24, bucket: 30, label: '24 h' },
]

const PAD = { top: 14, right: 14, bottom: 28, left: 46 }
const BOX = { w: 760, h: 210 }

type Point = { x: number; y: number; nul?: boolean }
type Serie = { nodeId: number; points: Point[] }

function heure(iso: string): string {
  return new Date(iso).toLocaleTimeString('fr-FR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function Chart({
  series,
  instants,
  min,
  max,
  format,
}: {
  series: Serie[]
  instants: string[]
  min: number
  max: number
  format: (v: number) => string
}) {
  const innerH = BOX.h - PAD.top - PAD.bottom
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    value: min + (max - min) * f,
    y: PAD.top + innerH * (1 - f),
  }))
  const pasX = Math.max(1, Math.ceil(instants.length / 8))

  return (
    <svg className="net-chart" viewBox={`0 0 ${BOX.w} ${BOX.h}`} role="img">
      {ticks.map((t) => (
        <g key={t.y}>
          <line x1={PAD.left} y1={t.y} x2={BOX.w - PAD.right} y2={t.y} className="err-grid" />
          <text x={PAD.left - 8} y={t.y + 4} className="err-axis" textAnchor="end">
            {format(t.value)}
          </text>
        </g>
      ))}

      {series.map((s) => (
        <g key={s.nodeId}>
          <polyline
            className="err-line"
            stroke={nodeColor(s.nodeId)}
            points={s.points.map((p) => `${p.x},${p.y}`).join(' ')}
          />
          {/* Un creux à zéro est le signal, pas un trou de données : on le marque. */}
          {s.points
            .filter((p) => p.nul)
            .map((p, i) => (
              <circle key={i} cx={p.x} cy={p.y} r={3.5} fill={nodeColor(s.nodeId)} />
            ))}
        </g>
      ))}

      {instants.map((t, i) => {
        if (i % pasX !== 0) return null
        const innerW = BOX.w - PAD.left - PAD.right
        const x = PAD.left + (instants.length > 1 ? (i * innerW) / (instants.length - 1) : 0)
        return (
          <text key={t} x={x} y={BOX.h - 9} className="err-axis" textAnchor="middle">
            {heure(t)}
          </text>
        )
      })}
    </svg>
  )
}

function buildSeries(
  data: LinkHistory,
  valeur: (b: LinkHistory['nodes'][0]['buckets'][0]) => number | null,
  min: number,
  max: number,
): Serie[] {
  const innerW = BOX.w - PAD.left - PAD.right
  const innerH = BOX.h - PAD.top - PAD.bottom
  const n = data.nodes[0]?.buckets.length ?? 0

  return data.nodes.map((node) => ({
    nodeId: node.node_id,
    points: node.buckets.flatMap((b, i) => {
      const v = valeur(b)
      if (v == null) return []
      const borne = Math.min(max, Math.max(min, v))
      return [
        {
          x: PAD.left + (n > 1 ? (i * innerW) / (n - 1) : 0),
          y: PAD.top + innerH * (1 - (borne - min) / (max - min)),
          nul: b.recus === 0,
        },
      ]
    }),
  }))
}

function Legende({ nodes }: { nodes: number[] }) {
  return (
    <p className="err-legend">
      {nodes.map((id) => (
        <span key={id} className="err-key">
          <i className="dot" style={{ background: nodeColor(id), borderColor: nodeColor(id) }} />
          Nœud {id}
        </span>
      ))}
    </p>
  )
}

function LatencyTable({ rounds }: { rounds: RoundLatency[] }) {
  const derniers = rounds.slice(-14).reverse()
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Round</th>
            <th>Nœud</th>
            <th>Délai de réponse</th>
            <th>Dans la fenêtre</th>
          </tr>
        </thead>
        <tbody>
          {derniers.length === 0 && (
            <tr>
              <td colSpan={4} className="empty">Aucun round clos à mesurer.</td>
            </tr>
          )}
          {derniers.flatMap((r) =>
            r.nodes.map((n) => (
              <tr key={`${r.round_id}-${n.node_id}`} className={n.dans_les_temps ? '' : 'bad'}>
                <td>{r.round_id}</td>
                <td>
                  <span className="err-dot" style={{ background: nodeColor(n.node_id) }} />
                  {n.node_id}
                </td>
                <td>{n.latence_s.toFixed(1)} s</td>
                <td>{n.dans_les_temps ? 'oui' : `non (timeout ${r.timeout_s} s)`}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </div>
  )
}

export function NetworkView() {
  const [fenetre, setFenetre] = useState(FENETRES[1])
  const [data, setData] = useState<LinkHistory | null>(null)
  const [latence, setLatence] = useState<LatencyHistory | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let stopped = false
    const load = async () => {
      try {
        const [h, l] = await Promise.all([
          fetchLinkHistory(fenetre.hours, fenetre.bucket),
          fetchLatency(),
        ])
        if (!stopped) {
          setData(h)
          setLatence(l)
          setError(null)
        }
      } catch (err) {
        if (!stopped) setError(err instanceof Error ? err.message : 'réseau')
      }
    }
    void load()
    const poll = window.setInterval(() => { void load() }, POLL_MS)
    return () => {
      stopped = true
      window.clearInterval(poll)
    }
  }, [fenetre])

  const instants = data?.nodes[0]?.buckets.map((b) => b.t) ?? []
  const nodeIds = data?.nodes.map((n) => n.node_id) ?? []

  const rssiValues = (data?.nodes ?? []).flatMap((n) =>
    n.buckets.map((b) => b.rssi_avg).filter((v): v is number => v != null),
  )
  const rssiMin = rssiValues.length ? Math.floor(Math.min(...rssiValues) / 10) * 10 - 5 : -120
  const rssiMax = rssiValues.length ? Math.ceil(Math.max(...rssiValues) / 10) * 10 : -30

  return (
    <div className="app">
      <header className="top">
        <div>
          <p className="kicker">Dashboard v4</p>
          <h1>Liaison dans le temps</h1>
          <p className="sub">
            Taux de réception, niveau reçu et délai de réponse aux rounds.
          </p>
        </div>
        <div className="status">
          <ViewNav current="reseau" />
          <span className="host">federated.near-u-api.org</span>
        </div>
      </header>

      {error && <p className="banner">Backend injoignable ({error})</p>}

      <div className="auto-bar">
        <span className="auto-interval">Fenêtre</span>
        {FENETRES.map((f) => (
          <button
            key={f.hours}
            type="button"
            className={`btn-auto ${f.hours === fenetre.hours ? 'on' : ''}`}
            onClick={() => setFenetre(f)}
          >
            {f.label}
          </button>
        ))}
        {data && (
          <p className="sub auto-state">
            Tranches de {data.bucket_min} min · un nœud émet toutes les {data.sample_period_s} s
          </p>
        )}
      </div>

      <section className="log">
        <header>
          <h2>Taux de réception</h2>
          <p>
            Part des paquets attendus qui parviennent réellement au serveur. C’est cette
            grandeur — et non le niveau reçu — qui prédit qu’un nœud manquera un round.
          </p>
        </header>
        <div className="net-chart-wrap">
          {data && (
            <Chart
              series={buildSeries(data, (b) => b.reception, 0, 1)}
              instants={instants}
              min={0}
              max={1}
              format={(v) => `${Math.round(v * 100)} %`}
            />
          )}
          <Legende nodes={nodeIds} />
          <p className="sub">
            Un point marqué sur la ligne signale une tranche <strong>totalement muette</strong>.
            Le silence est une mesure, pas une absence de donnée.
          </p>
        </div>
      </section>

      <section className="log">
        <header>
          <h2>Niveau reçu (RSSI)</h2>
          <p>
            À comparer avec la courbe précédente : le niveau moyen reste stable quand la
            réception s’effondre, parce qu’il n’est mesuré que sur les paquets arrivés.
          </p>
        </header>
        <div className="net-chart-wrap">
          {data && (
            <Chart
              series={buildSeries(data, (b) => b.rssi_avg, rssiMin, rssiMax)}
              instants={instants}
              min={rssiMin}
              max={rssiMax}
              format={(v) => `${Math.round(v)}`}
            />
          )}
          <Legende nodes={nodeIds} />
          <p className="sub">
            Biais du survivant : quand un lien lâche, il n’arrive pas de paquet faible, il
            n’arrive rien. La courbe s’interrompt au lieu de descendre.
          </p>
        </div>
      </section>

      <section className="log">
        <header>
          <h2>Délai de réponse aux rounds</h2>
          <p>
            Temps entre l’ouverture d’un round et l’arrivée des poids d’un nœud. Au-delà du
            timeout, les poids sont enregistrés mais restent hors de la moyenne.
          </p>
        </header>
        <LatencyTable rounds={latence?.rounds ?? []} />
      </section>

      <footer>
        433 MHz · SF7 · BW 125 kHz · CR 4/5 · réception mesurée sur <code>readings</code>
      </footer>
    </div>
  )
}
