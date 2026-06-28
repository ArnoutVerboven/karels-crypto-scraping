"""Optimize the word-solver prompt with DSPy.

Supervised prompt optimization: we treat the scraped solutions as labels and
maximise *zero-shot accuracy* (the fraction of clues the program answers
correctly with no few-shot examples; the model may still reason/think). By
default we optimise the **instruction only** (0 few-shot demos) on **empty
patterns** (no letter hints), the hardest setup.

Three techniques are selectable with ``--optimizer``:

* ``mipro``  - MIPROv2: a proposer LM writes instruction candidates grounded in
  the data/program/tips; Bayesian search picks the best (default).
* ``copro``  - COPRO: coordinate ascent; a proposer LM rewrites the instruction
  over ``--depth`` rounds, ``--breadth`` candidates each, keeping the best.
* ``gepa``   - GEPA: a reflection LM reads failing traces + the metric's textual
  feedback and proposes targeted instruction edits (Pareto search).

Run:

    uv sync --extra optimize
    karels-crypto-optimize --optimizer mipro --auto light --reveal none

Requires OPENAI_API_KEY / OPENAI_BASE_URL (and optionally OPENAI_MODEL); a local
``.env`` is loaded automatically.

Artifacts are written to ``optimization_results/<optimizer>/`` so techniques can
be compared side by side:

* ``optimized_prompt.txt``       - the optimised instruction.
* ``optimized_word_solver.json`` - the full compiled DSPy program.
* ``metrics.json``               - config, baseline/optimized accuracy, curve.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .. import config, data
from ..patterns import build_pattern
from .program import (
    build_program,
    exact_match_metric,
    gepa_feedback_metric,
    normalise,
)

logger = logging.getLogger(__name__)

# <module root>/optimization_results (module root = karels-crypto-solving/).
_MODULE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_RESULTS_DIR = _MODULE_ROOT / "optimization_results"

# Instructions can be long, so give proposer/reflection LMs a generous budget.
_PROPOSER_MAX_TOKENS = 8000


def make_lm(
    model_id: str,
    *,
    max_tokens: int,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
):
    """Build a dspy.LM, applying reasoning-model requirements automatically."""
    import dspy

    kwargs = {"max_tokens": max_tokens}
    if config.is_reasoning_model(model_id):
        # Reasoning models need temperature=1.0 and a large budget, else empty.
        temperature = 1.0
        kwargs["max_tokens"] = max(max_tokens or 0, config.REASONING_MIN_MAX_TOKENS)
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
    if temperature is not None:
        kwargs["temperature"] = temperature
    return dspy.LM(
        f"openai/{model_id}",
        api_key=os.environ.get("OPENAI_API_KEY"),
        api_base=os.environ.get("OPENAI_BASE_URL"),
        **kwargs,
    )


def build_examples(
    reveal: str,
    fraction: float,
    seed: int,
    max_examples: int | None,
    include_ingested: bool = True,
) -> list:
    """Build DSPy examples (cryptogram + pattern -> solution) from history.

    Also includes puzzles ingested from photos (see ``ingest.py``) unless
    ``include_ingested`` is False.
    """
    import dspy

    puzzles = data.load_history()
    if include_ingested:
        puzzles = puzzles + data.load_ingested()

    rng = random.Random(seed)
    examples = []
    for _puzzle, _index, word in data.iter_solved_words(puzzles):
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


def evaluate(program, examples, num_threads: int = 1) -> float:
    """Return zero-shot accuracy of ``program`` over ``examples`` (optionally parallel)."""
    if not examples:
        return 0.0

    def correct(ex) -> bool:
        pred = program(cryptogram=ex.cryptogram, pattern=ex.pattern)
        return normalise(getattr(pred, "solution", "")) == normalise(ex.solution)

    if num_threads and num_threads > 1:
        with ThreadPoolExecutor(max_workers=num_threads) as pool:
            hits = sum(pool.map(correct, examples))
    else:
        hits = sum(correct(ex) for ex in examples)
    return hits / len(examples)


def extract_instruction(program) -> str:
    predictor = next(iter(program.predictors()))
    return predictor.signature.instructions


def training_curve(compiled) -> list[dict]:
    """JSON-safe per-trial score curve from MIPROv2's trial_logs (if present)."""
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


