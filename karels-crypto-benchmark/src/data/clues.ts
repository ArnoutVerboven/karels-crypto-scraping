import data from './clues.json'

export interface Clue {
  id: string
  letter: string
  text: string
  answer: string
}
export interface Crypto {
  id: number
  no: number
  date: string
  clues: Clue[]
}
export interface ClueRef {
  clue: Clue
  crypto: Crypto
  /** position in the global oldest-first order */
  order: number
}

export const CRYPTOS: Crypto[] = data as Crypto[]

/** Every clue, oldest crypto first, then in letter order. */
export const ALL_CLUES: ClueRef[] = CRYPTOS.flatMap((crypto) =>
  crypto.clues.map((clue) => ({ clue, crypto, order: 0 })),
).map((ref, order) => ({ ...ref, order }))

export const CLUE_BY_ID = new Map(ALL_CLUES.map((r) => [r.clue.id, r]))

const MONTHS = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec']
/** 2026-05-30 → "30 mei 2026" */
export function formatDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-')
  return `${Number(d)} ${MONTHS[Number(m) - 1] ?? ''} ${y}`
}
