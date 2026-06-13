"""Read and write the JSON datasets stored in the repository.

Two datasets are kept under ``data/``:

* ``history.json`` - the list of historical Crypto's, each *with* its solution.
* ``latest.json``  - the most recent Crypto, *without* its solution.

Datasets are sorted by date (then id) and written deterministically so diffs
stay small and reviewable across weekly commits.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Crypto

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
HISTORY_PATH = DATA_DIR / "history.json"
LATEST_PATH = DATA_DIR / "latest.json"


def _sort_key(crypto: Crypto) -> tuple[str, int]:
    return (crypto.date, crypto.id)


def load_history(path: Path = HISTORY_PATH) -> list[Crypto]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Crypto.from_dict(item) for item in raw]


def load_latest(path: Path = LATEST_PATH) -> Crypto | None:
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not raw:
        return None
    return Crypto.from_dict(raw)


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=False)
    path.write_text(text + "\n", encoding="utf-8")


def save_history(history: list[Crypto], path: Path = HISTORY_PATH) -> None:
    ordered = sorted(history, key=_sort_key)
    _write_json(path, [c.to_dict() for c in ordered])


def save_latest(latest: Crypto | None, path: Path = LATEST_PATH) -> None:
    _write_json(path, latest.to_dict() if latest is not None else None)


def merge_history(existing: list[Crypto], new: list[Crypto]) -> list[Crypto]:
    """Merge puzzles by id (new entries win) and return a sorted list."""
    by_id: dict[int, Crypto] = {c.id: c for c in existing}
    for crypto in new:
        by_id[crypto.id] = crypto
    return sorted(by_id.values(), key=_sort_key)
