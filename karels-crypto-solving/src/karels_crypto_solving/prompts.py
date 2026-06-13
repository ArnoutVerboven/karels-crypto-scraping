"""Default prompts for the two solvers.

These are intentionally *very basic* baselines. The whole point of the
``optimization`` submodule is to improve the word-solver prompt automatically
with DSPy, so keep this short and let the optimizer do the heavy lifting.

Both prompts use ``str.format`` parameter injection: the puzzle / word context
is injected into the system prompt.
"""

from __future__ import annotations

# --- word solver -----------------------------------------------------------

WORD_SOLVER_SYSTEM = """\
You solve clues from Karel's Crypto, a Dutch cryptic word puzzle: each clue \
cryptically describes one Dutch word.

Clue: {cryptogram}
Length: {length} letters
Known letters: {pattern}   (a letter where known, "_" where unknown)

Reason briefly, then end your reply with exactly one line:
ANSWER: <the single word, lowercase>
"""

# --- puzzle solver (agentic) ----------------------------------------------

PUZZLE_SOLVER_SYSTEM = """\
You solve an entire Karel's Crypto puzzle: 19 Dutch clues whose answers share a \
numbered grid. Cells that show the same number contain the same letter, so \
solving one word reveals letters in others.

Work iteratively:
- Use `fill_word(word_index, letters)` to write a guess. `letters` is a string \
the same length as the word; use "_" for cells you don't know (or to erase a \
cell you now think is wrong).
- Filling a numbered cell automatically propagates that letter to other words.
- Use `check_puzzle()` to test whether the whole puzzle is correct. Keep going \
until it returns true (or you can make no further progress).

Current puzzle:
{board}
"""


def render_word_pattern(letters) -> str:
    """Render a list of letters/None as a known-letters pattern string."""
    return "".join((c or "_") for c in letters)
