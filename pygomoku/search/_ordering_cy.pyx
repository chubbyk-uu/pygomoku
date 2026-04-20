"""Optional Cython helpers for move ordering."""

from pygomoku.constants import BOARD_SIZE


def getmi_raw(object grid, int x, int y, int c, int size=BOARD_SIZE):
    cdef int ret = 1
    cdef int opponent = -c
    cdef int ii, jj
    cdef list grid_list = grid
    cdef list row

    # horizontal right — row y is constant
    row = grid_list[y]
    ii = x + 1
    while ii <= x + 4 and ii < size:
        if <int>row[ii] == opponent:
            break
        ret += 1
        ii += 1

    # horizontal left — same row
    ii = x - 1
    while ii >= x - 4 and ii >= 0:
        if <int>row[ii] == opponent:
            break
        ret += 1
        ii -= 1

    # vertical down — column x varies by row
    jj = y + 1
    while jj <= y + 4 and jj < size:
        row = grid_list[jj]
        if <int>row[x] == opponent:
            break
        ret += 1
        jj += 1

    # vertical up
    jj = y - 1
    while jj >= y - 4 and jj >= 0:
        row = grid_list[jj]
        if <int>row[x] == opponent:
            break
        ret += 1
        jj -= 1

    # diagonal down-right
    ii = x + 1
    jj = y + 1
    while ii <= x + 4 and ii < size and jj < size:
        row = grid_list[jj]
        if <int>row[ii] == opponent:
            break
        ret += 1
        ii += 1
        jj += 1

    # diagonal up-left
    ii = x - 1
    jj = y - 1
    while ii >= x - 4 and ii >= 0 and jj >= 0:
        row = grid_list[jj]
        if <int>row[ii] == opponent:
            break
        ret += 1
        ii -= 1
        jj -= 1

    # diagonal up-right
    ii = x - 1
    jj = y + 1
    while ii >= x - 4 and ii >= 0 and jj < size:
        row = grid_list[jj]
        if <int>row[ii] == opponent:
            break
        ret += 1
        ii -= 1
        jj += 1

    # diagonal down-left
    ii = x + 1
    jj = y - 1
    while ii <= x + 4 and ii < size and jj >= 0:
        row = grid_list[jj]
        if <int>row[ii] == opponent:
            break
        ret += 1
        ii += 1
        jj -= 1

    return ret
