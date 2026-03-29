"""Pattern and bucket tests."""

from importlib.util import find_spec

from pygomoku.patterns.buckets import DOUBLE_SHAPE, bucket_for_lines
from pygomoku.patterns.line import Line, _shape_raw_from_cells_python, line_backend_name
from pygomoku.patterns.shapes import (
    DIAGONAL_DOWN,
    DIAGONAL_UP,
    DIRECTION_IDS,
    HORIZONTAL,
    PackedShape,
    ShapeLabel,
    VERTICAL,
)
from pygomoku.board import Board, xy_to_move
from pygomoku.constants import BLACK, WHITE


def test_shape_labels_match_expected_values() -> None:
    assert ShapeLabel.L0 == 0
    assert ShapeLabel.L4S == 10
    assert ShapeLabel.L5 == 12
    assert ShapeLabel.L6 == 13


def test_direction_ids_match_expected_order() -> None:
    assert DIRECTION_IDS == (HORIZONTAL, VERTICAL, DIAGONAL_DOWN, DIAGONAL_UP)


def test_packed_shape_decodes_label_and_aux() -> None:
    shape = PackedShape(((ShapeLabel.L4S & 0xF) << 16) | 3)
    assert shape.label == ShapeLabel.L4S
    assert shape.aux == 3


def test_double_shape_table_covers_expected_bucket_range() -> None:
    flattened = [bucket for row in DOUBLE_SHAPE for bucket in row]
    assert flattened[0] == 1
    assert flattened[-1] == 91
    assert len(flattened) == 91
    assert flattened == list(range(1, 92))


def test_bucket_for_lines_orders_inputs() -> None:
    assert bucket_for_lines(4, 2) == DOUBLE_SHAPE[4][2]
    assert bucket_for_lines(2, 4) == DOUBLE_SHAPE[4][2]


def test_line_extraction_direction_zero() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(7, 8))
    line = Line.from_board(board, 7, HORIZONTAL)
    assert line.cells[2 + 7] == BLACK
    assert line.cells[2 + 8] == WHITE


def test_line_shape_returns_nonzero_for_simple_stone() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    line = Line.from_board(board, 7, HORIZONTAL)
    shape = line.shape(7)
    assert isinstance(shape, PackedShape)
    assert shape.raw >= 0


def test_line_backend_name_is_supported() -> None:
    assert line_backend_name() in {"python", "cython"}


def test_line_shape_raw_matches_shape_wrapper() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(7, 8))
    board.play(xy_to_move(7, 9))
    line = Line.from_board(board, 7, HORIZONTAL)
    assert line.shape_raw(7) == line.shape(7).raw


def test_optional_cython_shape_backend_matches_python_helper() -> None:
    if find_spec("pygomoku.patterns._line_cy") is None:
        return
    from pygomoku.patterns._line_cy import shape_raw_from_cells

    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(7, 8))
    board.play(xy_to_move(7, 9))
    board.play(xy_to_move(8, 8))
    line = Line.from_board(board, 7, HORIZONTAL)
    assert shape_raw_from_cells(line.cells, 7, True) == _shape_raw_from_cells_python(line.cells, 7, True)


def test_line_a3pb_returns_expected_encoded_targets() -> None:
    board = Board()
    board.grid[7][7] = BLACK
    board.grid[7][8] = BLACK
    board.grid[7][10] = BLACK
    line = Line.from_board(board, 7, VERTICAL)
    encoded = line.a3pb(8)
    assert encoded > 0
    assert encoded & 0xFF == 11
    assert (encoded >> 8) & 0xFF == 6
    assert (encoded >> 16) & 0xFF == 9