def _compile_mipro(args, program, trainset, valset, prompt_lm, log_dir):
    from dspy.teleprompt import MIPROv2

    manual = args.auto == "none"
    kwargs = {
        "metric": exact_match_metric,
        "max_bootstrapped_demos": args.demos,
        "max_labeled_demos": args.demos,
        "num_threads": args.num_threads,
        "track_stats": True,
        "log_dir": str(log_dir),
    }
    if prompt_lm is not None:
        kwargs["prompt_model"] = prompt_lm
    if args.max_errors is not None:
        kwargs["max_errors"] = args.max_errors
    if manual:
        kwargs["auto"] = None
        kwargs["num_candidates"] = args.num_candidates or 5
    else:
        kwargs["auto"] = args.auto
    optimizer = MIPROv2(**kwargs)

    minibatch_size = min(args.minibatch_size or 35, len(valset))
    compile_kwargs = {
        "trainset": trainset,
        "valset": valset,
        "minibatch": args.minibatch,
        "minibatch_size": minibatch_size,
    }
    if manual:
        compile_kwargs["num_trials"] = args.num_trials or 10
    return optimizer.compile(program, **compile_kwargs)


def _compile_copro(args, program, trainset, valset, prompt_lm, log_dir):
    from dspy.teleprompt import COPRO

    # COPRO applies init_temperature when the proposer generates candidates;
    # reasoning models only allow temperature=1.0, so clamp it for them.
    proposer_model = args.prompt_model or args.model or config.model_name()
    init_temperature = args.init_temperature
    if config.is_reasoning_model(proposer_model) and init_temperature != 1.0:
        logger.warning(
            "COPRO: proposer %s is a reasoning model; forcing init_temperature=1.0 "
            "(was %s).",
            proposer_model,
            init_temperature,
        )
        init_temperature = 1.0

    kwargs = {
        "metric": exact_match_metric,
        "breadth": args.breadth,
        "depth": args.depth,
        "init_temperature": init_temperature,
        "track_stats": True,
    }
    if prompt_lm is not None:
        kwargs["prompt_model"] = prompt_lm
    optimizer = COPRO(**kwargs)
    eval_kwargs = {"num_threads": args.num_threads, "display_progress": True, "display_table": 0}
    # COPRO re-scores every candidate on its whole devset, so cap it (otherwise
    # breadth*depth * |devset| calls explodes).
    devset = valset[: args.copro_devset_size]
    return optimizer.compile(program, trainset=devset, eval_kwargs=eval_kwargs)


def _compile_gepa(args, program, trainset, valset, reflection_lm, log_dir):
    import dspy

    # Exactly one budget: an explicit iteration/call cap wins over the preset.
    if args.max_metric_calls is not None:
        budget = {"max_metric_calls": args.max_metric_calls}
    elif args.max_full_evals is not None:
        budget = {"max_full_evals": args.max_full_evals}
    else:
        budget = {"auto": args.auto if args.auto != "none" else "light"}

    optimizer = dspy.GEPA(
        metric=gepa_feedback_metric,
        reflection_lm=reflection_lm,
        reflection_minibatch_size=args.reflection_minibatch_size,
        num_threads=args.num_threads,
        track_stats=True,
        log_dir=str(log_dir),
        seed=args.seed,
        **budget,
    )
    return optimizer.compile(program, trainset=trainset, valset=valset)


_COMPILERS = {"mipro": _compile_mipro, "copro": _compile_copro, "gepa": _compile_gepa}


