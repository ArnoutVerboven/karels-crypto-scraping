# optimization — DSPy prompt optimization for the word solver

Supervised optimization of the **word-solver prompt** using [DSPy](https://dspy.ai),
with the scraped solutions as labels. Three techniques are selectable with
`--optimizer`: `mipro` (default), `copro`, `gepa`.

## Goal / loss

Maximise **zero-shot accuracy**: the fraction of clues answered correctly with no
few-shot examples (the model may still reason/think). Measured by default on
**empty patterns** (no letters revealed) — the hardest setting.

The metric `program.exact_match_metric(example, pred, trace=None) -> bool` is a
normalised exact match (used by MIPROv2/COPRO). GEPA uses
`program.gepa_feedback_metric`, which returns `dspy.Prediction(score, feedback)`.

## How instruction candidates are generated

DSPy separates a **Signature** (typed inputs/outputs + an instruction docstring —
this *is* the starting prompt) from a **Module** (`ChainOfThought`, so the model
reasons before answering). All three optimizers **use an LLM to write new
instruction candidates**, but differently:

### MIPROv2 (`--optimizer mipro`)
A **proposer LM** (`GroundedProposer`) writes `num_candidates` instruction
candidates up front, grounding each in: (1) an LLM-generated **summary of the
training data**, (2) a **summary of your program/signature** (so the *starting
prompt and field descriptions matter* — they're fed in as grounding), (3) some
bootstrapped example input/outputs, and (4) a randomly sampled **"tip"** (e.g.
"be creative", "be concise"). Then **Bayesian optimization** searches
instruction (× demo) combinations, scoring each on the metric over a minibatch of
the valset.

### COPRO (`--optimizer copro`)
**Coordinate ascent / hill-climbing.** A proposer LM (signature
`BasicGenerateInstruction`) takes the *current* instruction and proposes
`--breadth` rewrites; each is scored on the trainset; the best becomes the seed
for the next of `--depth` rounds. Less data-aware than MIPROv2 — it leans on the
current instruction, so the **starting prompt matters even more**.

### GEPA (`--optimizer gepa`)
**Reflective evolution.** A **reflection LM** reads a minibatch of *failing*
traces (inputs, outputs, and the **textual feedback** your metric returns) and
diagnoses *why* they failed, then proposes a targeted instruction edit; a
Pareto-frontier keeps the best candidates. Sample-efficient and the natural place
to **inject domain knowledge** (via the feedback string).

### Which LM, and can I configure it?

| | task LM (scoring) | proposer/reflection LM |
| --- | --- | --- |
| mipro | `--model` | `--prompt-model` (default = task LM) |
| copro | `--model` | `--prompt-model` (default = task LM) |
| gepa  | `--model` | `--reflection-model` (default = task LM; use a **strong** one) |

The task LM is the model under test; the proposer/reflection LM writes the
prompts. They can differ — a common pattern is a cheap task model + a strong
proposer/reflection model. Their meta-prompts are DSPy-internal (e.g.
`GroundedProposer`, `BasicGenerateInstruction`); you influence them indirectly
(see below) rather than rewriting them here.

## Injecting your own domain knowledge

Three supported ways:

1. **Edit the starting prompt** — the `SolveCryptogram` docstring and field
   descriptions in [`program.py`](./program.py). This seeds COPRO, is grounding
   for MIPROv2, and is GEPA's starting point.
2. **`--seed-instruction "..."`** — override the starting instruction at runtime
   without editing code (handy for A/B-ing your own prompt).
3. **GEPA feedback** — edit `program.WRONG_ANSWER_FEEDBACK` (passed verbatim to
   the reflection LM for every wrong answer). This is the richest channel: tell
   it which cryptic devices to consider, common Flemish pitfalls, etc.

Does the starting prompt matter? Yes — most for COPRO (it mutates it directly),
meaningfully for GEPA (start point + feedback), and least for MIPROv2 (it grounds
proposals in data/program but explores broadly).

## Run

```bash
uv sync --extra optimize          # installs DSPy (+ optuna for MIPROv2)

# default: MIPROv2, hardest setting (no letters)
karels-crypto-optimize --optimizer mipro --auto light --reveal none

# COPRO with a strong proposer model
karels-crypto-optimize --optimizer copro --breadth 8 --depth 3 --prompt-model gpt-5-2025-08-07

# GEPA with a strong reflection model and low-effort task model
karels-crypto-optimize --optimizer gepa --model gpt-5-mini-2025-08-07 \
    --reasoning-effort low --reflection-model gpt-5-2025-08-07 --auto light

# inject your own starting prompt
karels-crypto-optimize --seed-instruction "Je lost een Vlaams cryptogram op ..."
```

Reads `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` (a local `.env` is
loaded automatically — see [`../../.env.example`](../../.env.example)).

## Where results are stored

Per technique, under `../../optimization_results/<optimizer>/`:

- `optimized_prompt.txt` — the optimised instruction (copy into
  `prompts.WORD_SOLVER_SYSTEM`, or load the program).
- `optimized_word_solver.json` — the full compiled DSPy program.
- `metrics.json` — config, baseline vs optimized accuracy, best score, total LM
  calls, and (MIPROv2) the per-trial **training curve**.

So `mipro/`, `copro/`, `gepa/` results sit side by side for comparison. Override
with `--output-dir`.

### GitHub Actions

Set `OPENAI_API_KEY` (secret), `OPENAI_BASE_URL` (variable) and optionally
`OPENAI_MODEL` (variable), then run the **optimize** workflow and pick the
`optimizer` from the dropdown. It commits `optimization_results/<optimizer>/`.

## Cost / budget knobs

There is **no built-in hard token/spend cap** in DSPy — bound cost via search
size, dataset size and per-call tokens:

| Flag | Applies to | Controls |
| --- | --- | --- |
| `--auto light\|medium\|heavy\|none` | mipro, gepa | overall search budget (biggest lever) |
| `--num-candidates` / `--num-trials` | mipro (`--auto none`) | manual search size |
| `--breadth` / `--depth` | copro | candidates per round / rounds |
| `--init-temperature` | copro | proposal diversity |
| `--reflection-minibatch-size` | gepa | failures analysed per reflection |
| `--minibatch` / `--minibatch-size` | mipro | eval cost per trial |
| `--max-tokens` | all | output tokens per task-LM call |
| `--reasoning-effort` | all (reasoning models) | thinking budget (`low` = cheap) |
| `--num-threads` | all | parallelism (speed) |
| `--max-examples` | all | cap labelled words used |
| `--demos` | mipro | few-shot demos (0 = instruction-only) |

The chosen config is recorded in `metrics.json -> config`; MIPROv2's actual call
count is in `total_lm_calls`.

## Notes

- DSPy recommends ~50–500 examples; the history dataset grows weekly.
- Reasoning models (gpt-5 / o-series) are auto-configured (temperature=1.0,
  `max_tokens ≥ 16000`); set `--reasoning-effort low` to keep them cheap/fast.
- Optimizer APIs validated against DSPy 3.x; real runs need working `OPENAI_*`.
