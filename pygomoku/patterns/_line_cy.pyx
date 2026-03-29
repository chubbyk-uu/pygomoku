"""Optional Cython helpers for line extraction and raw shape lookup."""

from pygomoku.constants import BLACK, EMPTY, WHITE
from pygomoku.patterns.shape_table import SHAPE_TABLE
from pygomoku.patterns.shapes import DIAGONAL_DOWN, DIAGONAL_UP, HORIZONTAL, VERTICAL


def extract_cells(object grid, int size, int pivot, int direction, int sentinel):
    cdef list cells = [sentinel] * (size + 4)
    cdef int i
    cdef int start

    if direction == HORIZONTAL:
        for y in range(size):
            cells[y + 2] = grid[y][pivot]
    elif direction == VERTICAL:
        row = grid[pivot]
        for i in range(size):
            cells[i + 2] = row[i]
    elif direction == DIAGONAL_DOWN:
        if pivot < size:
            for i in range(pivot + 1):
                cells[i + 2] = grid[i][pivot - i]
        else:
            start = pivot - size + 1
            for i in range(start, size):
                cells[i + 2] = grid[i][pivot - i]
    elif direction == DIAGONAL_UP:
        if pivot < size:
            for i in range(pivot + 1):
                cells[i + 2] = grid[size - 1 - i][pivot - i]
        else:
            start = pivot - size + 1
            for i in range(start, size):
                cells[i + 2] = grid[size - 1 - i][pivot - i]
    else:
        raise ValueError(f"invalid direction: {direction}")

    return cells


def shape_raw_from_cells(object cells, int point_index, bint freestyle):
    cdef int p = point_index + 2
    cdef int stone = cells[p]
    cdef int trt
    cdef int ssp = 0
    cdef int si = 0
    cdef int sj = 0
    cdef int offset
    cdef int value
    cdef int row
    cdef int table_index
    cdef tuple forward_masks = (16, 8, 4, 2, 1)
    cdef tuple backward_masks = (32, 64, 128, 256, 512)

    if stone != BLACK and stone != WHITE:
        return 0

    for offset in range(1, 6):
        value = cells[p + offset]
        if value == EMPTY:
            continue
        if value == stone:
            ssp |= forward_masks[offset - 1]
        else:
            sj = offset - 1
            break
    else:
        sj = 5

    for offset in range(1, 6):
        value = cells[p - offset]
        if value == EMPTY:
            continue
        if value == stone:
            ssp |= backward_masks[offset - 1]
        else:
            si = offset - 1
            break
    else:
        si = 5

    ssp >>= 5 - sj
    table_index = (1 << si) * ((1 << sj) + 62) - 63 + ssp
    row = 1 if (stone == BLACK and not freestyle) else 0
    trt = SHAPE_TABLE[row][table_index]
    return ((trt & 0xF0) << 12) | (trt & 0xF)
