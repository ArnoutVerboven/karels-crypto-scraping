import random

from karels_crypto_solving import config
from karels_crypto_solving.models import Word
from karels_crypto_solving.patterns import build_pattern, helper_positions
from karels_crypto_solving.word_solver import _parse_answer


def make_word() -> Word:
    # "forza": helper cells at positions 0 and 3.
    return Word(
        cryptogram="Italia, Ninove",
        length=5,
        help_numbers=[15, None, None, 18, None],
        offset=4,
        solution="forza",
    )


def test_helper_positions():
    assert helper_positions(make_word()) == [0, 3]


def test_build_pattern_none():
    assert build_pattern(make_word(), "none") == "_____"


def test_build_pattern_all():
    # Reveal the helper-cell letters from the solution: f at 0, z at 3.
    assert build_pattern(make_word(), "all") == "f__z_"


def test_build_pattern_partial_is_deterministic_with_seed():
    w = make_word()
    a = build_pattern(w, "partial", fraction=0.5, rng=random.Random(0))
    b = build_pattern(w, "partial", fraction=0.5, rng=random.Random(0))
    assert a == b
    # Partial reveals no more than the "all" case.
    revealed = sum(c != "_" for c in a)
    assert revealed <= 2


def test_is_reasoning_model():
    for m in ["o3", "o4-mini", "gpt-5-2025-08-07", "gpt-5.5-2026-04-23", "gpt-5-mini-2025-08-07"]:
        assert config.is_reasoning_model(m), m
    for m in ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", "gpt-4.1", "gpt-5-chat-latest"]:
        assert not config.is_reasoning_model(m), m


def test_parse_answer_variants():
    assert _parse_answer("reasoning...\nANSWER: forza") == "forza"
    assert _parse_answer("ANSWER: Forza!") == "forza"
    assert _parse_answer("some text\nthe word is\nlege") == "lege"
    assert _parse_answer('ANSWER: "spiegeleieren"') == "spiegeleieren"
