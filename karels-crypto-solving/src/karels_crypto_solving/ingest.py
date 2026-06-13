"""Ingest photos of Karel's Crypto puzzles into the JSON data format.

Vision-capable OpenAI models read the clues (and any filled-in answers) straight
from an image. We send each picture as a base64 data URL and ask for structured
JSON, then normalise it into the same Crypto shape the scraper produces.

    karels-crypto-ingest --images-dir ./photos --model gpt-4o

Output goes to ``karels-crypto-solving/data/ingested_puzzles.json`` by default,
which the optimizer includes in its training set (disable with
``--no-ingested``).

Note on scope: a photo reliably yields the **clue text** and, if the puzzle is
filled in, the **answers** + the 19-letter solution. The grid's help-numbers /
offsets are hard to OCR, so those are left empty - which is fine for word-solver
optimization (it uses cryptogram + solution).
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import mimetypes
from pathlib import Path

import openai

from . import config, data

logger = logging.getLogger(__name__)

DEFAULT_INGEST_MODEL = "gpt-4o"  # strong, cheap vision + reliable JSON
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Per-image failures we tolerate during a batch (model hiccup, model not enabled,
# rate limit, transient). Other errors propagate and crash.
_EXPECTED_ERRORS = (
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.PermissionDeniedError,
    openai.NotFoundError,
    openai.InternalServerError,
    json.JSONDecodeError,
)

EXTRACT_SYSTEM = """\
You are reading a photo of "Karel's Crypto", a Dutch/Flemish cryptic word puzzle
that has 19 numbered clues, each describing one Dutch word.

Return ONLY a JSON object with this exact shape:
{
  "title": string or null,        // e.g. a date or puzzle number printed on it
  "date": "YYYY-MM-DD" or null,   // only if a date is clearly shown
  "solution": string or null,     // the 19-letter word hidden vertically, if shown
  "words": [                      // the clues, in order, top to bottom
    {"cryptogram": string, "solution": string or null}
  ]
}

Rules:
- "cryptogram" is the clue text, transcribed exactly (keep accents/punctuation).
- "solution" is the answer ONLY if it is filled in / printed in the image;
  otherwise null. Never guess or invent an answer.
- Transcribe Dutch text faithfully; do not translate.
"""


def data_url(path: Path) -> str:
    mime = mimetypes.guess_type(str(path))[0] or "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def extract_image(path: Path, *, client, model: str) -> dict:
    """Call the vision model and return the parsed JSON for one image."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract this puzzle to JSON."},
                    {"type": "image_url", "image_url": {"url": data_url(path)}},
                ],
            },
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content or "{}")


def to_crypto_dict(raw: dict, puzzle_id: int, title_fallback: str) -> dict:
    """Normalise the model's JSON into the scraper's Crypto dict format."""
    words = []
    for entry in raw.get("words") or []:
        solution = entry.get("solution")
        solution = solution.strip().lower() if solution else None
        length = len(solution) if solution else int(entry.get("length") or 0)
        words.append(
            {
                "cryptogram": (entry.get("cryptogram") or "").strip(),
                "length": length,
                "help_numbers": [None] * length,  # not OCR'd from a photo
                "offset": 0,
                "solution": solution,
            }
        )
    solution = raw.get("solution")
    return {
        "id": puzzle_id,
        "title": raw.get("title") or title_fallback,
        "date": raw.get("date") or "",
        "solution": solution.strip().lower() if solution else None,
        "words": words,
    }


def iter_images(images_dir: Path, glob: str):
    for path in sorted(images_dir.glob(glob)):
        if path.is_file() and path.suffix.lower() in _IMAGE_EXTS:
            yield path


def run(args: argparse.Namespace) -> int:
    images_dir = Path(args.images_dir)
    if not images_dir.is_dir():
        print(f"Not a directory: {images_dir}")
        return 1

    images = list(iter_images(images_dir, args.glob))
    if not images:
        print(f"No images found in {images_dir} (glob={args.glob}).")
        return 1

    client = config.openai_client()
    model = args.model
    print(f"Ingesting {len(images)} image(s) with {model} ...")

    puzzles: list[dict] = []
    for index, path in enumerate(images):
        puzzle_id = args.id_start + index
        try:
            raw = extract_image(path, client=client, model=model)
        except _EXPECTED_ERRORS as exc:
            logger.warning("Skipping %s: %s", path.name, exc)
            continue
        crypto = to_crypto_dict(raw, puzzle_id, title_fallback=path.stem)
        solved = sum(1 for w in crypto["words"] if w["solution"])
        print(f"  {path.name}: {len(crypto['words'])} clues, {solved} answers filled")
        puzzles.append(crypto)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.append and output.exists():
        existing = json.loads(output.read_text(encoding="utf-8"))
        puzzles = existing + puzzles
    output.write_text(
        json.dumps(puzzles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    total_words = sum(len(p["words"]) for p in puzzles)
    print(f"\nWrote {len(puzzles)} puzzle(s) ({total_words} clues) to {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest puzzle photos into the JSON data format.")
    parser.add_argument("--images-dir", required=True, help="Folder of puzzle images.")
    parser.add_argument("--glob", default="*", help="Filename glob within the folder.")
    parser.add_argument("--model", default=DEFAULT_INGEST_MODEL, help="Vision model id.")
    parser.add_argument(
        "--output", default=str(data.INGESTED_PATH),
        help="Output JSON file (default: the optimizer's ingested dataset).",
    )
    parser.add_argument(
        "--id-start", type=int, default=900000,
        help="First id to assign (kept high to avoid clashing with scraped ids).",
    )
    parser.add_argument(
        "--append", action="store_true",
        help="Append to the existing output file instead of overwriting.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    config.load_env()
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
