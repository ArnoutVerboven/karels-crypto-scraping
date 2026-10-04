import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { ALL_CLUES, CLUE_BY_ID, formatDate, type ClueRef } from '@/data/clues'
import { skippedUnseen, toAttempt } from '@/game/attempt'
import { nextOpenClue } from '@/game/order'
import { newWord, randomSeed, revealOrderFor, step, type Action, type WordState } from '@/game/word'
import type { AuthUser } from '@/services/auth'
import {
  clearLocalAttempts,
  loadDraft,
  localAttempts,
  saveDraft,
  type Attempts,
  type AttemptStore,
} from '@/services/store'
import { Board } from './Board'
import { Keyboard, type Layout } from './Keyboard'
import { Menu } from './Menu'
import { Logo } from './Logo'

const FINISH_DELAY = { solved: 800, failed: 1100 } as const

function readLayout(): Layout {
  try {
    return localStorage.getItem('kcb:layout') === 'azerty' ? 'azerty' : 'qwerty'
  } catch {
    return 'qwerty'
  }
}

export function Game({ store, user }: { store: AttemptStore; user: AuthUser | null }) {
  const [attempts, setAttempts] = useState<Attempts | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  /** the clue just finished or skipped: play continues with the next open clue after it */
  const [after, setAfter] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [layout, setLayout] = useState<Layout>(readLayout)

  useEffect(() => store.subscribe(setAttempts, (e) => setError(String(e))), [store])

  // After the first cloud sign-in, upload what was played in local mode on this device.
  const uploaded = useRef(false)
  useEffect(() => {
    if (store.kind !== 'cloud' || !attempts || uploaded.current) return
    uploaded.current = true
    const missing = localAttempts().filter((a) => !attempts[a.clueId])
    if (missing.length) void store.save(missing).then(clearLocalAttempts)
  }, [store, attempts])

  const current: ClueRef | null = useMemo(() => {
    if (!attempts) return null
    if (picked) return CLUE_BY_ID.get(picked) ?? null
    return nextOpenClue(attempts, after)
  }, [attempts, picked, after])

  const [word, setWord] = useState<WordState | null>(null)
  useEffect(() => {
    if (!current) return setWord(null)
    setWord((w) => {
      if (w?.clueId === current.clue.id) return w
      const draft = loadDraft(current.clue.id)
      const now = Date.now()
      if (!draft) return newWord(current.clue.id, current.clue.answer, now)
      // drafts saved before seeds were recorded get one now
      const seed = draft.seed ?? randomSeed()
      const seeded = { ...draft, seed, revealOrder: draft.revealOrder ?? revealOrderFor(current.clue.answer, seed) }
      return step(seeded, { type: 'show' }, now)
    })
  }, [current])

  const dispatch = useCallback((a: Action) => {
    setWord((w) => (w ? step(w, a, Date.now()) : w))
  }, [])

  useEffect(() => saveDraft(word), [word])

  // Pause the clock while the app is in the background or the menu covers the clue.
  useEffect(() => {
    const onVis = () => dispatch({ type: document.visibilityState === 'hidden' ? 'hide' : 'show' })
    const onHide = () => dispatch({ type: 'hide' })
    document.addEventListener('visibilitychange', onVis)
    window.addEventListener('pagehide', onHide)
    return () => {
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('pagehide', onHide)
    }
  }, [dispatch])
  useEffect(() => {
    if (menuOpen) dispatch({ type: 'hide' })
    else if (document.visibilityState === 'visible') dispatch({ type: 'show' })
  }, [menuOpen, dispatch])

  // Finished: let the green/red blink play, then save and move to the next clue.
  useEffect(() => {
    if (!word || !current || word.status === 'playing' || word.clueId !== current.clue.id) return
    const status = word.status
    const id = setTimeout(() => {
      void store.save([toAttempt(current, word, status, Date.now())]).catch((e: unknown) => setError(String(e)))
      setAfter(current.clue.id)
      setPicked(null)
    }, FINISH_DELAY[status])
    return () => clearTimeout(id)
  }, [word, current, store])

  const skipClue = () => {
    if (!word || !current || word.status !== 'playing') return
    void store.save([toAttempt(current, word, 'skipped', Date.now(), 'clue')])
    setAfter(current.clue.id)
    setPicked(null)
  }
  const skipCrypto = () => {
    if (!word || !current || word.status !== 'playing' || !attempts) return
    const now = Date.now()
    const rest = current.crypto.clues
      .filter((c) => c.id !== current.clue.id && !attempts[c.id])
      .map((c) => skippedUnseen(CLUE_BY_ID.get(c.id)!, now))
    void store.save([toAttempt(current, word, 'skipped', now, 'crypto'), ...rest])
    setAfter(current.clue.id)
    setPicked(null)
  }

  // Physical keyboard (laptop).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (menuOpen || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'Backspace') dispatch({ type: 'backspace' })
      else if (e.key === 'ArrowLeft') dispatch({ type: 'left' })
      else if (e.key === 'ArrowRight') dispatch({ type: 'right' })
      else if (/^[a-zA-Z]$/.test(e.key)) dispatch({ type: 'key', key: e.key })
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dispatch, menuOpen])

  const changeLayout = (l: Layout) => {
    setLayout(l)
    try {
      localStorage.setItem('kcb:layout', l)
    } catch {
      /* ignore */
    }
  }

  const left = attempts ? ALL_CLUES.filter((r) => !attempts[r.clue.id]).length : 0
  const playing = word?.status === 'playing'

  return (
    <div className="app">
      <header className="topbar">
        <button className="icon-btn" aria-label="Browse cryptos" onClick={() => setMenuOpen(true)}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M4 7h16M4 12h16M4 17h10" />
          </svg>
        </button>
        <div className="where">
          {current && (
            <>
              Crypto <b>{current.crypto.no}</b> · <b>{current.clue.letter}</b>
              <span className="sr-only"> from {formatDate(current.crypto.date)}</span>
            </>
          )}
        </div>
        <div className="left">{attempts ? `${left} left` : ''}</div>
      </header>

      {!attempts ? (
        <div className="center">
          <Logo />
        </div>
      ) : !current || !word ? (
        <div className="center">
          <Logo />
          <h1>All clues done</h1>
          <p>Every clue is solved, failed or skipped. New cryptos are added each week.</p>
        </div>
      ) : (
        <>
          <main className="stage" key={current.clue.id}>
            <p className="clue">{current.clue.text}</p>
            <Board word={word} onMove={(pos) => dispatch({ type: 'move', pos })} />
            <div className="actions">
              <button className="pill" disabled={!playing} onClick={() => dispatch({ type: 'reveal' })}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
                  <circle cx="12" cy="12" r="3" />
                </svg>
                Show letter
              </button>
              <div className="skips">
                <button className="link" disabled={!playing} onClick={skipClue}>
                  Skip clue
                </button>
                <button className="link" disabled={!playing} onClick={skipCrypto}>
                  Skip crypto
                </button>
              </div>
            </div>
          </main>
          <Keyboard layout={layout} onKey={(key) => dispatch({ type: 'key', key })} onBackspace={() => dispatch({ type: 'backspace' })} />
        </>
      )}
      {error && <div className="note" style={{ textAlign: 'center', padding: 8 }}>{error}</div>}

      {menuOpen && attempts && (
        <Menu
          attempts={attempts}
          currentId={current?.clue.id ?? null}
          store={store}
          user={user}
          layout={layout}
          onLayout={changeLayout}
          onPick={(id) => {
            setPicked(id)
            setMenuOpen(false)
          }}
          onClose={() => setMenuOpen(false)}
        />
      )}
    </div>
  )
}
