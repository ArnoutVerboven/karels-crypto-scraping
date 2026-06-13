# optimization_results

Artifacts produced by `karels-crypto-optimize` (the DSPy word-solver prompt
optimization). These are committed so the optimised prompt and its metrics live
in the repo.

After a run you'll find:

| File | Contents |
| ---- | -------- |
| `optimized_prompt.txt` | The optimised instruction — copy it into `prompts.WORD_SOLVER_SYSTEM` (or load the program below). |
| `optimized_word_solver.json` | The full compiled DSPy program (instruction + any demos), loadable with `dspy`. |
| `metrics.json` | Run config, baseline vs. optimized zero-shot accuracy, best validation score, total LM calls, and the per-trial **training curve**. |

`metrics.json -> training_curve` is a list of `{trial, minibatch_score,
full_eval_score, eval_calls_so_far}` entries — plot `full_eval_score` (or
`minibatch_score`) against `trial` to see optimization progress.

DSPy's raw per-trial dumps go to `dspy_logs/` (git-ignored).
