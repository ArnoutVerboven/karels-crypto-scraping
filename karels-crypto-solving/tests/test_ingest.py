import json

from karels_crypto_solving import data
from karels_crypto_solving.ingest import (
    flatten_solutions,
    merge,
    merge_puzzle,
    normalise_date,
)


def sample_puzzle() -> dict:
    return {
        "number": 122,
        "date": "09-03-2019",
        "clues": [
            {"label": "A", "cryptogram": "  grappige meisjesnaam ", "numbers": [4, 1, 9, 2]},
            {"label": "B", "cryptogram": "onverwachte intriges", "numbers": [1, 9]},
            {"label": "C", "cryptogram": "no answer clue", "numbers": [2, 8, 5]},
        ],
    }


def test_normalise_date():
    assert normalise_date("09-03-2019") == "2019-03-09"
    assert normalise_date("2019-03-09") == "2019-03-09"
    assert normalise_date(None) == ""


def test_merge_puzzle_joins_answers_by_label():
    solution = {"number": 122, "solution": "Meta", "answers": {"A": "Lola", "B": "Plots"}}
    crypto = merge_puzzle(sample_puzzle(), solution, puzzle_id=900122)

    assert crypto["id"] == 900122
    assert crypto["title"] == "Karels Crypto 122"
    assert crypto["date"] == "2019-03-09"
    assert crypto["solution"] == "meta"

    a, b, c = crypto["words"]
    assert a["cryptogram"] == "grappige meisjesnaam"  # trimmed
    assert a["solution"] == "lola"  # lowercased, matched by label A
    assert a["length"] == 4
    assert a["help_numbers"] == [4, 1, 9, 2]  # key kept (count matches length)

    # 'B' answer 'plots' has length 5 but only 2 numbers -> don't trust alignment.
    assert b["solution"] == "plots"
    assert b["length"] == 5
    assert b["help_numbers"] == [None] * 5

    # 'C' has no answer -> solution None, length falls back to the number count.
    assert c["solution"] is None
    assert c["length"] == 3


def test_merge_puzzle_without_solution():
    crypto = merge_puzzle(sample_puzzle(), None, puzzle_id=1)
    assert all(w["solution"] is None for w in crypto["words"])
    assert crypto["solution"] is None


def test_merge_matches_by_number_and_assigns_ids():
    puzzles = [sample_puzzle()]
    solutions = [{"number": 122, "answers": {"A": "lola"}}]
    merged = merge(puzzles, solutions, id_start=900000)
    assert merged[0]["id"] == 900122  # id_start + number
    assert merged[0]["words"][0]["solution"] == "lola"


def test_flatten_solutions():
    raw = [{"puzzles": [{"number": 1}, {"number": 2}]}, {"puzzles": [{"number": 3}]}]
    assert [p["number"] for p in flatten_solutions(raw)] == [1, 2, 3]


def test_merged_output_loads_as_puzzles(tmp_path):
    merged = merge([sample_puzzle()], [{"number": 122, "answers": {"A": "lola"}}], 900000)
    path = tmp_path / "ingested.json"
    path.write_text(json.dumps(merged), encoding="utf-8")

    puzzles = data.load_ingested(path)
    assert len(puzzles) == 1
    assert puzzles[0].id == 900122
    assert puzzles[0].words[0].solution == "lola"
    # solved-word iteration picks up the labelled answer
    solved = list(data.iter_solved_words(puzzles))
    assert any(w.solution == "lola" for _p, _i, w in solved)
