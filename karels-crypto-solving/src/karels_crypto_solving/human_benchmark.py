"""Human solver benchmark worksheet (randomized reveals).

Builds a fill-in worksheet to measure the **human** accuracy ceiling across the
same difficulty grid as the model reveal sweep (REPORT §6): word-length bucket x
reveal fraction. To avoid depending on the puzzles' real grid key (which we
mostly lack), revealed letters are **randomized** exactly like
``reveal_analysis`` (nested random positions) — so human and model numbers are
measured on the same kind of partial-information task.

Each clue appears **once** at a single reveal level (distinct words per cell), so
you never see the same answer twice. The solution is kept out of the worksheet
(in a separate answer key) so it can't be glimpsed while solving.

    # 1) generate the worksheet + answer key
    karels-crypto-human-benchmark generate --per-cell 5

    # 2) ...you fill the `answer` / `seen_before` columns in the CSV...

    # 3) score it (and compare to the model reveal grid)
    karels-crypto-human-benchmark score \
        --worksheet research/human/human_benchmark_worksheet.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from pathlib import Path

from . import data
from .reveal_analysis import _BUCKETS, _permutation, _reveal_count, bucket_of, reveal_pattern

_MODULE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = _MODULE_ROOT / "research" / "human"
DEFAULT_WORKSHEET = DEFAULT_DIR / "human_benchmark_worksheet.csv"
DEFAULT_KEY = DEFAULT_DIR / "answer_key.json"
DEFAULT_MODEL_GRID = _MODULE_ROOT / "research" / "reveal" / "reveal_analysis.json"

WORKSHEET_FIELDS = [
    "id", "puzzle_id", "puzzle_date", "length", "reveal_pct",
    "known", "clue", "answer", "seen_before", "confidence",
]
_TRUE = {"y", "yes", "true", "1"}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-zà-ÿ]", "", (text or "").strip().lower())


def _display_pattern(pattern: str) -> str:
    # Underscores for blanks, the known letters in place (e.g. "g__el_").
    return pattern


def generate(args: argparse.Namespace) -> int:
    fractions = args.fractions
    puzzles = data.load_history() + data.load_ingested()
    # Unique solved words, de-duplicated by answer so no answer repeats.
    seen, unique = set(), []
    for _, _, w in data.iter_solved_words(puzzles):
        sol = (w.solution or "").lower()
        if sol and len(sol) == w.length and sol not in seen:
            seen.add(sol)
            unique.append(w)
    by_bucket: dict[str, list] = {label: [] for _, _, label in _BUCKETS}
    for w in unique:
        by_bucket[bucket_of(w.length)].append(w)

    # Need each word's puzzle for id/date.
    word_puzzle = {}
    for p in puzzles:
        for w in p.words:
            word_puzzle[id(w)] = p

    rng = random.Random(args.seed)
    rows, key = [], {}
    for _, _, label in _BUCKETS:
        pool = by_bucket[label]
        rng.shuffle(pool)
        cursor = 0
        for frac in fractions:
            picked = pool[cursor:cursor + args.per_cell]
            cursor += args.per_cell
            for w in picked:
                p = word_puzzle.get(id(w))
                pid = getattr(p, "id", 0) if p else 0
                pdate = getattr(p, "date", "") if p else ""
                pct = int(round(frac * 100))
                k = _reveal_count(w.length, frac)
                pattern = reveal_pattern(w, _permutation(w, args.seed), k)
                rid = f"p{pid}w{w.length}r{pct}n{len(rows)}"
                rows.append({
                    "id": rid,
                    "puzzle_id": pid,
                    "puzzle_date": pdate,
                    "length": w.length,
                    "reveal_pct": pct,
                    "known": _display_pattern(pattern),
                    "clue": w.cryptogram,
                    "answer": "",
                    "seen_before": "",
                    "confidence": "",
                })
                key[rid] = {
                    "solution": (w.solution or "").lower(),
                    "length": w.length,
                    "reveal_pct": pct,
                    "bucket": label,
                }
    rng.shuffle(rows)  # interleave reveal levels so the task feels varied

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    worksheet = out_dir / "human_benchmark_worksheet.csv"
    with worksheet.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=WORKSHEET_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "answer_key.json").write_text(
        json.dumps(key, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {len(rows)} clues to {worksheet}")
    print(f"Answer key: {out_dir / 'answer_key.json'}")
    print(
        "\nFill the `answer` column (your guess) and `seen_before` (y/n if you'd "
        "solved this exact clue before); `confidence` (1-3) optional. "
        "`known` shows revealed letters (`_` = blank)."
    )
    return 0


def _load_model_grid(path: Path) -> dict[str, float]:
    """bucket@pct -> model accuracy, averaged over models in the reveal run."""
    if not path.exists():
        return {}
    report = json.loads(path.read_text())
    acc: dict[str, list[float]] = {}
    for m in report.get("models", []):
        for cell, stats in m.get("by_cell", {}).items():
            bucket, frac = cell.split("@")
            pct = int(round(float(frac) * 100))
            acc.setdefault(f"{bucket}@{pct}", []).append(stats["accuracy"])
    return {k: sum(v) / len(v) for k, v in acc.items() if v}


def score(args: argparse.Namespace) -> int:
    key = json.loads(Path(args.key).read_text())
    cells: dict[str, dict] = {}
    overall = {"correct": 0, "total": 0, "skipped": 0}
    with Path(args.worksheet).open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rid = row.get("id", "")
            meta = key.get(rid)
            if not meta or not (row.get("answer") or "").strip():
                continue
            if (row.get("seen_before") or "").strip().lower() in _TRUE:
                overall["skipped"] += 1
                continue
            correct = _normalize(row["answer"]) == _normalize(meta["solution"])
            ckey = f"{meta['bucket']}@{meta['reveal_pct']}"
            cell = cells.setdefault(ckey, {"correct": 0, "total": 0})
            cell["total"] += 1
            cell["correct"] += int(correct)
            overall["total"] += 1
            overall["correct"] += int(correct)
    for cell in cells.values():
        cell["accuracy"] = cell["correct"] / cell["total"] if cell["total"] else 0.0
    overall["accuracy"] = overall["correct"] / overall["total"] if overall["total"] else 0.0

    model_grid = _load_model_grid(Path(args.model_grid))
    report = {"overall": overall, "by_cell": cells, "human_vs_model": {}}
    for ckey, cell in sorted(cells.items()):
        report["human_vs_model"][ckey] = {
            "human": round(cell["accuracy"], 3),
            "model_avg": round(model_grid[ckey], 3) if ckey in model_grid else None,
            "n": cell["total"],
        }

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "human_vs_model.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    pcts = sorted({int(k.split("@")[1]) for k in cells})
    lines = [
        "# Human vs model (reveal x length)",
        "",
        f"Human overall: {overall['accuracy']:.0%} "
        f"({overall['correct']}/{overall['total']}; {overall['skipped']} skipped as seen-before)",
        "",
        "| length \\ reveal | " + " | ".join(f"{p}%" for p in pcts) + " |",
        "| --- | " + " | ".join(["---:"] * len(pcts)) + " |",
    ]
    for _, _, label in _BUCKETS:
        cells_row = []
        for p in pcts:
            cell = cells.get(f"{label}@{p}")
            cells_row.append(f"{cell['accuracy']:.0%}" if cell and cell["total"] else "-")
        lines.append(f"| {label} | " + " | ".join(cells_row) + " |")
    md = "\n".join(lines) + "\n"
    (out_dir / "human_vs_model.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"Saved to {out_dir / 'human_vs_model.json'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Human solver benchmark (randomized reveals).")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Build the fill-in worksheet + answer key.")
    g.add_argument(
        "--per-cell", type=int, default=5, help="Clues per (length-bucket x reveal) cell."
    )
    g.add_argument("--fractions", nargs="*", type=float, default=[0.0, 0.25, 0.5, 0.75])
    g.add_argument("--seed", type=int, default=0)
    g.add_argument("--output-dir", default=str(DEFAULT_DIR))
    g.set_defaults(func=generate)

    s = sub.add_parser("score", help="Score a filled worksheet, compare to the model grid.")
    s.add_argument("--worksheet", default=str(DEFAULT_WORKSHEET))
    s.add_argument("--key", default=str(DEFAULT_KEY))
    s.add_argument("--model-grid", default=str(DEFAULT_MODEL_GRID))
    s.add_argument("--output-dir", default=str(DEFAULT_DIR))
    s.set_defaults(func=score)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
