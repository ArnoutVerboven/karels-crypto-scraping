# optimization — DSPy prompt optimization for the word solver

Supervised optimization of the **word-solver prompt** using
[DSPy](https://dspy.ai) and the `MIPROv2` optimizer, with the scraped solutions
as labels.

## Goal / loss

Maximise **one-shot accuracy**: the fraction of clues the program answers
correctly in a single attempt. By default this is measured on **empty patterns**
(no letters revealed) — the hardest setting and the one we care about most.

The metric (`program.one_shot_metric`) is a normalised exact match
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

Reads `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`. The compiled program
is written to `--output` (default `optimized_word_solver.json`) and the optimised
instruction is printed so it can be copied into `prompts.WORD_SOLVER_SYSTEM`.

## Notes

- DSPy recommends ~50–500 examples. The training set is the scraped **history**,
  which grows every week, so optimization quality improves over time.
- `--auto light|medium|heavy` trades cost for search depth (even `light` makes
  many LLM calls).
- This was validated for import/API correctness against DSPy 3.x; an actual
  optimization run needs working `OPENAI_*` credentials.
