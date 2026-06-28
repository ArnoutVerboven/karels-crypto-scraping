# karels-crypto

Tools for **Karel's Crypto**, the weekly Dutch cryptic puzzle by Karel
Vereertbrugghen in *De Standaard*. The repository is split into two independent
modules:

| Module | What it does |
| ------ | ------------ |
| [`karels-crypto-scraping`](./karels-crypto-scraping) | Scrapes the puzzle every Saturday from De Standaard's GraphQL API and stores the puzzles as JSON datasets (`data/history.json`, `data/latest.json`). Runs on a schedule via GitHub Actions. |
| [`karels-crypto-solving`](./karels-crypto-solving) | Solves Karel's Crypto with an LLM (prompt only, no tools/dictionaries): a single-word solver, an agentic whole-puzzle solver, a model benchmark, photo ingestion (vision), and a DSPy submodule that optimizes the word-solver prompt. Research findings: [`research/REPORT.md`](./karels-crypto-solving/research/REPORT.md). |

The modules are independent (each is its own [uv](https://docs.astral.sh/uv/)
project with its own dependencies and lockfile) and are coupled only through the
JSON data format: the solver reads the datasets produced by the scraper.

## Quick start

```bash
# Scraping
cd karels-crypto-scraping && uv sync && uv run karels-crypto

# Solving (needs OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL)
cd karels-crypto-solving && uv sync
uv run karels-crypto-solve word --limit 20      # single-word solver
uv run karels-crypto-solve puzzle               # agentic whole-puzzle solver

# Compare models on word solving (accuracy + estimated cost)
uv run karels-crypto-benchmark --limit 20

# Ingest puzzle/solution photos (vision LLM) -> data format
uv run karels-crypto-ingest puzzles && uv run karels-crypto-ingest solutions && uv run karels-crypto-ingest merge

# Prompt optimization (DSPy: mipro/copro/gepa)
cd karels-crypto-solving && uv sync --extra optimize
uv run karels-crypto-optimize --optimizer gepa --reveal none
```

See each module's README for details, and
[`karels-crypto-solving/research/REPORT.md`](./karels-crypto-solving/research/REPORT.md)
for the word-solver research findings.
