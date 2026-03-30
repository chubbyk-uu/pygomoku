"""Global board evaluation."""

from __future__ import annotations

from math import floor

from pygomoku.board import Board
from pygomoku.config import EngineConfig
from pygomoku.constants import BLACK, LAST5, NEXT4, NEXT43, NEXT5, WHITE, WIN
from pygomoku.eval.caches import EvalCaches
from pygomoku.eval.local import value_wide_compute
from pygomoku.patterns.line import Line
from pygomoku.patterns.shapes import DIAGONAL_DOWN, DIAGONAL_UP, HORIZONTAL, VERTICAL

_DIR_MAP = (3, 1, 2, 0, 0, 0, 2, 1, 3)


def _ga(value: int) -> int:
    return value & 0xFF


def _decode_b4_reply(board_size: int, x: int, y: int, direction_index: int, encoded: int) -> tuple[int, int] | None:
    r1 = _ga(encoded)
    if direction_index == 1:
        return (x, r1)
    if direction_index == 2:
        return (r1, y)
    if direction_index == 3:
        return (x + y - r1, r1)
    if direction_index == 4:
        return (board_size - 1 + x - y - r1, board_size - 1 - r1)
    return None


def _has_b4p_after_move(board: Board, x: int, y: int) -> bool:
    return (
        Line.from_board(board, x, HORIZONTAL).b4p(y) > 0
        or Line.from_board(board, y, VERTICAL).b4p(x) > 0
        or Line.from_board(board, x + y, DIAGONAL_DOWN).b4p(y) > 0
        or Line.from_board(board, board.size - 1 - y + x, DIAGONAL_UP).b4p(board.size - 1 - y) > 0
    )


def _find_last5_target(board: Board, caches: EvalCaches, side: int, config: EngineConfig) -> tuple[int, int] | None:
    size = board.size
    grid = board.grid
    value_cache = caches.value_cache[0 if side == BLACK else 1]
    last_eval = config.eval_tables.last_eval
    threshold = LAST5 * 65536 / 2
    for x in range(size):
        value_col = value_cache[x]
        for y in range(size):
            if grid[y][x] == 0 and last_eval[value_col[y]] >= threshold:
                return (x, y)
    return None


def _evaluate_last5_branch(board: Board, caches: EvalCaches, side: int, opo: int, config: EngineConfig) -> float:
    # Temporarily place stone directly on grid (bypassing board.play) for
    # evaluation only. Zobrist/history/winner are not updated because this
    # is a speculative probe, not an actual move. Restored in finally block.
    target = _find_last5_target(board, caches, side, config)
    if target is None:
        return WIN
    x, y = target
    snapshot = caches.snapshot()
    grid = board.grid
    grid[y][x] = -side
    try:
        value_wide_compute(board, caches)
        return -evaluate_board(board, caches, -side, 1 - opo, config)
    finally:
        grid[y][x] = 0
        caches.restore_snapshot(snapshot)


def _evaluate_next43_branch(board: Board, caches: EvalCaches, side: int, config: EngineConfig) -> bool:
    # Direct grid writes for speculative probing — see _evaluate_last5_branch.
    size = board.size
    grid = board.grid
    next_eval = config.eval_tables.next_eval
    opponent_cache = caches.value_cache[0 if side == WHITE else 1]
    threshold = NEXT43 * 65536 / 2
    for x in range(size):
        opponent_value_col = opponent_cache[x]
        for y in range(size):
            if grid[y][x] != 0 or next_eval[opponent_value_col[y]] < threshold:
                continue
            line_specs = (
                (x, HORIZONTAL, y, 1),
                (y, VERTICAL, x, 2),
                (x + y, DIAGONAL_DOWN, y, 3),
                (size - 1 - y + x, DIAGONAL_UP, size - 1 - y, 4),
            )
            grid[y][x] = -side
            encoded = 0
            direction = 0
            try:
                for pivot, direction_value, point_index, direction_id in line_specs:
                    encoded = Line.from_board(board, pivot, direction_value).b4p(point_index)
                    if encoded > 0:
                        direction = direction_id
                        break
                if direction == 0:
                    continue
                reply = _decode_b4_reply(board.size, x, y, direction, encoded)
                if reply is None:
                    continue
                rx, ry = reply
                if not (0 <= rx < size and 0 <= ry < size) or grid[ry][rx] != 0:
                    continue
                grid[ry][rx] = side
                try:
                    if not _has_b4p_after_move(board, rx, ry):
                        return True
                finally:
                    grid[ry][rx] = 0
            finally:
                grid[y][x] = 0
    return False


def evaluate_board(board: Board, caches: EvalCaches, side: int, opo: int, config: EngineConfig) -> float:
    offensive = 0.0
    defensive = 0.0
    dgn = 0
    player = 0 if side == BLACK else 1
    opponent = 1 - player
    size = board.size
    grid = board.grid
    shape_cache_player = caches.shape_cache[player]
    shape_cache_opponent = caches.shape_cache[opponent]
    player_values = caches.value_cache[player]
    opponent_values = caches.value_cache[opponent]
    last_eval = config.eval_tables.last_eval
    next_eval = config.eval_tables.next_eval

    for x in range(size):
        player_shape_col = shape_cache_player[x]
        opponent_shape_col = shape_cache_opponent[x]
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

    total = offensive - defensive
    if -32768 < total < 32768:
        return total - config.search.drift + dgn * config.search.dgn

    winv = floor((total + 32768) / 65536.0)
    if winv <= -NEXT5 / 2:
        return -WIN
    if winv >= LAST5 / 2:
        return _evaluate_last5_branch(board, caches, side, opo, config)
    if winv <= -NEXT4 / 2:
        return -WIN
    if winv <= -NEXT43:
        if _evaluate_next43_branch(board, caches, side, config):
            return -WIN
    return total - 65536 * winv - config.search.drift + dgn * config.search.dgn
