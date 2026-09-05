import { useEffect, useState } from 'react'
import { fetchRounds, startRound } from '../api'
import type { FlRound } from '../types'
import { ViewNav } from './ViewNav'

const POLL_MS = 2500
const EXPECTED = [1, 2]

function fmtW(w: number[] | null | undefined): string {
  if (!w || w.length < 4) return '-'
  return w.map((x) => x.toFixed(4)).join('  ')
}

function fmtTime(iso: string | null): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleTimeString('fr-FR', { hour12: false })
}

function remaining(round: FlRound, now: number): string {
  if (round.status !== 'open') return 'clos'
  const start = new Date(round.started_at).getTime()
  const timeout = round.timeout_s ?? 90
  if (!Number.isFinite(start)) return 'ouvert'
  const left = Math.max(0, Math.round(timeout - (now - start) / 1000))
  return `${left} s`
}

function participantsOf(round: FlRound): FlRound['participants'] {
  return round.participants ?? []
}

export function RoundsView() {
  const [rounds, setRounds] = useState<FlRound[]>([])
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const tick = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(tick)
  }, [])

  useEffect(() => {
    let stopped = false
    const load = async () => {
      try {
        const list = await fetchRounds()
        if (!stopped) {
          setRounds(list)
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
  }, [])

  const openRound = rounds.find((r) => r.status === 'open') ?? null

  const onStart = async () => {
    if (busy || openRound) return
    setBusy(true)
    try {
      const row = await startRound()
      const list = await fetchRounds()
      setRounds(list.length ? list : [{ ...row, participants: row.participants ?? [] }])
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'start')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <header className="top">
        <div>
          <p className="kicker">POC · Dashboard v3</p>
          <h1>Rounds FedAvg</h1>
          <p className="sub">
            Moyenne pondérée par n_samples. Un nœud absent n’entre pas dans la somme.
            Vue radio inchangée (Liaison).
          </p>
        </div>
        <div className="status">
          <ViewNav current="rounds" />
          <span className="host">federated.near-u-api.org</span>
        </div>
      </header>

      {error && <p className="banner">Backend injoignable ({error})</p>}

      <section className="round-panel">
        <div className="round-actions">
          <button
            type="button"
            className="btn-round"
            disabled={busy || openRound !== null}
            onClick={() => { void onStart() }}
          >
            {openRound ? `Round ${openRound.id} ouvert` : 'Démarrer un round'}
          </button>
          {openRound && (
            <p className="sub">
              Timeout {remaining(openRound, now)} · en attente des nœuds 1 et 2
            </p>
          )}
        </div>

        {openRound && (
          <div className="grid">
            {EXPECTED.map((id) => {
              const p = participantsOf(openRound).find((x) => x.node_id === id)
              return (
                <article key={id} className={`node-card ${p ? 'ok' : 'off'}`}>
                  <header>
                    <div>
                      <p className="kicker">Participant</p>
                      <h2>Nœud {id}</h2>
                    </div>
                    <span className={`pill ${p ? 'ok' : 'warn'}`}>
                      <i />
                      {p ? 'update reçue' : 'en attente'}
                    </span>
                  </header>
                  <p className="age">{p ? `${p.n_samples} échantillons` : 'pas encore de poids pour ce round'}</p>
                  <p className="w-vec">{fmtW(p?.w)}</p>
                </article>
              )
            })}
          </div>
        )}
      </section>

      <section className="log">
        <header>
          <h2>Historique des rounds</h2>
          <p>Le plus récent en haut. Clos dès que 2 nœuds ont envoyé, ou au timeout.</p>
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Round</th>
                <th>État</th>
                <th>Début</th>
                <th>Nœuds</th>
                <th>n total</th>
                <th>w global</th>
              </tr>
            </thead>
            <tbody>
              {rounds.length === 0 && (
                <tr>
                  <td colSpan={6} className="empty">
                    Aucun round. Le bouton ci-dessus enfile un start_round vers l’agent.
                  </td>
                </tr>
              )}
              {rounds.map((r) => {
                const parts = participantsOf(r)
                return (
                <tr key={r.id}>
                  <td>{r.id}</td>
                  <td>{r.status === 'open' ? `ouvert (${remaining(r, now)})` : 'clos'}</td>
                  <td>{fmtTime(r.started_at)}</td>
                  <td>
                    {parts.length
                      ? parts.map((p) => p.node_id).join(', ')
                      : '-'}
                    {r.n_nodes != null ? ` (${r.n_nodes})` : ''}
                  </td>
                  <td>{r.n_total ?? '-'}</td>
                  <td className="w-cell">{fmtW(r.w)}</td>
                </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>

      <footer>
        FedAvg : w = Σ (n_k / n) w^(k) · LoRa 433 MHz SF7 · token ingest hors navigateur
      </footer>
    </div>
  )
}
