# optimization — DSPy prompt optimization for the word solver

Supervised optimization of the **word-solver prompt** using
[DSPy](https://dspy.ai) and the `MIPROv2` optimizer, with the scraped solutions
as labels.

## Goal / loss

Maximise **zero-shot accuracy**: the fraction of clues the program answers
correctly with no few-shot examples (the model may still reason/think before
answering). By default this is measured on **empty patterns** (no letters
revealed) — the hardest setting and the one we care about most.

The metric (`program.exact_match_metric`) is a normalised exact match
(`example, pred, trace=None) -> bool`), which is exactly what MIPROv2 maximises.

## How DSPy does this (brief)

DSPy separates a **Signature** (typed inputs/outputs + an instruction docstring)
from a **Module** (`ChainOfThought`, so the model reasons before answering).
`MIPROv2`:

1. (optionally) bootstraps few-shot demo candidates from the trainset,
2. proposes several candidate **instructions** grounded in the data/task,
3. uses Bayesian optimization to search instruction (+demo) combinations,
   scoring each candidate on the metric over a validation split.

We default to **instruction-only** optimization (`--demos 0`): no few-shot
examples are baked in, so the result is a pure improved *prompt* (in keeping with
the "prompt only, no vocabulary" constraint). Raise `--demos` to also search
few-shot demonstrations.

## Run

```bash
uv sync --extra optimize          # installs DSPy

# Hardest setting: no letters revealed (the default)
karels-crypto-optimize --auto light --reveal none

# Easier experiments if 'none' is too hard:
karels-crypto-optimize --reveal partial --reveal-fraction 0.5
karels-crypto-optimize --reveal all
```

Reads `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`.

### Where results are stored

All artifacts are written to (and committed from) `../../optimization_results/`
(i.e. `karels-crypto-solving/optimization_results/`):

- `optimized_prompt.txt` — the optimised instruction (copy into
  `prompts.WORD_SOLVER_SYSTEM`, or load the program).
- `optimized_word_solver.json` — the full compiled DSPy program.
- `metrics.json` — config, baseline vs optimized accuracy, best score, total LM
  calls, and the per-trial **training curve** (`training_curve[]`).

Override the location with `--output-dir`.

### Running on GitHub Actions

Add the `OPENAI_API_KEY` / `OPENAI_BASE_URL` (and optionally `OPENAI_MODEL`)
repository secrets, then trigger the **optimize** workflow
(`.github/workflows/optimize.yml`) from the Actions tab. It runs the optimizer
with the chosen inputs and commits the updated `optimization_results/` back to
the branch.

## Notes

- DSPy recommends ~50–500 examples. The training set is the scraped **history**,
  which grows every week, so optimization quality improves over time.
- `--auto light|medium|heavy` trades cost for search depth (even `light` makes
  many LLM calls).
- This was validated for import/API correctness against DSPy 3.x; an actual
  optimization run needs working `OPENAI_*` credentials.
