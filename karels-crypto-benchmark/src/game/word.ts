import type { AttemptEvent } from './types'

/** Strip accents and case: "Première" → "premiere". */
export function normalize(s: string): string {
  return s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase()
}

export interface Cell {
  /** the letter to find (a–z), or the fixed character for hyphens/spaces */
  target: string
  /** non-letters such as "-" are shown and never typed */
  fixed: boolean
  value: string | null
  revealed: boolean
  /** active ms when the current value was typed */
  typedAt: number | null
}

export type Status = 'playing' | 'solved' | 'failed'

export interface WordState {
  clueId: string
  cells: Cell[]
  cursor: number
  status: Status
  /** increments on every wrong full guess so the UI can replay its animation */
  wrongCount: number
  events: AttemptEvent[]
  /** wall clock (epoch ms) when the clue was first shown */
  startedAt: number
  /** total hidden ms so far, plus the epoch ms the tab went hidden (if hidden now) */
  hiddenMs: number
  hiddenSince: number | null
  completedByReveal: boolean
  finishedAt: number | null
  /** seed of the "Show letter" order, stored so the same letters can be shown to an LLM */
  seed: number
  /** letter positions in the order "Show letter" reveals them (derived from `seed`) */
  revealOrder: number[]
}

export type Action =
  | { type: 'key'; key: string }
  | { type: 'backspace' }
  | { type: 'move'; pos: number }
  | { type: 'left' }
  | { type: 'right' }
  | { type: 'reveal' }
  | { type: 'hide' }
  | { type: 'show' }

/** mulberry32: tiny seeded PRNG returning floats in [0, 1). */
export function seededRng(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export const randomSeed = () => Math.floor(Math.random() * 2 ** 32)

/**
 * The order in which "Show letter" reveals letter positions: a Fisher–Yates shuffle of the
 * letter positions driven by `seededRng(seed)`. Each reveal takes the first position in this
 * order that is still empty or wrong, so a seed fixes which letters get shown.
 */
export function revealOrderFor(answer: string, seed: number): number[] {
  const pos = [...normalize(answer)].flatMap((ch, i) => (/[a-z]/.test(ch) ? [i] : []))
  const rng = seededRng(seed)
  for (let i = pos.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1))
    ;[pos[i], pos[j]] = [pos[j]!, pos[i]!]
  }
  return pos
}

export function newWord(clueId: string, answer: string, now: number, seed: number = randomSeed()): WordState {
  const cells: Cell[] = [...normalize(answer)].map((ch) => {
    const fixed = !/[a-z]/.test(ch)
    return { target: ch, fixed, value: fixed ? ch : null, revealed: false, typedAt: null }
  })
  const state: WordState = {
    clueId,
    cells,
    cursor: 0,
    status: 'playing',
    wrongCount: 0,
    events: [],
    startedAt: now,
    hiddenMs: 0,
    hiddenSince: null,
    completedByReveal: false,
    finishedAt: null,
    seed,
    revealOrder: revealOrderFor(answer, seed),
  }
  state.cursor = nextEditable(state.cells, -1) ?? 0
  return state
}

export function activeMs(s: WordState, now: number): number {
  const end = s.finishedAt ?? now
  const hidden = s.hiddenMs + (s.hiddenSince !== null ? Math.max(0, end - s.hiddenSince) : 0)
  return Math.max(0, end - s.startedAt - hidden)
}

export const editable = (c: Cell) => !c.fixed && !c.revealed

function nextEditable(cells: Cell[], from: number): number | null {
  for (let i = from + 1; i < cells.length; i++) if (editable(cells[i]!)) return i
  return null
}
function prevEditable(cells: Cell[], from: number): number | null {
  for (let i = from - 1; i >= 0; i--) if (editable(cells[i]!)) return i
  return null
}

