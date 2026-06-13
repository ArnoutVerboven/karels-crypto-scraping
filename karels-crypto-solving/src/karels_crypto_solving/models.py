"""Puzzle state for solving, with helper-letter propagation.

A :class:`Puzzle` mirrors a scraped Crypto but adds a *fill state*: the letters
that have been entered so far. The grid's help numbers (``help_numbers``) link
cells across words - identical numbers mean identical letters. We model this
with a single ``helper_map`` (number -> letter) that is shared by the whole
puzzle, so filling a letter on a numbered cell of one word automatically shows
up on every other word that has the same number.

Each :class:`Word` therefore has two kinds of cells:

* *helper cells* (``help_numbers[i] is not None``): their letter is governed by
  the shared ``helper_map``;
* *plain cells*: their letter is stored directly on the word (``direct``).

The *effective* letters of a word combine both. This is what gets serialised as
``filled`` so a partially-solved puzzle round-trips through JSON.

The blank placeholder ``"_"`` represents an unknown / removed cell.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BLANK = "_"
_BLANK_CHARS = {BLANK, ".", " ", ""}


def _normalise_cell(value: str | None) -> str | None:
    """Map a raw cell value to a single lowercase letter or ``None``."""
    if value is None:
        return None
    value = value.strip().lower()
    if value in _BLANK_CHARS:
        return None
    return value[0]


@dataclass
class Word:
    cryptogram: str
    length: int
    help_numbers: list[int | None]
    offset: int
    solution: str | None = None
    # Letters entered on plain (non-helper) cells. Helper cells are ignored
    # here; their value lives in Puzzle.helper_map.
    direct: list[str | None] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.direct:
            self.direct = [None] * self.length


@dataclass
class Puzzle:
    id: int
    title: str
    date: str
    solution: str | None
    words: list[Word]
    # Shared grid key: help number -> letter.
    helper_map: dict[int, str] = field(default_factory=dict)

    # -- reading state ----------------------------------------------------

    def effective_letters(self, word_index: int) -> list[str | None]:
        """The letters currently shown for a word (plain + propagated helper)."""
        word = self.words[word_index]
        letters: list[str | None] = []
        for pos in range(word.length):
            number = word.help_numbers[pos]
            if number is not None:
                letters.append(self.helper_map.get(number))
            else:
                letters.append(word.direct[pos])
        return letters

    def pattern(self, word_index: int) -> str:
        """A length-sized string with letters where known and ``_`` elsewhere."""
        return "".join(c or BLANK for c in self.effective_letters(word_index))

    def current_word(self, word_index: int) -> str | None:
        """The fully-filled word, or ``None`` if any cell is still blank."""
        letters = self.effective_letters(word_index)
        if any(c is None for c in letters):
            return None
        return "".join(letters)

    # -- mutating state ---------------------------------------------------

    def fill_word(self, word_index: int, letters: str | list[str | None]) -> str:
        """Fill (or partially fill / clear) a word and propagate helper letters.

        ``letters`` may be a string (``"_"`` clears a cell) or a list whose
        entries are single letters or ``None``. Entries beyond the word length
        are ignored; missing trailing entries are left untouched.
        """
        word = self.words[word_index]
        cells = list(letters) if not isinstance(letters, str) else list(letters)

        for pos, raw in enumerate(cells):
            if pos >= word.length:
                break
            value = _normalise_cell(raw)
            number = word.help_numbers[pos]
            if number is not None:
                if value is None:
                    self.helper_map.pop(number, None)
                else:
                    self.helper_map[number] = value
            else:
                word.direct[pos] = value
        return self.pattern(word_index)

    def clear_word(self, word_index: int) -> str:
        return self.fill_word(word_index, BLANK * self.words[word_index].length)

    # -- checking ---------------------------------------------------------

    def is_word_correct(self, word_index: int) -> bool:
        word = self.words[word_index]
        if not word.solution:
            return False
        current = self.current_word(word_index)
        return current is not None and current.lower() == word.solution.lower()

    def is_solved(self) -> bool:
        """True when every word is completely and correctly filled."""
        return bool(self.words) and all(
            self.is_word_correct(i) for i in range(len(self.words))
        )

    # -- serialisation ----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "date": self.date,
            "solution": self.solution,
            "helper_map": {str(k): v for k, v in sorted(self.helper_map.items())},
            "words": [
                {
                    "cryptogram": w.cryptogram,
                    "length": w.length,
                    "help_numbers": w.help_numbers,
                    "offset": w.offset,
                    "solution": w.solution,
                    "filled": self.effective_letters(i),
                }
                for i, w in enumerate(self.words)
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Puzzle:
        helper_map = {int(k): v for k, v in (data.get("helper_map") or {}).items()}
        words: list[Word] = []
        for w in data["words"]:
            help_numbers = list(w["help_numbers"])
            filled = w.get("filled") or [None] * w["length"]
            # Plain cells are restored from `filled`; helper cells come from
            # helper_map and are left as None in `direct`.
            direct = [
                (filled[p] if help_numbers[p] is None else None)
                for p in range(w["length"])
            ]
            words.append(
                Word(
                    cryptogram=w["cryptogram"],
                    length=w["length"],
                    help_numbers=help_numbers,
                    offset=w["offset"],
                    solution=w.get("solution"),
                    direct=direct,
                )
            )
        return cls(
            id=data["id"],
            title=data["title"],
            date=data["date"],
            solution=data.get("solution"),
            words=words,
            helper_map=helper_map,
        )
