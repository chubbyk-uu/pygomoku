"""Evaluation tests."""

import random

from pyslow.board import Board, xy_to_move
from pyslow.config import load_default_config
from pyslow.constants import BOARD_SIZE
from pyslow.eval.caches import EvalCaches
from pyslow.eval.global_eval import _evaluate_last5_branch, _evaluate_next43_branch, _find_last5_target, evaluate_board
from pyslow.eval.local import (
    attack_level,
    move_value,
    recompute_all,
    recompute_point_caches,
    value_wide_compute,
)
from pyslow.patterns.shapes import ShapeLabel


def test_eval_caches_start_with_zeroed_storage() -> None:
    caches = EvalCaches()
    assert not caches.initialized
    assert len(caches.board_shadow) == BOARD_SIZE
    assert len(caches.shape_cache) == 2
    assert caches.board_shadow[0][0] == 0
    assert caches.shape_cache[0][0][0] == [0, 0, 0, 0]
    assert caches.value_cache[1][BOARD_SIZE - 1][BOARD_SIZE - 1] == 0


def test_eval_caches_reset_restores_zero_state() -> None:
    caches = EvalCaches()
    caches.initialized = True
    caches.board_shadow[0][0] = 1
    caches.shape_cache[0][0][0][0] = 123
    caches.value_cache[1][0][0] = 9
    caches.attack_cache[1][0][0] = 7
    caches.reset()
    assert not caches.initialized
    assert caches.board_shadow[0][0] == 0
    assert caches.shape_cache[0][0][0] == [0, 0, 0, 0]
    assert caches.value_cache[1][0][0] == 0
    assert caches.attack_cache[1][0][0] == 0


def test_eval_caches_snapshot_restore_roundtrip() -> None:
    caches = EvalCaches()
    caches.initialized = True
    caches.board_shadow[0][0] = 1
    caches.shape_cache[0][1][1][2] = 99
    caches.value_cache[1][2][2] = 7
    caches.attack_cache[1][3][3] = 5
    snapshot = caches.snapshot()
    caches.board_shadow[0][0] = 0
    caches.shape_cache[0][1][1][2] = 0
    caches.value_cache[1][2][2] = 0
    caches.attack_cache[1][3][3] = 0
    caches.restore_snapshot(snapshot)
    assert caches.initialized
    assert caches.board_shadow[0][0] == 1
    assert caches.shape_cache[0][1][1][2] == 99
    assert caches.value_cache[1][2][2] == 7
    assert caches.attack_cache[1][3][3] == 5


def test_recompute_point_caches_finds_black_five_threat() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_point_caches(board, caches, 7, 7)
    assert attack_level(caches, 7, 7, 1) == 6
    assert caches.value_cache[0][7][7] > 0


def test_recompute_all_populates_board_shadow_from_board() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    assert caches.board_shadow[7][7] == 1
    assert caches.board_shadow[8][7] == -1


def test_incremental_value_wide_matches_full_recompute() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    board.play(xy_to_move(7, 8))
    board.play(xy_to_move(8, 8))

    incremental = EvalCaches()
    full = EvalCaches()
    value_wide_compute(board, incremental)
    recompute_all(board, full)

    assert incremental.board_shadow == full.board_shadow
    assert incremental.shape_cache == full.shape_cache
    assert incremental.value_cache == full.value_cache
    assert incremental.attack_cache == full.attack_cache


def test_value_wide_compute_roundtrip_after_play_and_undo() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    snapshot = caches.snapshot()

    board.play(xy_to_move(7, 8))
    value_wide_compute(board, caches)
    board.undo()
    value_wide_compute(board, caches)

    assert caches.snapshot() == snapshot


def test_value_wide_compute_matches_full_recompute_after_multiple_steps() -> None:
    board = Board()
    caches = EvalCaches()
    recompute_all(board, caches)

    sequence = [xy_to_move(7, 7), xy_to_move(8, 7), xy_to_move(7, 8), xy_to_move(8, 8), xy_to_move(6, 7)]
    for move in sequence:
        board.play(move)
        value_wide_compute(board, caches)
        full = EvalCaches()
        recompute_all(board, full)
        assert caches.board_shadow == full.board_shadow
        assert caches.shape_cache == full.shape_cache
        assert caches.value_cache == full.value_cache
        assert caches.attack_cache == full.attack_cache


