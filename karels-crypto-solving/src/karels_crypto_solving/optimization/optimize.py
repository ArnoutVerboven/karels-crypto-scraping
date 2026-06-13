"""Optimize the word-solver prompt with DSPy / MIPROv2.

Supervised prompt optimization: we treat the scraped solutions as labels and
maximise *zero-shot accuracy* (the fraction of clues the program answers
correctly with no few-shot examples; the model may still reason/think). By
default we optimise the **instruction only** (0 few-shot demos) on **empty
patterns** (no letter hints), matching the hardest setup. If that proves too
hard, reveal some/all helper letters with ``--reveal``.

Run:

    uv sync --extra optimize
    karels-crypto-optimize --auto light --reveal none

Requires OPENAI_API_KEY / OPENAI_BASE_URL (and optionally OPENAI_MODEL).

Artifacts (committed to the repo) are written to ``optimization_results/`` next
to the solving package:

* ``optimized_prompt.txt``      - the optimised instruction (copy into prompts).
* ``optimized_word_solver.json``- the full compiled DSPy program.
* ``metrics.json``              - config, baseline/optimized accuracy and the
                                  per-trial score curve (for plotting).
"""

from __future__ import annotations

import argparse
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

from .. import config, data
from ..patterns import build_pattern
from .program import build_program, exact_match_metric, normalise

# <module root>/optimization_results (module root = karels-crypto-solving/).
_MODULE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = _MODULE_ROOT / "optimization_results"


def _configure_lm(model: str | None) -> None:
    import dspy

    lm = dspy.LM(
        f"openai/{model or config.model_name()}",
        api_key=os.environ.get("OPENAI_API_KEY"),
        api_base=os.environ.get("OPENAI_BASE_URL"),
    )
    dspy.configure(lm=lm)


def build_examples(reveal: str, fraction: float, seed: int) -> list:
    """Build DSPy examples (cryptogram + pattern -> solution) from history."""
    import dspy

    rng = random.Random(seed)
    examples = []
    for _puzzle, _index, word in data.iter_solved_words(data.load_history()):
        pattern = build_pattern(word, reveal, fraction=fraction, rng=rng)
        examples.append(
            dspy.Example(
                cryptogram=word.cryptogram,
                pattern=pattern,
                solution=word.solution.lower(),
            ).with_inputs("cryptogram", "pattern")
        )
    rng.shuffle(examples)
    return examples


def evaluate(program, examples) -> float:
    """Return zero-shot accuracy of ``program`` over ``examples``."""
    if not examples:
        return 0.0
    hits = 0
    for ex in examples:
        pred = program(cryptogram=ex.cryptogram, pattern=ex.pattern)
        hits += normalise(getattr(pred, "solution", "")) == normalise(ex.solution)
    return hits / len(examples)


def extract_instruction(program) -> str:
    predictor = next(iter(program.predictors()))
    return predictor.signature.instructions


def training_curve(compiled) -> list[dict]:
    """JSON-safe per-trial score curve from MIPROv2's trial_logs."""
    logs = getattr(compiled, "trial_logs", {}) or {}
    curve = []
    for trial in sorted(logs):
        entry = logs[trial]
        curve.append(
            {
                "trial": trial,
                "minibatch_score": entry.get("mb_score"),
                "full_eval_score": entry.get("full_eval_score"),
                "eval_calls_so_far": entry.get("total_eval_calls_so_far"),
            }
        )
    return curve


def run(args: argparse.Namespace) -> int:
    from dspy.teleprompt import MIPROv2

    _configure_lm(args.model)

    results_dir = Path(args.output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    examples = build_examples(args.reveal, args.reveal_fraction, args.seed)
    if not examples:
        print("No labelled words available; scrape some history first.")
        return 1

    split = max(1, int(len(examples) * (1 - args.val_fraction)))
    trainset, valset = examples[:split], examples[split:] or examples[:1]
    print(f"{len(examples)} examples ({len(trainset)} train / {len(valset)} val), "
          f"reveal={args.reveal}")

    program = build_program()
    baseline = evaluate(program, valset)
    print(f"Baseline zero-shot accuracy (val): {baseline:.1%}")

    optimizer = MIPROv2(
        metric=exact_match_metric,
        auto=args.auto,
        # 0 demos => pure instruction (prompt) optimization, no few-shot vocab.
        max_bootstrapped_demos=args.demos,
        max_labeled_demos=args.demos,
        track_stats=True,
        log_dir=str(results_dir / "dspy_logs"),
    )
    compiled = optimizer.compile(
        program,
        trainset=trainset,
        valset=valset,
        requires_permission_to_run=False,
    )

    optimized = evaluate(compiled, valset)
    print(f"Optimized zero-shot accuracy (val): {optimized:.1%}")

    instruction = extract_instruction(compiled)
    program_path = results_dir / "optimized_word_solver.json"
    prompt_path = results_dir / "optimized_prompt.txt"
    metrics_path = results_dir / "metrics.json"

    compiled.save(str(program_path))
    prompt_path.write_text(instruction + "\n", encoding="utf-8")

    metrics = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "model": args.model or config.model_name(),
            "auto": args.auto,
            "demos": args.demos,
            "reveal": args.reveal,
            "reveal_fraction": args.reveal_fraction,
            "val_fraction": args.val_fraction,
            "seed": args.seed,
            "n_examples": len(examples),
            "n_train": len(trainset),
            "n_val": len(valset),
        },
        "baseline_accuracy": baseline,
        "optimized_accuracy": optimized,
        "best_val_score": getattr(compiled, "score", None),
        "total_lm_calls": getattr(compiled, "total_calls", None),
        "training_curve": training_curve(compiled),
    }
    metrics_path.write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"\nSaved artifacts to {results_dir}:")
    print(f"  - {prompt_path.name}      (optimized instruction)")
    print(f"  - {program_path.name} (compiled DSPy program)")
    print(f"  - {metrics_path.name}        (metrics + training curve)")
    print("\nOptimized instruction:\n" + instruction)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Optimize the word-solver prompt with DSPy.")
    parser.add_argument("--model", default=None, help="Override OPENAI_MODEL.")
    parser.add_argument(
        "--auto", choices=["light", "medium", "heavy"], default="light",
        help="MIPROv2 search budget.",
    )
    parser.add_argument(
        "--demos", type=int, default=0,
        help="Max few-shot demos (0 = instruction-only prompt optimization).",
    )
    parser.add_argument(
        "--reveal", choices=["none", "partial", "all"], default="none",
        help="Helper letters revealed in the pattern (none = hardest).",
    )
    parser.add_argument("--reveal-fraction", type=float, default=0.5)
    parser.add_argument("--val-fraction", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument(
        "--output-dir", default=str(DEFAULT_RESULTS_DIR),
        help="Directory for the prompt / program / metrics artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
