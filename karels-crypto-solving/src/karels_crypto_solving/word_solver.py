"""Solve a single Karel's Crypto clue with an LLM.

No tools, no vocabulary database - just a prompt. The clue (and any already
known letters) are injected into the system prompt. The model may reason in its
reply ("thinking steps"); we read the final ``ANSWER:`` line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import config, providers
from .models import Puzzle
from .prompts import WORD_SOLVER_SYSTEM, render_word_pattern

_ANSWER_RE = re.compile(r"answer\s*[:\-]\s*(.+)", re.IGNORECASE)


@dataclass
class WordSolution:
    answer: str
    raw: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


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
    client=None,  # deprecated/ignored; kept for backwards compatibility
    model: str | None = None,
    system_prompt: str = WORD_SOLVER_SYSTEM,
    temperature: float | None = None,
    max_completion_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> WordSolution:
    """Solve one clue via the generic provider interface (OpenAI/Anthropic/Google).

    ``pattern`` is the known-letters string (``_`` = unknown). Provider-specific
    param handling (thinking, temperature, token budget) lives in ``providers``.
    """
    if pattern is None:
        pattern = "_" * length
    model = model or config.model_name()
    system = system_prompt.format(cryptogram=cryptogram, length=length, pattern=pattern)

    result = providers.chat(
        model,
        system,
        "Solve the clue.",
        max_tokens=max_completion_tokens,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )
    return WordSolution(
        answer=_parse_answer(result.text),
        raw=result.text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )


def solve_word_in_puzzle(puzzle: Puzzle, word_index: int, **kwargs) -> WordSolution:
    """Solve a word using the puzzle's current known letters as the pattern."""
    word = puzzle.words[word_index]
    pattern = render_word_pattern(puzzle.effective_letters(word_index))
    return solve_word(word.cryptogram, word.length, pattern, **kwargs)
