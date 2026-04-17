"""Root iterative deepening search."""

from __future__ import annotations

from dataclasses import dataclass
import time

from pygomoku.board import Board, move_to_xy, xy_to_move
from pygomoku.config import EngineConfig
from pygomoku.constants import INF, WIN
from pygomoku.eval.caches import EvalCaches
from pygomoku.eval.local import recompute_all
from pygomoku.search.alphabeta import AlphaBetaSearcher, SearchStats
from pygomoku.search.movegen import generate_candidates
from pygomoku.search.ordering import order_candidates
from pygomoku.search.tt import TranspositionTable
from pygomoku.threats.vcf import VCFSearcher

_CLASSIC_RAND_SEED = 1232356
_CLASSIC_FALLBACK_STATE = (
    -950575697,
    -534807373,
    229790648,
    -966373420,
    529145457,
    -273021231,
    1735816513,
    469166854,
    1730624144,
    -1386466792,
    649120694,
    -1282397366,
    473519764,
    1775465023,
    936985512,
    994684877,
    -63353161,
    825016603,
    -643785611,
    -1367318099,
    -45443784,
    1063826198,
    2094918629,
    -1988741269,
    -281467344,
    563982589,
    367722354,
    742065300,
    1591101748,
    477268195,
    -574683412,
)
_CLASSIC_FALLBACK_FPTR = 25
_CLASSIC_FALLBACK_RPTR = 22


class _ClassicFallbackRng:
    """Mirror the classic Gomocup fallback rand() stream."""

    def __init__(self, seed: int = _CLASSIC_RAND_SEED) -> None:
        if seed != _CLASSIC_RAND_SEED:
            raise ValueError("only the classic fallback seed is supported")
        # In Gomocup mode the engine process calls `InitHash()` twice before the
        # first real move search: once on `START` and once on the initial
        # `RESTART` used by `_sync_full_board()`. These values were captured from
        # the local libc `rand()` state after `srand(1232356)` and both InitHash
        # passes (2 * 4010 draws with the classic N=20 zobrist stream shape).
        self._state = [value & 0xFFFFFFFF for value in _CLASSIC_FALLBACK_STATE]
        self._fptr = _CLASSIC_FALLBACK_FPTR
        self._rptr = _CLASSIC_FALLBACK_RPTR

    def randrange(self, upper: int) -> int:
        if upper <= 0:
            raise ValueError("upper must be positive")
        value = (self._state[self._fptr] + self._state[self._rptr]) & 0xFFFFFFFF
        self._state[self._fptr] = value
        self._fptr = (self._fptr + 1) % len(self._state)
        self._rptr = (self._rptr + 1) % len(self._state)
        return ((value >> 1) & 0x7FFFFFFF) % upper


def _new_classic_fallback_rng() -> _ClassicFallbackRng:
    return _ClassicFallbackRng()


def _shape_label(shape: int) -> int:
    return (shape >> 16) & 0xF


def _shape_aux(shape: int) -> int:
    return shape & 0xF


def _fallback_ai_move(
    board: Board,
    caches: EvalCaches,
    side: int,
    *,
    rng: _ClassicFallbackRng | None = None,
) -> int:
    player = 0 if side == 1 else 1
    opponent = 1 - player
    best_value = -10**18
    best_moves: list[int] = []
    if rng is None:
        rng = _new_classic_fallback_rng()

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
            best_moves = [move]
        elif total == best_value:
            best_moves.append(move)

    if not best_moves:
        raise ValueError("fallback AIs found no legal move on non-terminal board")
    return best_moves[rng.randrange(len(best_moves))]


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
        self._fallback_rng = _new_classic_fallback_rng()

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
        return filtered

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
        search_start = time.perf_counter()
        deadline_s = None if limits.time_limit_ms is None else search_start + limits.time_limit_ms / 1000.0
        root_allowed_moves = self._root_allowed_moves(board)
        root_allowed_moves = self._apply_opponent_vcf_filter(board, side, root_allowed_moves)
        if root_allowed_moves is not None:
            root_legal_moves = sorted(move for move in root_allowed_moves if board.is_legal_move(move))
            if len(root_legal_moves) == 0:
                return SearchResult(
                    move=_fallback_ai_move(board, caches, side, rng=self._fallback_rng),
                    score=-INF,
                    depth=0,
                    nodes=0,
                )
            if len(root_legal_moves) == 1:
                # Classic root search short-circuits here: after VCF root filtering leaves
                # a single legal move, alphabeta returns the previous outer-iteration score
                # (`abval.first`), which is still 0 before the first completed iteration.
                return SearchResult(
                    move=root_legal_moves[0],
                    score=0,
                    depth=0,
                    nodes=0,
                )

        completed_depth = 0
        for depth in range(1, limits.max_depth + 1):
            if deadline_s is not None and time.perf_counter() >= deadline_s:
                break
            stats = SearchStats(node_limit=limits.node_limit, deadline_s=deadline_s)
            score, move = self.alphabeta.search(
                board,
                caches,
                side,
                depth,
                -INF,
                INF,
                limits.root_width,
                opo=1,
                stats=stats,
                root=True,
                root_allowed_moves=root_allowed_moves,
            )
            total_nodes += stats.nodes
            if stats.stop:
                break
            completed_depth = depth
            if move != -1:
                best_move = move
                best_score = score
            elif score <= -WIN:
                # Classic root search does not keep the previous PV when the
                # current iteration reports "all root children lose" via
                # `abval.second == -1`; it falls back to AIs() immediately.
                best_move = _fallback_ai_move(board, caches, side, rng=self._fallback_rng)
                best_score = score
            if stats.stop or score >= WIN or score <= -WIN:
                break

        if best_move == -1:
            best_move = _fallback_ai_move(board, caches, side, rng=self._fallback_rng)
        return SearchResult(move=best_move, score=best_score, depth=completed_depth, nodes=total_nodes)
