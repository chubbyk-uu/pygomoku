"""Alpha-beta search implementation."""

from __future__ import annotations

from dataclasses import dataclass
from math import log
import os
import time

from pygomoku.board import Board
from pygomoku.config import EngineConfig
from pygomoku.constants import HASHF_ALPHA, HASHF_BETA, HASHF_EXACT, INF, WIN
from pygomoku.eval.caches import EvalCaches
from pygomoku.eval.global_eval import evaluate_board
from pygomoku.eval.local import value_wide_compute
from pygomoku.search.movegen import generate_candidates
from pygomoku.search.ordering import order_candidates, order_candidates_root_classic
from pygomoku.search.tt import TTEntry, TranspositionTable
from pygomoku.threats.vcf import VCFSearcher

_DEBUG_TT_KEY = int(os.getenv("PYSLOW_DEBUG_TT_KEY", "0"))
_DEBUG_ROOT_KEY = int(os.getenv("PYSLOW_DEBUG_ROOT_KEY", "0"))
_DEBUG_NODE_KEY = int(os.getenv("PYSLOW_DEBUG_NODE_KEY", "0"))


@dataclass
class SearchStats:
    nodes: int = 0
    leaf_nodes: int = 0
    tt_hits: int = 0
    cutoffs: int = 0
    stop: bool = False
    node_limit: int | None = None
    deadline_s: float | None = None
    time_check_mask: int = 0xFF


def _terminal_score(board: Board, side: int, ply: int) -> int | None:
    if board.winner == 0:
        return None
    if board.winner == side:
        return INF - ply
    return -INF + ply


