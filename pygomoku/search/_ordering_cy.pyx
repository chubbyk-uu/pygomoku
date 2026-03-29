"""Optional Cython helpers for move ordering."""

from pygomoku.constants import BOARD_SIZE


def getmi_raw(object grid, int x, int y, int c, int size=BOARD_SIZE):
    cdef int ret = 1
    cdef int opponent = -c
    cdef int ii, jj

    ii, jj = x + 1, y
    while ii <= x + 4 and ii < size:
        if grid[jj][ii] == opponent:
            break
        ret += 1
        ii += 1

    ii, jj = x - 1, y
    while ii >= x - 4 and ii >= 0:
        if grid[jj][ii] == opponent:
            break
        ret += 1
        ii -= 1

    ii, jj = x, y + 1
    while jj <= y + 4 and jj < size:
        if grid[jj][ii] == opponent:
            break
        ret += 1
        jj += 1

    ii, jj = x, y - 1
    while jj >= y - 4 and jj >= 0:
        if grid[jj][ii] == opponent:
            break
        ret += 1
        jj -= 1

    ii, jj = x + 1, y + 1
    while ii <= x + 4 and ii < size and jj < size:
        if grid[jj][ii] == opponent:
            break
        ret += 1
        ii += 1
        jj += 1

    ii, jj = x - 1, y - 1
    while ii >= x - 4 and ii >= 0 and jj >= 0:
        if grid[jj][ii] == opponent:
            break
        ret += 1
        ii -= 1
        jj -= 1

    ii, jj = x - 1, y + 1
    while ii >= x - 4 and ii >= 0 and jj < size:
        if grid[jj][ii] == opponent:
            break
        ret += 1
        ii -= 1
        jj += 1

    ii, jj = x + 1, y - 1
    while ii <= x + 4 and ii < size and jj >= 0:
        if grid[jj][ii] == opponent:
            break
        ret += 1
        ii += 1
        jj -= 1

    return ret
