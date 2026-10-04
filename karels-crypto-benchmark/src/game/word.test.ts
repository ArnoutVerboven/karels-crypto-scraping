import { newWord, step, type WordState, type Action } from './word'
import { toAttempt } from './attempt'
import { ALL_CLUES } from '@/data/clues'

const run = (s: WordState, actions: Action[], rng = () => 0) => {
  let t = s.startedAt
  for (const a of actions) s = step(s, a, (t += 1000), rng)
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

  it('reveal fills a random wrong/empty letter and locks it', () => {
    const s = run(newWord('x', 'roma', 0), [{ type: 'reveal' }])
    expect(s.cells[0]).toMatchObject({ value: 'r', revealed: true })
    expect(s.cursor).toBe(1)
    const s2 = run(s, [{ type: 'move', pos: 0 }])
    expect(s2.cursor).toBe(1)
  })

  it('fails when the last missing letter comes from Show letter', () => {
    const s = run(newWord('x', 'roma', 0), [...keys('rom'), { type: 'reveal' }])
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
    let s = newWord(ref.clue.id, 'roma', 0)
    s = run(s, [{ type: 'reveal' }, ...keys('omx'), { type: 'backspace' }, { type: 'key', key: 'a' }])
    const a = toAttempt(ref, s, 'solved', 10_000)
    expect(a).toMatchObject({ length: 4, lettersNeeded: 3, revealedCount: 1, outcome: 'solved' })
    expect(a.letterMs[0]).toBeNull()
    expect(a.wrongGuesses).toEqual([{ t: 4000, guess: 'romx' }])
  })
})
