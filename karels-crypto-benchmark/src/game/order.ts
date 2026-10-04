import { ALL_CLUES, CLUE_BY_ID, type ClueRef } from '@/data/clues'
import type { Attempt } from './types'

/**
 * The first clue after `after` (in oldest-first order) that is not solved, failed or skipped,
 * wrapping around to the start; with no `after` (app just opened), the oldest open clue.
 */
export function nextOpenClue(attempts: Record<string, Attempt>, after: string | null): ClueRef | null {
  const start = after ? (CLUE_BY_ID.get(after)?.order ?? -1) + 1 : 0
  for (let k = 0; k < ALL_CLUES.length; k++) {
    const ref = ALL_CLUES[(start + k) % ALL_CLUES.length]!
    if (!attempts[ref.clue.id]) return ref
  }
  return null
}
