# benchmark_results

Output of `karels-crypto-benchmark` — a comparison of OpenAI chat models on
Karel's Crypto word solving. Committed so results live in the repo.

| File | Contents |
| ---- | -------- |
| `benchmark.json` | Run config + per-model `{accuracy, correct, total, errors, prompt_tokens, completion_tokens, elapsed_s, est_cost_usd}`. |
| `benchmark.md` | Human-readable table, sorted by accuracy. |

Each model solves the **same** sampled clues (seeded) for a fair comparison.
Cost is estimated from `pricing.py` (input + output tokens). **Expected** API
errors (a model not enabled on the gateway, rate limits, transient
network/server issues) are logged, counted in `errors`/`last_error`, and skipped.
Anything else - a bad request / wrong parameter (e.g. `max_tokens` too large for
a model), auth failures, or bugs - is left to crash the run so the problem is
surfaced rather than hidden.
