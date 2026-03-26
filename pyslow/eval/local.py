"""Local point evaluation and ValueWide cache maintenance."""

from __future__ import annotations

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
    for x in range(board.size):
        for y in range(board.size):
            caches.board_shadow[x][y] = board.at(x, y)


def compute_direction_shape(board: Board, x: int, y: int, direction: int, side: int) -> int:
    if board.at(x, y) != EMPTY:
        return 0
    board.grid[y][x] = side
    try:
        pivot, point_index = _pivot_and_point_index(x, y, direction)
        line = Line.from_board(board, pivot, direction)
        return line.shape(point_index).raw
    finally:
        board.grid[y][x] = EMPTY


def compute_bucket_and_attack(direction_shapes: tuple[int, int, int, int]) -> tuple[int, int]:
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


def recompute_point_caches(board: Board, caches: EvalCaches, x: int, y: int) -> None:
    if board.at(x, y) != EMPTY:
        for player in range(2):
            caches.value_cache[player][x][y] = 0
            caches.attack_cache[player][x][y] = 0
            for direction in _FOUR_DIRECTIONS:
                caches.shape_cache[player][x][y][direction] = 0
        return

    for side in (BLACK, WHITE):
        player = _side_index(side)
        direction_shapes = []
        for direction in _FOUR_DIRECTIONS:
            shape = compute_direction_shape(board, x, y, direction, side)
            caches.shape_cache[player][x][y][direction] = shape
            direction_shapes.append(shape)
        bucket, attack = compute_bucket_and_attack(tuple(direction_shapes))
        caches.value_cache[player][x][y] = bucket
        caches.attack_cache[player][x][y] = attack


def recompute_all(board: Board, caches: EvalCaches) -> None:
    for x in range(board.size):
        for y in range(board.size):
            recompute_point_caches(board, caches, x, y)
    _copy_board_into_shadow(board, caches)
    caches.initialized = True


def value_wide_compute(board: Board, caches: EvalCaches) -> None:
    if not caches.initialized:
        if any(board.at(x, y) != EMPTY for x in range(board.size) for y in range(board.size)):
            recompute_all(board, caches)
            return
        caches.initialized = True

    ar = 4
    comp = [[bytearray(4) for _ in range(board.size)] for _ in range(board.size)]

    for x in range(board.size):
        for y in range(board.size):
            if caches.board_shadow[x][y] != board.at(x, y):
                comp[x][y][:] = b"\x01\x01\x01\x01"

                fixed = x
                seen = 0
                for yy in range(y + 1, min(board.size, y + ar + 1)):
                    value = board.at(fixed, yy)
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[fixed][yy][0] = 1
                seen = 0
                for yy in range(y - 1, max(-1, y - ar - 1), -1):
                    value = board.at(fixed, yy)
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[fixed][yy][0] = 1

                fixed = y
                seen = 0
                for xx in range(x + 1, min(board.size, x + ar + 1)):
                    value = board.at(xx, fixed)
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][fixed][1] = 1
                seen = 0
                for xx in range(x - 1, max(-1, x - ar - 1), -1):
                    value = board.at(xx, fixed)
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][fixed][1] = 1

                seen = 0
                xx = x - 1
                yy = y + 1
                while xx >= 0 and yy < board.size and xx >= x - ar and yy <= y + ar:
                    value = board.at(xx, yy)
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][yy][2] = 1
                    xx -= 1
                    yy += 1
                seen = 0
                xx = x + 1
                yy = y - 1
                while xx < board.size and yy >= 0 and xx <= x + ar and yy >= y - ar:
                    value = board.at(xx, yy)
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][yy][2] = 1
                    xx += 1
                    yy -= 1

                seen = 0
                xx = x + 1
                yy = y + 1
                while xx < board.size and yy < board.size and xx <= x + ar and yy <= y + ar:
                    value = board.at(xx, yy)
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][yy][3] = 1
                    xx += 1
                    yy += 1
                seen = 0
                xx = x - 1
                yy = y - 1
                while xx >= 0 and yy >= 0 and xx >= x - ar and yy >= y - ar:
                    value = board.at(xx, yy)
                    if seen == 0:
                        seen = value
                    elif value != EMPTY and value != seen:
                        break
                    comp[xx][yy][3] = 1
                    xx -= 1
                    yy -= 1

    for x in range(board.size):
        for y in range(board.size):
            caches.board_shadow[x][y] = board.at(x, y)
            if any(comp[x][y]) and board.at(x, y) == EMPTY:
                for direction in _FOUR_DIRECTIONS:
                    if comp[x][y][direction]:
                        for side in (BLACK, WHITE):
                            player = _side_index(side)
                            caches.shape_cache[player][x][y][direction] = compute_direction_shape(
                                board, x, y, direction, side
                            )
                for player in range(2):
                    direction_shapes = tuple(caches.shape_cache[player][x][y][direction] for direction in _FOUR_DIRECTIONS)
                    bucket, attack = compute_bucket_and_attack(direction_shapes)
                    caches.value_cache[player][x][y] = bucket
                    caches.attack_cache[player][x][y] = attack
            elif board.at(x, y) != EMPTY:
                for player in range(2):
                    caches.value_cache[player][x][y] = 0
                    caches.attack_cache[player][x][y] = 0
                    for direction in _FOUR_DIRECTIONS:
                        caches.shape_cache[player][x][y][direction] = 0


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
