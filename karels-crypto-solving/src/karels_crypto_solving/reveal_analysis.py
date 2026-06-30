"""Letter-reveal difficulty sweep for the single-word solver.

How much does revealing some of a word's letters help, and how does that
interact with word length? The source puzzles' grid key (which cells are legally
revealable) is mostly unavailable, so we **randomize** which letters are
revealed: per word we fix a random permutation of positions and, for each reveal
*fraction*, uncover the first ``round(fraction * length)`` of them (nested, so
more reveal is always a superset). Each word is solved at every reveal level by
every model, giving a within-word comparison.

Output (``research/reveal/``): ``reveal_analysis.json`` + ``reveal_analysis.md``
with accuracy as a length-bucket x reveal-fraction grid per model.

    karels-crypto-reveal-analysis --models gpt-5-mini-2025-08-07 gpt-4.1 \
        --per-bucket 30 --fractions 0 0.25 0.5 0.75

OpenAI-only by default; uses OPENAI_API_KEY / OPENAI_BASE_URL.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import config, data, pricing
from .models import BLANK, Word
from .providers import ProviderError
from .word_solver import solve_word

logger = logging.getLogger(__name__)

_MODULE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = _MODULE_ROOT / "research" / "reveal"
_SKIP_STATUS = {403, 404, 408, 409, 429, 500, 502, 503, 504, None}

# Same buckets as the length analysis (REPORT §2) for comparability.
_BUCKETS: list[tuple[int, int, str]] = [
    (3, 4, "3-4"),
    (5, 6, "5-6"),
    (7, 8, "7-8"),
    (9, 10, "9-10"),
    (11, 999, "11+"),
]
DEFAULT_MODELS = ["gpt-5-mini-2025-08-07", "gpt-5-2025-08-07", "gpt-4.1"]


def bucket_of(length: int) -> str:
    for lo, hi, label in _BUCKETS:
        if lo <= length <= hi:
            return label
    return "3-4" if length < 3 else "11+"


def sample_words(per_bucket: int, seed: int) -> list[Word]:
    """Stratified sample: up to ``per_bucket`` solved words per length bucket."""
    words = [w for _, _, w in data.iter_solved_words(data.load_history() + data.load_ingested())]
    # De-duplicate identical clue/answer pairs.
    seen, unique = set(), []
    for w in words:
        key = (w.cryptogram, (w.solution or "").lower())
        if w.solution and len(w.solution) == w.length and key not in seen:
            seen.add(key)
            unique.append(w)
    by_bucket: dict[str, list[Word]] = defaultdict(list)
    for w in unique:
        by_bucket[bucket_of(w.length)].append(w)
    rng = random.Random(seed)
    chosen: list[Word] = []
    for _, _, label in _BUCKETS:
        lst = by_bucket.get(label, [])
        rng.shuffle(lst)
        chosen.extend(lst[:per_bucket])
    return chosen


def _permutation(word: Word, seed: int) -> list[int]:
    # Seed per word so the revealed positions are stable and reproducible.
    rng = random.Random(f"{seed}|{word.cryptogram}|{word.solution}")
    positions = list(range(word.length))
    rng.shuffle(positions)
    return positions


def reveal_pattern(word: Word, perm: list[int], k: int) -> str:
    """Reveal ``k`` letters of ``word`` at the first ``k`` permuted positions."""
    letters = [BLANK] * word.length
    solution = (word.solution or "").lower()
    for pos in perm[:k]:
        if pos < len(solution):
            letters[pos] = solution[pos]
    return "".join(letters)


def _reveal_count(length: int, fraction: float) -> int:
    # Always leave at least one unknown letter so it stays a solve task.
    return max(0, min(round(fraction * length), length - 1))


def evaluate_model(
    model: str,
    words: list[Word],
    fractions: list[float],
    *,
    reasoning_effort: str | None,
    seed: int,
    num_threads: int,
) -> dict:
    tasks = []
    for word in words:
        perm = _permutation(word, seed)
        for fraction in fractions:
            k = _reveal_count(word.length, fraction)
            tasks.append((word, fraction, reveal_pattern(word, perm, k)))

    def attempt(task):
        word, fraction, pattern = task
        try:
            sol = solve_word(
                word.cryptogram,
                word.length,
                pattern,
                model=model,
                reasoning_effort=reasoning_effort,
            )
        except ProviderError as exc:
            if exc.status_code not in _SKIP_STATUS:
                raise
            logger.warning("Skip %s (%s): %s", model, exc.status_code, exc)
            return None
        correct = sol.answer == (word.solution or "").lower()
        return (fraction, bucket_of(word.length), correct, sol.prompt_tokens, sol.completion_tokens)

    if num_threads and num_threads > 1:
        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            outcomes = list(pool.map(attempt, tasks))
    else:
        outcomes = [attempt(t) for t in tasks]

    by_frac: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
    by_cell: dict[str, dict] = defaultdict(lambda: {"correct": 0, "total": 0})
    prompt_tokens = completion_tokens = errors = 0
    for outcome in outcomes:
        if outcome is None:
            errors += 1
            continue
        fraction, bucket, correct, p_tok, c_tok = outcome
        prompt_tokens += p_tok
        completion_tokens += c_tok
        fkey = f"{fraction:g}"
        ckey = f"{bucket}@{fkey}"
        for store, key in ((by_frac, fkey), (by_cell, ckey)):
            store[key]["total"] += 1
            store[key]["correct"] += int(correct)

    for store in (by_frac, by_cell):
        for stats in store.values():
            stats["accuracy"] = stats["correct"] / stats["total"] if stats["total"] else 0.0

    return {
        "model": model,
        "n_words": len(words),
        "fractions": fractions,
        "reasoning_effort": reasoning_effort,
        "errors": errors,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "est_cost_usd": pricing.estimate_cost(model, prompt_tokens, completion_tokens),
        "by_fraction": dict(by_frac),
        "by_cell": dict(by_cell),
    }


def render_markdown(report: dict) -> str:
    fractions = report["config"]["fractions"]
    cols = [f"{f:g}" for f in fractions]
    header = "| length \\ reveal | " + " | ".join(f"{int(f * 100)}%" for f in fractions) + " |"
    sep = "| --- | " + " | ".join(["---:"] * len(fractions)) + " |"
    lines = ["# Letter-reveal sweep (randomized reveals, by word length)", ""]
    lines.append(
        "Reveal = fraction of letters uncovered at random positions (nested). "
        "Each cell = accuracy; `n` per (length x reveal) cell is roughly per-bucket size."
    )
    for m in report["models"]:
        cost = m.get("est_cost_usd")
        cost_s = f"${cost:.2f}" if cost is not None else "n/a"
        lines += [
            "",
            f"### {m['model']} (n={m['n_words']}, effort={m['reasoning_effort']}, cost {cost_s})",
            "",
            header,
            sep,
        ]
        for _, _, label in _BUCKETS:
            cells = []
            for c in cols:
                stats = m["by_cell"].get(f"{label}@{c}")
                cells.append(f"{stats['accuracy']:.0%}" if stats and stats["total"] else "-")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        overall = []
        for c in cols:
            stats = m["by_fraction"].get(c)
            overall.append(f"{stats['accuracy']:.0%}" if stats and stats["total"] else "-")
        lines.append("| **overall** | " + " | ".join(overall) + " |")
    lines.append("")
    total_cost = sum((m.get("est_cost_usd") or 0.0) for m in report["models"])
    lines.append(f"Total estimated cost: ${total_cost:.2f}")
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    words = sample_words(args.per_bucket, args.seed)
    logger.info("Sampled %d words across %d buckets", len(words), len(_BUCKETS))
    models = []
    for model in args.models:
        logger.info("Evaluating %s ...", model)
        result = evaluate_model(
            model,
            words,
            args.fractions,
            reasoning_effort=args.reasoning_effort,
            seed=args.seed,
            num_threads=args.num_threads,
        )
        cost = result["est_cost_usd"]
        logger.info("  %s done (cost %s)", model, f"${cost:.2f}" if cost is not None else "n/a")
        models.append(result)

    report = {
        "config": {
            "per_bucket": args.per_bucket,
            "fractions": args.fractions,
            "seed": args.seed,
            "reasoning_effort": args.reasoning_effort,
            "models": args.models,
        },
        "models": models,
    }
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "reveal_analysis.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    md = render_markdown(report)
    (out_dir / "reveal_analysis.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"Saved to {out_dir}/reveal_analysis.json and reveal_analysis.md")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Letter-reveal difficulty sweep (by word length).")
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS, help="OpenAI model ids.")
    parser.add_argument(
        "--per-bucket", type=int, default=30, help="Words sampled per length bucket."
    )
    parser.add_argument(
        "--fractions", nargs="*", type=float, default=[0.0, 0.25, 0.5, 0.75],
        help="Reveal fractions to sweep.",
    )
    parser.add_argument(
        "--reasoning-effort", choices=["minimal", "low", "medium", "high"], default="low"
    )
    parser.add_argument("--num-threads", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config.load_env()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
