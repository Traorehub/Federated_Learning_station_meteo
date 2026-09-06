import { useEffect, useState } from 'react'
import { NetworkView } from './components/NetworkView'
import { NodeCard } from './components/NodeCard'
import { PacketLog } from './components/PacketLog'
import { RoundsView } from './components/RoundsView'
import { ViewNav, type View } from './components/ViewNav'
import { useLiveData } from './hooks/useLiveData'

const PLACEHOLDERS = [{ node_id: 1 }, { node_id: 2 }] as const

function viewFromHash(hash: string): View {
  if (hash === '#rounds') return 'rounds'
  if (hash === '#reseau') return 'reseau'
  return 'radio'
}

export default function App() {
  const [view, setView] = useState<View>(() => viewFromHash(window.location.hash))

  useEffect(() => {
    const onHash = () => setView(viewFromHash(window.location.hash))
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  if (view === 'rounds') return <RoundsView />
  if (view === 'reseau') return <NetworkView />

  return <RadioView />
}

function RadioView() {
  const { data, error, live, now } = useLiveData()
  const known = data?.nodes ?? []
  const cards = PLACEHOLDERS.map((ph) => known.find((n) => n.node_id === ph.node_id) ?? {
    node_id: ph.node_id,
    last_seq: null,
    last_seen_at: null,
    last_rssi: null,
    last_snr: null,
    last_temperature: null,
    last_humidity: null,
    packets_received: 0,
    packets_missing: 0,
    packets_corrupt: 0,
    loss_rate: null,
  })
  const extras = known.filter((n) => n.node_id > 2)
  const badHeaderCount = known.find((n) => n.node_id === 0)?.packets_corrupt ?? 0

  return (
    <div className="app">
      <header className="top">
        <div>
          <p className="kicker">POC · 2 nœuds · Dashboard v1</p>
          <h1>Liaison LoRa brute</h1>
          <p className="sub">
            ESP32 → RA-02 → gateway Arduino → série → VPS · pas d’entraînement
          </p>
        </div>
        <div className="status">
          <ViewNav current="radio" />
          <span className={`pill ${live ? 'ok' : 'warn'}`}>
            <i />
            {live ? 'live' : 'polling'}
          </span>
          <span className="host">federated.near-u-api.org</span>
        </div>
      </header>

      {error && <p className="banner">Backend injoignable ({error})</p>}

      <section className="grid">
        {cards.map((n) => (
          <NodeCard key={n.node_id} node={n} now={now} />
        ))}
        {extras.map((n) => (
          <NodeCard key={n.node_id} node={n} now={now} />
        ))}
      </section>

      <PacketLog readings={data?.readings ?? []} badHeaderCount={badHeaderCount} />

      <footer>
        Radio POC : 433 MHz · SF7 · BW 125 kHz · CR 4/5 · table unique <code>readings</code> + <code>node_id</code>
      </footer>
    </div>
  )
}
