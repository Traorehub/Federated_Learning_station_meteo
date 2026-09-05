type View = 'radio' | 'rounds'

type Props = { current: View }

export function ViewNav({ current }: Props) {
  return (
    <nav className="view-nav">
      <a href="#radio" className={current === 'radio' ? 'active' : ''}>
        Liaison
      </a>
      <a href="#rounds" className={current === 'rounds' ? 'active' : ''}>
        Rounds FedAvg
      </a>
    </nav>
  )
}
