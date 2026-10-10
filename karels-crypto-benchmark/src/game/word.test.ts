import { newWord, revealOrderFor, step, type WordState, type Action } from './word'
import { nextOpenClue } from './order'
import type { Attempt } from './types'
import { toAttempt } from './attempt'
import { ALL_CLUES } from '@/data/clues'

const run = (s: WordState, actions: Action[]) => {
  let t = s.startedAt
  for (const a of actions) s = step(s, a, (t += 1000))
  return s
}
const keys = (w: string): Action[] => [...w].map((key) => ({ type: 'key', key }))

describe('word', () => {
  it('solves when the last letter is typed correctly', () => {
    const s = run(newWord('x', 'roma', 0), keys('roma'))
    expect(s.status).toBe('solved')
    expect(s.cells.map((c) => c.typedAt)).toEqual([1000, 2000, 3000, 4000])
  })

  it('stays in place on a wrong guess and can be corrected', () => {
    let s = run(newWord('x', 'roma', 0), keys('rome'))
    expect(s.status).toBe('playing')
    expect(s.wrongCount).toBe(1)
    expect(s.cells.map((c) => c.value).join('')).toBe('rome')
    s = run(s, [{ type: 'backspace' }, { type: 'key', key: 'a' }])
    expect(s.status).toBe('solved')
  })

  it('backspace on an empty cell clears the previous one', () => {
    const s = run(newWord('x', 'roma', 0), [...keys('ro'), { type: 'backspace' }])
    expect(s.cells.map((c) => c.value)).toEqual(['r', null, null, null])
    expect(s.cursor).toBe(1)
  })

  it('reveal shows the next unrevealed letter in the seeded order and locks it', () => {
    const s = run({ ...newWord('x', 'roma', 0), revealOrder: [0, 2, 1, 3] }, [{ type: 'reveal' }])
    expect(s.cells[0]).toMatchObject({ value: 'r', revealed: true })
    expect(s.cursor).toBe(1)
    const s2 = run(s, [{ type: 'move', pos: 0 }])
    expect(s2.cursor).toBe(1)
    // position 2 is next in the order: it is revealed even though it was already typed correctly
    const s3 = run(s2, [...keys('om'), { type: 'reveal' }])
    expect(s3.cells[2]).toMatchObject({ value: 'm', revealed: true })
    expect(s3.cells[3]!.revealed).toBe(false)
    expect(s3.status).toBe('playing')
  })

  it('locking an already-correct letter on a full wrong board adds no wrong guess', () => {
    let s = run({ ...newWord('x', 'roma', 0), revealOrder: [0, 3, 1, 2] }, keys('rome'))
    expect(s.wrongCount).toBe(1)
    s = run(s, [{ type: 'reveal' }])
    expect(s.cells[0]).toMatchObject({ value: 'r', revealed: true })
    expect(s.wrongCount).toBe(1)
    s = run(s, [{ type: 'reveal' }])
    expect(s.cells[3]).toMatchObject({ value: 'a', revealed: true })
    expect(s.status).toBe('failed')
  })

  it('the seed fixes the reveal order', () => {
    expect(revealOrderFor('Lay-out', 42)).toEqual(revealOrderFor('Lay-out', 42))
    expect([...revealOrderFor('Lay-out', 42)].sort()).toEqual([0, 1, 2, 4, 5, 6])
    expect(newWord('x', 'Lay-out', 0, 42).revealOrder).toEqual(revealOrderFor('Lay-out', 42))
    const orders = new Set([1, 2, 3, 4, 5, 6, 7, 8].map((seed) => revealOrderFor('abcdefgh', seed).join()))
    expect(orders.size).toBeGreaterThan(1)
  })

  it('fails when the last missing letter comes from Show letter', () => {
    const s = run({ ...newWord('x', 'roma', 0), revealOrder: [3, 0, 1, 2] }, [...keys('rom'), { type: 'reveal' }])
    expect(s.cells[3]).toMatchObject({ value: 'a', revealed: true })
    expect(s.status).toBe('failed')
    expect(s.completedByReveal).toBe(true)
  })

  it('treats hyphens as fixed and accents as plain letters', () => {
    const s = newWord('x', 'Lay-out', 0)
    expect(s.cells.map((c) => c.fixed)).toEqual([false, false, false, true, false, false, false])
    expect(run(s, keys('layout')).status).toBe('solved')
    expect(run(newWord('x', 'première', 0), keys('premiere')).status).toBe('solved')
  })

  it('excludes hidden time from active time', () => {
    let s = newWord('x', 'ab', 0)
    s = step(s, { type: 'hide' }, 1000)
    s = step(s, { type: 'show' }, 61000)
    s = step(s, { type: 'key', key: 'a' }, 62000)
    expect(s.cells[0]!.typedAt).toBe(2000)
  })

  it('builds an attempt record', () => {
    const ref = ALL_CLUES[0]!
    let s = { ...newWord(ref.clue.id, 'roma', 0, 7), revealOrder: [0, 1, 2, 3] }
    s = run(s, [{ type: 'reveal' }, ...keys('omx'), { type: 'backspace' }, { type: 'key', key: 'a' }])
    const a = toAttempt(ref, s, 'solved', 10_000)
    expect(a).toMatchObject({ v: 3, length: 4, lettersNeeded: 3, revealedCount: 1, outcome: 'solved', seed: 7 })
    expect(a.letterMs[0]).toBeNull()
    expect(a.wrongGuesses).toEqual([{ t: 4000, guess: 'romx' }])
  })
})

describe('nextOpenClue', () => {
  const done = (...refs: number[]) =>
    Object.fromEntries(refs.map((i) => [ALL_CLUES[i]!.clue.id, { outcome: 'solved' } as Attempt]))

  it('starts at the oldest open clue', () => {
    expect(nextOpenClue(done(0, 1), null)).toBe(ALL_CLUES[2])
  })

  it('continues after the clue just finished, skipping done ones', () => {
    expect(nextOpenClue(done(0, 5, 6, 7), ALL_CLUES[5]!.clue.id)).toBe(ALL_CLUES[8])
  })

  it('wraps around to earlier open clues', () => {
    const last = ALL_CLUES.length - 1
    expect(nextOpenClue(done(0, last), ALL_CLUES[last]!.clue.id)).toBe(ALL_CLUES[1])
  })
})
