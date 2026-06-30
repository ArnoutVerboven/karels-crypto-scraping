import argparse
import csv
import json

from karels_crypto_solving import human_benchmark as hb


def _generate(tmp_path, per_cell=2):
    args = argparse.Namespace(
        per_cell=per_cell, fractions=[0.0, 0.5], seed=0, output_dir=str(tmp_path)
    )
    hb.generate(args)
    rows = list(csv.DictReader((tmp_path / "human_benchmark_worksheet.csv").open(encoding="utf-8")))
    key = json.loads((tmp_path / "answer_key.json").read_text())
    return rows, key


def test_normalize():
    assert hb._normalize("  Café! ") == "café"
    assert hb._normalize("ABC-def") == "abcdef"


def test_generate_no_answer_leak_and_pattern_matches(tmp_path):
    rows, key = _generate(tmp_path)
    assert rows, "expected some rows"
    for r in rows:
        # The worksheet must never contain the solution.
        assert r["answer"] == ""
        assert r["id"] in key
        sol = key[r["id"]]["solution"]
        assert r["known"] != sol  # not fully revealed
        assert len(r["known"]) == int(r["length"]) == len(sol)
        # Revealed letters are consistent with the solution.
        for i, ch in enumerate(r["known"]):
            if ch != "_":
                assert ch == sol[i]


def test_score_excludes_seen_before(tmp_path):
    rows, key = _generate(tmp_path, per_cell=3)
    # Fill: all correct, but mark the first as seen_before -> excluded.
    for i, r in enumerate(rows):
        r["answer"] = key[r["id"]]["solution"]
        r["seen_before"] = "y" if i == 0 else ""
    filled = tmp_path / "filled.csv"
    with filled.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    args = argparse.Namespace(
        worksheet=str(filled), key=str(tmp_path / "answer_key.json"),
        model_grid=str(tmp_path / "missing.json"), output_dir=str(tmp_path),
    )
    hb.score(args)
    report = json.loads((tmp_path / "human_vs_model.json").read_text())
    assert report["overall"]["skipped"] == 1
    assert report["overall"]["total"] == len(rows) - 1
    assert report["overall"]["accuracy"] == 1.0
