# karels-crypto-solving

LLM-based solver for **Karel's Crypto** (the weekly Dutch cryptic puzzle from De
Standaard). It consumes the JSON datasets produced by the sibling
[`karels-crypto-scraping`](../karels-crypto-scraping) module.

> Constraint: the solver uses **only an LLM and a prompt** — no tools, no
> dictionaries, no vocabulary databases. The model is allowed to *think* (reason
> in its output / chain-of-thought) before answering.

## The puzzle, briefly

19 cryptic clues, each describing one Dutch word. The answers share a numbered
grid: cells with the same number hold the same letter, so solving one word
reveals letters in others. A 19-letter word is hidden vertically.

## Proposed plan

The solver is built in three layers:

1. **Puzzle state (`models.py`)** — a `Puzzle`/`Word` model with a *fill state*.
   The grid's `help_numbers` are modelled as a shared `helper_map`
   (number → letter), so filling a numbered cell of one word automatically
   propagates that letter to every other word (the "helper letters" mechanic).
   The state serialises to JSON (each word gains a `filled` array), so a
   partially-solved puzzle round-trips.

2. **Two solve functions:**

   - **`solve_word`** (`word_solver.py`) — solves a *single* clue. The clue, its
     length and any known letters (`pattern`) are injected into the **system
     prompt** (`str.format` parameter injection). One LLM call, no tools; the
     model reasons then emits `ANSWER: <word>`. Uses the plain `openai` library.

   - **`solve_puzzle`** (`puzzle_solver.py`) — solves a *whole* puzzle as a
     single **agentic chat loop** (OpenAI Agents SDK) with exactly two tools:
     - `fill_word(word_index, letters)` — write/erase a (partial) guess (`"_"`
       = unknown); helper letters propagate automatically.
     - `check_puzzle()` — returns whether the puzzle is fully correct.
     The current board is injected into the system prompt every turn via dynamic
     instructions. The agent fills, checks, and revises until solved.

3. **Runner (`runner.py`)** — runs either solver over the scraped datasets and
   reports zero-shot word accuracy / whether a puzzle was solved.

The default prompts (`prompts.py`) are deliberately minimal baselines; the
`optimization/` submodule improves the word-solver prompt automatically (see
[`optimization/README.md`](./src/karels_crypto_solving/optimization/README.md)).

### Why these design choices

- **System-prompt parameter injection** keeps the "what to solve" data out of
  the model's free-form input and makes the prompt the single optimisation
  target.
- **Two tools only** keeps the agent loop honest: it can act (`fill_word`) and
  verify (`check_puzzle`), nothing else. `check_puzzle` is the oracle used during
  evaluation on solved (historical) puzzles.

## Usage

```bash
uv sync                       # install (core: openai + openai-agents)

# Evaluate the single-word solver on historical clues (no letters given):
uv run karels-crypto-solve word --limit 20

# Reveal some/all helper letters as hints:
uv run karels-crypto-solve word --reveal all
uv run karels-crypto-solve word --reveal partial --reveal-fraction 0.5

# Run the agentic puzzle solver on the most recent historical puzzle:
uv run karels-crypto-solve puzzle

# Compare OpenAI models on word solving (accuracy + estimated cost):
uv run karels-crypto-benchmark --limit 20
uv run karels-crypto-benchmark --models gpt-4o-mini gpt-4o o3 --limit 30

# Ingest photos of puzzles + solutions into the data format (vision LLM):
uv run karels-crypto-ingest puzzles   --model gpt-5.5-2026-04-23
uv run karels-crypto-ingest solutions --model gpt-5.5-2026-04-23
uv run karels-crypto-ingest merge
```

## Ingesting puzzle photos

The book puzzles are number-substitution cryptograms: an **empty** grid of
numbered cells (equal numbers = equal letters) with 19 clues labelled A-S, and
the **answers live on separate solutions pages** (many puzzles per page). So
ingestion is a **two-pass + merge** pipeline using a **vision-capable** model
(images sent as base64 data URLs):

Images live in `uploads/images/puzzles/` and `uploads/images/solutions/` (the
defaults). Use the **strongest** vision model you have for accurate OCR; for
reasoning models (gpt-5.x) optionally add `--reasoning-effort high`.

```bash
# 1) the empty puzzle pages -> clues + the number key
uv run karels-crypto-ingest puzzles   --model gpt-5.5-2026-04-23
# 2) the solutions pages -> answers per puzzle number
uv run karels-crypto-ingest solutions --model gpt-5.5-2026-04-23
# 3) join them (by puzzle number + clue label) into the data format
uv run karels-crypto-ingest merge
```

(Override the folders with `--images-dir`. The default model is `gpt-4o`.)

`merge` writes `data/ingested_puzzles.json`, which the optimizer includes in its
training set by default (`karels-crypto-optimize --no-ingested` to exclude).

What's extracted: per puzzle the **number/date** and the 19 **clues** (label +
cryptogram + the row's cell numbers); per solution page the **answer word** for
each label (+ the 19-letter hidden word). Merge joins them on puzzle number and
A-S label to produce `cryptogram` + `solution` pairs (with `help_numbers` from
the captured key when the count matches the answer length). Answers are taken
only from the solutions pages (never guessed). Ids are `--id-start` + puzzle
number (default base 900000) so they don't clash with scraped ids.

Tip: transcription of Dutch accents / the grid numbers is where a vision model is
most likely to slip — eyeball a few entries in `data/ingested_puzzles.json` (and
the `_ingest_*_raw.json` intermediates) before optimizing on them.

LLM access uses the standard environment variables: `OPENAI_API_KEY`,
`OPENAI_BASE_URL`, and `OPENAI_MODEL` (defaults to `gpt-4o-mini`). On GitHub
Actions, `OPENAI_API_KEY` is a repository **secret**, while `OPENAI_BASE_URL`
and `OPENAI_MODEL` are repository **variables** (they aren't sensitive).

Locally you can put them in a `.env` file (copy `.env.example`) in this folder or
the repo root — it's loaded automatically. Real environment variables override
the file, and `.env` is git-ignored.

The datasets are read from `../karels-crypto-scraping/data` by default; override
with `KARELS_CRYPTO_DATA_DIR`.

### Tests / lint

```bash
uv run pytest        # state propagation, pattern building, answer parsing, data
uv run ruff check .
```

## Layout

```
src/karels_crypto_solving/
  models.py         Puzzle/Word state + helper-letter propagation
  data.py           load puzzles from the scraping datasets
  config.py         OpenAI client/model from env
  prompts.py        very basic default prompts
  word_solver.py    solve_word (single clue, prompt only)
  puzzle_solver.py  solve_puzzle (agentic loop, 2 tools)
  patterns.py       build known-letter patterns (none/partial/all)
  ingest.py         vision-LLM ingestion of puzzle photos -> data format
  runner.py         CLI
  pricing.py        OpenAI model prices (for benchmark cost estimates)
  benchmark.py      compare models on word solving (accuracy + cost)
  optimization/     DSPy prompt optimization submodule (optional extra)
```

## Benchmarking models

`karels-crypto-benchmark` runs the word solver across several OpenAI models on
the same sampled clues and reports zero-shot accuracy, token usage and estimated
cost (from `pricing.py`). Results are written to `benchmark_results/`
(`benchmark.json` + a sorted `benchmark.md` table). Expected API errors (model
not enabled on your gateway, rate limits, transient failures) are logged and
skipped; unexpected errors (bad parameters, bugs) crash the run. `--reasoning-effort`
and `--num-threads` keep reasoning models fast/cheap. It can also be run via the
**benchmark** GitHub Actions workflow (commits results back).
