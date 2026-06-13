"""Convert raw GraphQL puzzle nodes into :class:`Crypto` models.

The grid uses a legend that maps a *number* to a *letter* (identical numbers
mean identical letters). A row's ``numbers`` list marks which letter positions
carry a pre-printed number. The actual number for a marked position is the
legend entry whose letter matches that position's letter, so we derive the
``help_numbers`` array from the legend and the answer.
"""

from __future__ import annotations

from .models import Crypto, Word


def _legend_lookup(legends: list[dict]) -> dict[str, int]:
    """Build a ``letter -> number`` map from the puzzle legend."""
    lookup: dict[str, int] = {}
    for entry in legends or []:
        letter = entry.get("letter")
        number = entry.get("number")
        if letter is None or number is None:
            continue
        lookup[str(letter).lower()] = int(number)
    return lookup


def _help_numbers(row: dict, letter_to_number: dict[str, int]) -> list[int | None]:
    """Return one entry per answer letter: the grid number, or ``None``."""
    answer = row.get("answer") or ""
    length = len(answer)
    numbers: list[int | None] = [None] * length

    for marker in row.get("numbers") or []:
        idx = marker.get("index")
        if idx is None or not (0 <= idx < length):
            continue
        letter = answer[idx].lower()
        numbers[idx] = letter_to_number.get(letter)
    return numbers


def _iso_date(raw: str | None) -> str:
    """Normalise ``"2026-06-13 00:00:00"`` to ``"2026-06-13"``."""
    if not raw:
        return ""
    return str(raw).split(" ", 1)[0].split("T", 1)[0]


def puzzle_to_crypto(node: dict) -> Crypto:
    """Convert a raw GraphQL puzzle node into a :class:`Crypto`."""
    letter_to_number = _legend_lookup(node.get("legends") or [])

    words: list[Word] = []
    for row in node.get("rows") or []:
        answer = row.get("answer") or ""
        words.append(
            Word(
                cryptogram=row.get("hint") or "",
                length=len(answer),
                help_numbers=_help_numbers(row, letter_to_number),
                offset=int(row.get("offset") or 0),
                solution=answer or None,
            )
        )

    return Crypto(
        id=int(node["id"]),
        title=node.get("title") or "",
        date=_iso_date(node.get("start_date")),
        solution=node.get("solution"),
        words=words,
    )