def test_move_value_uses_attack_and_defend_tables() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_point_caches(board, caches, 7, 7)
    config = load_default_config()
    expected = (
        config.eval_tables.attack_value[caches.value_cache[0][7][7]]
        + config.eval_tables.defend_value[caches.value_cache[1][7][7]]
    )
    assert move_value(caches, 7, 7, 1, config) == expected


def test_global_evaluation_prefers_side_with_immediate_five() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    score = evaluate_board(board, caches, 1, 0, load_default_config())
    assert score > 0


def test_shape_cache_contains_valid_labels_for_empty_point() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    caches = EvalCaches()
    recompute_point_caches(board, caches, 7, 8)
    for direction in range(4):
        label = (caches.shape_cache[0][7][8][direction] >> 16) & 0xF
        assert 0 <= label <= ShapeLabel.L6


def test_find_last5_target_preserves_reference_scan_order() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    target = _find_last5_target(board, caches, 1, load_default_config())
    assert target == (2, 7)


def test_last5_branch_returns_positive_value_for_open_four() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    value = _evaluate_last5_branch(board, caches, 1, 0, load_default_config())
    assert value > 0


def test_next43_branch_is_false_on_non_forcing_shape() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    board.play(xy_to_move(7, 8))
    caches = EvalCaches()
    recompute_all(board, caches)
    assert not _evaluate_next43_branch(board, caches, 1, load_default_config())


def test_value_wide_incremental_matches_full_recompute_on_random_sequences() -> None:
    rng = random.Random(12345)
    config = load_default_config()

    for _ in range(6):
        board = Board()
        incremental = EvalCaches()
        recompute_all(board, incremental)

        for ply in range(14):
            legal_moves = [move for move in range(board.size * board.size) if board.is_legal_move(move)]
            move = rng.choice(legal_moves)
            board.play(move)
            value_wide_compute(board, incremental)

            full = EvalCaches()
            recompute_all(board, full)

            assert incremental.board_shadow == full.board_shadow
            assert incremental.shape_cache == full.shape_cache
            assert incremental.value_cache == full.value_cache
            assert incremental.attack_cache == full.attack_cache
            assert evaluate_board(board, incremental, board.side_to_move, 0, config) == evaluate_board(
                board, full, board.side_to_move, 0, config
            )

            if ply % 4 == 3 and board.move_history:
                board.undo()
                value_wide_compute(board, incremental)
                full_after_undo = EvalCaches()
                recompute_all(board, full_after_undo)
                assert incremental.board_shadow == full_after_undo.board_shadow
                assert incremental.shape_cache == full_after_undo.shape_cache
                assert incremental.value_cache == full_after_undo.value_cache
                assert incremental.attack_cache == full_after_undo.attack_cache


