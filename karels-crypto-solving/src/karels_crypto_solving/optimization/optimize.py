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


def _configure_lm(
    model: str | None,
    max_tokens: int,
    temperature: float | None,
    reasoning_effort: str | None = None,
) -> None:
    import dspy

    model_id = model or config.model_name()
    kwargs = {"max_tokens": max_tokens}
    # Reasoning models (gpt-5 family, o-series) require temperature=1.0 and a
    # large token budget, otherwise the reply comes back empty.
    if config.is_reasoning_model(model_id):
        temperature = 1.0
        kwargs["max_tokens"] = max(max_tokens or 0, config.REASONING_MIN_MAX_TOKENS)
        if reasoning_effort:
            # Forwarded to the OpenAI API via litellm; caps how much the model
            # "thinks" (low = cheaper/faster).
            kwargs["reasoning_effort"] = reasoning_effort
    if temperature is not None:
        kwargs["temperature"] = temperature
    lm = dspy.LM(
        f"openai/{model_id}",
        api_key=os.environ.get("OPENAI_API_KEY"),
        api_base=os.environ.get("OPENAI_BASE_URL"),
        **kwargs,
    )
    dspy.configure(lm=lm)


def build_examples(reveal: str, fraction: float, seed: int, max_examples: int | None) -> list:
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
    if max_examples:
        examples = examples[:max_examples]
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

    _configure_lm(args.model, args.max_tokens, args.temperature, args.reasoning_effort)

    results_dir = Path(args.output_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    examples = build_examples(
        args.reveal, args.reveal_fraction, args.seed, args.max_examples
    )
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

    manual = args.auto == "none"
    optimizer_kwargs = {
        "metric": exact_match_metric,
        # 0 demos => pure instruction (prompt) optimization, no few-shot vocab.
        "max_bootstrapped_demos": args.demos,
        "max_labeled_demos": args.demos,
        "num_threads": args.num_threads,
        "track_stats": True,
        "log_dir": str(results_dir / "dspy_logs"),
    }
    if args.max_errors is not None:
        optimizer_kwargs["max_errors"] = args.max_errors
    if manual:
        # Manual budget: you control the search size explicitly.
        optimizer_kwargs["auto"] = None
        optimizer_kwargs["num_candidates"] = args.num_candidates or 5
    else:
        optimizer_kwargs["auto"] = args.auto
    optimizer = MIPROv2(**optimizer_kwargs)

    # minibatch_size must not exceed the validation set size.
    minibatch_size = min(args.minibatch_size or 35, len(valset))
    compile_kwargs = {
        "trainset": trainset,
        "valset": valset,
        "minibatch": args.minibatch,
        "minibatch_size": minibatch_size,
    }
    if manual:
        compile_kwargs["num_trials"] = args.num_trials or 10
    compiled = optimizer.compile(program, **compile_kwargs)

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
            "num_candidates": args.num_candidates if manual else None,
            "num_trials": args.num_trials if manual else None,
            "minibatch": args.minibatch,
            "minibatch_size": minibatch_size,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "reasoning_effort": args.reasoning_effort,
            "num_threads": args.num_threads,
            "demos": args.demos,
            "reveal": args.reveal,
            "reveal_fraction": args.reveal_fraction,
            "val_fraction": args.val_fraction,
            "max_examples": args.max_examples,
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

    # --- search budget (the main cost knobs) -------------------------------
    budget = parser.add_argument_group("search budget / cost")
    budget.add_argument(
        "--auto", choices=["light", "medium", "heavy", "none"], default="light",
        help="Preset search budget. 'none' = manual (--num-candidates/--num-trials).",
    )
    budget.add_argument(
        "--num-candidates", type=int, default=None,
        help="Instruction candidates to propose (only when --auto none).",
    )
    budget.add_argument(
        "--num-trials", type=int, default=None,
        help="Optimization trials to run (only when --auto none).",
    )
    budget.add_argument(
        "--minibatch", action=argparse.BooleanOptionalAction, default=True,
        help="Evaluate candidates on minibatches (cheaper) vs the full valset.",
    )
    budget.add_argument(
        "--minibatch-size", type=int, default=None,
        help="Minibatch size (clamped to the valset size; default 35).",
    )
    budget.add_argument(
        "--max-tokens", type=int, default=1000,
        help="Max output tokens per LM call (caps token consumption).",
    )
    budget.add_argument("--temperature", type=float, default=None)
    budget.add_argument(
        "--reasoning-effort",
        choices=["minimal", "low", "medium", "high"],
        default=None,
        help="Reasoning budget for reasoning models (low = fast/cheap). Ignored by others.",
    )
    budget.add_argument(
        "--num-threads", type=int, default=1,
        help="Parallel eval threads (speed, not cost).",
    )
    budget.add_argument(
        "--max-errors", type=int, default=None,
        help="Abort after this many failing LM calls.",
    )
    budget.add_argument(
        "--max-examples", type=int, default=None,
        help="Cap the number of labelled words used (cheaper runs).",
    )

    # --- task setup --------------------------------------------------------
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
    config.load_env()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
