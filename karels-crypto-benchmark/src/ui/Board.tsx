import { useEffect, useRef, useState } from 'react'
import { editable, type WordState } from '@/game/word'

/** The answer cells. Tap a cell to move the cursor there. */
export function Board({ word, onMove }: { word: WordState; onMove: (pos: number) => void }) {
  const [shake, setShake] = useState(false)
  const lastWrong = useRef(word.wrongCount)
  useEffect(() => {
    if (word.wrongCount > lastWrong.current) {
      setShake(true)
      navigator.vibrate?.(60)
      const id = setTimeout(() => setShake(false), 450)
      lastWrong.current = word.wrongCount
      return () => clearTimeout(id)
    }
    lastWrong.current = word.wrongCount
  }, [word.wrongCount])

  const state = word.status === 'solved' ? 'good' : word.status === 'failed' ? 'failed bad' : shake ? 'bad' : ''
  return (
    <div
      className={`cells ${state}`}
      style={{ ['--n' as string]: word.cells.length }}
      role="group"
      aria-label={`${word.cells.filter((c) => !c.fixed).length} letters`}
    >
      {word.cells.map((c, i) => {
        const cls = [
          'cell',
          c.fixed && 'fixed',
          c.revealed && 'revealed',
          word.status === 'playing' && i === word.cursor && editable(c) && 'cursor',
          c.value && !c.fixed && 'pop',
        ]
          .filter(Boolean)
          .join(' ')
        return (
          <button
            key={`${i}-${c.value ?? ''}`}
            className={cls}
            style={{ ['--i' as string]: i }}
            tabIndex={-1}
            aria-label={`Letter ${i + 1}${c.value ? `: ${c.value}` : ''}${c.revealed ? ' (shown)' : ''}`}
            onPointerDown={(e) => {
              e.preventDefault()
              onMove(i)
            }}
          >
            {c.value ?? ''}
          </button>
        )
      })}
    </div>
  )
}
