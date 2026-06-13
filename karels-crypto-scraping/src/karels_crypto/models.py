"""Data models for Karel's Crypto puzzles.

A *Crypto* is one weekly puzzle. It holds an ordered list of *words* (19 of
them). Each word is one cryptic clue whose answer is placed in a numbered grid
row; the vertical column through every row spells the 19-letter ``solution``.

Per the project data format, each word exposes:

* ``cryptogram`` - the cryptic clue text.
* ``length`` - the number of letters in the answer.
* ``help_numbers`` - an array (one entry per letter, ``None`` where empty) with
  the pre-printed grid numbers; identical numbers mean identical letters.
* ``offset`` - the index where the central/vertical word intersects this row
  (i.e. how far the word is shifted so its crossing letter lines up).
* ``solution`` - the answer word, or ``None`` for the latest (unsolved) puzzle.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Word:
    cryptogram: str
    length: int
    help_numbers: list[int | None] = field(default_factory=list)
    offset: int = 0
    solution: str | None = None

    def to_dict(self) -> dict:
        return {
            "cryptogram": self.cryptogram,
            "length": self.length,
            "help_numbers": self.help_numbers,
            "offset": self.offset,
            "solution": self.solution,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Word:
        return cls(
            cryptogram=data["cryptogram"],
            length=data["length"],
            help_numbers=list(data.get("help_numbers", [])),
            offset=data.get("offset", 0),
            solution=data.get("solution"),
        )

    def without_solution(self) -> Word:
        """Return a copy with the answer removed (kept hints/help numbers)."""
        return Word(
            cryptogram=self.cryptogram,
            length=self.length,
            help_numbers=list(self.help_numbers),
            offset=self.offset,
            solution=None,
        )


@dataclass
class Crypto:
    id: int
    title: str
    date: str  # ISO date (YYYY-MM-DD)
    solution: str | None
    words: list[Word] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "date": self.date,
            "solution": self.solution,
            "words": [w.to_dict() for w in self.words],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Crypto:
        return cls(
            id=data["id"],
            title=data["title"],
            date=data["date"],
            solution=data.get("solution"),
            words=[Word.from_dict(w) for w in data.get("words", [])],
        )

    def without_solution(self) -> Crypto:
        """Return a copy with the puzzle and word solutions removed."""
        return Crypto(
            id=self.id,
            title=self.title,
            date=self.date,
            solution=None,
            words=[w.without_solution() for w in self.words],
        )
