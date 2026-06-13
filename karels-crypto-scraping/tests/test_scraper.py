import json
from pathlib import Path

import pytest

from karels_crypto.scraper import build_datasets, run
from karels_crypto.storage import load_history, load_latest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw_puzzles() -> list[dict]:
    payload = json.loads((FIXTURES / "puzzles.json").read_text(encoding="utf-8"))
    return payload["data"]["puzzles"]["data"]


def test_build_datasets_splits_latest_and_history(raw_puzzles):
    history, latest = build_datasets(raw_puzzles)

    # Newest puzzle (id 868, 2026-06-13) is the latest, without a solution.
    assert latest is not None
    assert latest.id == 868
    assert latest.solution is None
    assert all(w.solution is None for w in latest.words)

    # The rest are kept as history, each with its solution.
    assert {c.id for c in history} == {866, 867}
    assert all(c.solution for c in history)
    assert all(any(w.solution for w in c.words) for c in history)


def test_build_datasets_empty():
    assert build_datasets([]) == ([], None)


def test_run_persists_and_accumulates(tmp_path, raw_puzzles):
    history_path = tmp_path / "history.json"
    latest_path = tmp_path / "latest.json"

    run(history_path=history_path, latest_path=latest_path, raw_puzzles=raw_puzzles)

    assert {c.id for c in load_history(history_path)} == {866, 867}
    assert load_latest(latest_path).id == 868

    # A later run that only sees a brand-new puzzle keeps prior history and
    # archives the previously-latest puzzle (idempotent + accumulating).
    newer = dict(raw_puzzles[0])
    newer["id"] = 869
    newer["start_date"] = "2026-06-20 00:00:00"
    newer["title"] = "Karels Crypto 20 juni"

    run(
        history_path=history_path,
        latest_path=latest_path,
        raw_puzzles=raw_puzzles + [newer],
    )

    history_ids = {c.id for c in load_history(history_path)}
    assert history_ids == {866, 867, 868}
    assert load_latest(latest_path).id == 869


def test_round_trip_serialisation(tmp_path, raw_puzzles):
    history_path = tmp_path / "history.json"
    latest_path = tmp_path / "latest.json"
    run(history_path=history_path, latest_path=latest_path, raw_puzzles=raw_puzzles)

    reloaded = load_history(history_path)
    assert [c.to_dict() for c in reloaded] == [
        c.to_dict() for c in load_history(history_path)
    ]
