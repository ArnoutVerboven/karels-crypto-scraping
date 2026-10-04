import { useEffect, useRef, useState } from 'react'
import { CRYPTOS, formatDate } from '@/data/clues'
import type { Attempt } from '@/game/types'
import { signOut, type AuthUser } from '@/services/auth'
import type { Attempts, AttemptStore } from '@/services/store'
import type { Layout } from './Keyboard'

const OUTCOME_LABEL = { solved: 'Solved', failed: 'Failed', skipped: 'Skipped' } as const

function shortDate(iso: string): string {
  const d = formatDate(iso.slice(0, 10))
  return iso.slice(0, 4) === String(new Date().getFullYear()) ? d.replace(/ \d{4}$/, '') : d
}
function seconds(ms: number): string {
  const s = Math.round(ms / 1000)
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`
}
function meta(a: Attempt | undefined, length: number): string {
  if (!a) return `${length} letters`
  const parts = [`${OUTCOME_LABEL[a.outcome]} ${shortDate(a.finishedAt)}`]
  if (a.outcome !== 'skipped') {
    parts.push(seconds(a.activeMs))
    parts.push(`${a.lettersNeeded}/${a.length} letters guessed`)
  } else if (a.skipReason === 'crypto') parts.push('with crypto')
  return parts.join(' · ')
}

export function Menu({
  attempts,
  currentId,
  store,
  user,
  layout,
  onLayout,
  onPick,
  onClose,
}: {
  attempts: Attempts
  currentId: string | null
  store: AttemptStore
  user: AuthUser | null
  layout: Layout
  onLayout: (l: Layout) => void
  onPick: (clueId: string) => void
  onClose: () => void
}) {
  const currentCrypto = CRYPTOS.find((c) => c.clues.some((cl) => cl.id === currentId))?.id ?? null
  const [open, setOpen] = useState<number | null>(currentCrypto)
  const openRef = useRef<HTMLDivElement>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    openRef.current?.scrollIntoView({ block: 'start' })
  }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const all = Object.values(attempts)
  const count = (o: Attempt['outcome']) => all.filter((a) => a.outcome === o).length
  const total = CRYPTOS.reduce((s, c) => s + c.clues.length, 0)

  const exportJson = () => JSON.stringify({ exportedAt: new Date().toISOString(), attempts: all }, null, 1)
  const download = () => {
    const url = URL.createObjectURL(new Blob([exportJson()], { type: 'application/json' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `karels-crypto-benchmark-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const copy = () => {
    navigator.clipboard
      ?.writeText(exportJson())
      .then(() => {
        setCopied(true)
        setTimeout(() => setCopied(false), 1500)
      })
      .catch(() => {})
  }

  return (
    <>
      <div className="scrim" onClick={onClose} />
      <aside className="sheet" aria-label="Cryptos">
        <div className="sheet-head">
          <h2>Karel's Crypto</h2>
          <button className="icon-btn" aria-label="Close" onClick={onClose}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <path d="M6 6l12 12M18 6 6 18" />
            </svg>
          </button>
        </div>
        <div className="stats">
          {(['solved', 'failed', 'skipped'] as const).map((o) => (
            <div className="stat" key={o}>
              <span>{count(o)}</span>
              <span>
                <i className={`dot ${o}`} />
                {OUTCOME_LABEL[o]}
              </span>
            </div>
          ))}
          <div className="stat">
            <span>{total - CRYPTOS.reduce((s, c) => s + c.clues.filter((cl) => attempts[cl.id]).length, 0)}</span>
            <span>
              <i className="dot" />
              To go
            </span>
          </div>
        </div>

        <div className="list">
          {CRYPTOS.map((c) => {
            const done = c.clues.filter((cl) => attempts[cl.id]).length
            const isOpen = open === c.id
            return (
              <div className="crypto" key={c.id} ref={c.id === currentCrypto ? openRef : undefined}>
                <button className="crypto-row" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : c.id)}>
                  <span className="crypto-title">
                    Crypto {c.no}
                    <span className="crypto-date">{formatDate(c.date)}</span>
                    {c.yellow && <span className="crypto-yellow">{c.yellow}</span>}
                  </span>
                  <span className="crypto-count">
                    {done}/{c.clues.length}
                  </span>
                  <span className="strip" aria-hidden="true">
                    {c.clues.map((cl) => (
                      <i key={cl.id} className={`dot ${attempts[cl.id]?.outcome ?? (cl.id === currentId ? 'current' : '')}`} />
                    ))}
                  </span>
                </button>
                {isOpen &&
                  c.clues.map((cl) => {
                    const a = attempts[cl.id]
                    const final = a && a.outcome !== 'skipped'
                    const letters = cl.answer.replace(/[^\p{L}]/gu, '').length
                    return (
                      <button
                        key={cl.id}
                        className={`clue-row ${cl.id === currentId ? 'is-current' : ''}`}
                        disabled={final || cl.id === currentId}
                        onClick={() => onPick(cl.id)}
                      >
                        <span className={`letter ${a?.outcome ?? ''}`}>{cl.letter}</span>
                        <span>
                          <div className="clue-text">{cl.text}</div>
                          <div className="clue-meta">
                            {cl.id === currentId ? 'Now playing · ' : ''}
                            {meta(a, letters)}
                            {a?.outcome === 'skipped' ? ' · tap to play' : ''}
                          </div>
                        </span>
                      </button>
                    )
                  })}
              </div>
            )
          })}
        </div>

        <div className="sheet-foot">
          <div className="who">
            {store.kind === 'cloud' ? `Signed in as ${user?.email ?? 'you'}` : 'Saved on this device only'}
          </div>
          <button className="link" onClick={() => onLayout(layout === 'qwerty' ? 'azerty' : 'qwerty')}>
            Keyboard: {layout.toUpperCase()}
          </button>
          <button className="link" onClick={download}>
            Download data
          </button>
          <button className="link" onClick={copy}>
            {copied ? 'Copied' : 'Copy data'}
          </button>
          {store.kind === 'cloud' && (
            <button className="link" onClick={() => void signOut()}>
              Sign out
            </button>
          )}
        </div>
      </aside>
    </>
  )
}
