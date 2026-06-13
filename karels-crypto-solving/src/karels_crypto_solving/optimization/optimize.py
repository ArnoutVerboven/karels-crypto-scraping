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
"""

from __future__ import annotations

import argparse
import os
import random

from .. import config, data
from ..patterns import build_pattern
from .program import build_program, exact_match_metric, normalise


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


def run(args: argparse.Namespace) -> int:
    from dspy.teleprompt import MIPROv2

    _configure_lm(args.model)

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
    )
    compiled = optimizer.compile(
        program,
        trainset=trainset,
        valset=valset,
        requires_permission_to_run=False,
    )

    optimized = evaluate(compiled, valset)
    print(f"Optimized zero-shot accuracy (val): {optimized:.1%}")

    compiled.save(args.output)
    print(f"Saved optimized program to {args.output}")

    # Surface the optimised instruction so it can be reused as the solver prompt.
    try:
        predictor = next(iter(compiled.predictors()))
        print("\nOptimized instruction:\n" + predictor.signature.instructions)
    except Exception as exc:  # noqa: BLE001
        print(f"(could not extract instruction: {exc})")
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
        "--output", default="optimized_word_solver.json",
        help="Where to save the compiled DSPy program.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