def test_value_wide_matches_reference_on_handpicked_points() -> None:
    board = Board()
    moves = [(7, 7), (7, 6), (8, 7), (6, 6), (9, 7), (5, 5), (6, 7), (8, 6)]
    for idx, (x, y) in enumerate(moves):
        board.play(xy_to_move(x, y), 1 if idx % 2 == 0 else -1)

    caches = EvalCaches()
    recompute_all(board, caches)

    expected = {
        (6, 8): {
            "bucket_black": 10,
            "attack_black": 0,
            "bucket_white": 6,
            "attack_white": 0,
            "shape_black": [196609, 131073, 196609, 131073],
            "shape_white": [65537, 131073, 65537, 131073],
        },
        (8, 8): {
            "bucket_black": 25,
            "attack_black": 0,
            "bucket_white": 5,
            "attack_white": 0,
            "shape_black": [196609, 131073, 393217, 196609],
            "shape_white": [65537, 131073, 65537, 65537],
        },
        (5, 7): {
            "bucket_black": 81,
            "attack_black": 6,
            "bucket_white": 27,
            "attack_white": 0,
            "shape_black": [131073, 786433, 65537, 131073],
            "shape_white": [327681, 65537, 393217, 131073],
        },
        (10, 7): {
            "bucket_black": 81,
            "attack_black": 6,
            "bucket_white": 6,
            "attack_white": 0,
            "shape_black": [131073, 786433, 131073, 131073],
            "shape_white": [131073, 65537, 131073, 131073],
        },
        (4, 4): {
            "bucket_black": 6,
            "attack_black": 0,
            "bucket_white": 31,
            "attack_white": 0,
            "shape_black": [131073, 131073, 131073, 65537],
            "shape_white": [131073, 131073, 131073, 458753],
        },
    }

    for (x, y), point in expected.items():
        assert caches.value_cache[0][x][y] == point["bucket_black"]
        assert caches.attack_cache[0][x][y] == point["attack_black"]
        assert caches.value_cache[1][x][y] == point["bucket_white"]
        assert caches.attack_cache[1][x][y] == point["attack_white"]
        assert caches.shape_cache[0][x][y] == point["shape_black"]
        assert caches.shape_cache[1][x][y] == point["shape_white"]


def test_global_eval_matches_reference_on_handpicked_positions() -> None:
    config = load_default_config()
    positions = {
        "quiet": ([(7, 7), (7, 6), (8, 7), (6, 6), (9, 7), (5, 5), (6, 7), (8, 6)], 15000, -15000),
        "last5_black": ([(7, 7), (0, 0), (8, 7), (1, 0), (9, 7), (2, 0), (10, 7)], 15000, -15000),
        "next43_white": ([(7, 7), (6, 7), (8, 8), (7, 8), (10, 10), (8, 7)], -23.692430307108392, -15000),
    }

    for moves, black_expected, white_expected in positions.values():
        board = Board()
        for idx, (x, y) in enumerate(moves):
            board.play(xy_to_move(x, y), 1 if idx % 2 == 0 else -1)
        caches = EvalCaches()
        recompute_all(board, caches)
        assert evaluate_board(board, caches, 1, 0, config) == black_expected
        assert evaluate_board(board, caches, -1, 0, config) == white_expected


def test_value_wide_incremental_snapshots_match_reference_sequence() -> None:
    board = Board()
    caches = EvalCaches()
    sequence = [(7, 7), (7, 6), (8, 7), (6, 6), (9, 7), (5, 5), (6, 7), (8, 6)]
    expected = {
        1: {(6, 8): (24, 0, 6, 0), (8, 8): (24, 0, 6, 0), (5, 7): (18, 0, 6, 0)},
        2: {(6, 8): (24, 0, 6, 0), (8, 8): (24, 0, 6, 0), (5, 7): (18, 0, 6, 0)},
        3: {(6, 8): (24, 0, 6, 0), (8, 8): (28, 0, 6, 0), (5, 7): (39, 3, 6, 0)},
        4: {(6, 8): (24, 0, 18, 0), (8, 8): (25, 0, 6, 0), (5, 7): (39, 3, 24, 0)},
        5: {(6, 8): (24, 0, 18, 0), (8, 8): (28, 0, 5, 0), (5, 7): (58, 4, 24, 0)},
        6: {(6, 8): (24, 0, 18, 0), (8, 8): (28, 0, 5, 0), (5, 7): (58, 4, 27, 0)},
        7: {(6, 8): (25, 0, 6, 0), (8, 8): (28, 0, 5, 0), (5, 7): (81, 6, 27, 0)},
        8: {(6, 8): (10, 0, 6, 0), (8, 8): (25, 0, 5, 0), (5, 7): (81, 6, 27, 0)},
    }

    for ply, (x, y) in enumerate(sequence, start=1):
        board.play(xy_to_move(x, y), 1 if ply % 2 == 1 else -1)
        value_wide_compute(board, caches)
        for (px, py), values in expected[ply].items():
            assert (
                caches.value_cache[0][px][py],
                caches.attack_cache[0][px][py],
                caches.value_cache[1][px][py],
                caches.attack_cache[1][px][py],
            ) == values
