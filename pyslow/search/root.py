"""Root iterative deepening search."""

from __future__ import annotations

from dataclasses import dataclass
import time

from pyslow.board import Board, move_to_xy, xy_to_move
from pyslow.config import EngineConfig
from pyslow.constants import INF
from pyslow.eval.caches import EvalCaches
from pyslow.eval.local import recompute_all
from pyslow.search.alphabeta import AlphaBetaSearcher, SearchStats
from pyslow.search.movegen import generate_candidates
from pyslow.search.ordering import order_candidates
from pyslow.search.tt import TranspositionTable
from pyslow.threats.vcf import VCFSearcher


def _shape_label(shape: int) -> int:
    return (shape >> 16) & 0xF


def _shape_aux(shape: int) -> int:
    return shape & 0xF


def _fallback_ai_move(board: Board, caches: EvalCaches, side: int) -> int:
    player = 0 if side == 1 else 1
    opponent = 1 - player
    best_move = -1
    best_value = -10**18

    for move in range(board.size * board.size):
        if not board.is_legal_move(move):
            continue
        x, y = move_to_xy(move)

        offensive = 0
        A1l = B2l = A2l = B3l = A4l = A3l = B4l = A5l = A6l = 0
        for direction in range(4):
            shape = caches.shape_cache[player][x][y][direction]
            label = _shape_label(shape)
            if label == 2:
                A1l += 1
            elif label == 3:
                B2l += 1
            elif label in (9, 8):
                A3l += 1
            elif label == 10:
                B4l += _shape_aux(shape)
            elif label == 12:
                A5l += 1
            elif label == 7:
                B3l += 1
            elif label in (6, 5, 4):
                A2l += 1
            elif label == 11:
                A4l += 1
                B4l += 1
            elif label == 13:
                A6l += 1
        offensive += A1l
        offensive += B2l
        offensive += A2l * 5
        offensive += B3l * 10
        offensive += A3l * 12
        offensive += B4l * 16
        offensive += (1 if A3l >= 2 else 0) * 100
        offensive += (1 if (B4l and A3l) else 0) * 3000
        offensive += (1 if B4l >= 2 else 0) * 4000
        offensive += A4l * 6000
        offensive += A5l * 1000000

        defensive = 0
        A2l = B3l = A3l = B4l = A4l = A5l = A6l = 0
        for direction in range(4):
            shape = caches.shape_cache[opponent][x][y][direction]
            label = _shape_label(shape)
            if label in (9, 8):
                A3l += 1
            elif label == 10:
                B4l += _shape_aux(shape)
            elif label == 12:
                A5l += 1
            elif label == 7:
                B3l += 1
            elif label in (6, 5, 4):
                A2l += 1
            elif label == 11:
                A4l += 1
                B4l += 1
            elif label == 13:
                A6l += 1
        defensive += A2l
        defensive += B3l
        defensive += A3l * 6
        defensive += B4l * 11
        defensive += (1 if A3l >= 2 else 0) * 15
        defensive += (1 if (B4l and A3l) else 0) * 1500
        defensive += (1 if B4l >= 2 else 0) * 2000
        defensive += A4l * 3000
        defensive += A5l * 50000

        total = 5 * offensive + 5 * defensive
        if total > best_value:
            best_value = total
            best_move = move

    if best_move == -1:
        raise ValueError("fallback AIs found no legal move on non-terminal board")
    return best_move


@dataclass(frozen=True)
class SearchLimits:
    max_depth: int
    root_width: int
    node_limit: int | None = None
    time_limit_ms: float | None = None


@dataclass(frozen=True)
class SearchResult:
    move: int
    score: int
    depth: int
    nodes: int


