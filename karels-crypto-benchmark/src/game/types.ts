export type Outcome = 'solved' | 'failed' | 'skipped'

/** One event in a clue attempt; `t` is active milliseconds since the clue was first shown. */
export type AttemptEvent =
  | { t: number; type: 'type'; pos: number; key: string }
  | { t: number; type: 'delete'; pos: number }
  | { t: number; type: 'reveal'; pos: number; key: string }
  | { t: number; type: 'submit'; guess: string; correct: boolean }
  | { t: number; type: 'hide' | 'show' }

/** What is stored per clue (Firestore users/{uid}/attempts/{clueId}). */
export interface Attempt {
  /** 2 adds `seed` / `revealOrder` */
  v: 1 | 2
  clueId: string
  cryptoId: number
  cryptoNo: number
  letter: string
  outcome: Outcome
  skipReason?: 'clue' | 'crypto'
  /** letters in the answer (hyphens etc. excluded) */
  length: number
  /** letters the solver still had to find themselves: length − revealed */
  lettersNeeded: number
  revealedCount: number
  /** failed because the last missing letter came from "Show letter" */
  completedByReveal: boolean
  /** active ms (tab hidden time excluded) from first view to the end */
  activeMs: number
  /** wall-clock ms from first view to the end */
  wallMs: number
  /** active ms of the first keystroke, null if none */
  firstKeyMs: number | null
  /** per answer position: active ms when its final letter was typed; null if revealed / fixed */
  letterMs: (number | null)[]
  wrongGuesses: { t: number; guess: string }[]
  reveals: { t: number; pos: number }[]
  events: AttemptEvent[]
  /** seed for the "Show letter" order (see `revealOrderFor` in word.ts); absent on v1 records */
  seed?: number
  /** answer positions in the order "Show letter" reveals them, derived from `seed` */
  revealOrder?: number[]
  startedAt: string
  finishedAt: string
  userAgent: string
}
