"""Optional Cython helpers for threat-board hot paths."""

from pyslow.constants import BOARD_SIZE

cdef int _EMPTY = 0
cdef int _SENTINEL = 1024

cdef tuple _THREAT_DIRS = (
    (-2, -2), (-1, -1), (2, 2), (1, 1),
    (-2, 2), (-1, 1), (2, -2), (1, -1),
    (2, 0), (1, 0), (0, 2), (0, 1),
    (-2, 0), (-1, 0), (0, -2), (0, -1),
)


cdef inline int _comb(int x, int y):
    return (x << 8) | (y - 2)


cdef inline int _comc(int x, int y, int z):
    return _comb(_comb(x, y), z)


cdef inline int _padded_get(object row, int idx, int size):
    if idx < 2 or idx >= size + 2:
        return _SENTINEL
    return row[idx - 2]


cdef inline int _b4p_row(object row, int point_index, int size):
    cdef int p = point_index + 2
    cdef int x0 = _padded_get(row, p, size)
    cdef int xmin
    cdef int xmax
    cdef int i
    cdef int shape
    cdef int c0
    cdef int c1
    cdef int c2
    cdef int c3
    cdef int c4

    if x0 == _EMPTY:
        return 0

    xmin = p - 4
    if xmin < 2:
        xmin = 2
    xmax = p
    if xmax > size - 3:
        xmax = size - 3

    for i in range(xmin, xmax + 1):
        c0 = _padded_get(row, i, size)
        c1 = _padded_get(row, i + 1, size)
        c2 = _padded_get(row, i + 2, size)
        c3 = _padded_get(row, i + 3, size)
        c4 = _padded_get(row, i + 4, size)
        if c0 + c1 + c2 + c3 + c4 != 4 * x0:
            continue
        shape = (c0 << 4) + (c1 << 3) + (c2 << 2) + (c3 << 1) + c4
        if x0 < 0:
            shape = -shape
        if shape == 0x1E:
            if _padded_get(row, i - 1, size) == _EMPTY:
                return _comc(1, i - 1, i + 4)
            return _comb(1, i + 4)
        if shape == 0x1D:
            if i <= size - 7 and _padded_get(row, i + 5, size) == x0 and _padded_get(row, i + 6, size) == x0 and _padded_get(row, i + 7, size) == x0:
                if p == i + 4 and _padded_get(row, i + 3, size) == _EMPTY:
                    return _comc(1, i + 3, i + 5)
            if _padded_get(row, i + 3, size) == _EMPTY:
                return _comb(1, i + 3)
        if shape == 0x1B:
            if i <= size - 6 and _padded_get(row, i + 5, size) == _EMPTY and _padded_get(row, i + 6, size) == x0 and _padded_get(row, i + 7, size) == x0:
                if (p == i + 4 or p == i + 3) and _padded_get(row, i + 2, size) == _EMPTY:
                    return _comc(1, i + 2, i + 5)
            if _padded_get(row, i + 2, size) == _EMPTY:
                return _comb(1, i + 2)
        if shape == 0x17:
            if i <= size - 5 and _padded_get(row, i + 5, size) == _EMPTY and _padded_get(row, i + 6, size) == x0:
                if (p == i + 4 or p == i + 3 or p == i + 2) and _padded_get(row, i + 1, size) == _EMPTY:
                    return _comc(1, i + 1, i + 5)
            if _padded_get(row, i + 1, size) == _EMPTY:
                return _comb(1, i + 1)
        if shape == 0x0F:
            if _padded_get(row, i + 5, size) == _EMPTY:
                return _comc(1, i, i + 5)
            return _comb(1, i)
    return 0


cdef inline int _decode_line_move(int size, int x, int y, int direction_index, int encoded):
    cdef int raw = encoded & 0xFF
    cdef int tx
    cdef int ty
    if direction_index == 1:
        tx = x
        ty = raw
    elif direction_index == 2:
        tx = raw
        ty = y
    elif direction_index == 3:
        tx = x + y - raw
        ty = raw
    elif direction_index == 4:
        tx = size - 1 + x - y - raw
        ty = size - 1 - raw
    else:
        return -1
    if 0 <= tx < size and 0 <= ty < size:
        return ty * size + tx
    return -1


