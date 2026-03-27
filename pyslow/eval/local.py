"""Local point evaluation and ValueWide cache maintenance."""

from __future__ import annotations

import os

from pyslow.board import Board
from pyslow.config import EngineConfig
from pyslow.constants import BLACK, BOARD_SIZE, EMPTY, WHITE
from pyslow.eval.caches import EvalCaches
from pyslow.patterns.buckets import bucket_for_lines
from pyslow.patterns.line import Line
from pyslow.patterns.shapes import DIAGONAL_DOWN, DIAGONAL_UP, HORIZONTAL, VERTICAL, ShapeLabel

_FOUR_DIRECTIONS = (HORIZONTAL, VERTICAL, DIAGONAL_DOWN, DIAGONAL_UP)


def _side_index(side: int) -> int:
    if side == BLACK:
        return 0
    if side == WHITE:
        return 1
    raise ValueError(f"invalid side: {side}")


def _pivot_and_point_index(x: int, y: int, direction: int) -> tuple[int, int]:
    if direction == HORIZONTAL:
        return x, y
    if direction == VERTICAL:
        return y, x
    if direction == DIAGONAL_DOWN:
        return x + y, y
    if direction == DIAGONAL_UP:
        return BOARD_SIZE - 1 - y + x, BOARD_SIZE - 1 - y
    raise ValueError(f"invalid direction: {direction}")


def _copy_board_into_shadow(board: Board, caches: EvalCaches) -> None:
    size = board.size
    grid = board.grid
    shadow = caches.board_shadow
    for x in range(size):
        shadow_col = shadow[x]
        for y in range(size):
            shadow_col[y] = grid[y][x]


def _compute_bucket_and_attack_python(direction_shapes: tuple[int, int, int, int]) -> tuple[int, int]:
    attack = 0
    active_threes = 0
    broken_fours = 0
    fives = 0
    overlines = 0
    lines = [0, 0, 0, 0]

    for idx, shape in enumerate(direction_shapes):
        label = (shape >> 16) & 0xF
        aux = shape & 0xF
        lines[idx] = label % ShapeLabel.L6
        if label in (ShapeLabel.L3, ShapeLabel.L3B):
            active_threes += 1
            attack = max(attack, 3)
        elif label == ShapeLabel.L4S:
            broken_fours += aux
            attack = max(attack, 4)
            if aux >= 2:
                lines[idx] = 8
        elif label == ShapeLabel.L5:
            fives += 1
            attack = 6
        elif label == ShapeLabel.L4:
            broken_fours += 1
            attack = max(attack, 5)
        elif label == ShapeLabel.L6:
            overlines += 1

    if lines[0] < lines[1]:
        lines[0], lines[1] = lines[1], lines[0]
    if lines[2] < lines[3]:
        lines[2], lines[3] = lines[3], lines[2]

    if lines[1] >= lines[2]:
        top1, top2 = lines[0], lines[1]
    elif lines[3] >= lines[0]:
        top1, top2 = lines[2], lines[3]
    elif lines[0] >= lines[2]:
        top1, top2 = lines[0], lines[2]
    else:
        top1, top2 = lines[2], lines[0]

    bucket = bucket_for_lines(top1, top2)
    _ = active_threes, broken_fours, fives, overlines
    return bucket, attack


_LOCAL_BACKEND_MODE = os.getenv("PYSLOW_LOCAL_BACKEND", "auto").lower()
_USING_CYTHON_LOCAL_BACKEND = False

if _LOCAL_BACKEND_MODE != "python":
    try:
        from pyslow.eval._local_cy import compute_bucket_and_attack_raw as _compute_bucket_and_attack_native
        from pyslow.eval._local_cy import compute_direction_shape_raw as _compute_direction_shape_native
        from pyslow.eval._local_cy import compute_point_cache_entry as _compute_point_cache_entry_native
        from pyslow.eval._local_cy import value_wide_update as _value_wide_update_native
    except ImportError:
        if _LOCAL_BACKEND_MODE == "cython":
            raise
        _compute_bucket_and_attack_native = None
        _compute_direction_shape_native = None
        _compute_point_cache_entry_native = None
        _value_wide_update_native = None
    else:
        _USING_CYTHON_LOCAL_BACKEND = True
else:
    _compute_bucket_and_attack_native = None
    _compute_direction_shape_native = None
    _compute_point_cache_entry_native = None
    _value_wide_update_native = None


