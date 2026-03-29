"""Move ordering helpers."""

from __future__ import annotations

import os

from pyslow.board import Board
from pyslow.search.movegen import Candidate

_ORDERING_BACKEND_MODE = os.getenv("PYSLOW_ORDERING_BACKEND", "auto").lower()
_USING_CYTHON_ORDERING_BACKEND = False

if _ORDERING_BACKEND_MODE != "python":
    try:
        from pyslow.search._ordering_cy import getmi_raw as _getmi_native
    except ImportError:
        if _ORDERING_BACKEND_MODE == "cython":
            raise
        _getmi_native = None
    else:
        _USING_CYTHON_ORDERING_BACKEND = True
else:
    _getmi_native = None


def ordering_backend_name() -> str:
    return "cython" if _USING_CYTHON_ORDERING_BACKEND else "python"


def getmi(board: Board, x: int, y: int, c: int) -> int:
    if _getmi_native is not None:
        return _getmi_native(board.grid, x, y, c, board.size)
    ret = 1
    size = board.size
    grid = board.grid
    opponent = -c

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


def order_candidates(
    board: Board,
    candidates: tuple[Candidate, ...],
    side: int,
    tt_best_move: int = -1,
) -> tuple[Candidate, ...]:
    def sort_key(candidate: Candidate) -> tuple[int, float, int, int]:
        x = candidate.move % board.size
        y = candidate.move // board.size
        tt_bias = 1 if candidate.move == tt_best_move else 0
        return (-tt_bias, -candidate.order_score, -getmi(board, x, y, side), candidate.move)

    return tuple(sorted(candidates, key=sort_key))


def order_candidates_root_classic(
    board: Board,
    candidates: tuple[Candidate, ...],
    side: int,
) -> tuple[Candidate, ...]:
    ordered = list(candidates)
    mis = [0] * (board.size * board.size)
    limit = len(ordered)
    for i in range(limit):
        best_index = i
        best = ordered[best_index]
        best_mi = 0
        for j in range(i + 1, limit):
            candidate = ordered[j]
            if candidate.order_score > best.order_score:
                best_index = j
                best = candidate
                best_mi = 0
                continue
            if candidate.order_score < best.order_score:
                continue
            if best_mi == 0:
                bx = best.move % board.size
                by = best.move // board.size
                best_mi = getmi(board, bx, by, side)
                mis[best.move] = best_mi
            candidate_mi = mis[candidate.move]
            if candidate_mi == 0:
                cx = candidate.move % board.size
                cy = candidate.move // board.size
                candidate_mi = getmi(board, cx, cy, side)
                mis[candidate.move] = candidate_mi
            if candidate_mi > best_mi:
                best_index = j
                best = candidate
                best_mi = candidate_mi
        ordered[i], ordered[best_index] = ordered[best_index], ordered[i]
    return tuple(ordered)
