"""CLI to run the solvers over the scraped datasets.

    karels-crypto-solve word    [options]   # evaluate the single-word solver
    karels-crypto-solve puzzle  [options]   # run the agentic puzzle solver

Both read from the ``karels-crypto-scraping`` datasets (override with
``KARELS_CRYPTO_DATA_DIR``). LLM access uses the OPENAI_* environment variables.
"""

from __future__ import annotations

import argparse
import random

from . import config, data
from .patterns import build_pattern
from .puzzle_solver import render_board, solve_puzzle
from .word_solver import solve_word


def _load_puzzles(dataset: str) -> list:
    if dataset == "latest":
        latest = data.load_latest()
        return [latest] if latest else []
    return data.load_history()


def _run_word(args: argparse.Namespace) -> int:
    puzzles = _load_puzzles(args.dataset)
    if args.puzzle_id is not None:
        puzzles = [p for p in puzzles if p.id == args.puzzle_id]

    rng = random.Random(args.seed)
    items = list(data.iter_solved_words(puzzles))
    if args.limit:
        items = items[: args.limit]

    if not items:
        print("No solved words found (the latest puzzle has no solution).")
        return 1

    correct = 0
    for puzzle, index, word in items:
        pattern = build_pattern(
            word, args.reveal, fraction=args.reveal_fraction, rng=rng
        )
        result = solve_word(word.cryptogram, word.length, pattern, model=args.model)
        ok = result.answer == word.solution.lower()
        correct += ok
        flag = "OK " if ok else "XX "
        print(
            f"{flag}[{puzzle.id}:{index:>2}] {word.cryptogram!r} "
            f"pattern={pattern} -> {result.answer!r} (expected {word.solution!r})"
        )

    total = len(items)
    print(f"\nZero-shot accuracy: {correct}/{total} = {correct / total:.1%}")
    return 0


def _run_puzzle(args: argparse.Namespace) -> int:
    puzzles = _load_puzzles(args.dataset)
    if args.puzzle_id is not None:
        puzzles = [p for p in puzzles if p.id == args.puzzle_id]
    if not puzzles:
        print("No puzzle found for the given selection.")
        return 1

    puzzle = puzzles[-1]
    print(f"Solving puzzle {puzzle.id} - {puzzle.title}\n")
    result = solve_puzzle(puzzle, model=args.model, max_turns=args.max_turns)

    print("\nFinal board:")
    print(render_board(result.puzzle))
    print(f"\nSolved: {result.solved}")
    return 0 if result.solved else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Karel's Crypto solvers.")
    parser.add_argument("--model", default=None, help="Override OPENAI_MODEL.")
    sub = parser.add_subparsers(dest="command", required=True)

    word = sub.add_parser("word", help="Evaluate the single-word solver.")
    word.add_argument("--dataset", choices=["history", "latest"], default="history")
    word.add_argument("--puzzle-id", type=int, default=None)
    word.add_argument("--limit", type=int, default=None, help="Max words to solve.")
    word.add_argument(
        "--reveal",
        choices=["none", "partial", "all"],
        default="none",
        help="How many helper letters to pre-fill in the pattern.",
    )
    word.add_argument("--reveal-fraction", type=float, default=0.5)
    word.add_argument("--seed", type=int, default=0)
    word.set_defaults(func=_run_word)

    puzzle = sub.add_parser("puzzle", help="Run the agentic puzzle solver.")
    puzzle.add_argument("--dataset", choices=["history", "latest"], default="history")
    puzzle.add_argument("--puzzle-id", type=int, default=None)
    puzzle.add_argument("--max-turns", type=int, default=60)
    puzzle.set_defaults(func=_run_puzzle)
    return parser


def main(argv: list[str] | None = None) -> int:
    config.load_env()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
