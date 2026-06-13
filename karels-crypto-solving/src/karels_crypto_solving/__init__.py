"""LLM-based solver for Karel's Crypto (De Standaard).

Public API:

* :func:`~karels_crypto_solving.word_solver.solve_word` - solve a single clue.
* :func:`~karels_crypto_solving.puzzle_solver.solve_puzzle` - solve a whole
  puzzle with an agentic loop.
* :mod:`karels_crypto_solving.models` - the puzzle state with helper-letter
  propagation.
"""

from __future__ import annotations

__version__ = "0.1.0"
