from karels_crypto_solving.models import Puzzle, Word


def make_puzzle() -> Puzzle:
    # Two words sharing help number 5.
    w0 = Word(cryptogram="clue0", length=3, help_numbers=[5, None, None], offset=0, solution="abc")
    w1 = Word(cryptogram="clue1", length=2, help_numbers=[None, 5], offset=0, solution="xa")
    return Puzzle(id=1, title="t", date="2026-01-01", solution=None, words=[w0, w1])


def test_helper_letter_propagation():
    p = make_puzzle()
    assert p.pattern(0) == "___"
    assert p.pattern(1) == "__"

    # Fill word 0; its cell 0 carries number 5 -> propagates to word 1 cell 1.
    p.fill_word(0, "abc")
    assert p.pattern(0) == "abc"
    assert p.pattern(1) == "_a"  # 'a' auto-filled via the shared number


def test_partial_fill_and_clear():
    p = make_puzzle()
    p.fill_word(0, "a__")
    assert p.pattern(0) == "a__"
    assert p.pattern(1) == "_a"

    # Clearing the helper cell removes it everywhere.
    p.fill_word(0, "_")
    assert p.pattern(0) == "___"
    assert p.pattern(1) == "__"


def test_fill_with_list_and_none():
    p = make_puzzle()
    p.fill_word(0, ["a", "b", None])
    assert p.pattern(0) == "ab_"


def test_correctness_and_solved():
    p = make_puzzle()
    assert not p.is_solved()
    p.fill_word(0, "abc")  # also reveals 'a' for word 1
    assert p.is_word_correct(0)
    assert not p.is_word_correct(1)
    p.fill_word(1, "xa")
    assert p.is_word_correct(1)
    assert p.is_solved()


def test_invalid_index_ignored_via_bounds():
    p = make_puzzle()
    # Extra letters beyond the word length are ignored.
    p.fill_word(0, "abcdef")
    assert p.pattern(0) == "abc"


def test_round_trip_serialisation():
    p = make_puzzle()
    p.fill_word(0, "abc")
    p.fill_word(1, "x")  # only cell 0 (cell 1 is the shared helper)
    restored = Puzzle.from_dict(p.to_dict())
    assert restored.pattern(0) == p.pattern(0)
    assert restored.pattern(1) == p.pattern(1)
    assert restored.helper_map == p.helper_map
    assert restored.is_solved() == p.is_solved()
