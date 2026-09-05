import { useEffect, useState } from 'react'
import { fetchAuto, fetchRoundErrors, fetchRounds, setAuto, startRound } from '../api'
import type { FlAuto, FlErrors, FlRound } from '../types'
import { ErrorPanel } from './ErrorPanel'
import { ViewNav } from './ViewNav'

const POLL_MS = 2500
const ERR_POLL_MS = 30000
const EXPECTED = [1, 2]

/** Le tampon d'un nœud (32 échantillons × 15 s) se renouvelle en 8 min :
 *  en dessous, deux rounds consécutifs réapprennent les mêmes données. */
const INTERVALS = [
  { s: 180, label: '3 min' },
  { s: 300, label: '5 min' },
  { s: 480, label: '8 min' },
]

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
  const [errors, setErrors] = useState<FlErrors | null>(null)
  const [auto, setAutoState] = useState<FlAuto | null>(null)
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
        const [list, autoState] = await Promise.all([fetchRounds(), fetchAuto()])
        if (!stopped) {
          setRounds(list)
          setAutoState(autoState)
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

  // Le RMSE dépend des lectures qui arrivent après la clôture : il bouge
  // lentement, un rafraîchissement au rythme des rounds suffit.
  useEffect(() => {
    let stopped = false
    const load = async () => {
      try {
        const data = await fetchRoundErrors()
        if (!stopped) setErrors(data)
      } catch {
        /* la vue reste utilisable sans les erreurs de prédiction */
      }
    }
    void load()
    const poll = window.setInterval(() => { void load() }, ERR_POLL_MS)
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

  const onAuto = async (enabled: boolean, intervalS?: number) => {
    try {
      setAutoState(await setAuto(enabled, intervalS))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'auto')
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

        {auto && (
          <div className="auto-bar">
            <button
              type="button"
              className={`btn-auto ${auto.enabled ? 'on' : ''}`}
              onClick={() => { void onAuto(!auto.enabled, auto.interval_s) }}
            >
              {auto.enabled ? 'Arrêter la série' : 'Lancer en série'}
            </button>

            <label className="auto-interval">
              Toutes les
              <select
                value={auto.interval_s}
                onChange={(e) => { void onAuto(auto.enabled, Number(e.target.value)) }}
              >
                {INTERVALS.map((i) => (
                  <option key={i.s} value={i.s}>{i.label}</option>
                ))}
              </select>
            </label>

            <p className="sub auto-state">
              {auto.enabled
                ? `${auto.rounds_started} round${auto.rounds_started > 1 ? 's' : ''} lancé${auto.rounds_started > 1 ? 's' : ''}` +
                  (auto.next_in_s != null ? ` · prochain dans ${auto.next_in_s} s` : '')
                : 'Série à l’arrêt. Le serveur enchaîne les rounds même navigateur fermé.'}
            </p>

            {auto.last_error && <p className="sub auto-err">Dernière erreur : {auto.last_error}</p>}
          </div>
        )}

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

      <ErrorPanel data={errors} />

      <footer>
        FedAvg : w = Σ (n_k / n) w^(k) · LoRa 433 MHz SF7 · token ingest hors navigateur
      </footer>
    </div>
  )
}
