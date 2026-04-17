"""Optional Cython helpers for global board evaluation hot paths."""

_DIR_MAP = (3, 1, 2, 0, 0, 0, 2, 1, 3)


def evaluate_board_main_raw(
    object grid,
    object shape_cache_player,
    object shape_cache_opponent,
    object player_values,
    object opponent_values,
    object last_eval,
    object next_eval,
    int side,
    int size,
):
    cdef double offensive = 0.0
    cdef double defensive = 0.0
    cdef int dgn = 0
    cdef int x, y, xx, yy, k, cc, stone
    cdef object player_value_col
    cdef object opponent_value_col

    for x in range(size):
        player_value_col = player_values[x]
        opponent_value_col = opponent_values[x]
        for y in range(size):
            stone = grid[y][x]
            if stone == side:
                cc = 1
                for k in range(9):
                    if k == 4:
                        continue
                    xx = x - 1 + k // 3
                    yy = y - 1 + k % 3
                    if xx < 0 or yy < 0 or xx >= size or yy >= size or grid[yy][xx] != 0:
                        cc += 1
                    elif ((shape_cache_player[xx][yy][_DIR_MAP[k]] >> 16) & 15) == 0:
                        cc += 1
                if cc <= 1:
                    dgn -= 5
                elif cc - 1 >= 5:
                    dgn -= cc - 1 - 3
            elif stone == -side:
                cc = 1
                for k in range(9):
                    if k == 4:
                        continue
                    xx = x - 1 + k // 3
                    yy = y - 1 + k % 3
                    if xx < 0 or yy < 0 or xx >= size or yy >= size or grid[yy][xx] != 0:
                        cc += 1
                    elif ((shape_cache_opponent[xx][yy][_DIR_MAP[k]] >> 16) & 15) == 0:
                        cc += 1
                if cc <= 1:
                    dgn += 5
                elif cc - 1 >= 5:
                    dgn += cc - 1 - 3
            else:
                offensive += last_eval[player_value_col[y]]
                defensive += next_eval[opponent_value_col[y]]

    return offensive - defensive, dgn
