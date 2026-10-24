from karels_crypto_solving.llm_reveal import letters_only, matrix, pattern_for, reveal_order_for


def test_reveal_order_matches_app():
    # Same values as revealOrderFor() in karels-crypto-benchmark/src/game/word.ts
    assert reveal_order_for("roma", 0) == [3, 2, 0, 1]
    assert reveal_order_for("ezeltje-prik", 123) == [8, 0, 6, 3, 11, 5, 2, 10, 4, 1, 9]
    assert reveal_order_for("Première", 4294967295) == [0, 2, 6, 3, 5, 4, 1, 7]


def test_pattern_keeps_hyphen_and_shows_prefix():
    order = reveal_order_for("ezeltje-prik", 123)
    assert pattern_for("ezeltje-prik", order, 0) == "_______-____"
    assert pattern_for("ezeltje-prik", order, 3) == "e_____e-p___"
    assert letters_only("Ezeltje-Prik") == "ezeltjeprik"


def test_matrix_counts_success_from_k_star_up():
    m = matrix([(4, 2), (4, None), (3, 0)])
    assert m[4] == {0: [0, 2], 1: [0, 2], 2: [1, 2], 3: [1, 2]}
    assert m[3] == {0: [1, 1], 1: [1, 1], 2: [1, 1]}


def test_transport_errors_are_retried(monkeypatch):
    import karels_crypto_solving.llm_reveal as lr
    from karels_crypto_solving.word_solver import WordSolution

    calls = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("Server disconnected without sending a response.")
        return WordSolution(answer="roma", raw="ANSWER: roma")

    monkeypatch.setattr(lr, "solve_word", flaky)
    monkeypatch.setattr(lr.time, "sleep", lambda s: None)
    task = {"clueId": "1-0", "text": "x", "answer": "roma", "length": 4, "order": [3, 2, 0, 1]}
    res = lr.solve_with_reveals("m", task, None)
    assert res["k_star"] == 0 and len(calls) == 2
