"""Load Karel's Crypto puzzles from the scraping module's JSON datasets.

The two modules are independent code-wise; they are coupled only through the
JSON data format. By default we read the datasets produced by
``karels-crypto-scraping`` (``../karels-crypto-scraping/data``). Override the
location with the ``KARELS_CRYPTO_DATA_DIR`` environment variable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Puzzle, Word

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DATA_DIR = _REPO_ROOT / "karels-crypto-scraping" / "data"

# Puzzles ingested from photos (see ingest.py) live with the solving module.
_SOLVING_MODULE_ROOT = Path(__file__).resolve().parents[2]
INGESTED_PATH = _SOLVING_MODULE_ROOT / "data" / "ingested_puzzles.json"


def data_dir() -> Path:
    return Path(os.environ.get("KARELS_CRYPTO_DATA_DIR", str(_DEFAULT_DATA_DIR)))


def puzzle_from_scraping(node: dict) -> Puzzle:
    """Build a fresh (unfilled) :class:`Puzzle` from a scraped Crypto dict."""
    words = [
        Word(
            cryptogram=w["cryptogram"],
            length=w["length"],
            help_numbers=list(w["help_numbers"]),
            offset=w["offset"],
            solution=w.get("solution"),
        )
        for w in node["words"]
    ]
    return Puzzle(
        id=node["id"],
        title=node["title"],
        date=node["date"],
        solution=node.get("solution"),
        words=words,
    )


def _load_json(path: Path) -> object:
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {path}. Run the scraper first, or set "
            "KARELS_CRYPTO_DATA_DIR."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_history(path: Path | None = None) -> list[Puzzle]:
    raw = _load_json(path or (data_dir() / "history.json"))
    return [puzzle_from_scraping(item) for item in raw]


def load_latest(path: Path | None = None) -> Puzzle | None:
    raw = _load_json(path or (data_dir() / "latest.json"))
    if not raw:
        return None
    return puzzle_from_scraping(raw)


def load_ingested(path: Path | None = None) -> list[Puzzle]:
    """Load puzzles ingested from photos (empty list if none exist yet)."""
    path = path or INGESTED_PATH
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [puzzle_from_scraping(item) for item in raw]


def iter_solved_words(puzzles: list[Puzzle]):
    """Yield ``(puzzle, word_index, word)`` for every word with a known answer."""
    for puzzle in puzzles:
        for index, word in enumerate(puzzle.words):
            if word.solution:
                yield puzzle, index, word
