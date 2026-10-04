const LAYOUTS = {
  qwerty: ['qwertyuiop', 'asdfghjkl', 'zxcvbnm'],
  azerty: ['azertyuiop', 'qsdfghjklm', 'wxcvbn'],
} as const
export type Layout = keyof typeof LAYOUTS

/** On-screen keyboard: no native keyboard, autocorrect or composition getting in the way. */
export function Keyboard({
  layout,
  onKey,
  onBackspace,
}: {
  layout: Layout
  onKey: (k: string) => void
  onBackspace: () => void
}) {
  const rows = LAYOUTS[layout]
  return (
    <div className="keyboard" role="group" aria-label="Keyboard">
      {rows.map((row, r) => (
        <div className="krow" key={r}>
          {[...row].map((k) => (
            <button
              key={k}
              className="key"
              onPointerDown={(e) => {
                e.preventDefault()
                onKey(k)
              }}
              onClick={(e) => {
                // keyboard activation (Enter/Space) only; pointer input is handled on pointerdown
                if (e.detail === 0) onKey(k)
              }}
            >
              {k}
            </button>
          ))}
          {r === rows.length - 1 && (
            <button
              className="key wide"
              aria-label="Backspace"
              onPointerDown={(e) => {
                e.preventDefault()
                onBackspace()
              }}
              onClick={(e) => {
                if (e.detail === 0) onBackspace()
              }}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 5H9l-6 7 6 7h12a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1Z" />
                <path d="m12 9 6 6m0-6-6 6" />
              </svg>
            </button>
          )}
        </div>
      ))}
    </div>
  )
}
