"""Ingest photos of Karel's Crypto puzzles into the JSON data format.

Karel's Crypto (book form) is a number-substitution cryptogram: 19 clues labelled
A-S, and a diamond grid where every cell shows a number (equal numbers = equal
letters). The puzzle pages are *empty* (only numbers); the answers live in a
separate solutions section, many puzzles per page.

So ingestion is a two-pass + merge pipeline (vision models read images as base64
data URLs):

    # 1) one pass over the (empty) puzzle pages -> clues + the number key
    karels-crypto-ingest puzzles   --images-dir ./puzzles   --model gpt-4o
    # 2) one pass over the solutions pages -> answers per puzzle number
    karels-crypto-ingest solutions --images-dir ./solutions --model gpt-4o
    # 3) join them into the data format the optimizer reads
    karels-crypto-ingest merge

`merge` writes ``data/ingested_puzzles.json`` (included in optimization by
default; ``karels-crypto-optimize --no-ingested`` to skip). Puzzles are matched
by their printed number; clues by their A-S label.
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import mimetypes
import re
from pathlib import Path

import openai

from . import config, data

logger = logging.getLogger(__name__)

DEFAULT_INGEST_MODEL = "gpt-4o"  # strong, cheap vision + reliable JSON
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

_REPO_ROOT = Path(__file__).resolve().parents[3]
_UPLOADS = _REPO_ROOT / "uploads" / "images"
DEFAULT_PUZZLES_DIR = _UPLOADS / "puzzles"
DEFAULT_SOLUTIONS_DIR = _UPLOADS / "solutions"

_SOLVING_DATA = data.INGESTED_PATH.parent
PUZZLES_RAW = _SOLVING_DATA / "_ingest_puzzles_raw.json"
SOLUTIONS_RAW = _SOLVING_DATA / "_ingest_solutions_raw.json"

# Per-image failures we tolerate during a batch; other errors propagate & crash.
_EXPECTED_ERRORS = (
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.InternalServerError,
    json.JSONDecodeError,
)

PUZZLE_SYSTEM = """\
You are reading a photo of a "Karels Crypto" puzzle (a Dutch/Flemish number
cryptogram). The page shows a title like "Karels Crypto 122", a date, 19 clues
labelled A, B, C, ... S, and a diamond-shaped grid. Each clue's answer occupies
one row of cells; every cell shows a small number (the substitution key - equal
numbers mean equal letters). The grid is EMPTY (no letters are filled in).

Return ONLY a JSON object:
{
  "number": integer or null,      // the puzzle number in the title
  "date": "YYYY-MM-DD" or null,
  "clues": [
    {"label": "A", "cryptogram": "<clue text>", "numbers": [<cell numbers, left to right>]}
  ]
}

Rules:
- One entry per clue, in order A, B, C, ...
- "cryptogram": the clue text transcribed exactly (keep Dutch spelling, accents,
  punctuation). Do NOT translate.
- "numbers": the numbers printed in that clue's row of grid cells, left to right.
  If a row's numbers are unreadable, use [].
- The grid is empty: never output letters or answers.
"""

SOLUTIONS_SYSTEM = """\
You are reading a photo from the SOLUTIONS section of a "Karels Crypto" puzzle
book. One page lists the answers for MULTIPLE puzzles. Each puzzle is identified
by its number (e.g. 122) and gives the answer word for each clue A, B, C, ...

Return ONLY a JSON object:
{
  "puzzles": [
    {
      "number": integer,
      "solution": "<the hidden 19-letter word, or null>",
      "answers": {"A": "<word>", "B": "<word>", ...}
    }
  ]
}

