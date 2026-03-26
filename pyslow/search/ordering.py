"""Move ordering helpers."""

from __future__ import annotations

from pyslow.board import Board, move_to_xy
from pyslow.search.movegen import Candidate


def getmi(board: Board, x: int, y: int, c: int) -> int:
    ret = 1

    ii, jj = x + 1, y
    while ii <= x + 4 and ii < board.size:
        if board.at(ii, jj) == -c:
            break
        ret += 1
        ii += 1

    ii, jj = x - 1, y
    while ii >= x - 4 and ii >= 0:
        if board.at(ii, jj) == -c:
            break
        ret += 1
        ii -= 1

    ii, jj = x, y + 1
    while jj <= y + 4 and jj < board.size:
        if board.at(ii, jj) == -c:
            break
        ret += 1
        jj += 1

    ii, jj = x, y - 1
    while jj >= y - 4 and jj >= 0:
        if board.at(ii, jj) == -c:
            break
        ret += 1
        jj -= 1

    ii, jj = x + 1, y + 1
    while ii <= x + 4 and ii < board.size and jj < board.size:
        if board.at(ii, jj) == -c:
            break
        ret += 1
        ii += 1
        jj += 1

    ii, jj = x - 1, y - 1
    while ii >= x - 4 and ii >= 0 and jj >= 0:
        if board.at(ii, jj) == -c:
            break
        ret += 1
        ii -= 1
        jj -= 1

    ii, jj = x - 1, y + 1
    while ii >= x - 4 and ii >= 0 and jj < board.size:
        if board.at(ii, jj) == -c:
            break
        ret += 1
        ii -= 1
        jj += 1

    ii, jj = x + 1, y - 1
    while ii <= x + 4 and ii < board.size and jj >= 0:
        if board.at(ii, jj) == -c:
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
        x, y = move_to_xy(candidate.move)
        tt_bias = 1 if candidate.move == tt_best_move else 0
        return (-tt_bias, -candidate.order_score, -getmi(board, x, y, side), candidate.move)

    return tuple(sorted(candidates, key=sort_key))
