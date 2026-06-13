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
```

LLM access uses the standard environment variables (provide via GitHub secrets):
`OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL` (defaults to
`gpt-4o-mini`).

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
  runner.py         CLI
  optimization/     DSPy prompt optimization submodule (optional extra)
```
