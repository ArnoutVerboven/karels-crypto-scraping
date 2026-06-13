"""Helpers to build a word's "known letters" pattern.

Used both by the runner (to optionally pre-fill helper letters) and by the
optimization submodule (to run the no-letters vs. some-letters experiments).
"""

from __future__ import annotations

import random

from .models import BLANK, Word

RevealMode = str  # "none" | "partial" | "all"


def helper_positions(word: Word) -> list[int]:
    return [i for i, n in enumerate(word.help_numbers) if n is not None]


def build_pattern(
    word: Word,
    mode: RevealMode = "none",
    *,
    fraction: float = 0.0,
    rng: random.Random | None = None,
) -> str:
    """Return a length-sized pattern (``_`` = unknown).

    * ``none``    - everything unknown.
    * ``all``     - every helper-cell letter revealed (from the solution).
    * ``partial`` - a ``fraction`` of the helper cells revealed.
    """
    letters = [BLANK] * word.length
    if not word.solution or mode == "none":
        return "".join(letters)

    positions = helper_positions(word)
    if mode == "partial" and positions:
        rng = rng or random.Random(0)
        count = round(len(positions) * fraction)
        positions = sorted(rng.sample(positions, count)) if count < len(positions) else positions

    solution = word.solution.lower()
    for pos in positions:
        if pos < len(solution):
            letters[pos] = solution[pos]
    return "".join(letters)
