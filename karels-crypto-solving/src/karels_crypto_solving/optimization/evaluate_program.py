"""Evaluate a word-solver program (baseline or optimized) on a chosen model.

Used for the research experiments: cross-model capability, and transferring an
optimized prompt from a small model to a large one. Dumps per-word predictions
so failure analysis can run on them.

    # baseline (basic prompt) on gpt-5-mini, whole set
    karels-crypto-eval --model gpt-5-mini-2025-08-07 --split all --output preds.json
    # an optimized program transferred to gpt-5.5, on the held-out val split
    karels-crypto-eval --program optimization_results/gepa/optimized_word_solver.json \
        --model gpt-5.5-2026-04-23 --split val --output transfer.json
"""

from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .. import config
from .optimize import build_examples, make_lm
from .program import build_program, normalise

logger = logging.getLogger(__name__)


def val_split(examples: list, val_fraction: float) -> list:
    split = max(1, int(len(examples) * (1 - val_fraction)))
    return examples[split:] or examples[:1]


def evaluate_with_predictions(program, examples, num_threads: int) -> list[dict]:
    def one(ex) -> dict:
        pred = program(cryptogram=ex.cryptogram, pattern=ex.pattern)
        raw = getattr(pred, "solution", "") or ""
        return {
            "cryptogram": ex.cryptogram,
            "pattern": ex.pattern,
            "expected": ex.solution,
            "predicted": raw,
            "normalised": normalise(raw),
            "correct": normalise(raw) == normalise(ex.solution),
        }

    if num_threads and num_threads > 1:
        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            return list(pool.map(one, examples))
    return [one(ex) for ex in examples]


def run(args: argparse.Namespace) -> int:
    import dspy

    model = args.model or config.model_name()
    dspy.configure(lm=make_lm(
        model, max_tokens=args.max_tokens, reasoning_effort=args.reasoning_effort,
    ))

    program = build_program()
    if args.program:
        program.load(args.program)

    examples = build_examples(
        args.reveal, args.reveal_fraction, args.seed, None,
        include_ingested=not args.no_ingested,
    )
    if args.split == "val":
        examples = val_split(examples, args.val_fraction)
    if args.limit:
        examples = examples[: args.limit]

    preds = evaluate_with_predictions(program, examples, args.num_threads)
    correct = sum(p["correct"] for p in preds)
    accuracy = correct / len(preds) if preds else 0.0

    payload = {
        "model": model,
        "program": args.program,
        "split": args.split,
        "n": len(preds),
        "correct": correct,
        "accuracy": accuracy,
        "predictions": preds,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{model} (program={args.program or 'baseline'}, n={len(preds)}): "
          f"{accuracy:.1%} -> {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate a word-solver program on a model.")
    parser.add_argument("--program", default=None, help="Saved DSPy program (omit for baseline).")
    parser.add_argument("--model", default=None)
    parser.add_argument("--reasoning-effort", choices=["minimal", "low", "medium", "high"],
                        default=None)
    parser.add_argument("--max-tokens", type=int, default=2000)
    parser.add_argument("--num-threads", type=int, default=16)
    parser.add_argument("--split", choices=["all", "val"], default="val",
                        help="Evaluate the whole set or just the held-out val split.")
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--reveal", choices=["none", "partial", "all"], default="none")
    parser.add_argument("--reveal-fraction", type=float, default=0.5)
    parser.add_argument("--no-ingested", action="store_true")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config.load_env()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
