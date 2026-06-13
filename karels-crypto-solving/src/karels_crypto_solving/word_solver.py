"""Solve a single Karel's Crypto clue with an LLM.

No tools, no vocabulary database - just a prompt. The clue (and any already
known letters) are injected into the system prompt. The model may reason in its
reply ("thinking steps"); we read the final ``ANSWER:`` line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import config
from .models import Puzzle
from .prompts import WORD_SOLVER_SYSTEM, render_word_pattern

_ANSWER_RE = re.compile(r"answer\s*[:\-]\s*(.+)", re.IGNORECASE)


@dataclass
class WordSolution:
    answer: str
    raw: str


def _parse_answer(text: str) -> str:
    """Extract the answer word from the model's reply."""
    candidate = ""
    for match in _ANSWER_RE.finditer(text):
        candidate = match.group(1).strip()
    if not candidate:
        # Fall back to the last non-empty line.
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        candidate = lines[-1] if lines else ""
    # Keep letters only (handles quotes, punctuation, trailing notes).
    cleaned = re.sub(r"[^^a-zA-Zàâäéèêëïîôöùûüçáíóúñ]", " ", candidate).split()
    return cleaned[0].lower() if cleaned else candidate.strip().lower()


def solve_word(
    cryptogram: str,
    length: int,
    pattern: str | None = None,
    *,
    client=None,
    model: str | None = None,
    system_prompt: str = WORD_SOLVER_SYSTEM,
    temperature: float | None = None,
) -> WordSolution:
    """Solve one clue. ``pattern`` is the known-letters string (``_`` = unknown)."""
    if pattern is None:
        pattern = "_" * length

    client = client or config.openai_client()
    model = model or config.model_name()

    system = system_prompt.format(
        cryptogram=cryptogram, length=length, pattern=pattern
    )
    kwargs = {}
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": "Solve the clue."},
        ],
        **kwargs,
    )
    raw = response.choices[0].message.content or ""
    return WordSolution(answer=_parse_answer(raw), raw=raw)


def solve_word_in_puzzle(puzzle: Puzzle, word_index: int, **kwargs) -> WordSolution:
    """Solve a word using the puzzle's current known letters as the pattern."""
    word = puzzle.words[word_index]
    pattern = render_word_pattern(puzzle.effective_letters(word_index))
    return solve_word(word.cryptogram, word.length, pattern, **kwargs)
