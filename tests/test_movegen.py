"""Move generation tests."""

from pyslow.board import Board, move_to_xy, xy_to_move
from pyslow.config import load_default_config
from pyslow.eval.caches import EvalCaches
from pyslow.eval.local import attack_level, move_value, recompute_all
from pyslow.search.movegen import _apply_hostile_three_extension, covered_moves, generate_candidates


def test_covered_moves_uses_reference_template() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    moves = covered_moves(board)
    assert len(moves) == 32
    assert xy_to_move(7, 4) in moves
    assert xy_to_move(4, 4) in moves
    assert xy_to_move(5, 4) not in moves


def test_covered_moves_returns_center_on_empty_board() -> None:
    board = Board()
    moves = covered_moves(board)
    assert moves == (xy_to_move(7, 7),)


def test_generate_candidates_collapses_single_forcing_class() -> None:
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
    result = generate_candidates(board, caches, 1, load_default_config())
    assert len(result.candidates) == 1
    x, y = move_to_xy(result.candidates[0].move)
    assert (x, y) in {(2, 7), (7, 7)}


def test_generate_candidates_respects_root_allowed_mask_penalty() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    preferred = xy_to_move(7, 8)
    result = generate_candidates(
        board,
        caches,
        1,
        load_default_config(),
        root_allowed_moves={preferred},
        wide=5,
    )
    assert result.candidates
    assert result.candidates[0].move == preferred


def test_generate_candidates_injects_preferred_move_score() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    preferred = xy_to_move(7, 8)
    result = generate_candidates(
        board,
        caches,
        1,
        load_default_config(),
        preferred_move=preferred,
        wide=8,
    )
    assert result.candidates
    assert any(candidate.move == preferred and candidate.order_score == 100 for candidate in result.candidates)


def test_hostile_three_extension_matches_reference_bonus_on_known_fallback_position() -> None:
    board = Board()
    sequence = [
        (1, (7, 7)),
        (-1, (7, 6)),
        (1, (7, 5)),
        (-1, (6, 5)),
        (1, (8, 7)),
        (-1, (6, 7)),
        (1, (6, 6)),
        (-1, (5, 8)),
        (1, (8, 5)),
        (-1, (5, 4)),
        (1, (8, 6)),
        (-1, (4, 9)),
        (1, (3, 10)),
        (-1, (4, 3)),
        (1, (3, 2)),
    ]
    for side, (x, y) in sequence:
        board.play(xy_to_move(x, y), side)

    caches = EvalCaches()
    recompute_all(board, caches)
    cfg = load_default_config()
    side = board.side_to_move
    vbw_map: dict[int, float] = {}
    hsflag = 0
    sglflag = 0
    for move in covered_moves(board):
        x, y = move_to_xy(move)
        value = move_value(caches, x, y, side, cfg)
        att1 = attack_level(caches, x, y, side)
        att2 = attack_level(caches, x, y, -side)
        vbw_map[move] = value
        if value <= 0:
            continue
        if att2 == 6 or att1 >= 5:
            sglflag += 1
        elif att2 == 5:
            hsflag = move + 1

    before = dict(vbw_map)
    assert sglflag == 0
    assert hsflag == xy_to_move(8, 8) + 1
    _apply_hostile_three_extension(board, hsflag - 1, side, vbw_map)
    changed = {move_to_xy(move): vbw_map[move] - before[move] for move in vbw_map if vbw_map[move] != before[move]}
    assert changed == {(8, 4): 10000, (8, 8): 10000}


def test_generate_candidates_matches_reference_casen_on_known_fallback_position() -> None:
    board = Board()
    sequence = [
        (1, (7, 7)),
        (-1, (7, 6)),
        (1, (7, 5)),
        (-1, (6, 5)),
        (1, (8, 7)),
        (-1, (6, 7)),
        (1, (6, 6)),
        (-1, (5, 8)),
        (1, (8, 5)),
        (-1, (5, 4)),
        (1, (8, 6)),
        (-1, (4, 9)),
        (1, (3, 10)),
        (-1, (4, 3)),
        (1, (3, 2)),
    ]
    for side, (x, y) in sequence:
        board.play(xy_to_move(x, y), side)

    caches = EvalCaches()
    recompute_all(board, caches)
    result = generate_candidates(board, caches, board.side_to_move, load_default_config(), wide=10)
    assert len(result.candidates) == 2
    assert {move_to_xy(candidate.move) for candidate in result.candidates} == {(8, 4), (8, 8)}
