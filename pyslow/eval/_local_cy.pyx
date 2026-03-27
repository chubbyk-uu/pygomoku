"""Optional Cython helpers for local evaluation hot paths."""

from pyslow.constants import BLACK, BOARD_SIZE, EMPTY, WHITE
from pyslow.patterns.line import _SENTINEL
from pyslow.patterns._line_cy import extract_cells, shape_raw_from_cells
from pyslow.patterns.shapes import DIAGONAL_DOWN, DIAGONAL_UP, HORIZONTAL, VERTICAL, ShapeLabel


def compute_direction_shape_raw(object grid, int x, int y, int direction, int side, int size=BOARD_SIZE):
    cdef int pivot
    cdef int point_index
    cdef object cells

    if grid[y][x] != EMPTY:
        return 0
    grid[y][x] = side
    try:
        if direction == HORIZONTAL:
            pivot = x
            point_index = y
        elif direction == VERTICAL:
            pivot = y
            point_index = x
        elif direction == DIAGONAL_DOWN:
            pivot = x + y
            point_index = y
        elif direction == DIAGONAL_UP:
            pivot = size - 1 - y + x
            point_index = size - 1 - y
        else:
            raise ValueError(f"invalid direction: {direction}")
        cells = extract_cells(grid, size, pivot, direction, _SENTINEL)
        return shape_raw_from_cells(cells, point_index, True)
    finally:
        grid[y][x] = EMPTY


def compute_bucket_and_attack_raw(int s0, int s1, int s2, int s3):
    cdef int attack = 0
    cdef int lines0 = ((s0 >> 16) & 0xF) % ShapeLabel.L6
    cdef int lines1 = ((s1 >> 16) & 0xF) % ShapeLabel.L6
    cdef int lines2 = ((s2 >> 16) & 0xF) % ShapeLabel.L6
    cdef int lines3 = ((s3 >> 16) & 0xF) % ShapeLabel.L6
    cdef int label
    cdef int aux
    cdef int top1
    cdef int top2
    cdef int tmp

    for shape_index in range(4):
        if shape_index == 0:
            label = (s0 >> 16) & 0xF
            aux = s0 & 0xF
        elif shape_index == 1:
            label = (s1 >> 16) & 0xF
            aux = s1 & 0xF
        elif shape_index == 2:
            label = (s2 >> 16) & 0xF
            aux = s2 & 0xF
        else:
            label = (s3 >> 16) & 0xF
            aux = s3 & 0xF

        if label == ShapeLabel.L3 or label == ShapeLabel.L3B:
            if attack < 3:
                attack = 3
        elif label == ShapeLabel.L4S:
            if attack < 4:
                attack = 4
            if aux >= 2:
                if shape_index == 0:
                    lines0 = 8
                elif shape_index == 1:
                    lines1 = 8
                elif shape_index == 2:
                    lines2 = 8
                else:
                    lines3 = 8
        elif label == ShapeLabel.L5:
            attack = 6
        elif label == ShapeLabel.L4:
            if attack < 5:
                attack = 5

    if lines0 < lines1:
        tmp = lines0
        lines0 = lines1
        lines1 = tmp
    if lines2 < lines3:
        tmp = lines2
        lines2 = lines3
        lines3 = tmp

    if lines1 >= lines2:
        top1 = lines0
        top2 = lines1
    elif lines3 >= lines0:
        top1 = lines2
        top2 = lines3
    elif lines0 >= lines2:
        top1 = lines0
        top2 = lines2
    else:
        top1 = lines2
        top2 = lines0

    return ((top1 * (top1 + 1)) // 2 + top2 + 1, attack)


def compute_point_cache_entry(object grid, int x, int y, int side, int size=BOARD_SIZE):
    cdef int h_shape = compute_direction_shape_raw(grid, x, y, HORIZONTAL, side, size)
    cdef int v_shape = compute_direction_shape_raw(grid, x, y, VERTICAL, side, size)
    cdef int d_down_shape = compute_direction_shape_raw(grid, x, y, DIAGONAL_DOWN, side, size)
    cdef int d_up_shape = compute_direction_shape_raw(grid, x, y, DIAGONAL_UP, side, size)
    cdef tuple ba = compute_bucket_and_attack_raw(h_shape, v_shape, d_down_shape, d_up_shape)
    return h_shape, v_shape, d_down_shape, d_up_shape, ba[0], ba[1]
