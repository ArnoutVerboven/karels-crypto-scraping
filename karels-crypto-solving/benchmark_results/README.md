# benchmark_results

Output of `karels-crypto-benchmark` — a comparison of OpenAI chat models on
Karel's Crypto word solving. Committed so results live in the repo.

| File | Contents |
| ---- | -------- |
| `benchmark.json` | Run config + per-model `{accuracy, correct, total, errors, prompt_tokens, completion_tokens, elapsed_s, est_cost_usd}`. |
| `benchmark.md` | Human-readable table, sorted by accuracy. |

Each model solves the **same** sampled clues (seeded) for a fair comparison.
Cost is estimated from `pricing.py` (input + output tokens). Models that error
out (e.g. not enabled on your gateway) are reported with an `errors` count and a
`last_error` rather than aborting the whole run.
