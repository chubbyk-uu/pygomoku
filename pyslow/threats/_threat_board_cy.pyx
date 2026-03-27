"""Optional Cython helpers for threat-board hot paths."""

from pyslow.constants import BOARD_SIZE

cdef tuple _THREAT_DIRS = (
    (-2, -2), (-1, -1), (2, 2), (1, 1),
    (-2, 2), (-1, 1), (2, -2), (1, -1),
    (2, 0), (1, 0), (0, 2), (0, 1),
    (-2, 0), (-1, 0), (0, -2), (0, -1),
)


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
