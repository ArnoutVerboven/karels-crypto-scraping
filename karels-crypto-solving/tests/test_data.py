"""Integration with the scraped datasets (read-only, no network)."""

from karels_crypto_solving import data


def test_load_history_and_iter_words():
    puzzles = data.load_history()
    assert puzzles, "expected scraped history puzzles to be available"
    for p in puzzles:
        assert len(p.words) == 19
        # Each word starts unfilled.
        assert p.pattern(0) == "_" * p.words[0].length

    words = list(data.iter_solved_words(puzzles))
    assert words, "history words should have known solutions"
    _, _, word = words[0]
    assert word.solution
    assert len(word.solution) == word.length
