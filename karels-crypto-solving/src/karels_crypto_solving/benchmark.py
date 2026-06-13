"""Compare OpenAI chat models on Karel's Crypto word solving.

Runs the (prompt-only) word solver across several models on the same set of
clues and reports zero-shot accuracy, token usage and estimated cost per model.

    karels-crypto-benchmark --limit 20
    karels-crypto-benchmark --models gpt-4o-mini gpt-4o o3 --limit 30
    karels-crypto-benchmark --all-models --reveal all

Artifacts are written to ``benchmark_results/`` (``benchmark.json`` +
``benchmark.md``). Uses OPENAI_API_KEY / OPENAI_BASE_URL (a local ``.env`` is
loaded automatically).
"""

from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import config, data, pricing
from .patterns import build_pattern
from .word_solver import solve_word

_MODULE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = _MODULE_ROOT / "benchmark_results"

# A representative spread of "main" models across generations. Override with
# --models, or use --all-models for everything in the pricing table.
DEFAULT_MODELS = [
    "gpt-3.5-turbo",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4.5-preview",
    "o4-mini",
    "o3",
    "gpt-5-mini-2025-08-07",
    "gpt-5-2025-08-07",
    "gpt-5.1-2025-11-13",
    "gpt-5.2-2025-12-11",
    "gpt-5.4-2026-03-05",
    "gpt-5.5-2026-04-23",
]

ALL_MODELS = sorted(pricing.PRICING)


@dataclass
class ModelResult:
    model: str
    correct: int
    total: int
    errors: int
    prompt_tokens: int
    completion_tokens: int
    elapsed_s: float
    accuracy: float
    est_cost_usd: float | None
    last_error: str | None = None


def sample_clues(limit: int | None, reveal: str, reveal_fraction: float, seed: int):
    """Return a fixed list of ``(cryptogram, length, pattern, solution)``."""
    items = list(data.iter_solved_words(data.load_history()))
    rng = random.Random(seed)
    rng.shuffle(items)
    if limit:
        items = items[:limit]
    pattern_rng = random.Random(seed)
    clues = []
    for _puzzle, _index, word in items:
        pattern = build_pattern(word, reveal, fraction=reveal_fraction, rng=pattern_rng)
        clues.append((word.cryptogram, word.length, pattern, word.solution.lower()))
    return clues


def benchmark_model(
    model, clues, *, client, max_completion_tokens, solve_fn=solve_word
) -> ModelResult:
    correct = errors = prompt_tokens = completion_tokens = 0
    last_error = None
    start = time.perf_counter()
    for cryptogram, length, pattern, solution in clues:
        try:
            result = solve_fn(
                cryptogram,
                length,
                pattern,
                client=client,
                model=model,
                max_completion_tokens=max_completion_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - one bad model shouldn't abort the run
            errors += 1
            last_error = str(exc)
            continue
        prompt_tokens += result.prompt_tokens
        completion_tokens += result.completion_tokens
        if result.answer == solution:
            correct += 1
    elapsed = time.perf_counter() - start

    total = len(clues)
    return ModelResult(
        model=model,
        correct=correct,
        total=total,
        errors=errors,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        elapsed_s=round(elapsed, 2),
        accuracy=(correct / total) if total else 0.0,
        est_cost_usd=pricing.estimate_cost(model, prompt_tokens, completion_tokens),
        last_error=last_error,
    )


def run_benchmark(
    models,
    *,
    limit=20,
    reveal="none",
    reveal_fraction=0.5,
    seed=0,
    max_completion_tokens=None,
    client=None,
    solve_fn=solve_word,
) -> list[ModelResult]:
    clues = sample_clues(limit, reveal, reveal_fraction, seed)
    client = client or config.openai_client()
    results = []
    for model in models:
        print(f"Benchmarking {model} on {len(clues)} clues ...", flush=True)
        result = benchmark_model(
            model,
            clues,
            client=client,
            max_completion_tokens=max_completion_tokens,
            solve_fn=solve_fn,
        )
        note = f" (errors: {result.errors})" if result.errors else ""
        cost = f"${result.est_cost_usd:.4f}" if result.est_cost_usd is not None else "n/a"
        print(
            f"  {model}: {result.accuracy:.1%} "
            f"({result.correct}/{result.total}), cost {cost}{note}"
        )
        results.append(result)
    return results


def render_markdown(results: list[ModelResult], config_info: dict) -> str:
    rows = sorted(results, key=lambda r: r.accuracy, reverse=True)
    lines = [
        "# Model comparison: Karel's Crypto word solving",
        "",
        f"- clues: {config_info['n_clues']} (reveal={config_info['reveal']})",
        f"- generated: {config_info['timestamp']}",
        "",
        "| Model | Accuracy | Correct/Total | Errors | Est. cost (USD) | Tokens in/out |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in rows:
        cost = f"${r.est_cost_usd:.4f}" if r.est_cost_usd is not None else "n/a"
        lines.append(
            f"| {r.model} | {r.accuracy:.1%} | {r.correct}/{r.total} | {r.errors} | "
            f"{cost} | {r.prompt_tokens}/{r.completion_tokens} |"
        )
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    models = ALL_MODELS if args.all_models else (args.models or DEFAULT_MODELS)
    results = run_benchmark(
        models,
        limit=args.limit,
        reveal=args.reveal,
        reveal_fraction=args.reveal_fraction,
        seed=args.seed,
        max_completion_tokens=args.max_tokens,
    )

    results_dir = Path(args.output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    config_info = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "n_clues": results[0].total if results else 0,
        "limit": args.limit,
        "reveal": args.reveal,
        "reveal_fraction": args.reveal_fraction,
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "models": models,
    }
    payload = {"config": config_info, "results": [asdict(r) for r in results]}
    (results_dir / "benchmark.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (results_dir / "benchmark.md").write_text(
        render_markdown(results, config_info), encoding="utf-8"
    )
    print(f"\nSaved benchmark to {results_dir}/benchmark.json and benchmark.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare OpenAI models on Karel's Crypto.")
    parser.add_argument("--models", nargs="*", default=None, help="Model ids to compare.")
    parser.add_argument("--all-models", action="store_true", help="Use every priced model.")
    parser.add_argument("--limit", type=int, default=20, help="Clues per model.")
    parser.add_argument("--reveal", choices=["none", "partial", "all"], default="none")
    parser.add_argument("--reveal-fraction", type=float, default=0.5)
    parser.add_argument(
        "--max-tokens", type=int, default=None,
        help="max_completion_tokens per call (caps cost; leave room for reasoning models).",
    )
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=str(DEFAULT_RESULTS_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    config.load_env()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
