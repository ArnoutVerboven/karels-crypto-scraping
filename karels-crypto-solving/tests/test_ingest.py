from karels_crypto_solving import data
from karels_crypto_solving.ingest import to_crypto_dict


def test_to_crypto_dict_normalises_answers():
    raw = {
        "title": "Karels Crypto 1 mei",
        "date": "2026-05-01",
        "solution": "Groepsisolationisme",
        "words": [
            {"cryptogram": "  die kleur mengen leidt tot kale ", "solution": "Lege"},
            {"cryptogram": "Italia, Ninove", "solution": None},
        ],
    }
    crypto = to_crypto_dict(raw, puzzle_id=900000, title_fallback="img_1")

    assert crypto["id"] == 900000
    assert crypto["solution"] == "groepsisolationisme"  # lowercased
    w0, w1 = crypto["words"]
    # cryptogram trimmed; answer lowercased; length derived from the answer.
    assert w0["cryptogram"] == "die kleur mengen leidt tot kale"
    assert w0["solution"] == "lege"
    assert w0["length"] == 4
    assert w0["help_numbers"] == [None, None, None, None]
    assert w0["offset"] == 0
    # No filled answer -> solution None, length falls back (0 here).
    assert w1["solution"] is None
    assert w1["length"] == 0


def test_to_crypto_dict_title_fallback():
    crypto = to_crypto_dict({"words": []}, puzzle_id=1, title_fallback="photo_3")
    assert crypto["title"] == "photo_3"
    assert crypto["solution"] is None


def test_load_ingested_missing_returns_empty(tmp_path):
    assert data.load_ingested(tmp_path / "nope.json") == []


def test_load_ingested_round_trips(tmp_path):
    crypto = to_crypto_dict(
        {"title": "t", "date": "2026-05-01", "solution": "abc",
         "words": [{"cryptogram": "clue", "solution": "abc"}]},
        puzzle_id=900001,
        title_fallback="x",
    )
    import json

    path = tmp_path / "ingested.json"
    path.write_text(json.dumps([crypto]), encoding="utf-8")

    puzzles = data.load_ingested(path)
    assert len(puzzles) == 1
    assert puzzles[0].id == 900001
    assert puzzles[0].words[0].solution == "abc"