cdef inline tuple _broken_four_reply_counts_to_result(int size, int x, int y, int c1, int c2, int c3, int c4):
    cdef tuple counts = (c1, c2, c3, c4)
    cdef int direction
    cdef int encoded
    cdef int mask = 0
    cdef int index

    for index in range(4):
        encoded = counts[index]
        if encoded >= (1 << 16):
            return _decode_line_move(size, x, y, index + 1, encoded), True

    for index in range(4):
        if counts[index]:
            mask |= 1 << index

    if mask == 0:
        return -1, False
    if mask == 1:
        return _decode_line_move(size, x, y, 1, c1), False
    if mask == 2:
        return _decode_line_move(size, x, y, 2, c2), False
    if mask == 4:
        return _decode_line_move(size, x, y, 3, c3), False
    if mask == 8:
        return _decode_line_move(size, x, y, 4, c4), False
    if mask in (3, 5, 7, 9, 11, 13, 15):
        return _decode_line_move(size, x, y, 1, c1), True
    if mask in (6, 10, 14):
        return _decode_line_move(size, x, y, 2, c2), True
    if mask == 12:
        return _decode_line_move(size, x, y, 3, c3), True
    return -1, False


def broken_four_reply_raw(object x1, object x2, object x3, object x4, int x, int y, int size=BOARD_SIZE):
    cdef int c1 = _b4p_row(x1[x], y, size)
    cdef int c2 = _b4p_row(x2[y], x, size)
    cdef int c3 = _b4p_row(x3[x + y], y, size)
    cdef int c4 = _b4p_row(x4[size - 1 - y + x], size - 1 - y, size)
    return _broken_four_reply_counts_to_result(size, x, y, c1, c2, c3, c4)


def broken_four_point_for_side_raw(object grid, object x1, object x2, object x3, object x4, int side, int size=BOARD_SIZE):
    cdef int x
    cdef int y
    cdef int reply
    cdef int first_reply = -1
    cdef bint ambiguous

    for x in range(size):
        for y in range(size):
            if grid[y][x] != side:
                continue
            reply, ambiguous = broken_four_reply_raw(x1, x2, x3, x4, x, y, size)
            if reply < 0:
                continue
            if ambiguous:
                return reply, True
            if first_reply < 0:
                first_reply = reply
            elif reply != first_reply:
                return reply, True
    if first_reply < 0:
        return -1, False
    return first_reply, False


def build_views(object grid, int size=BOARD_SIZE):
    cdef int width = 2 * size - 1
    cdef list x1 = [[grid[y][x] for y in range(size)] for x in range(size)]
    cdef list x2 = [[grid[y][x] for x in range(size)] for y in range(size)]
    cdef list x3 = [[1024 for _ in range(size)] for _ in range(width)]
    cdef list x4 = [[1024 for _ in range(size)] for _ in range(width)]
    cdef int p, i

    for p in range(width):
        if p < size:
            for i in range(p + 1):
                x3[p][i] = grid[i][p - i]
                x4[p][i] = grid[size - 1 - i][p - i]
        else:
            for i in range(p - size + 1, size):
                x3[p][i] = grid[i][p - i]
                x4[p][i] = grid[size - 1 - i][p - i]
    return x1, x2, x3, x4


def threat_moves_grid(object grid, int side, int size=BOARD_SIZE):
    cdef list candidates = []
    cdef int x, y, xx, yy
    cdef tuple offset
    for x in range(size):
        for y in range(size):
            if grid[y][x] != 0:
                continue
            for offset in _THREAT_DIRS:
                xx = x + offset[0]
                yy = y + offset[1]
                if 0 <= xx < size and 0 <= yy < size and grid[yy][xx] == side:
                    candidates.append(y * size + x)
                    break
    return tuple(candidates)
