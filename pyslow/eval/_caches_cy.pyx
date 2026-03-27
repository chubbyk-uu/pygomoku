"""Optional Cython helpers for cache copying."""


def copy_board_shadow(object board_shadow):
    cdef Py_ssize_t i
    cdef Py_ssize_t n = len(board_shadow)
    cdef list out = [None] * n
    for i in range(n):
        out[i] = board_shadow[i][:]
    return out


def copy_value_cache(object cache):
    cdef Py_ssize_t p
    cdef Py_ssize_t n = len(cache)
    cdef list out = [None] * n
    cdef object player
    cdef Py_ssize_t i
    cdef list copied_player
    for p in range(n):
        player = cache[p]
        copied_player = [None] * len(player)
        for i in range(len(player)):
            copied_player[i] = player[i][:]
        out[p] = copied_player
    return out


def copy_shape_cache(object shape_cache):
    cdef Py_ssize_t p
    cdef Py_ssize_t n = len(shape_cache)
    cdef list out = [None] * n
    cdef object player
    cdef Py_ssize_t i
    cdef Py_ssize_t j
    cdef list copied_player
    cdef object row
    cdef list copied_rows
    for p in range(n):
        player = shape_cache[p]
        copied_player = [None] * len(player)
        for i in range(len(player)):
            row = player[i]
            copied_rows = [None] * len(row)
            for j in range(len(row)):
                copied_rows[j] = row[j][:]
            copied_player[i] = copied_rows
        out[p] = copied_player
    return out