def local_backend_name() -> str:
    return "cython" if _USING_CYTHON_LOCAL_BACKEND else "python"


def compute_direction_shape(board: Board, x: int, y: int, direction: int, side: int) -> int:
    if _compute_direction_shape_native is not None:
        return _compute_direction_shape_native(board.grid, x, y, direction, side, board.size)
    grid = board.grid
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
            pivot = BOARD_SIZE - 1 - y + x
            point_index = BOARD_SIZE - 1 - y
        else:
            raise ValueError(f"invalid direction: {direction}")
        return Line.from_board(board, pivot, direction).shape_raw(point_index)
    finally:
        grid[y][x] = EMPTY


def compute_bucket_and_attack(direction_shapes: tuple[int, int, int, int]) -> tuple[int, int]:
    if _compute_bucket_and_attack_native is not None:
        return _compute_bucket_and_attack_native(
            direction_shapes[0],
            direction_shapes[1],
            direction_shapes[2],
            direction_shapes[3],
        )
    return _compute_bucket_and_attack_python(direction_shapes)


def recompute_point_caches(board: Board, caches: EvalCaches, x: int, y: int) -> None:
    active_snapshots = caches._active_snapshot_count
    shape_log_append = caches._shape_log.append
    shape_cache = caches.shape_cache

    if board.grid[y][x] != EMPTY:
        for player in (0, 1):
            caches.value_cache[player][x][y] = 0
            caches.attack_cache[player][x][y] = 0
            shape_col = shape_cache[player][x][y]
            old = shape_col[HORIZONTAL]
            if old != 0:
                if active_snapshots:
                    shape_log_append((player, x, y, HORIZONTAL, old))
                shape_col[HORIZONTAL] = 0
            old = shape_col[VERTICAL]
            if old != 0:
                if active_snapshots:
                    shape_log_append((player, x, y, VERTICAL, old))
                shape_col[VERTICAL] = 0
            old = shape_col[DIAGONAL_DOWN]
            if old != 0:
                if active_snapshots:
                    shape_log_append((player, x, y, DIAGONAL_DOWN, old))
                shape_col[DIAGONAL_DOWN] = 0
            old = shape_col[DIAGONAL_UP]
            if old != 0:
                if active_snapshots:
                    shape_log_append((player, x, y, DIAGONAL_UP, old))
                shape_col[DIAGONAL_UP] = 0
        return

    for side, player in ((BLACK, 0), (WHITE, 1)):
        shape_col = shape_cache[player][x][y]
        if _compute_point_cache_entry_native is not None:
            h_shape, v_shape, d_down_shape, d_up_shape, bucket, attack = _compute_point_cache_entry_native(
                board.grid, x, y, side, board.size
            )
        else:
            h_shape = compute_direction_shape(board, x, y, HORIZONTAL, side)
            v_shape = compute_direction_shape(board, x, y, VERTICAL, side)
            d_down_shape = compute_direction_shape(board, x, y, DIAGONAL_DOWN, side)
            d_up_shape = compute_direction_shape(board, x, y, DIAGONAL_UP, side)
            bucket, attack = compute_bucket_and_attack((h_shape, v_shape, d_down_shape, d_up_shape))
        old = shape_col[HORIZONTAL]
        if old != h_shape:
            if active_snapshots:
                shape_log_append((player, x, y, HORIZONTAL, old))
            shape_col[HORIZONTAL] = h_shape
        old = shape_col[VERTICAL]
        if old != v_shape:
            if active_snapshots:
                shape_log_append((player, x, y, VERTICAL, old))
            shape_col[VERTICAL] = v_shape
        old = shape_col[DIAGONAL_DOWN]
        if old != d_down_shape:
            if active_snapshots:
                shape_log_append((player, x, y, DIAGONAL_DOWN, old))
            shape_col[DIAGONAL_DOWN] = d_down_shape
        old = shape_col[DIAGONAL_UP]
        if old != d_up_shape:
            if active_snapshots:
                shape_log_append((player, x, y, DIAGONAL_UP, old))
            shape_col[DIAGONAL_UP] = d_up_shape
        caches.value_cache[player][x][y] = bucket
        caches.attack_cache[player][x][y] = attack