def _rootbonus(board: Board, x: int, y: int) -> int:
    is_corner = False
    half_corner = 0
    for xx in range(board.size):
        for yy in range(board.size):
            if board.at(xx, yy) == 0:
                continue
            cur_height = min(xx, yy, board.size - 1 - xx, board.size - 1 - yy)
            if cur_height <= 2:
                if cur_height == 2:
                    half_corner += 1
                    if half_corner >= 2:
                        is_corner = True
                        break
                else:
                    is_corner = True
                    break
        if is_corner:
            break

    height = min(x, y, board.size - 1 - x, board.size - 1 - y)
    if is_corner:
        bonus = 0.0
        height_score = (4.0, 3.0, 2.0, 1.0)
        if height <= 3:
            bonus += height_score[height]
        countall_list = (0.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
        countall = 0
        for xx in range(x - 1, x + 2):
            for yy in range(y - 1, y + 2):
                if 0 <= xx < board.size and 0 <= yy < board.size:
                    if board.at(xx, yy) != 0:
                        countall += 1
                else:
                    countall += 1
        bonus += countall_list[min(countall, len(countall_list) - 1)] * 0.7
        return int(round(bonus))

    if height <= 3:
        return (8, 4, 2, 1)[height]
    return 0


class AlphaBetaSearcher:
    def __init__(self, config: EngineConfig, tt: TranspositionTable | None = None) -> None:
        self.config = config
        self.tt = tt or TranspositionTable()
        self.vcf = VCFSearcher()

    @staticmethod
    def _nonroot_vcf_depth(depth: float, root_depth: float) -> int:
        return int(depth + 6 - 2 * root_depth)

    def search(
        self,
        board: Board,
        caches: EvalCaches,
        side: int,
        depth: float,
        alpha: int,
        beta: int,
        wide: int,
        *,
        opo: int = 0,
        ply: int = 0,
        stats: SearchStats | None = None,
        root: bool = False,
        root_allowed_moves: set[int] | None = None,
        downf: int = 0,
        root_depth: float | None = None,
        priority_base: int | None = None,
    ) -> tuple[int, int]:
        if root_depth is None:
            root_depth = depth
        if priority_base is None:
            priority_base = board.move_count
        hash_depth = int(depth)
        original_beta = beta
        if stats is None:
            stats = SearchStats()
        next_node = stats.nodes + 1
        if stats.node_limit is not None and stats.nodes >= stats.node_limit:
            stats.stop = True
            return 0, -1
        if stats.deadline_s is not None and (
            next_node == 1 or (next_node & stats.time_check_mask) == 0
        ) and time.perf_counter() >= stats.deadline_s:
            stats.stop = True
            return 0, -1
        stats.nodes = next_node

        terminal = _terminal_score(board, side, ply)
        if terminal is not None:
            return terminal, -1

        probe = self.tt.probe(board.zobrist_key, hash_depth, alpha, beta)
        if _DEBUG_TT_KEY and board.zobrist_key == _DEBUG_TT_KEY:
            print(
                "DBG key probe",
                {
                    "depth": depth,
                    "hash_depth": hash_depth,
                    "alpha": alpha,
                    "beta": beta,
                    "opo": opo,
                    "ply": ply,
                    "root": root,
                    "downf": downf,
                    "probe": probe,
                },
            )
        if probe.hit and probe.value is not None:
            return probe.value, probe.best_move
        if probe.has_window and not root:
            alpha = max(alpha, probe.window_alpha)
            beta = min(beta, probe.window_beta)

        if depth <= 0:
            # Classic leaf nodes use `vv = -value(c, opo)` with
            # `c = bmove % 2 ? 1 : -1`, i.e. evaluate from the opponent-color
            # perspective and negate back to the side-to-move score.
            score = int(-evaluate_board(board, caches, -side, opo, self.config))
            if score >= WIN:
                score = INF - ply
            elif score <= -WIN:
                score = -INF + ply
            self.tt.store(
                TTEntry(
                    key=board.zobrist_key,
                    value=score,
                    flag=HASHF_EXACT,
                    depth=0,
                    priority=priority_base * 10,
                    best_move=-1,
                )
            )
            return score, -1

        generated = generate_candidates(
            board,
            caches,
            side,
            self.config,
            wide=wide,
            root_allowed_moves=root_allowed_moves if root else None,
            preferred_move=probe.best_move,
            preserve_scan_order=root,
        )
        if root:
            ordered = order_candidates_root_classic(board, generated.candidates, side)
        else:
            ordered = order_candidates(board, generated.candidates, side, probe.best_move)
        if generated.win_priority and ordered:
            return INF, ordered[0].move
        if self.config.runtime.compute_vcf and self.config.runtime.nonroot_vcf and not root:
            nonroot_vcf_depth = self._nonroot_vcf_depth(depth, root_depth)
            if nonroot_vcf_depth > 0 and self.vcf.search(board, -side, nonroot_vcf_depth).found:
                filtered: list = []
                for candidate in ordered:
                    trial = board.copy()
                    trial.side_to_move = side
                    trial.play(candidate.move, side)
                    if not self.vcf.search(trial, -side, nonroot_vcf_depth).found:
                        filtered.append(candidate)
                ordered = tuple(filtered)
        if not generated.win_priority and not generated.single_forcing:
            ordered = ordered[:wide]
        if not ordered:
            return -INF - 1, -1

        current = -INF - 1
        best_move = -1
        original_alpha = alpha
        hash_flag = HASHF_ALPHA
        found_pv = False
        child_wide = min((wide * self.config.root_search.ratio_num) // self.config.root_search.ratio_den + 1, wide)
        case_count = len(ordered)

        running_downf = downf
        for index, candidate in enumerate(ordered):
            snapshot = caches.snapshot()
            board.play(candidate.move, side)
            value_wide_compute(board, caches)
            running_downf += index
            local_downf = running_downf
            depthdown = max(
                0.0,
                1.0
                - self.config.search.extend_ratio
                + self.config.search.extend_ratio * log(float(max(case_count, 1))) / log(float(max(wide, 2))),
            )
            net = 0
            if local_downf >= 15:
                net = local_downf // 15
                depthdown += net
                local_downf %= 15
            running_downf = local_downf

            atdown = 0
            if candidate.self_attack == 4:
                atdown = int(self.config.search.atdown4)
            elif candidate.self_attack == 3:
                atdown = int(self.config.search.atdown3)
            if root:
                x, y = board.move_history[-1].move % board.size, board.move_history[-1].move // board.size
                atdown += _rootbonus(board, x, y)

            attempt_depth = depth - depthdown
            score = 0
            while True:
                if found_pv:
                    score, _ = self.search(
                        board,
                        caches,
                        -side,
                        attempt_depth,
                        -(alpha + atdown) - 1,
                        -(alpha + atdown),
                        child_wide,
                        opo=1 - opo,
                        ply=ply + 1,
                        stats=stats,
                        downf=local_downf,
                        root_depth=root_depth,
                        priority_base=priority_base,
                    )
                    if stats.stop:
                        break
                    score = -atdown - score
                    if alpha < score < beta:
                        score, _ = self.search(
                            board,
                            caches,
                            -side,
                            attempt_depth,
                            -(beta + atdown),
                            -(alpha + atdown),
                            child_wide,
                            opo=1 - opo,
                            ply=ply + 1,
                            stats=stats,
                            downf=local_downf,
                            root_depth=root_depth,
                            priority_base=priority_base,
                        )
                        if stats.stop:
                            break
                        score = -atdown - score
                else:
                    score, _ = self.search(
                        board,
                        caches,
                        -side,
                        attempt_depth,
                        -(beta + atdown),
                        -(alpha + atdown),
                        child_wide,
                        opo=1 - opo,
                        ply=ply + 1,
                        stats=stats,
                        downf=local_downf,
                        root_depth=root_depth,
                        priority_base=priority_base,
                    )
                    if stats.stop:
                        break
                    score = -atdown - score
                if score >= WIN:
                    break
                if score > alpha and score > current and net > 0:
                    attempt_depth += net
                    net = 0
                    continue
                break

            board.undo()
            caches.restore_snapshot(snapshot)
            if stats.stop:
                break

            if _DEBUG_ROOT_KEY and root and board.zobrist_key == _DEBUG_ROOT_KEY:
                print(
                    "DBG root child",
                    {
                        "depth": depth,
                        "move": (candidate.move % board.size, candidate.move // board.size),
                        "score": score,
                        "alpha": alpha,
                        "current": current,
                        "downf": local_downf,
                        "case_index": index,
                    },
                )
            if _DEBUG_NODE_KEY and board.zobrist_key == _DEBUG_NODE_KEY:
                print(
                    "DBG node child",
                    {
                        "board_key": board.zobrist_key,
                        "depth": depth,
                        "root": root,
                        "ply": ply,
                        "move": (candidate.move % board.size, candidate.move // board.size),
                        "score": score,
                        "alpha": alpha,
                        "current": current,
                        "downf": local_downf,
                        "case_index": index,
                        "history": [(m.move % board.size, m.move // board.size) for m in board.move_history[-8:]],
                    },
                )

            if score > current:
                current = score
            if score > alpha:
                alpha = score
                best_move = candidate.move
                hash_flag = HASHF_EXACT
                found_pv = True
            if root and score >= WIN:
                break
            if alpha >= beta:
                hash_flag = HASHF_BETA
                break

        if current <= original_alpha and hash_flag != HASHF_BETA:
            hash_flag = HASHF_ALPHA

        if stats.stop:
            return current, best_move

        store_depth = hash_depth
        if (current >= WIN and current > original_alpha) or (current <= -WIN and current < original_beta):
            hash_flag = HASHF_EXACT
            store_depth += 10

        self.tt.store(
            TTEntry(
                key=board.zobrist_key,
                value=current,
                flag=hash_flag,
                depth=store_depth,
                priority=priority_base * 10 + hash_depth,
                best_move=best_move,
            )
        )
        if _DEBUG_TT_KEY and board.zobrist_key == _DEBUG_TT_KEY:
            print(
                "DBG key store",
                {
                    "depth": depth,
                    "hash_depth": hash_depth,
                    "alpha0": original_alpha,
                    "beta0": beta,
                    "opo": opo,
                    "ply": ply,
                    "root": root,
                    "downf": downf,
                    "value": current,
                    "flag": hash_flag,
                    "best_move": best_move,
                },
            )
        return current, best_move
