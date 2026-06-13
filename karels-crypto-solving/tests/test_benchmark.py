import pytest

from karels_crypto_solving import benchmark, pricing
from karels_crypto_solving.word_solver import WordSolution


def fake_solve(cryptogram, length, pattern, *, client=None, model=None, max_completion_tokens=None):
    # "correct" when the clue starts with 'good'.
    answer = "right" if cryptogram.startswith("good") else "wrong"
    return WordSolution(answer=answer, raw="", prompt_tokens=10, completion_tokens=5)


def test_benchmark_model_aggregates():
    clues = [
        ("good1", 5, "_____", "right"),
        ("good2", 5, "_____", "right"),
        ("bad1", 4, "____", "right"),
    ]
    r = benchmark.benchmark_model(
        "gpt-4o", clues, client=None, max_completion_tokens=None, solve_fn=fake_solve
    )
    assert (r.correct, r.total, r.errors) == (2, 3, 0)
    assert r.accuracy == pytest.approx(2 / 3)
    assert r.prompt_tokens == 30 and r.completion_tokens == 15
    # 30 in @ $2.5/1M + 15 out @ $10/1M
    assert r.est_cost_usd == pytest.approx(30 / 1e6 * 2.5 + 15 / 1e6 * 10)


def test_benchmark_model_handles_errors():
    def boom(*args, **kwargs):
        raise RuntimeError("model not allowed")

    clues = [("x", 1, "_", "y"), ("z", 1, "_", "w")]
    r = benchmark.benchmark_model(
        "made-up-model", clues, client=None, max_completion_tokens=None, solve_fn=boom
    )
    assert r.errors == 2 and r.correct == 0 and r.accuracy == 0.0
    assert r.last_error == "model not allowed"
    assert r.est_cost_usd is None  # unknown model -> no price


def test_estimate_cost_known_and_unknown():
    assert pricing.estimate_cost("gpt-4o", 1_000_000, 0) == pytest.approx(2.5)
    assert pricing.estimate_cost("gpt-4o", 0, 1_000_000) == pytest.approx(10.0)
    assert pricing.estimate_cost("does-not-exist", 100, 100) is None


def test_render_markdown_sorted_by_accuracy():
    results = [
        benchmark.ModelResult("a", 1, 10, 0, 0, 0, 0.0, 0.1, 0.0),
        benchmark.ModelResult("b", 9, 10, 0, 0, 0, 0.0, 0.9, 0.0),
    ]
    md = benchmark.render_markdown(results, {"n_clues": 10, "reveal": "none", "timestamp": "t"})
    assert md.index("| b |") < md.index("| a |")  # higher accuracy first
