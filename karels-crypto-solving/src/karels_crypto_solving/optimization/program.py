"""The DSPy program and metric optimised for the word solver.

DSPy splits *what* (a ``Signature``: typed inputs/outputs + an instruction
docstring) from *how* (a ``Module``: e.g. ``ChainOfThought`` for thinking
steps). MIPROv2 then rewrites the instruction (and optionally picks few-shot
demos) to maximise our metric.
"""

from __future__ import annotations

import re

import dspy


class SolveCryptogram(dspy.Signature):
    """Solve a clue from Karel's Crypto, a Dutch cryptic word puzzle.

    Each clue cryptically describes exactly one Dutch word (through wordplay,
    double meanings, hidden words, anagram-like tricks, etc.). Return that word.
    """

    cryptogram: str = dspy.InputField(desc="the cryptic clue")
    pattern: str = dspy.InputField(
        desc="known letters in the answer, '_' marks an unknown position"
    )
    solution: str = dspy.OutputField(desc="the single Dutch word, lowercase")


def build_program() -> dspy.Module:
    """ChainOfThought lets the model reason before answering ('thinking steps')."""
    return dspy.ChainOfThought(SolveCryptogram)


def normalise(word: str) -> str:
    """Lowercase and keep letters only, for robust exact-match comparison."""
    return re.sub(r"[^a-zàâäéèêëïîôöùûüçáíóúñ]", "", (word or "").lower())


def one_shot_metric(example, pred, trace=None) -> bool:
    """Exact-match metric: the 'loss' is how many words are one-shotted."""
    return normalise(getattr(pred, "solution", "")) == normalise(example.solution)
