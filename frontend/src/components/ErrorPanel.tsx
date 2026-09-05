import type { FlErrors, FlNodeErrorSummary, FlRoundError } from '../types'

/** Témoin en tungstène, nœud distant en braise : même code que les cartes radio. */
const NODE_COLOR: Record<number, string> = { 1: '#e8b45a', 2: '#c45c3e' }

const PAD = { top: 16, right: 14, bottom: 34, left: 48 }
const BOX = { w: 720, h: 250 }

function color(nodeId: number): string {
  return NODE_COLOR[nodeId] ?? '#a89880'
}

function fmt(v: number | null | undefined, digits = 3): string {
  return v == null ? '-' : v.toFixed(digits)
}

function niceMax(values: number[]): number {
  const max = Math.max(...values, 0.1)
  const step = max > 2 ? 0.5 : max > 0.5 ? 0.25 : 0.1
  return Math.ceil(max / step) * step
}

type Serie = { nodeId: number; points: { x: number; y: number; participated: boolean }[] }

function buildSeries(rounds: FlRoundError[], max: number): Serie[] {
  const innerW = BOX.w - PAD.left - PAD.right
  const innerH = BOX.h - PAD.top - PAD.bottom
  const stepX = rounds.length > 1 ? innerW / (rounds.length - 1) : 0
  const nodeIds = [...new Set(rounds.flatMap((r) => r.nodes.map((n) => n.node_id)))].sort()

  return nodeIds.map((nodeId) => ({
    nodeId,
    points: rounds.flatMap((r, i) => {
      const entry = r.nodes.find((n) => n.node_id === nodeId)
      if (!entry || entry.rmse_global == null) return []
      return [
        {
          x: PAD.left + (rounds.length > 1 ? i * stepX : innerW / 2),
          y: PAD.top + innerH * (1 - entry.rmse_global / max),
          participated: entry.participated,
        },
      ]
    }),
  }))
}

function Chart({ rounds }: { rounds: FlRoundError[] }) {
  const all = rounds.flatMap((r) =>
    r.nodes.map((n) => n.rmse_global).filter((v): v is number => v != null),
  )
  if (all.length === 0) return null

  const max = niceMax(all)
  const series = buildSeries(rounds, max)
  const innerH = BOX.h - PAD.top - PAD.bottom
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => ({
    value: max * f,
    y: PAD.top + innerH * (1 - f),
  }))

  return (
    <svg className="err-chart" viewBox={`0 0 ${BOX.w} ${BOX.h}`} role="img"
      aria-label="RMSE du modèle global par round et par nœud">
      {ticks.map((t) => (
        <g key={t.y}>
          <line x1={PAD.left} y1={t.y} x2={BOX.w - PAD.right} y2={t.y} className="err-grid" />
          <text x={PAD.left - 8} y={t.y + 4} className="err-axis" textAnchor="end">
            {t.value.toFixed(2)}
          </text>
        </g>
      ))}

      {series.map((s) => (
        <g key={s.nodeId}>
          {s.points.length > 1 && (
            <polyline
              className="err-line"
              stroke={color(s.nodeId)}
              points={s.points.map((p) => `${p.x},${p.y}`).join(' ')}
            />
          )}
          {s.points.map((p, i) =>
            p.participated ? (
              <circle key={i} cx={p.x} cy={p.y} r={4} fill={color(s.nodeId)} />
            ) : (
              /* creux = le nœud n'était pas dans la moyenne de ce round */
              <rect
                key={i}
                x={p.x - 4}
                y={p.y - 4}
                width={8}
                height={8}
                fill="var(--bg-2)"
                stroke={color(s.nodeId)}
                strokeWidth={2}
              />
            ),
          )}
        </g>
      ))}

      {rounds.map((r, i) => {
        const innerW = BOX.w - PAD.left - PAD.right
        const x = PAD.left + (rounds.length > 1 ? (i * innerW) / (rounds.length - 1) : innerW / 2)
        const every = Math.ceil(rounds.length / 12)
        if (i % every !== 0) return null
        return (
          <text key={r.round_id} x={x} y={BOX.h - 12} className="err-axis" textAnchor="middle">
            {r.round_id}
          </text>
        )
      })}
    </svg>
  )
}

function SummaryTable({ nodes }: { nodes: FlNodeErrorSummary[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Nœud</th>
            <th>Persistance</th>
            <th>Son modèle local</th>
            <th>Global s’il a participé</th>
            <th>Global s’il était absent</th>
            <th>Pénalité</th>
          </tr>
        </thead>
        <tbody>
          {nodes.length === 0 && (
            <tr>
              <td colSpan={6} className="empty">
                Pas encore assez de lectures après clôture pour évaluer un round.
              </td>
            </tr>
          )}
          {nodes.map((n) => (
            <tr key={n.node_id}>
              <td>
                <span className="err-dot" style={{ background: color(n.node_id) }} />
                {n.node_id}
              </td>
              <td>{fmt(n.rmse_persistence)}</td>
              <td>{fmt(n.rmse_local)}</td>
              <td>
                {fmt(n.rmse_global_present)}
                <span className="err-n"> · {n.rounds_present} rounds</span>
              </td>
              <td>
                {fmt(n.rmse_global_absent)}
                <span className="err-n"> · {n.rounds_absent} rounds</span>
              </td>
              <td>{n.penalty == null ? '-' : `×${n.penalty.toFixed(1)}`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ErrorPanel({ data }: { data: FlErrors | null }) {
  if (!data) return null

  return (
    <section className="log err-panel">
      <header>
        <h2>Erreur du modèle</h2>
        <p>
          RMSE en °C, mesuré sur les lectures des {data.horizon_min} min qui suivent la clôture,
          donc hors échantillon d’entraînement. La persistance (prédire « même température
          qu’au pas précédent ») sert de référence : un RMSE seul ne dit pas si le modèle appris
          apporte quelque chose.
        </p>
      </header>

      <SummaryTable nodes={data.nodes} />

      <div className="err-chart-wrap">
        <p className="kicker">Modèle global, par round</p>
        <Chart rounds={data.rounds} />
        <p className="err-legend">
          <span className="err-key"><i className="dot" /> le nœud a été agrégé dans ce round</span>
          <span className="err-key"><i className="sq" /> le nœud était absent : il reçoit le modèle de l’autre</span>
        </p>
        <p className="sub">
          Un point haut signifie un modèle qui prédit mal <em>pour ce nœud-là</em>. Les marqueurs
          creux mesurent le coût d’un timeout LoRa sur la qualité du modèle redescendu.
        </p>
      </div>
    </section>
  )
}
