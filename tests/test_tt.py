"""Transposition table tests."""

from pygomoku.board import Board, xy_to_move
from pygomoku.config import load_default_config
from pygomoku.constants import HASHF_ALPHA, HASHF_BETA, HASHF_EXACT
from pygomoku.eval.caches import EvalCaches
from pygomoku.eval.local import recompute_all
from pygomoku.search.alphabeta import AlphaBetaSearcher, SearchStats
from pygomoku.search.tt import TTEntry, TranspositionTable


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


def test_tt_beta_entry_narrows_alpha_window_when_no_cut() -> None:
    table = TranspositionTable(bucket_bits=2)
    table.store(TTEntry(key=5, value=80, flag=HASHF_BETA, depth=4, priority=9, best_move=17))
    result = table.probe(5, depth=4, alpha=0, beta=100)
    assert result.hit is False
    assert result.has_window is True
    assert result.window_alpha == 80
    assert result.window_beta == 100
    assert result.value is None
    assert result.best_move == 17


def test_tt_beta_entry_alpha_already_above_value_keeps_alpha() -> None:
    table = TranspositionTable(bucket_bits=2)
    table.store(TTEntry(key=5, value=30, flag=HASHF_BETA, depth=4, priority=9, best_move=17))
    result = table.probe(5, depth=4, alpha=50, beta=100)
    assert result.has_window is True
    assert result.window_alpha == 50  # max(50, 30)
    assert result.window_beta == 100


def test_tt_second_slot_checked_when_first_has_insufficient_depth() -> None:
    # entry[0]: same key, shallow depth (insufficient) - should not block entry[1]
    # entry[1]: same key, deep exact hit - should be found
    table = TranspositionTable(bucket_bits=1)
    shallow = TTEntry(key=2, value=99, flag=HASHF_EXACT, depth=1, priority=100, best_move=5)
    deep = TTEntry(key=2, value=42, flag=HASHF_EXACT, depth=6, priority=10, best_move=7)
    table.store(shallow)   # goes to slot 0 (high priority)
    table.store(deep)      # goes to slot 1 (lower priority)
    # requesting depth=5: slot 0 has depth=1 (insufficient), slot 1 has depth=6 (sufficient)
    result = table.probe(2, depth=5, alpha=-200, beta=200)
    assert result.hit is True
    assert result.value == 42
    assert result.best_move == 7


def test_tt_prefers_second_slot_when_first_has_higher_priority() -> None:
    table = TranspositionTable(bucket_bits=1)
    first = TTEntry(key=2, value=10, flag=HASHF_EXACT, depth=1, priority=100, best_move=1)
    second = TTEntry(key=4, value=20, flag=HASHF_EXACT, depth=1, priority=10, best_move=2)
    table.store(first)
    table.store(second)
    assert table.probe(2, depth=1, alpha=-5, beta=5).value == 10
    assert table.probe(4, depth=1, alpha=-5, beta=5).value == 20


def test_tt_default_bucket_bits_match_corrected_alignment_baseline() -> None:
    table = TranspositionTable()
    assert table.bucket_mask == (1 << 20) - 1


def test_tt_starts_empty_and_grows_on_store() -> None:
    table = TranspositionTable(bucket_bits=4)
    assert len(table.buckets) == 0
    table.store(TTEntry(key=3, value=10, flag=HASHF_EXACT, depth=2, priority=5, best_move=7))
    assert len(table.buckets) == 1
    table.store(TTEntry(key=4, value=20, flag=HASHF_EXACT, depth=2, priority=5, best_move=8))
    assert len(table.buckets) == 2
    # Storing to the same slot (key & mask collision) must not grow the dict.
    table.store(TTEntry(key=3 + 16, value=30, flag=HASHF_EXACT, depth=1, priority=1, best_move=9))
    assert len(table.buckets) == 2


def test_tt_winning_exact_store_adds_windepth_as_expected() -> None:
    board = Board()
    sequence = [
        (3, 7, 1),
        (0, 0, -1),
        (4, 7, 1),
        (1, 0, -1),
        (5, 7, 1),
        (2, 0, -1),
        (6, 7, 1),
    ]
    for x, y, side in sequence:
        board.play(xy_to_move(x, y), side)

    caches = EvalCaches()
    recompute_all(board, caches)
    table = TranspositionTable()
    searcher = AlphaBetaSearcher(load_default_config(), table)
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        3.0,
        -20002,
        20002,
        8,
        opo=1,
        ply=1,
        stats=SearchStats(),
    )

    assert score <= -15000
    entry = next(item for item in table._bucket(board.zobrist_key) if item.key == board.zobrist_key)
    assert entry.flag == HASHF_EXACT
    assert entry.depth == 13
    assert entry.best_move == move