export const letterCount = (s: WordState) => s.cells.filter((c) => !c.fixed).length
export const revealedCount = (s: WordState) => s.cells.filter((c) => c.revealed).length
export const guess = (s: WordState) => s.cells.map((c) => c.value ?? '·').join('')
const isFull = (s: WordState) => s.cells.every((c) => c.value !== null)
const isCorrect = (s: WordState) => s.cells.every((c) => c.value === c.target)

/**
 * Pure state transition. "Show letter" follows the seeded `revealOrder`.
 * When the last empty cell gets filled the word is checked: correct → solved (or failed when
 * that last letter came from "Show letter"), wrong → stays in place with wrongCount + 1.
 */
export function step(s: WordState, a: Action, now: number): WordState {
  if (a.type === 'hide') {
    if (s.hiddenSince !== null || s.status !== 'playing') return s
    const t = activeMs(s, now)
    return { ...s, hiddenSince: now, events: [...s.events, { t, type: 'hide' }] }
  }
  if (a.type === 'show') {
    if (s.hiddenSince === null) return s
    const next = { ...s, hiddenMs: s.hiddenMs + Math.max(0, now - s.hiddenSince), hiddenSince: null }
    return { ...next, events: [...next.events, { t: activeMs(next, now), type: 'show' }] }
  }
  if (s.status !== 'playing') return s
  // any interaction implies the page is visible
  if (s.hiddenSince !== null) s = step(s, { type: 'show' }, now)
  const t = activeMs(s, now)
  const cells = s.cells.map((c) => ({ ...c }))

  switch (a.type) {
    case 'move': {
      if (!cells[a.pos] || !editable(cells[a.pos]!)) return s
      return { ...s, cursor: a.pos }
    }
    case 'left':
      return { ...s, cursor: prevEditable(cells, s.cursor) ?? s.cursor }
    case 'right':
      return { ...s, cursor: nextEditable(cells, s.cursor) ?? s.cursor }
    case 'backspace': {
      let pos = s.cursor
      const cur = cells[pos]
      if (!cur || !editable(cur) || cur.value === null) {
        const prev = prevEditable(cells, pos)
        if (prev === null) return s
        pos = prev
      }
      const target = cells[pos]!
      if (target.value === null) return { ...s, cursor: pos }
      target.value = null
      target.typedAt = null
      return { ...s, cells, cursor: pos, events: [...s.events, { t, type: 'delete', pos }] }
    }
    case 'key': {
      const key = normalize(a.key)
      if (!/^[a-z]$/.test(key)) return s
      const cur = cells[s.cursor]
      if (!cur || !editable(cur)) return s
      cur.value = key
      cur.typedAt = t
      const ev: AttemptEvent = { t, type: 'type', pos: s.cursor, key }
      const next = { ...s, cells, events: [...s.events, ev] }
      next.cursor = nextEditable(cells, s.cursor) ?? s.cursor
      return check(next, now, false)
    }
    case 'reveal': {
      const i = s.revealOrder.find((p) => editable(cells[p]!) && cells[p]!.value !== cells[p]!.target)
      if (i === undefined) return s
      const c = cells[i]!
      c.value = c.target
      c.revealed = true
      c.typedAt = null
      const next = { ...s, cells, events: [...s.events, { t, type: 'reveal' as const, pos: i, key: c.target }] }
      if (s.cursor === i || !editable(cells[s.cursor]!)) {
        next.cursor = nextEditable(cells, i) ?? prevEditable(cells, i) ?? s.cursor
      }
      return check(next, now, true)
    }
  }
}

function check(s: WordState, now: number, byReveal: boolean): WordState {
  if (!isFull(s)) return s
  const t = activeMs(s, now)
  const correct = isCorrect(s)
  const events: AttemptEvent[] = [...s.events, { t, type: 'submit', guess: guess(s), correct }]
  if (!correct) return { ...s, events, wrongCount: s.wrongCount + 1 }
  return {
    ...s,
    events,
    status: byReveal ? 'failed' : 'solved',
    completedByReveal: byReveal,
    finishedAt: now,
  }
}
