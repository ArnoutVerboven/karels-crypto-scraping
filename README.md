# karels-crypto-scraping

Scrapes [Karel's Crypto](https://puzzelkc.standaard.be/), the weekly cryptogram
by Karel Vereertbrugghen published every Saturday in *De Standaard*, and stores
the puzzles as JSON datasets in this repository. A GitHub Actions workflow runs
the scraper every Saturday and commits the refreshed data.

## Source

The puzzle single-page-app at `https://puzzelkc.standaard.be` is backed by a
GraphQL endpoint:

```
POST https://puzzelkc.standaard.be/graphql
```

Two public (unauthenticated) queries are used:

- **This week's Crypto** — `published_puzzle` (the home puzzle):

  ```graphql
  query getHomePuzzle { published_puzzle { ...puzzleFields } }
  ```

- **Recent Crypto's** (archive) — `puzzles(published: true, ...)`:

  ```graphql
  query getPuzzles($limit: Int, $page: Int, $published: Boolean) {
    puzzles(limit: $limit, page: $page, published: $published) {
      data { ...puzzleFields }
      total
    }
  }
  ```

The API only keeps a handful of puzzles online at any time, so the historical
dataset in this repo grows over time as the weekly job accumulates puzzles.

### The key GraphQL fields

Each puzzle node returns:

| Field        | Meaning                                                            |
| ------------ | ------------------------------------------------------------------ |
| `id`         | Unique puzzle id.                                                  |
| `title`      | e.g. `"Karels Crypto 13 juni"`.                                    |
| `start_date` | Publication date (`YYYY-MM-DD HH:MM:SS`).                          |
| `solution`   | The 19-letter word hidden vertically through the grid.            |
| `rows[]`     | The 19 clue rows (see below).                                      |
| `legends[]`  | Grid key: `{ number, letter }` — equal numbers mean equal letters. |

Each `rows[]` entry holds: `hint` (the cryptic clue), `answer` (the solution
word), `offset` (how far the row is shifted so its letter lines up with the
vertical word), and `numbers[]` (`{ index }` of the cells that show a
pre-printed help number).

## Data format

A dataset is a list of Crypto's. Each Crypto is an ordered list of words. Each
word has:

- `cryptogram` — the cryptic clue (`hint`).
- `length` — the number of letters in the answer.
- `help_numbers` — an array with one entry per letter (mostly `null`); a number
  is the grid digit for that cell, derived from the puzzle `legends`
  (`legend.number` for the letter at that position).
- `offset` — the index where the central/vertical word intersects this row.
- `solution` — the answer word, or `null` for the latest (unsolved) Crypto.

Two datasets are stored under [`data/`](./data):

- [`data/history.json`](./data/history.json) — historical Crypto's, **with**
  solutions (a list).
- [`data/latest.json`](./data/latest.json) — the latest Crypto, **without** its
  solution (clues and help numbers are kept, as they are public hints).

### Example word

```json
{
  "cryptogram": "Italia, Ninove",
  "length": 5,
  "help_numbers": [15, null, null, 18, null],
  "offset": 4,
  "solution": "Forza"
}
```

## Usage

Dependencies are managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync                # install dependencies (creates .venv)
uv run karels-crypto   # scrape and update data/history.json + data/latest.json
```

Useful flags:

```bash
uv run karels-crypto --from-file path/to/puzzles.json   # parse a saved response
uv run karels-crypto --endpoint https://.../graphql      # override the endpoint
uv run karels-crypto --history data/history.json --latest data/latest.json
```

### Tests and linting

```bash
uv run pytest        # unit tests (parsing + dataset building, real fixtures)
uv run ruff check .  # lint
```

## Automation

[`.github/workflows/scrape.yml`](./.github/workflows/scrape.yml) runs every
Saturday at 06:30 UTC (and on manual `workflow_dispatch`). It scrapes the latest
puzzle, merges it into the datasets and commits any changes back to the repo.

## Project layout

```
src/karels_crypto/
  api.py         GraphQL client + queries
  models.py      Word / Crypto dataclasses
  transform.py   raw GraphQL node -> Crypto (derives help numbers)
  storage.py     load / merge / save the JSON datasets
  scraper.py     orchestration + CLI entry point
data/            the committed JSON datasets
tests/           unit tests with captured fixtures
```
