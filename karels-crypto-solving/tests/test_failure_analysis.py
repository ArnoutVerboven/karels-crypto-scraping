from karels_crypto_solving.failure_analysis import quantitative


def test_quantitative_breakdown():
    preds = [
        {"expected": "lege", "predicted": "lege", "correct": True},
        {"expected": "forza", "predicted": "forte", "correct": False},  # right length, wrong
        {"expected": "stoven", "predicted": "stoof", "correct": False},  # wrong length
        {"expected": "algebra", "predicted": "", "correct": False},  # blank
    ]
    q = quantitative(preds)
    assert q["total"] == 4
    assert q["correct"] == 1
    assert q["accuracy"] == 0.25
    assert q["failures"] == 3
    assert q["blank_or_unparseable"] == 1
    assert q["wrong_length"] == 1
    assert q["right_length_wrong_word"] == 1
