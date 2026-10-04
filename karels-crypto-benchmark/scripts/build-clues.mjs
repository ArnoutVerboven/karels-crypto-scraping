// Builds src/data/clues.json from the scraped puzzles (karels-crypto-scraping/data/history.json)
// and the photo-ingested book puzzles (karels-crypto-solving/data/ingested_puzzles.json).
// Only words with a known solution are kept; the newest scraped puzzle has none until next week.
import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../..', import.meta.url))
const sources = [
  `${root}karels-crypto-scraping/data/history.json`,
  `${root}karels-crypto-solving/data/ingested_puzzles.json`,
]

const puzzles = sources.filter(existsSync).flatMap((p) => JSON.parse(readFileSync(p, 'utf8')))

const cryptos = puzzles
  .map((p) => ({
    id: p.id,
    no: p.number ?? p.id,
    date: p.date,
    yellow: typeof p.solution === 'string' ? p.solution : null,
    words: p.words
      .map((w, i) => ({ w, i }))
      .filter(({ w }) => typeof w.solution === 'string' && w.solution.length > 0),
  }))
  .filter((c) => c.words.length > 0)
  .sort((a, b) => a.date.localeCompare(b.date) || a.no - b.no)
  .map((c) => ({
    id: c.id,
    no: c.no,
    date: c.date,
    yellow: c.yellow,
    clues: c.words.map(({ w, i }) => ({
      id: `${c.id}-${i}`,
      letter: String.fromCharCode(65 + i),
      text: w.cryptogram,
      answer: w.solution.toLowerCase(),
    })),
  }))

const out = fileURLToPath(new URL('../src/data/clues.json', import.meta.url))
writeFileSync(out, JSON.stringify(cryptos))
const n = cryptos.reduce((s, c) => s + c.clues.length, 0)
console.log(`clues.json: ${cryptos.length} cryptos, ${n} clues`)
