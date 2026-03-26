"""Transposition table tests."""

from pyslow.constants import HASHF_ALPHA, HASHF_BETA, HASHF_EXACT
from pyslow.search.tt import TTEntry, TranspositionTable


def test_tt_exact_hit_returns_value_and_best_move() -> None:
    table = TranspositionTable(bucket_bits=2)
    table.store(TTEntry(key=5, value=123, flag=HASHF_EXACT, depth=4, priority=9, best_move=77))
    result = table.probe(5, depth=4, alpha=-10, beta=10)
    assert result.hit is True
    assert result.value == 123
    assert result.best_move == 77


def test_tt_alpha_entry_can_shrink_window() -> None:
    table = TranspositionTable(bucket_bits=2)
    table.store(TTEntry(key=5, value=20, flag=HASHF_ALPHA, depth=4, priority=9, best_move=11))
    result = table.probe(5, depth=4, alpha=0, beta=100)
    assert result.hit is False
    assert result.has_window is True
    assert result.window_alpha == 0
    assert result.window_beta == 21
    assert result.best_move == 11


def test_tt_beta_entry_cuts_when_value_exceeds_beta() -> None:
    table = TranspositionTable(bucket_bits=2)
    table.store(TTEntry(key=5, value=80, flag=HASHF_BETA, depth=4, priority=9, best_move=33))
    result = table.probe(5, depth=4, alpha=0, beta=50)
    assert result.hit is True
    assert result.value == 80
    assert result.best_move == -1


def test_tt_alpha_entry_returns_unknown_with_best_move_when_no_cut() -> None:
    table = TranspositionTable(bucket_bits=2)
    table.store(TTEntry(key=5, value=80, flag=HASHF_ALPHA, depth=4, priority=9, best_move=17))
    result = table.probe(5, depth=5, alpha=0, beta=100)
    assert result.hit is False
    assert result.has_window is False
    assert result.value is None
    assert result.best_move == 17


def test_tt_beta_entry_returns_unknown_with_best_move_when_no_cut() -> None:
    table = TranspositionTable(bucket_bits=2)
    table.store(TTEntry(key=5, value=80, flag=HASHF_BETA, depth=4, priority=9, best_move=17))
    result = table.probe(5, depth=4, alpha=0, beta=100)
    assert result.hit is False
    assert result.has_window is False
    assert result.value is None
    assert result.best_move == 17


def test_tt_prefers_second_slot_when_first_has_higher_priority() -> None:
    table = TranspositionTable(bucket_bits=1)
    first = TTEntry(key=2, value=10, flag=HASHF_EXACT, depth=1, priority=100, best_move=1)
    second = TTEntry(key=4, value=20, flag=HASHF_EXACT, depth=1, priority=10, best_move=2)
    table.store(first)
    table.store(second)
    assert table.probe(2, depth=1, alpha=-5, beta=5).value == 10
    assert table.probe(4, depth=1, alpha=-5, beta=5).value == 20
