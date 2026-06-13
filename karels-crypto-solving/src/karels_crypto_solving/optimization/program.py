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


def exact_match_metric(example, pred, trace=None) -> bool:
    """Exact-match metric: did the model produce the correct word (zero-shot)?"""
    return normalise(getattr(pred, "solution", "")) == normalise(example.solution)


# Edit this string to inject your own domain knowledge into GEPA's reflection
# (it is passed verbatim to the reflection LM for every wrong answer).
WRONG_ANSWER_FEEDBACK = (
    "Karel's Crypto clues use cryptic wordplay: a definition part plus a wordplay "
    "part (anagram, hidden word, reversal, container, deletion/insertion, "
    "homophone, charades, double definition, and sometimes bilingual puns - the "
    "puzzle is Flemish/Dutch). Identify which part is the definition and which is "
    "the wordplay, then make the answer a real Dutch word whose length and any "
    "known letters match the pattern exactly."
)


def gepa_feedback_metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    """GEPA feedback metric: returns a score plus natural-language feedback.

    The ``feedback`` string is what GEPA's reflection LM reads to propose a
    better instruction, so it's the place to add domain knowledge.
    """
    import dspy

    if exact_match_metric(gold, pred):
        return dspy.Prediction(score=1.0, feedback="Correct: the answer matches.")
    expected = getattr(gold, "solution", "")
    got = normalise(getattr(pred, "solution", "")) or "(no answer)"
    return dspy.Prediction(
        score=0.0,
        feedback=f"Incorrect. Expected '{expected}', got '{got}'. {WRONG_ANSWER_FEEDBACK}",
    )
