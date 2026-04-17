"""Optional Cython helpers for global board evaluation hot paths."""

# Keep the Python tuple for any external reference.
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
    # Precomputed neighbor table: 8 directions skipping self (replaces the
    # k=0..8 / k!=4 loop with k//3 and k%3 arithmetic).
    # dx[n], dy[n]: offset from (x,y); dmap[n]: corresponding _DIR_MAP value.
    cdef int dx[8]
    cdef int dy[8]
    cdef int dmap[8]
    dx[:]   = [-1, -1, -1,  0,  0,  1,  1,  1]
    dy[:]   = [-1,  0,  1, -1,  1, -1,  0,  1]
    dmap[:] = [ 3,  1,  2,  0,  0,  2,  1,  3]

    cdef double offensive = 0.0
    cdef double defensive = 0.0
    cdef int dgn = 0
    cdef int x, y, xx, yy, n, cc, stone, dir_idx, shape_val, bucket_idx

    # Typed list locals: Cython uses PyList_GET_ITEM (unchecked, fast) instead
    # of the Python __getitem__ protocol when the receiver is declared as list.
    cdef list player_value_col, opponent_value_col
    cdef list grid_row, grid_row_n
    cdef list sc_player_xx, sc_opponent_xx
    cdef list sc_player_xy, sc_opponent_xy

    for x in range(size):
        player_value_col = player_values[x]
        opponent_value_col = opponent_values[x]
        for y in range(size):
            grid_row = grid[y]
            stone = <int>grid_row[x]
            if stone == side:
                cc = 1
                for n in range(8):
                    xx = x + dx[n]
                    yy = y + dy[n]
                    if xx < 0 or yy < 0 or xx >= size or yy >= size:
                        cc += 1
                    else:
                        grid_row_n = grid[yy]
                        if <int>grid_row_n[xx] != 0:
                            cc += 1
                        else:
                            dir_idx = dmap[n]
                            sc_player_xx = shape_cache_player[xx]
                            sc_player_xy = sc_player_xx[yy]
                            shape_val = <int>sc_player_xy[dir_idx]
                            if ((shape_val >> 16) & 15) == 0:
                                cc += 1
                if cc <= 1:
                    dgn -= 5
                elif cc - 1 >= 5:
                    dgn -= cc - 1 - 3
            elif stone == -side:
                cc = 1
                for n in range(8):
                    xx = x + dx[n]
                    yy = y + dy[n]
                    if xx < 0 or yy < 0 or xx >= size or yy >= size:
                        cc += 1
                    else:
                        grid_row_n = grid[yy]
                        if <int>grid_row_n[xx] != 0:
                            cc += 1
                        else:
                            dir_idx = dmap[n]
                            sc_opponent_xx = shape_cache_opponent[xx]
                            sc_opponent_xy = sc_opponent_xx[yy]
                            shape_val = <int>sc_opponent_xy[dir_idx]
                            if ((shape_val >> 16) & 15) == 0:
                                cc += 1
                if cc <= 1:
                    dgn += 5
                elif cc - 1 >= 5:
                    dgn += cc - 1 - 3
            else:
                bucket_idx = <int>player_value_col[y]
                offensive += <double>last_eval[bucket_idx]
                bucket_idx = <int>opponent_value_col[y]
                defensive += <double>next_eval[bucket_idx]

    return offensive - defensive, dgn