def run(args: argparse.Namespace) -> int:
    import dspy

    task_model = args.model or config.model_name()
    dspy.configure(
        lm=make_lm(
            task_model,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            reasoning_effort=args.reasoning_effort,
        )
    )

    results_dir = Path(args.output_dir) / args.optimizer
    results_dir.mkdir(parents=True, exist_ok=True)

    examples = build_examples(
        args.reveal, args.reveal_fraction, args.seed, args.max_examples, args.ingested
    )
    if not examples:
        print("No labelled words available; scrape some history first.")
        return 1

    split = max(1, int(len(examples) * (1 - args.val_fraction)))
    trainset, valset = examples[:split], examples[split:] or examples[:1]
    print(f"[{args.optimizer}] {len(examples)} examples "
          f"({len(trainset)} train / {len(valset)} val), reveal={args.reveal}")

    program = build_program()
    if args.seed_instruction:
        # Inject your own starting prompt / domain knowledge.
        predictor = program.predictors()[0]
        predictor.signature = predictor.signature.with_instructions(args.seed_instruction)

    baseline = evaluate(program, valset, args.num_threads)
    print(f"Baseline zero-shot accuracy (val): {baseline:.1%}")

    # Optional separate LM for proposing/reflecting on instructions.
    proposer_model = args.prompt_model or args.reflection_model
    proposer_lm = None
    if args.optimizer == "gepa":
        reflection_model = args.reflection_model or args.prompt_model or task_model
        proposer_lm = make_lm(
            reflection_model,
            max_tokens=_PROPOSER_MAX_TOKENS,
            reasoning_effort=args.reasoning_effort,
        )
    elif proposer_model:
        proposer_lm = make_lm(proposer_model, max_tokens=_PROPOSER_MAX_TOKENS)

    compiled = _COMPILERS[args.optimizer](
        args, program, trainset, valset, proposer_lm, results_dir / "dspy_logs"
    )

    optimized = evaluate(compiled, valset, args.num_threads)
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
            "optimizer": args.optimizer,
            "model": task_model,
            "prompt_model": args.prompt_model,
            "reflection_model": args.reflection_model,
            "seed_instruction": bool(args.seed_instruction),
            "auto": args.auto,
            "breadth": args.breadth,
            "depth": args.depth,
            "init_temperature": args.init_temperature,
            "reflection_minibatch_size": args.reflection_minibatch_size,
            "max_full_evals": args.max_full_evals,
            "max_metric_calls": args.max_metric_calls,
            "num_candidates": args.num_candidates,
            "num_trials": args.num_trials,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "reasoning_effort": args.reasoning_effort,
            "num_threads": args.num_threads,
            "demos": args.demos,
            "ingested": args.ingested,
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
    parser.add_argument(
        "--optimizer", choices=["mipro", "copro", "gepa"], default="mipro",
        help="Prompt-optimization technique.",
    )
    parser.add_argument("--model", default=None, help="Task model (override OPENAI_MODEL).")
    parser.add_argument(
        "--prompt-model", default=None,
        help="Separate LM to propose instructions (MIPROv2/COPRO). Default: task model.",
    )
    parser.add_argument(
        "--reflection-model", default=None,
        help="LM that reflects/proposes for GEPA (use a strong model). Default: task model.",
    )
    parser.add_argument(
        "--seed-instruction", default=None,
        help="Override the starting instruction (inject your own domain knowledge).",
    )

    # --- search budget (the main cost knobs) -------------------------------
    budget = parser.add_argument_group("search budget / cost")
    budget.add_argument(
        "--auto", choices=["light", "medium", "heavy", "none"], default="light",
        help="Preset budget for MIPROv2/GEPA ('none' = manual for MIPROv2).",
    )
    budget.add_argument("--num-candidates", type=int, default=None,
                        help="MIPROv2 instruction candidates (with --auto none).")
    budget.add_argument("--num-trials", type=int, default=None,
                        help="MIPROv2 trials (with --auto none).")
    budget.add_argument("--breadth", type=int, default=10,
                        help="COPRO: candidates per round.")
    budget.add_argument("--depth", type=int, default=3,
                        help="COPRO: coordinate-ascent rounds.")
    budget.add_argument("--init-temperature", type=float, default=1.4,
                        help="COPRO: proposal temperature (diversity).")
    budget.add_argument("--copro-devset-size", type=int, default=60,
                        help="COPRO: cap the dev set used to score candidates.")
    budget.add_argument("--reflection-minibatch-size", type=int, default=8,
                        help="GEPA: failing examples analysed per reflection.")
    budget.add_argument("--max-full-evals", type=int, default=None,
                        help="GEPA: cap full evaluations (≈ iterations); overrides --auto.")
    budget.add_argument("--max-metric-calls", type=int, default=None,
                        help="GEPA: hard cap on total metric calls; overrides --auto.")
    budget.add_argument(
        "--minibatch", action=argparse.BooleanOptionalAction, default=True,
        help="MIPROv2: evaluate candidates on minibatches vs full valset.",
    )
    budget.add_argument("--minibatch-size", type=int, default=None,
                        help="MIPROv2 minibatch size (clamped to valset; default 35).")
    budget.add_argument("--max-tokens", type=int, default=1000,
                        help="Max output tokens per task-LM call.")
    budget.add_argument("--temperature", type=float, default=None)
    budget.add_argument(
        "--reasoning-effort", choices=["minimal", "low", "medium", "high"], default=None,
        help="Reasoning budget for reasoning models (low = fast/cheap).",
    )
    budget.add_argument("--num-threads", type=int, default=1, help="Parallel eval threads.")
    budget.add_argument("--max-errors", type=int, default=None,
                        help="MIPROv2: abort after this many failing LM calls.")
    budget.add_argument("--max-examples", type=int, default=None,
                        help="Cap the number of labelled words used.")

    # --- task setup --------------------------------------------------------
    parser.add_argument("--demos", type=int, default=0,
                        help="Max few-shot demos (0 = instruction-only).")
    parser.add_argument(
        "--ingested", action=argparse.BooleanOptionalAction, default=True,
        help="Include photo-ingested puzzles in the training set (--no-ingested to skip).",
    )
    parser.add_argument("--reveal", choices=["none", "partial", "all"], default="none",
                        help="Helper letters revealed in the pattern (none = hardest).")
    parser.add_argument("--reveal-fraction", type=float, default=0.5)
    parser.add_argument("--val-fraction", type=float, default=0.3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir", default=str(DEFAULT_RESULTS_DIR),
                        help="Base dir for artifacts (results go in <dir>/<optimizer>/).")
    return parser


def main(argv: list[str] | None = None) -> int:
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config.load_env()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