Rules:
- Include every puzzle visible on the page.
- Transcribe the Dutch answer words exactly (lowercase is fine). Do NOT translate.
- Use null or omit fields that are not present.
"""


# --- image helpers ---------------------------------------------------------

def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def iter_images(images_dir: Path, glob: str):
    for path in sorted(images_dir.glob(glob)):
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTS:
            yield path


def _extract(
    path: Path, *, client, model: str, system: str, reasoning_effort: str | None = None
) -> dict:
    kwargs = {}
    if config.is_reasoning_model(model):
        # Reasoning models need a big budget or the JSON comes back empty.
        kwargs["max_completion_tokens"] = config.REASONING_MIN_MAX_TOKENS
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract to JSON."},
                    {"type": "image_url", "image_url": {"url": data_url(path)}},
                ],
            },
        ],
        response_format={"type": "json_object"},
        **kwargs,
    )
    return json.loads(response.choices[0].message.content or "{}")


def _extract_dir(images_dir: Path, glob: str, *, client, model: str, system: str,
                 reasoning_effort: str | None = None):
    images = list(iter_images(images_dir, glob))
    results = []
    for path in images:
        try:
            results.append((path, _extract(
                path, client=client, model=model, system=system,
                reasoning_effort=reasoning_effort,
            )))
        except _EXPECTED_ERRORS as exc:
            logger.warning("Skipping %s: %s", path.name, exc)
    return images, results


# --- normalisation / merge (pure, unit-tested) -----------------------------

_DATE_DMY = re.compile(r"^(\d{2})-(\d{2})-(\d{4})$")


def normalise_date(value: str | None) -> str:
    if not value:
        return ""
    value = value.strip()
    m = _DATE_DMY.match(value)
    if m:  # DD-MM-YYYY -> YYYY-MM-DD
        day, month, year = m.groups()
        return f"{year}-{month}-{day}"
    return value


def _ints(values) -> list[int]:
    out = []
    for v in values or []:
        if isinstance(v, bool):
            continue
        if isinstance(v, int):
            out.append(v)
        elif isinstance(v, float):
            out.append(int(v))
        elif isinstance(v, str) and v.strip().isdigit():
            out.append(int(v.strip()))
    return out


def _help_numbers(numbers: list[int], length: int) -> list:
    """Align the row's cell numbers to the word length (every cell is numbered).

    If the count doesn't match the answer length we don't trust the alignment
    and leave them empty rather than mislabel cells.
    """
    if length and len(numbers) == length:
        return list(numbers)
    return [None] * length


def merge_puzzle(puzzle: dict, solution: dict | None, puzzle_id: int) -> dict:
    """Join one puzzle (clues + key) with its solution (answers) -> Crypto dict."""
    answers = {}
    meta = None
    if solution:
        answers = {str(k).upper().strip(): v for k, v in (solution.get("answers") or {}).items()}
        meta = solution.get("solution")

    words = []
    for clue in puzzle.get("clues") or []:
        label = str(clue.get("label") or "").upper().strip()
        numbers = _ints(clue.get("numbers"))
        answer = answers.get(label)
        answer = answer.strip().lower() if answer else None
        length = len(answer) if answer else len(numbers)
        words.append(
            {
                "cryptogram": (clue.get("cryptogram") or "").strip(),
                "length": length,
                "help_numbers": _help_numbers(numbers, length),
                "offset": 0,
                "solution": answer,
            }
        )

    number = puzzle.get("number")
    return {
        "id": puzzle_id,
        "number": number,
        "title": f"Karels Crypto {number}" if number is not None else "Karels Crypto",
        "date": normalise_date(puzzle.get("date")),
        "solution": meta.strip().lower() if meta else None,
        "words": words,
    }


def merge(puzzles: list[dict], solutions: list[dict], id_start: int) -> list[dict]:
    """Merge raw puzzle dicts with flattened solution dicts (matched by number)."""
    by_number: dict[int, dict] = {}
    for sol in solutions:
        num = sol.get("number")
        if isinstance(num, int):
            by_number[num] = sol

    merged = []
    for index, puzzle in enumerate(puzzles):
        number = puzzle.get("number")
        puzzle_id = id_start + number if isinstance(number, int) else id_start + index
        solution = by_number.get(number) if isinstance(number, int) else None
        merged.append(merge_puzzle(puzzle, solution, puzzle_id))
    return merged


def flatten_solutions(raw_results: list[dict]) -> list[dict]:
    """A solutions image yields {"puzzles": [...]}; flatten across images."""
    out = []
    for result in raw_results:
        out.extend(result.get("puzzles") or [])
    return out


# --- subcommands -----------------------------------------------------------

def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_puzzles(args: argparse.Namespace) -> int:
    client = config.openai_client()
    images, results = _extract_dir(
        Path(args.images_dir), args.glob, client=client, model=args.model,
        system=PUZZLE_SYSTEM, reasoning_effort=args.reasoning_effort,
    )
    if not images:
        print(f"No images found in {args.images_dir}.")
        return 1
    puzzles = []
    for path, raw in results:
        clues = raw.get("clues") or []
        print(f"  {path.name}: puzzle {raw.get('number')}, {len(clues)} clues")
        puzzles.append(raw)
    _write(Path(args.output), puzzles)
    print(f"\nWrote {len(puzzles)} puzzle(s) to {args.output}")
    return 0


def cmd_solutions(args: argparse.Namespace) -> int:
    client = config.openai_client()
    images, results = _extract_dir(
        Path(args.images_dir), args.glob, client=client, model=args.model,
        system=SOLUTIONS_SYSTEM, reasoning_effort=args.reasoning_effort,
    )
    if not images:
        print(f"No images found in {args.images_dir}.")
        return 1
    raw_results = []
    for path, raw in results:
        n = len(raw.get("puzzles") or [])
        print(f"  {path.name}: {n} puzzle solution(s)")
        raw_results.append(raw)
    solutions = flatten_solutions(raw_results)
    _write(Path(args.output), solutions)
    print(f"\nWrote {len(solutions)} puzzle solution(s) to {args.output}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    puzzles = json.loads(Path(args.puzzles).read_text(encoding="utf-8"))
    solutions = json.loads(Path(args.solutions).read_text(encoding="utf-8"))
    merged = merge(puzzles, solutions, args.id_start)

    solved_words = sum(1 for p in merged for w in p["words"] if w["solution"])
    matched = sum(1 for p in merged if any(w["solution"] for w in p["words"]))
    _write(Path(args.output), merged)
    print(
        f"Merged {len(merged)} puzzle(s); {matched} matched a solution; "
        f"{solved_words} solved clues -> {args.output}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ingest puzzle/solution photos into the data format."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    effort = ["minimal", "low", "medium", "high"]

    p = sub.add_parser("puzzles", help="Pass over the (empty) puzzle pages.")
    p.add_argument("--images-dir", default=str(DEFAULT_PUZZLES_DIR))
    p.add_argument("--glob", default="*")
    p.add_argument("--model", default=DEFAULT_INGEST_MODEL,
                   help="Vision model (use the strongest available for best OCR).")
    p.add_argument("--reasoning-effort", choices=effort, default=None,
                   help="For reasoning models (e.g. gpt-5.x): thinking budget.")
    p.add_argument("--output", default=str(PUZZLES_RAW))
    p.set_defaults(func=cmd_puzzles)

    s = sub.add_parser("solutions", help="Pass over the solutions pages.")
    s.add_argument("--images-dir", default=str(DEFAULT_SOLUTIONS_DIR))
    s.add_argument("--glob", default="*")
    s.add_argument("--model", default=DEFAULT_INGEST_MODEL,
                   help="Vision model (use the strongest available for best OCR).")
    s.add_argument("--reasoning-effort", choices=effort, default=None,
                   help="For reasoning models (e.g. gpt-5.x): thinking budget.")
    s.add_argument("--output", default=str(SOLUTIONS_RAW))
    s.set_defaults(func=cmd_solutions)

    m = sub.add_parser("merge", help="Merge puzzles + solutions into the data format.")
    m.add_argument("--puzzles", default=str(PUZZLES_RAW))
    m.add_argument("--solutions", default=str(SOLUTIONS_RAW))
    m.add_argument("--output", default=str(data.INGESTED_PATH))
    m.add_argument(
        "--id-start", type=int, default=900000,
        help="Base added to the puzzle number for ids (avoids clashing with scraped ids).",
    )
    m.set_defaults(func=cmd_merge)
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config.load_env()
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
