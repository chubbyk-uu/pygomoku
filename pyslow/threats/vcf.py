"""VCF search implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from pyslow.board import Board, move_to_xy
from pyslow.threats.threat_board import ThreatBoardView


@dataclass(frozen=True)
class VCFResult:
    move: int
    found: bool
    solved: bool


@dataclass(frozen=True)
class _MemoEntry:
    depth: int
    result: VCFResult


NO_MOVE: Final[int] = -1
VCFM: Final[int] = 5


class VCFSearcher:
    def __init__(self) -> None:
        self._memo: dict[tuple[int, tuple[int, ...], tuple[int, ...]], _MemoEntry] = {}

    @staticmethod
    def _canonical_sequence_key(
        attacker_moves: tuple[int, ...],
        defender_moves: tuple[int, ...],
    ) -> tuple[tuple[int, ...], tuple[int, ...]]:
        return tuple(sorted(attacker_moves)), tuple(sorted(defender_moves))

    def search(self, board: Board, side: int, depth: int) -> VCFResult:
        self._memo.clear()
        effective_depth = self._normalize_begin_depth(depth)
        return self._search_begin(ThreatBoardView.from_board(board.copy()), side, effective_depth)

    @staticmethod
    def _normalize_begin_depth(depth: int) -> int:
        if depth <= 0:
            return depth
        if depth == 8:
            return min(depth, VCFM)
        return min(depth, VCFM - 1)

    def _search_begin(self, view: ThreatBoardView, side: int, depth: int) -> VCFResult:
        if depth <= 0:
            return VCFResult(move=NO_MOVE, found=False, solved=False)
        shallower = self._search_begin(view, side, depth - 1)
        if shallower.found:
            return shallower
        if shallower.solved:
            return VCFResult(move=NO_MOVE, found=False, solved=True)
        return self._search_attacker(view, side, depth, (), ())

    def _search_attacker(
        self,
        view: ThreatBoardView,
        side: int,
        depth: int,
        attacker_moves: tuple[int, ...],
        defender_moves: tuple[int, ...],
    ) -> VCFResult:
        board = view.board
        if depth <= 0:
            return VCFResult(move=NO_MOVE, found=False, solved=False)

        sequence_key = self._canonical_sequence_key(attacker_moves, defender_moves)
        key = (side, sequence_key[0], sequence_key[1])
        memoized = self._memo.get(key)
        if memoized is not None:
            if memoized.result.found or memoized.result.solved:
                return memoized.result
            if memoized.depth == depth:
                return memoized.result

        direct_b4, _ = view.broken_four_point_for_side(side)
        if direct_b4 is not None:
            result = VCFResult(move=direct_b4, found=True, solved=True)
            self._memo[key] = _MemoEntry(depth=depth, result=result)
            return result

        opponent_b4, opponent_ambiguous = view.broken_four_point_for_side(-side)
        if opponent_b4 is not None and not opponent_ambiguous:
            view.play(opponent_b4, side)
            tx, ty = move_to_xy(opponent_b4)
            if board.winner == side or view.has_a4(tx, ty):
                view.undo()
                result = VCFResult(move=opponent_b4, found=True, solved=True)
                self._memo[key] = _MemoEntry(depth=depth, result=result)
                return result
            defender = self._search_defender(
                view,
                side,
                depth - 1,
                opponent_b4,
                attacker_moves + (opponent_b4,),
                defender_moves,
            )
            view.undo()
            if defender.found:
                result = VCFResult(move=opponent_b4, found=True, solved=True)
                self._memo[key] = _MemoEntry(depth=depth, result=result)
                return result
            if not defender.solved:
                result = VCFResult(move=NO_MOVE, found=False, solved=False)
                self._memo[key] = _MemoEntry(depth=depth, result=result)
                return result
            result = VCFResult(move=NO_MOVE, found=False, solved=True)
            self._memo[key] = _MemoEntry(depth=depth, result=result)
            return result
        elif opponent_b4 is not None:
            result = VCFResult(move=NO_MOVE, found=False, solved=True)
            self._memo[key] = _MemoEntry(depth=depth, result=result)
            return result

        immediate = view.winning_threat_moves(side)
        if immediate:
            result = VCFResult(move=immediate[0], found=True, solved=True)
            self._memo[key] = _MemoEntry(depth=depth, result=result)
            return result

        solved = True
        ordered_moves = view.threat_moves(side)
        for move in ordered_moves:
            view.play(move, side)
            x, y = move_to_xy(move)
            if board.winner == side or view.has_a4(x, y):
                view.undo()
                result = VCFResult(move=move, found=True, solved=True)
                self._memo[key] = _MemoEntry(depth=depth, result=result)
                return result
            view.undo()

        for move in ordered_moves:
            view.play(move, side)
            x, y = move_to_xy(move)
            if view.broken_four_reply(x, y) is None:
                view.undo()
                continue
            defender = self._search_defender(
                view,
                side,
                depth - 1,
                move,
                attacker_moves + (move,),
                defender_moves,
            )
            view.undo()
            if defender.found:
                result = VCFResult(move=move, found=True, solved=True)
                self._memo[key] = _MemoEntry(depth=depth, result=result)
                return result
            if not defender.solved:
                solved = False

        result = VCFResult(move=NO_MOVE, found=False, solved=solved)
        self._memo[key] = _MemoEntry(depth=depth, result=result)
        return result

    def _search_defender(
        self,
        view: ThreatBoardView,
        attacker: int,
        depth: int,
        attacker_move: int,
        attacker_moves: tuple[int, ...],
        defender_moves: tuple[int, ...],
    ) -> VCFResult:
        board = view.board
        if depth < 0:
            return VCFResult(move=NO_MOVE, found=False, solved=False)

        x, y = move_to_xy(attacker_move)
        reply = view.broken_four_reply(x, y)
        if reply is None:
            return VCFResult(move=NO_MOVE, found=False, solved=True)

        view.play(reply, -attacker)
        result = self._search_attacker(
            view,
            attacker,
            depth,
            attacker_moves,
            defender_moves + (reply,),
        )
        view.undo()
        return result
