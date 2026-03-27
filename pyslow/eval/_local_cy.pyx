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


cdef inline void _set_shape_value(
    object shape_log,
    int active_snapshots,
    object shape_cache,
    int player,
    int x,
    int y,
    int direction,
    int value,
):
    cdef object shape_col = shape_cache[player][x][y]
    cdef int old_value = shape_col[direction]
    if old_value == value:
        return
    if active_snapshots:
        shape_log.append((player, x, y, direction, old_value))
    shape_col[direction] = value


def value_wide_update(
    object grid,
    object shadow,
    object shape_cache,
    object value_cache,
    object attack_cache,
    int active_snapshots,
    object shape_log,
    int size=BOARD_SIZE,
):
    cdef list comp = [bytearray(size) for _ in range(size)]
    cdef int ar = 4
    cdef int horizontal_flag = 1
    cdef int vertical_flag = 2
    cdef int diag_down_flag = 4
    cdef int diag_up_flag = 8
    cdef int x, y, xx, yy, fixed, seen, value, cell, flags
    cdef int bh, bv, bdd, bdu, wh, wv, wdd, wdu, bucket, attack
    cdef object comp_col
    cdef object shadow_col
    cdef object black_value_col
    cdef object white_value_col
    cdef object black_attack_col
    cdef object white_attack_col

    for x in range(size):
        for y in range(size):
            if shadow[x][y] != grid[y][x]:
                comp[x][y] = 15

                fixed = x
                seen = 0
                for yy in range(y + 1, min(size, y + ar + 1)):
                    value = grid[yy][fixed]
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[fixed][yy] |= horizontal_flag
                seen = 0
                for yy in range(y - 1, max(-1, y - ar - 1), -1):
                    value = grid[yy][fixed]
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[fixed][yy] |= horizontal_flag

                fixed = y
                seen = 0
                for xx in range(x + 1, min(size, x + ar + 1)):
                    value = grid[fixed][xx]
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][fixed] |= vertical_flag
                seen = 0
                for xx in range(x - 1, max(-1, x - ar - 1), -1):
                    value = grid[fixed][xx]
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][fixed] |= vertical_flag

                seen = 0
                xx = x - 1
                yy = y + 1
                while xx >= 0 and yy < size and xx >= x - ar and yy <= y + ar:
                    value = grid[yy][xx]
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][yy] |= diag_down_flag
                    xx -= 1
                    yy += 1

                seen = 0
                xx = x + 1
                yy = y - 1
                while xx < size and yy >= 0 and xx <= x + ar and yy >= y - ar:
                    value = grid[yy][xx]
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][yy] |= diag_down_flag
                    xx += 1
                    yy -= 1

                seen = 0
                xx = x + 1
                yy = y + 1
                while xx < size and yy < size and xx <= x + ar and yy <= y + ar:
                    value = grid[yy][xx]
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][yy] |= diag_up_flag
                    xx += 1
                    yy += 1

                seen = 0
                xx = x - 1
                yy = y - 1
                while xx >= 0 and yy >= 0 and xx >= x - ar and yy >= y - ar:
                    value = grid[yy][xx]
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][yy] |= diag_up_flag
                    xx -= 1
                    yy -= 1

    for x in range(size):
        shadow_col = shadow[x]
        comp_col = comp[x]
        black_value_col = value_cache[0][x]
        white_value_col = value_cache[1][x]
        black_attack_col = attack_cache[0][x]
        white_attack_col = attack_cache[1][x]
        for y in range(size):
            cell = grid[y][x]
            shadow_col[y] = cell
            flags = comp_col[y]
            if flags and cell == EMPTY:
                if flags & horizontal_flag:
                    bh = compute_direction_shape_raw(grid, x, y, HORIZONTAL, BLACK, size)
                    wh = compute_direction_shape_raw(grid, x, y, HORIZONTAL, WHITE, size)
                    _set_shape_value(shape_log, active_snapshots, shape_cache, 0, x, y, HORIZONTAL, bh)
                    _set_shape_value(shape_log, active_snapshots, shape_cache, 1, x, y, HORIZONTAL, wh)
                if flags & vertical_flag:
                    bv = compute_direction_shape_raw(grid, x, y, VERTICAL, BLACK, size)
                    wv = compute_direction_shape_raw(grid, x, y, VERTICAL, WHITE, size)
                    _set_shape_value(shape_log, active_snapshots, shape_cache, 0, x, y, VERTICAL, bv)
                    _set_shape_value(shape_log, active_snapshots, shape_cache, 1, x, y, VERTICAL, wv)
                if flags & diag_down_flag:
                    bdd = compute_direction_shape_raw(grid, x, y, DIAGONAL_DOWN, BLACK, size)
                    wdd = compute_direction_shape_raw(grid, x, y, DIAGONAL_DOWN, WHITE, size)
                    _set_shape_value(shape_log, active_snapshots, shape_cache, 0, x, y, DIAGONAL_DOWN, bdd)
                    _set_shape_value(shape_log, active_snapshots, shape_cache, 1, x, y, DIAGONAL_DOWN, wdd)
                if flags & diag_up_flag:
                    bdu = compute_direction_shape_raw(grid, x, y, DIAGONAL_UP, BLACK, size)
                    wdu = compute_direction_shape_raw(grid, x, y, DIAGONAL_UP, WHITE, size)
                    _set_shape_value(shape_log, active_snapshots, shape_cache, 0, x, y, DIAGONAL_UP, bdu)
                    _set_shape_value(shape_log, active_snapshots, shape_cache, 1, x, y, DIAGONAL_UP, wdu)

                bh = shape_cache[0][x][y][HORIZONTAL]
                bv = shape_cache[0][x][y][VERTICAL]
                bdd = shape_cache[0][x][y][DIAGONAL_DOWN]
                bdu = shape_cache[0][x][y][DIAGONAL_UP]
                bucket, attack = compute_bucket_and_attack_raw(bh, bv, bdd, bdu)
                black_value_col[y] = bucket
                black_attack_col[y] = attack

                wh = shape_cache[1][x][y][HORIZONTAL]
                wv = shape_cache[1][x][y][VERTICAL]
                wdd = shape_cache[1][x][y][DIAGONAL_DOWN]
                wdu = shape_cache[1][x][y][DIAGONAL_UP]
                bucket, attack = compute_bucket_and_attack_raw(wh, wv, wdd, wdu)
                white_value_col[y] = bucket
                white_attack_col[y] = attack
            elif cell != EMPTY:
                black_value_col[y] = 0
                white_value_col[y] = 0
                black_attack_col[y] = 0
                white_attack_col[y] = 0
                _set_shape_value(shape_log, active_snapshots, shape_cache, 0, x, y, HORIZONTAL, 0)
                _set_shape_value(shape_log, active_snapshots, shape_cache, 0, x, y, VERTICAL, 0)
                _set_shape_value(shape_log, active_snapshots, shape_cache, 0, x, y, DIAGONAL_DOWN, 0)
                _set_shape_value(shape_log, active_snapshots, shape_cache, 0, x, y, DIAGONAL_UP, 0)
                _set_shape_value(shape_log, active_snapshots, shape_cache, 1, x, y, HORIZONTAL, 0)
                _set_shape_value(shape_log, active_snapshots, shape_cache, 1, x, y, VERTICAL, 0)
                _set_shape_value(shape_log, active_snapshots, shape_cache, 1, x, y, DIAGONAL_DOWN, 0)
                _set_shape_value(shape_log, active_snapshots, shape_cache, 1, x, y, DIAGONAL_UP, 0)
