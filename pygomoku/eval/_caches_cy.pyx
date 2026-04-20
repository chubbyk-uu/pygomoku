"""Optional Cython helpers for cache copying."""


def copy_board_shadow(object board_shadow):
    cdef Py_ssize_t i
    cdef Py_ssize_t n = len(board_shadow)
    cdef list src = board_shadow
    cdef list out = [None] * n
    for i in range(n):
        out[i] = src[i][:]
    return out


def copy_value_cache(object cache):
    cdef Py_ssize_t p
    cdef Py_ssize_t n = len(cache)
    cdef list src = cache
    cdef list out = [None] * n
    cdef list player
    cdef Py_ssize_t sz
    cdef Py_ssize_t i
    cdef list copied_player
    for p in range(n):
        player = src[p]
        sz = len(player)
        copied_player = [None] * sz
        for i in range(sz):
            copied_player[i] = player[i][:]
        out[p] = copied_player
    return out


def copy_shape_cache(object shape_cache):
    cdef Py_ssize_t p
    cdef Py_ssize_t n = len(shape_cache)
    cdef list src = shape_cache
    cdef list out = [None] * n
    cdef list player
    cdef Py_ssize_t sz
    cdef Py_ssize_t i
    cdef Py_ssize_t j
    cdef list copied_player
    cdef list row
    cdef Py_ssize_t row_sz
    cdef list copied_rows
    for p in range(n):
        player = src[p]
        sz = len(player)
        copied_player = [None] * sz
        for i in range(sz):
            row = player[i]
            row_sz = len(row)
            copied_rows = [None] * row_sz
            for j in range(row_sz):
                copied_rows[j] = row[j][:]
            copied_player[i] = copied_rows
        out[p] = copied_player
    return out
