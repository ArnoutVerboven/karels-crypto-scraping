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

Reads `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` (locally, a `.env`
file in the module folder or repo root is loaded automatically — see
[`../../.env.example`](../../.env.example)).

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

Under **Settings → Secrets and variables → Actions**, add:

- `OPENAI_API_KEY` as a repository **secret** (sensitive),
- `OPENAI_BASE_URL` as a repository **variable** (not sensitive),
- `OPENAI_MODEL` as a repository **variable** (optional).

Then trigger the **optimize** workflow (`.github/workflows/optimize.yml`) from
the Actions tab. It runs the optimizer with the chosen inputs and commits the
updated `optimization_results/` back to the branch. (The workflow also accepts a
`secrets` fallback for the base URL / model if you'd rather keep them as
secrets.)

## Controllable parameters (and cost)

There is **no built-in hard token/spend cap** in DSPy — you bound cost via the
search size, the dataset size and the per-call token limit. The total number of
LM calls is roughly:

```
(instruction proposals ≈ num_candidates) + (num_trials × minibatch_size evals)
                                          + bootstrapping/eval overhead
```

Knobs (CLI flags; the workflow exposes the main ones):

| Flag | Controls | Notes |
| --- | --- | --- |
| `--auto light\|medium\|heavy\|none` | overall search budget | biggest lever; `light` is cheapest. `none` = set the size yourself. |
| `--num-candidates N` | instruction candidates proposed | only with `--auto none`. |
| `--num-trials N` | optimization trials | only with `--auto none`. |
| `--minibatch / --no-minibatch` | eval on minibatches vs full valset | minibatching is cheaper. |
| `--minibatch-size N` | examples scored per trial | clamped to the valset size (default 35). |
| `--max-tokens N` | **output tokens per LM call** | the direct token cap (default 1000); lower it to save tokens, but leave room for reasoning. |
| `--temperature F` | sampling temperature | |
| `--num-threads N` | parallel eval threads | speed, not cost. |
| `--max-errors N` | abort after N failing calls | safety valve. |
| `--max-examples N` | cap labelled words used | fewer examples = cheaper trials. |
| `--demos N` | max few-shot demos | 0 = instruction-only (default). |
| `--reveal`, `--reveal-fraction` | helper letters in the pattern | the experiment setup. |
| `--val-fraction`, `--seed` | train/val split, determinism | |
| `--model` | model override | else `OPENAI_MODEL`. |

The chosen budget is recorded in `metrics.json -> config`, and the *actual* LM
calls made are reported as `metrics.json -> total_lm_calls` after the run.

To keep a first run cheap: `--auto light --max-tokens 600` (optionally
`--max-examples 40`). For a tightly bounded run: `--auto none --num-candidates 4
--num-trials 6 --max-tokens 600`.

## Notes

- DSPy recommends ~50–500 examples. The training set is the scraped **history**,
  which grows every week, so optimization quality improves over time.
- `--auto light|medium|heavy` trades cost for search depth (even `light` makes
  many LLM calls).
- This was validated for import/API correctness against DSPy 3.x; an actual
  optimization run needs working `OPENAI_*` credentials.