class RootSearcher:
    def __init__(self, config: EngineConfig, tt: TranspositionTable | None = None) -> None:
        self.config = config
        self.tt = tt or TranspositionTable()
        self.alphabeta = AlphaBetaSearcher(config, self.tt)
        self.vcf = VCFSearcher()

    def _root_allowed_moves(self, board: Board) -> set[int] | None:
        if self.config.runtime.static_board or board.move_count == 0:
            return None
        moves = board.occupied_moves()
        xs = []
        ys = []
        for move in moves:
            x, y = move_to_xy(move)
            xs.append(x)
            ys.append(y)
        margin = self.config.runtime.dynamic_board_margin
        xmin = max(0, min(xs) - margin)
        xmax = min(board.size - 1, max(xs) + margin)
        ymin = max(0, min(ys) - margin)
        ymax = min(board.size - 1, max(ys) + margin)

        toggle = 0
        while (xmax - xmin) != (ymax - ymin):
            toggle += 1
            if (xmax - xmin) > (ymax - ymin):
                if toggle % 2:
                    if ymin > 0:
                        ymin -= 1
                    else:
                        ymax = min(board.size - 1, ymax + 1)
                else:
                    if ymax < board.size - 1:
                        ymax += 1
                    else:
                        ymin = max(0, ymin - 1)
            else:
                if toggle % 2:
                    if xmin > 0:
                        xmin -= 1
                    else:
                        xmax = min(board.size - 1, xmax + 1)
                else:
                    if xmax < board.size - 1:
                        xmax += 1
                    else:
                        xmin = max(0, xmin - 1)

        allowed: set[int] = set()
        for y in range(ymin, ymax + 1):
            for x in range(xmin, xmax + 1):
                if board.at(x, y) == 0:
                    allowed.add(xy_to_move(x, y))
        return allowed

    def _apply_opponent_vcf_filter(self, board: Board, side: int, allowed_moves: set[int] | None) -> set[int] | None:
        if not self.config.runtime.compute_vcf:
            return allowed_moves
        opponent_vcf = self.vcf.search(board, -side, 7)
        if not opponent_vcf.found:
            return allowed_moves

        candidates: list[int]
        if allowed_moves is None:
            candidates = [move for move in range(board.size * board.size) if board.is_legal_move(move)]
        else:
            candidates = sorted(move for move in allowed_moves if board.is_legal_move(move))

        filtered: set[int] = set()
        for move in candidates:
            trial = board.copy()
            trial.side_to_move = side
            trial.play(move, side)
            if not self.vcf.search(trial, -side, 7).found:
                filtered.add(move)
        return filtered if allowed_moves is not None else filtered

    @staticmethod
    def _is_unstable(
        current_score: int,
        current_move: int,
        prev_score: int | None,
        prev_move: int | None,
        prev_prev_move: int | None,
    ) -> bool:
        if prev_score is None or prev_move is None:
            return True
        if current_score <= prev_score - 5:
            return True
        if current_move != prev_move:
            return True
        if prev_prev_move is not None and prev_move != prev_prev_move:
            return True
        return False

    @classmethod
    def _iteration_budget_ms(
        cls,
        base_time_limit_ms: float | None,
        current_score: int,
        current_move: int,
        prev_score: int | None,
        prev_move: int | None,
        prev_prev_move: int | None,
    ) -> float | None:
        if base_time_limit_ms is None:
            return None
        if cls._is_unstable(current_score, current_move, prev_score, prev_move, prev_prev_move):
            return max(1.0, base_time_limit_ms / 7.0 - 100.0)
        return max(1.0, base_time_limit_ms / 15.0 - 100.0)

    def search(self, board: Board, limits: SearchLimits | None = None) -> SearchResult:
        if limits is None:
            limits = SearchLimits(
                max_depth=self.config.root_search.depth,
                root_width=self.config.root_search.wide,
            )

        if board.move_count == 0:
            center = xy_to_move(board.size // 2, board.size // 2)
            return SearchResult(move=center, score=0, depth=0, nodes=0)

        side = board.side_to_move
        if self.config.runtime.compute_vcf:
            vcf_result = self.vcf.search(board, side, 8)
            if vcf_result.found:
                return SearchResult(move=vcf_result.move, score=INF, depth=0, nodes=0)

        caches = EvalCaches()
        recompute_all(board, caches)
        best_move = -1
        best_score = -INF
        total_nodes = 0
        prev_score: int | None = None
        prev_move: int | None = None
        prev_prev_move: int | None = None
        search_start = time.perf_counter()
        root_allowed_moves = self._root_allowed_moves(board)
        root_allowed_moves = self._apply_opponent_vcf_filter(board, side, root_allowed_moves)
        if root_allowed_moves is not None:
            root_legal_moves = sorted(move for move in root_allowed_moves if board.is_legal_move(move))
            if len(root_legal_moves) == 0:
                return SearchResult(move=_fallback_ai_move(board, caches, side), score=-INF, depth=0, nodes=0)
            if len(root_legal_moves) == 1:
                return SearchResult(move=root_legal_moves[0], score=-INF, depth=0, nodes=0)

        for depth in range(1, limits.max_depth + 2):
            stats = SearchStats(node_limit=limits.node_limit)
            score, move = self.alphabeta.search(
                board,
                caches,
                side,
                depth,
                -INF,
                INF,
                limits.root_width,
                opo=0,
                stats=stats,
                root=True,
                root_allowed_moves=root_allowed_moves,
            )
            total_nodes += stats.nodes
            if move != -1:
                prev_prev_move = prev_move
                prev_move = best_move if best_move != -1 else move
                prev_score = best_score if best_move != -1 else score
                best_move = move
                best_score = score
            budget_ms = self._iteration_budget_ms(
                limits.time_limit_ms,
                score,
                move,
                prev_score,
                prev_move,
                prev_prev_move,
            )
            if stats.stop or abs(score) >= INF - depth:
                break
            if budget_ms is not None:
                elapsed_ms = (time.perf_counter() - search_start) * 1000.0
                if elapsed_ms >= budget_ms / 3.0:
                    break

        if best_move == -1:
            best_move = _fallback_ai_move(board, caches, side)
        return SearchResult(move=best_move, score=best_score, depth=depth, nodes=total_nodes)
