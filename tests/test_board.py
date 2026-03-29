"""Board behavior tests."""

import pytest

from pygomoku.board import Board, move_to_xy, xy_to_move
from pygomoku.constants import BLACK, EMPTY, WHITE


def test_coordinate_conversion_round_trip() -> None:
    move = xy_to_move(7, 11)
    assert move_to_xy(move) == (7, 11)


def test_board_starts_empty() -> None:
    board = Board()
    assert board.move_count == 0
    assert board.side_to_move == BLACK
    assert board.winner == EMPTY
    assert board.at(0, 0) == EMPTY


def test_play_and_undo_restore_state() -> None:
    board = Board()
    first = board.play(xy_to_move(7, 7))
    second = board.play(xy_to_move(7, 8))

    assert first.side == BLACK
    assert second.side == WHITE
    assert board.move_count == 2
    assert board.side_to_move == BLACK

    undone = board.undo()
    assert undone == second
    assert board.move_count == 1
    assert board.side_to_move == WHITE
    assert board.at(7, 8) == EMPTY


def test_play_rejects_occupied_point() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    with pytest.raises(ValueError):
        board.play(xy_to_move(7, 7))


def test_play_rejects_wrong_side() -> None:
    board = Board()
    with pytest.raises(ValueError):
        board.play(xy_to_move(7, 7), side=WHITE)


def test_horizontal_win_detection() -> None:
    board = Board()
    moves = [
        xy_to_move(3, 7),
        xy_to_move(0, 0),
        xy_to_move(4, 7),
        xy_to_move(0, 1),
        xy_to_move(5, 7),
        xy_to_move(0, 2),
        xy_to_move(6, 7),
        xy_to_move(0, 3),
        xy_to_move(7, 7),
    ]
    for move in moves:
        board.play(move)
    assert board.winner == BLACK


def test_diagonal_win_detection() -> None:
    board = Board()
    moves = [
        xy_to_move(2, 2),
        xy_to_move(0, 0),
        xy_to_move(3, 3),
        xy_to_move(0, 1),
        xy_to_move(4, 4),
        xy_to_move(0, 2),
        xy_to_move(5, 5),
        xy_to_move(0, 3),
        xy_to_move(6, 6),
    ]
    for move in moves:
        board.play(move)
    assert board.winner == BLACK


def test_board_replay_reconstructs_position() -> None:
    moves = [xy_to_move(7, 7), xy_to_move(8, 7), xy_to_move(7, 8)]
    board = Board()
    board.replay(moves)
    assert board.occupied_moves() == tuple(moves)
    assert board.at(7, 7) == BLACK
    assert board.at(8, 7) == WHITE
    assert board.at(7, 8) == BLACK
