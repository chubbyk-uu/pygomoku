"""Optional Cython helpers for move generation hot paths."""

from pyslow.constants import BOARD_SIZE, EMPTY


def covered_moves_raw(object move_history, object grid, object cover_neighbors):
    cdef bytearray seen = bytearray(BOARD_SIZE * BOARD_SIZE)
    cdef list covered = []
    cdef object played
    cdef int candidate
    cdef int x
    cdef int y

    for played in move_history:
        for candidate in cover_neighbors[played.move]:
            if not seen[candidate]:
                x = candidate % BOARD_SIZE
                y = candidate // BOARD_SIZE
                if grid[y][x] == EMPTY:
                    seen[candidate] = 1
                    covered.append(candidate)
    covered.sort()
    return tuple(covered)


def candidate_stats_raw(
    object moves,
    object player_value_cache,
    object opponent_value_cache,
    object player_attack_cache,
    object opponent_attack_cache,
    object attack_value_table,
    object defend_value_table,
):
    cdef dict vbw_map = {}
    cdef dict self_attack_map = {}
    cdef dict opp_attack_map = {}
    cdef int at1pri = 0
    cdef int at2pri = 0
    cdef int sglflag = 0
    cdef int hsflag = 0
    cdef int move
    cdef int x
    cdef int y
    cdef int bucket_self
    cdef int bucket_opp
    cdef int vbw
    cdef int att1
    cdef int att2

    for move in moves:
        x = move % BOARD_SIZE
        y = move // BOARD_SIZE
        bucket_self = player_value_cache[x][y]
        bucket_opp = opponent_value_cache[x][y]
        vbw = <int>(attack_value_table[bucket_self] + defend_value_table[bucket_opp])
        att1 = player_attack_cache[x][y]
        att2 = opponent_attack_cache[x][y]
        vbw_map[move] = vbw
        self_attack_map[move] = att1
        opp_attack_map[move] = att2
        if vbw <= 0:
            if att2 > at2pri:
                at2pri = att2
            continue
        if att2 == 6 or att1 >= 5:
            sglflag += 1
        elif att2 == 5:
            hsflag = move + 1
        if att1 > at1pri:
            at1pri = att1
        if att2 > at2pri:
            at2pri = att2

    return vbw_map, self_attack_map, opp_attack_map, at1pri, at2pri, sglflag, hsflag
