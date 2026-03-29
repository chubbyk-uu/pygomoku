"""Zobrist stability tests."""

from pygomoku.board import Board, xy_to_move


def test_zobrist_changes_after_move() -> None:
    board = Board()
    start_key = board.zobrist_key
    board.play(xy_to_move(7, 7))
    assert board.zobrist_key != start_key


def test_zobrist_restores_after_undo() -> None:
    board = Board()
    start_key = board.zobrist_key
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    board.undo()
    board.undo()
    assert board.zobrist_key == start_key


def test_same_position_same_hash() -> None:
    moves = [xy_to_move(7, 7), xy_to_move(8, 7), xy_to_move(7, 8), xy_to_move(8, 8)]
    board_a = Board()
    board_b = Board()
    for move in moves:
        board_a.play(move)
    board_b.replay(moves)
    assert board_a.zobrist_key == board_b.zobrist_key


def test_hash_tracks_partial_undo_correctly() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    key_after_first = board.zobrist_key
    board.play(xy_to_move(8, 7))
    board.play(xy_to_move(7, 8))
    board.undo()
    board.undo()
    assert board.zobrist_key == key_after_first


def test_side_to_move_does_not_change_hash_on_same_grid() -> None:
    black_to_move = Board()
    white_to_move = Board(side_to_move=-1)
    assert black_to_move.zobrist_key == white_to_move.zobrist_key
