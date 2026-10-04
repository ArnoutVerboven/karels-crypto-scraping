import type { ClueRef } from '@/data/clues'
import type { Attempt, Outcome } from './types'
import { activeMs, letterCount, newWord, revealedCount, type WordState } from './word'

const ua = () => (typeof navigator !== 'undefined' ? navigator.userAgent : '')

/** Turn a finished (or skipped) word state into the stored attempt record. */
export function toAttempt(
  ref: ClueRef,
  s: WordState,
  outcome: Outcome,
  now: number,
  skipReason?: 'clue' | 'crypto',
): Attempt {
  const end = s.finishedAt ?? now
  const firstKey = s.events.find((e) => e.type === 'type')
  const a: Attempt = {
    v: 2,
    clueId: ref.clue.id,
    cryptoId: ref.crypto.id,
    cryptoNo: ref.crypto.no,
    letter: ref.clue.letter,
    outcome,
    length: letterCount(s),
    lettersNeeded: letterCount(s) - revealedCount(s),
    revealedCount: revealedCount(s),
    completedByReveal: s.completedByReveal,
    activeMs: Math.round(activeMs({ ...s, finishedAt: end }, end)),
    wallMs: Math.round(end - s.startedAt),
    firstKeyMs: firstKey ? Math.round(firstKey.t) : null,
    letterMs: s.cells.map((c) => (c.revealed || c.fixed || c.typedAt === null ? null : Math.round(c.typedAt))),
    wrongGuesses: s.events.flatMap((e) => (e.type === 'submit' && !e.correct ? [{ t: Math.round(e.t), guess: e.guess }] : [])),
    reveals: s.events.flatMap((e) => (e.type === 'reveal' ? [{ t: Math.round(e.t), pos: e.pos }] : [])),
    events: s.events.map((e) => ({ ...e, t: Math.round(e.t) })),
    seed: s.seed,
    revealOrder: s.revealOrder,
    startedAt: new Date(s.startedAt).toISOString(),
    finishedAt: new Date(end).toISOString(),
    userAgent: ua(),
  }
  if (skipReason) a.skipReason = skipReason
  return a
}

/** A skip for a clue that was never opened (Skip crypto marks the rest of the crypto). */
export function skippedUnseen(ref: ClueRef, now: number): Attempt {
  return toAttempt(ref, newWord(ref.clue.id, ref.clue.answer, now), 'skipped', now, 'crypto')
}
