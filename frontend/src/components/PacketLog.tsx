import type { Reading } from '../types'

function fmtTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('fr-FR', { hour12: false })
}

function nodeLabel(id: number): string {
  return id === 0 ? 'indét.' : String(id)
}

function okLabel(r: Reading): string {
  if (r.checksum_ok) return 'oui'
  if (r.error === 'bad_header') return 'bad_header'
  return 'non'
}

type Props = {
  readings: Reading[]
  badHeaderCount: number
}

export function PacketLog({ readings, badHeaderCount }: Props) {
  return (
    <section className="log">
      <header>
        <h2>Paquets reçus</h2>
        <p>
          Flux brut gateway → backend, plus récent en haut.
          Illisibles (bad_header, nœud inconnu) : {badHeaderCount}
        </p>
      </header>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Heure</th>
              <th>Nœud</th>
              <th>Seq</th>
              <th>T °C</th>
              <th>H %</th>
              <th>RSSI</th>
              <th>SNR</th>
              <th>OK</th>
            </tr>
          </thead>
          <tbody>
            {readings.length === 0 && (
              <tr>
                <td colSpan={8} className="empty">
                  En attente du premier paquet (agent série ou simulateur)
                </td>
              </tr>
            )}
            {readings.map((r) => (
              <tr key={r.id} className={r.checksum_ok ? '' : 'bad'}>
                <td>{fmtTime(r.received_at)}</td>
                <td>{nodeLabel(r.node_id)}</td>
                <td>{r.node_id === 0 ? '-' : r.seq}</td>
                <td>{r.temperature != null ? r.temperature.toFixed(1) : '-'}</td>
                <td>{r.humidity != null ? r.humidity.toFixed(1) : '-'}</td>
                <td>{r.rssi ?? '-'}</td>
                <td>{r.snr?.toFixed(2) ?? '-'}</td>
                <td>{okLabel(r)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
