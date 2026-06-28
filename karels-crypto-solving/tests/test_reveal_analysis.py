from karels_crypto_solving import reveal_analysis as ra
from karels_crypto_solving.models import Word


def _word(cryptogram="clue", solution="kraan"):
    return Word(cryptogram=cryptogram, length=len(solution), help_numbers=[None] * len(solution),
                offset=0, solution=solution)


def test_bucket_of():
    assert ra.bucket_of(3) == "3-4"
    assert ra.bucket_of(4) == "3-4"
    assert ra.bucket_of(6) == "5-6"
    assert ra.bucket_of(12) == "11+"


def test_reveal_count_leaves_one_unknown():
    assert ra._reveal_count(5, 0.0) == 0
    assert ra._reveal_count(4, 0.5) == 2
    # 75% of 4 = 3, but never reveal the whole word.
    assert ra._reveal_count(4, 1.0) == 3
    assert ra._reveal_count(8, 0.75) == 6


def test_reveal_pattern_is_nested_and_uses_solution():
    word = _word(solution="kraan")
    perm = ra._permutation(word, seed=0)
    p1 = ra.reveal_pattern(word, perm, 1)
    p3 = ra.reveal_pattern(word, perm, 3)
    assert len(p1) == len(p3) == 5
    assert sum(c != "_" for c in p1) == 1
    assert sum(c != "_" for c in p3) == 3
    # Nested: every letter revealed at k=1 is still revealed at k=3.
    for i, ch in enumerate(p1):
        if ch != "_":
            assert p3[i] == ch
    # Revealed letters come from the solution.
    for i, ch in enumerate(p3):
        if ch != "_":
            assert ch == "kraan"[i]


def test_permutation_is_deterministic():
    word = _word()
    assert ra._permutation(word, 0) == ra._permutation(word, 0)
