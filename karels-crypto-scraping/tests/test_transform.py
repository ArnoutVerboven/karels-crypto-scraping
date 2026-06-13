import json
from pathlib import Path

import pytest

from karels_crypto.transform import puzzle_to_crypto

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def home_node() -> dict:
    payload = json.loads((FIXTURES / "home_puzzle.json").read_text(encoding="utf-8"))
    return payload["data"]["published_puzzle"]


def test_puzzle_to_crypto_basic_fields(home_node):
    crypto = puzzle_to_crypto(home_node)
    assert crypto.id == 868
    assert crypto.date == "2026-06-13"
    assert crypto.solution == "groepsisolationisme"
    # Karel's Crypto always has 19 rows / a 19-letter vertical solution.
    assert len(crypto.words) == 19
    assert len(crypto.solution) == 19


def test_word_fields_and_lengths(home_node):
    crypto = puzzle_to_crypto(home_node)
    first = crypto.words[0]
    assert first.cryptogram == "die kleur mengen leidt tot kale"
    assert first.solution == "lege"
    assert first.length == 4
    assert first.length == len(first.solution)
    assert first.offset == 4
    # help_numbers has one slot per letter.
    assert len(first.help_numbers) == first.length


def test_help_numbers_derived_from_legend(home_node):
    crypto = puzzle_to_crypto(home_node)
    # "lege" has a numbered cell at index 0 ('l'); legend maps 'l' -> 11.
    assert crypto.words[0].help_numbers == [11, None, None, None]
    # "Forza" has numbered cells at index 0 ('f'->15) and index 3 ('z'->18).
    forza = next(w for w in crypto.words if w.solution == "Forza")
    assert forza.help_numbers == [15, None, None, 18, None]


def test_help_numbers_mostly_empty(home_node):
    crypto = puzzle_to_crypto(home_node)
    for word in crypto.words:
        filled = [n for n in word.help_numbers if n is not None]
        # By design only a few cells per row carry a number.
        assert len(filled) < word.length


def test_without_solution_strips_answers(home_node):
    crypto = puzzle_to_crypto(home_node).without_solution()
    assert crypto.solution is None
    assert all(w.solution is None for w in crypto.words)
    # Clues and help numbers remain (they are public hints).
    assert crypto.words[0].cryptogram == "die kleur mengen leidt tot kale"
    assert crypto.words[0].help_numbers == [11, None, None, None]