def recompute_all(board: Board, caches: EvalCaches) -> None:
    size = board.size
    for x in range(size):
        for y in range(size):
            recompute_point_caches(board, caches, x, y)
    _copy_board_into_shadow(board, caches)
    caches.initialized = True


def value_wide_compute(board: Board, caches: EvalCaches) -> None:
    size = board.size
    grid = board.grid
    shadow = caches.board_shadow
    if not caches.initialized:
        if any(grid[y][x] != EMPTY for x in range(size) for y in range(size)):
            recompute_all(board, caches)
            return
        caches.initialized = True

    if _value_wide_update_native is not None:
        _value_wide_update_native(
            grid,
            caches.board_shadow,
            caches.shape_cache,
            caches.value_cache,
            caches.attack_cache,
            caches._active_snapshot_count,
            caches._shape_log,
            size,
        )
        return

    ar = 4
    comp = [bytearray(size) for _ in range(size)]
    horizontal_flag = 1
    vertical_flag = 2
    diag_down_flag = 4
    diag_up_flag = 8

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
                for xx in range(x + 1, min(board.size, x + ar + 1)):
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

    shape_cache_black = caches.shape_cache[0]
    shape_cache_white = caches.shape_cache[1]
    value_cache_black = caches.value_cache[0]
    value_cache_white = caches.value_cache[1]
    attack_cache_black = caches.attack_cache[0]
    attack_cache_white = caches.attack_cache[1]
    active_snapshots = caches._active_snapshot_count
    shape_log_append = caches._shape_log.append
    for x in range(size):
        shadow_col = shadow[x]
        comp_col = comp[x]
        black_shape_col = shape_cache_black[x]
        white_shape_col = shape_cache_white[x]
        black_value_col = value_cache_black[x]
        white_value_col = value_cache_white[x]
        black_attack_col = attack_cache_black[x]
        white_attack_col = attack_cache_white[x]
        for y in range(size):
            row = grid[y]
            cell = row[x]
            shadow_col[y] = cell
            flags = comp_col[y]
            if flags and cell == EMPTY:
                if flags & horizontal_flag:
                    black_shape = black_shape_col[y]
                    white_shape = white_shape_col[y]
                    new_black = compute_direction_shape(board, x, y, HORIZONTAL, BLACK)
                    old = black_shape[HORIZONTAL]
                    if old != new_black:
                        if active_snapshots:
                            shape_log_append((0, x, y, HORIZONTAL, old))
                        black_shape[HORIZONTAL] = new_black
                    new_white = compute_direction_shape(board, x, y, HORIZONTAL, WHITE)
                    old = white_shape[HORIZONTAL]
                    if old != new_white:
                        if active_snapshots:
                            shape_log_append((1, x, y, HORIZONTAL, old))
                        white_shape[HORIZONTAL] = new_white
                if flags & vertical_flag:
                    black_shape = black_shape_col[y]
                    white_shape = white_shape_col[y]
                    new_black = compute_direction_shape(board, x, y, VERTICAL, BLACK)
                    old = black_shape[VERTICAL]
                    if old != new_black:
                        if active_snapshots:
                            shape_log_append((0, x, y, VERTICAL, old))
                        black_shape[VERTICAL] = new_black
                    new_white = compute_direction_shape(board, x, y, VERTICAL, WHITE)
                    old = white_shape[VERTICAL]
                    if old != new_white:
                        if active_snapshots:
                            shape_log_append((1, x, y, VERTICAL, old))
                        white_shape[VERTICAL] = new_white
                if flags & diag_down_flag:
                    black_shape = black_shape_col[y]
                    white_shape = white_shape_col[y]
                    new_black = compute_direction_shape(board, x, y, DIAGONAL_DOWN, BLACK)
                    old = black_shape[DIAGONAL_DOWN]
                    if old != new_black:
                        if active_snapshots:
                            shape_log_append((0, x, y, DIAGONAL_DOWN, old))
                        black_shape[DIAGONAL_DOWN] = new_black
                    new_white = compute_direction_shape(board, x, y, DIAGONAL_DOWN, WHITE)
                    old = white_shape[DIAGONAL_DOWN]
                    if old != new_white:
                        if active_snapshots:
                            shape_log_append((1, x, y, DIAGONAL_DOWN, old))
                        white_shape[DIAGONAL_DOWN] = new_white
                if flags & diag_up_flag:
                    black_shape = black_shape_col[y]
                    white_shape = white_shape_col[y]
                    new_black = compute_direction_shape(board, x, y, DIAGONAL_UP, BLACK)
                    old = black_shape[DIAGONAL_UP]
                    if old != new_black:
                        if active_snapshots:
                            shape_log_append((0, x, y, DIAGONAL_UP, old))
                        black_shape[DIAGONAL_UP] = new_black
                    new_white = compute_direction_shape(board, x, y, DIAGONAL_UP, WHITE)
                    old = white_shape[DIAGONAL_UP]
                    if old != new_white:
                        if active_snapshots:
                            shape_log_append((1, x, y, DIAGONAL_UP, old))
                        white_shape[DIAGONAL_UP] = new_white

                bucket, attack = compute_bucket_and_attack(
                    (
                        black_shape_col[y][HORIZONTAL],
                        black_shape_col[y][VERTICAL],
                        black_shape_col[y][DIAGONAL_DOWN],
                        black_shape_col[y][DIAGONAL_UP],
                    )
                )
                black_value_col[y] = bucket
                black_attack_col[y] = attack
                bucket, attack = compute_bucket_and_attack(
                    (
                        white_shape_col[y][HORIZONTAL],
                        white_shape_col[y][VERTICAL],
                        white_shape_col[y][DIAGONAL_DOWN],
                        white_shape_col[y][DIAGONAL_UP],
                    )
                )
                white_value_col[y] = bucket
                white_attack_col[y] = attack
            elif cell != EMPTY:
                black_value_col[y] = 0
                white_value_col[y] = 0
                black_attack_col[y] = 0
                white_attack_col[y] = 0
                black_shape = black_shape_col[y]
                white_shape = white_shape_col[y]
                old = black_shape[HORIZONTAL]
                if old != 0:
                    if active_snapshots:
                        shape_log_append((0, x, y, HORIZONTAL, old))
                    black_shape[HORIZONTAL] = 0
                old = black_shape[VERTICAL]
                if old != 0:
                    if active_snapshots:
                        shape_log_append((0, x, y, VERTICAL, old))
                    black_shape[VERTICAL] = 0
                old = black_shape[DIAGONAL_DOWN]
                if old != 0:
                    if active_snapshots:
                        shape_log_append((0, x, y, DIAGONAL_DOWN, old))
                    black_shape[DIAGONAL_DOWN] = 0
                old = black_shape[DIAGONAL_UP]
                if old != 0:
                    if active_snapshots:
                        shape_log_append((0, x, y, DIAGONAL_UP, old))
                    black_shape[DIAGONAL_UP] = 0
                old = white_shape[HORIZONTAL]
                if old != 0:
                    if active_snapshots:
                        shape_log_append((1, x, y, HORIZONTAL, old))
                    white_shape[HORIZONTAL] = 0
                old = white_shape[VERTICAL]
                if old != 0:
                    if active_snapshots:
                        shape_log_append((1, x, y, VERTICAL, old))
                    white_shape[VERTICAL] = 0
                old = white_shape[DIAGONAL_DOWN]
                if old != 0:
                    if active_snapshots:
                        shape_log_append((1, x, y, DIAGONAL_DOWN, old))
                    white_shape[DIAGONAL_DOWN] = 0
                old = white_shape[DIAGONAL_UP]
                if old != 0:
                    if active_snapshots:
                        shape_log_append((1, x, y, DIAGONAL_UP, old))
                    white_shape[DIAGONAL_UP] = 0


def move_value(caches: EvalCaches, x: int, y: int, side: int, config: EngineConfig) -> float:
    player = _side_index(side)
    opponent = 1 - player
    return (
        config.eval_tables.attack_value[caches.value_cache[player][x][y]]
        + config.eval_tables.defend_value[caches.value_cache[opponent][x][y]]
    )


def eval_value_next(caches: EvalCaches, x: int, y: int, side: int, config: EngineConfig) -> float:
    player = _side_index(side)
    return config.eval_tables.next_eval[caches.value_cache[player][x][y]]


def eval_value_last(caches: EvalCaches, x: int, y: int, side: int, config: EngineConfig) -> float:
    player = _side_index(side)
    return config.eval_tables.last_eval[caches.value_cache[player][x][y]]


def attack_level(caches: EvalCaches, x: int, y: int, side: int) -> int:
    return caches.attack_cache[_side_index(side)][x][y]
