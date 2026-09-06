export type View = 'radio' | 'rounds' | 'reseau'

type Props = { current: View }

const VUES: { id: View; hash: string; label: string }[] = [
  { id: 'radio', hash: '#radio', label: 'Liaison' },
  { id: 'rounds', hash: '#rounds', label: 'Rounds FedAvg' },
  { id: 'reseau', hash: '#reseau', label: 'Réseau' },
]

export function ViewNav({ current }: Props) {
  return (
    <nav className="view-nav">
      {VUES.map((v) => (
        <a key={v.id} href={v.hash} className={current === v.id ? 'active' : ''}>
          {v.label}
        </a>
      ))}
    </nav>
  )
}
