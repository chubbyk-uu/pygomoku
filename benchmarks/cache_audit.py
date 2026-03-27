"""Audit cache copy and local-eval update behavior on representative searches."""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.profile_search import build_midgame_board
from pyslow.board import Board, move_to_xy
from pyslow.config import load_default_config
import pyslow.eval.caches as caches_mod
import pyslow.eval.global_eval as global_eval_mod
import pyslow.eval.local as local_mod
import pyslow.search.alphabeta as alphabeta_mod
from pyslow.search.root import RootSearcher, SearchLimits


@dataclass
class AuditStats:
    snapshot_calls: int = 0
    restore_calls: int = 0
    snapshot_ms: float = 0.0
    restore_ms: float = 0.0
    copy_counts: Counter[str] = field(default_factory=Counter)
    copy_ms: Counter[str] = field(default_factory=Counter)
    snapshot_callers: Counter[str] = field(default_factory=Counter)
    restore_callers: Counter[str] = field(default_factory=Counter)
    last5_calls: int = 0
    next43_calls: int = 0
    last5_ms: float = 0.0
    next43_ms: float = 0.0
    value_wide_calls: int = 0
    value_wide_ms: float = 0.0
    value_wide_changed_stones: Counter[int] = field(default_factory=Counter)
    value_wide_impacted_points: Counter[int] = field(default_factory=Counter)


def _caller_name() -> str:
    frame = sys._getframe(2)
    return f"{Path(frame.f_code.co_filename).name}:{frame.f_code.co_name}"


def _estimate_impacted_points(board: Board, shadow: list[list[int]]) -> int:
    size = board.size
    grid = board.grid
    ar = 4
    comp = [bytearray(size) for _ in range(size)]
    hflag = 1
    vflag = 2
    ddown = 4
    dup = 8

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
                    elif value != 0 and value != seen:
                        break
                    comp[fixed][yy] |= hflag
                seen = 0
                for yy in range(y - 1, max(-1, y - ar - 1), -1):
                    value = grid[yy][fixed]
                    if seen == 0:
                        seen = value
                    elif value != 0 and value != seen:
                        break
                    comp[fixed][yy] |= hflag

                fixed = y
                seen = 0
                for xx in range(x + 1, min(size, x + ar + 1)):
                    value = grid[fixed][xx]
                    if seen == 0:
                        seen = value
                    elif value != 0 and value != seen:
                        break
                    comp[xx][fixed] |= vflag
                seen = 0
                for xx in range(x - 1, max(-1, x - ar - 1), -1):
                    value = grid[fixed][xx]
                    if seen == 0:
                        seen = value
                    elif value != 0 and value != seen:
                        break
                    comp[xx][fixed] |= vflag

                seen = 0
                xx = x - 1
                yy = y + 1
                while xx >= 0 and yy < size and xx >= x - ar and yy <= y + ar:
                    value = grid[yy][xx]
                    if seen == 0:
                        seen = value
                    elif value != 0 and value != seen:
                        break
                    comp[xx][yy] |= ddown
                    xx -= 1
                    yy += 1

                seen = 0
                xx = x + 1
                yy = y - 1
                while xx < size and yy >= 0 and xx <= x + ar and yy >= y - ar:
                    value = grid[yy][xx]
                    if seen == 0:
                        seen = value
                    elif value != 0 and value != seen:
                        break
                    comp[xx][yy] |= ddown
                    xx += 1
                    yy -= 1

                seen = 0
                xx = x + 1
                yy = y + 1
                while xx < size and yy < size and xx <= x + ar and yy <= y + ar:
                    value = grid[yy][xx]
                    if seen == 0:
                        seen = value
                    elif value != 0 and value != seen:
                        break
                    comp[xx][yy] |= dup
                    xx += 1
                    yy += 1

                seen = 0
                xx = x - 1
                yy = y - 1
                while xx >= 0 and yy >= 0 and xx >= x - ar and yy >= y - ar:
                    value = grid[yy][xx]
                    if seen == 0:
                        seen = value
                    elif value != 0 and value != seen:
                        break
                    comp[xx][yy] |= dup
                    xx -= 1
                    yy -= 1

    return sum(1 for x in range(size) for y in range(size) if comp[x][y])


@contextmanager
def install_audit_hooks(stats: AuditStats):
    orig_copy_board = caches_mod._copy_board_shadow_any
    orig_copy_shape = caches_mod._copy_shape_cache_any
    orig_copy_value = caches_mod._copy_value_cache_any
    orig_snapshot = caches_mod.EvalCaches.snapshot
    orig_restore = caches_mod.EvalCaches.restore_snapshot
    orig_last5 = global_eval_mod._evaluate_last5_branch
    orig_next43 = global_eval_mod._evaluate_next43_branch
    orig_local_vw = local_mod.value_wide_compute
    orig_ab_vw = alphabeta_mod.value_wide_compute
    orig_ge_vw = global_eval_mod.value_wide_compute

    def wrap_copy(name: str, fn: Callable):
        def wrapped(arg):
            start = time.perf_counter()
            result = fn(arg)
            elapsed = (time.perf_counter() - start) * 1000.0
            stats.copy_counts[name] += 1
            stats.copy_ms[name] += elapsed
            return result
        return wrapped

    def snapshot_wrapped(self):
        start = time.perf_counter()
        result = orig_snapshot(self)
        elapsed = (time.perf_counter() - start) * 1000.0
        stats.snapshot_calls += 1
        stats.snapshot_ms += elapsed
        stats.snapshot_callers[_caller_name()] += 1
        return result

    def restore_wrapped(self, snapshot):
        start = time.perf_counter()
        result = orig_restore(self, snapshot)
        elapsed = (time.perf_counter() - start) * 1000.0
        stats.restore_calls += 1
        stats.restore_ms += elapsed
        stats.restore_callers[_caller_name()] += 1
        return result

    def last5_wrapped(board, caches, side, opo, config):
        start = time.perf_counter()
        result = orig_last5(board, caches, side, opo, config)
        stats.last5_calls += 1
        stats.last5_ms += (time.perf_counter() - start) * 1000.0
        return result

    def next43_wrapped(board, caches, side, config):
        start = time.perf_counter()
        result = orig_next43(board, caches, side, config)
        stats.next43_calls += 1
        stats.next43_ms += (time.perf_counter() - start) * 1000.0
        return result

    def value_wide_wrapped(board, caches):
        changed = sum(
            1
            for x in range(board.size)
            for y in range(board.size)
            if caches.board_shadow[x][y] != board.grid[y][x]
        )
        impacted = _estimate_impacted_points(board, caches.board_shadow)
        start = time.perf_counter()
        result = orig_local_vw(board, caches)
        elapsed = (time.perf_counter() - start) * 1000.0
        stats.value_wide_calls += 1
        stats.value_wide_ms += elapsed
        stats.value_wide_changed_stones[changed] += 1
        stats.value_wide_impacted_points[impacted] += 1
        return result

    caches_mod._copy_board_shadow_any = wrap_copy("board_shadow", orig_copy_board)
    caches_mod._copy_shape_cache_any = wrap_copy("shape_cache", orig_copy_shape)
    caches_mod._copy_value_cache_any = wrap_copy("value_or_attack", orig_copy_value)
    caches_mod.EvalCaches.snapshot = snapshot_wrapped
    caches_mod.EvalCaches.restore_snapshot = restore_wrapped
    global_eval_mod._evaluate_last5_branch = last5_wrapped
    global_eval_mod._evaluate_next43_branch = next43_wrapped
    local_mod.value_wide_compute = value_wide_wrapped
    alphabeta_mod.value_wide_compute = value_wide_wrapped
    global_eval_mod.value_wide_compute = value_wide_wrapped
    try:
        yield
    finally:
        caches_mod._copy_board_shadow_any = orig_copy_board
        caches_mod._copy_shape_cache_any = orig_copy_shape
        caches_mod._copy_value_cache_any = orig_copy_value
        caches_mod.EvalCaches.snapshot = orig_snapshot
        caches_mod.EvalCaches.restore_snapshot = orig_restore
        global_eval_mod._evaluate_last5_branch = orig_last5
        global_eval_mod._evaluate_next43_branch = orig_next43
        local_mod.value_wide_compute = orig_local_vw
        alphabeta_mod.value_wide_compute = orig_ab_vw
        global_eval_mod.value_wide_compute = orig_ge_vw


def _print_counter(label: str, counter: Counter[int] | Counter[str], top: int = 8) -> None:
    print(label)
    for key, value in counter.most_common(top):
        print(f"  {key}: {value}")


def run_midgame(depth: int, width: int) -> AuditStats:
    stats = AuditStats()
    with install_audit_hooks(stats):
        board = build_midgame_board()
        searcher = RootSearcher(load_default_config())
        searcher.search(board, SearchLimits(max_depth=depth, root_width=width))
    return stats


def run_selfplay(plies: int, depth: int, width: int) -> AuditStats:
    stats = AuditStats()
    with install_audit_hooks(stats):
        board = Board()
        searcher = RootSearcher(load_default_config())
        for _ in range(plies):
            result = searcher.search(board, SearchLimits(max_depth=depth, root_width=width))
            board.play(result.move)
            if board.winner != 0:
                break
    return stats


def print_report(name: str, stats: AuditStats) -> None:
    print(f"\n[{name}]")
    print(
        f"snapshot_calls={stats.snapshot_calls} snapshot_ms={stats.snapshot_ms:.2f} "
        f"restore_calls={stats.restore_calls} restore_ms={stats.restore_ms:.2f}"
    )
    print(
        f"value_wide_calls={stats.value_wide_calls} value_wide_ms={stats.value_wide_ms:.2f} "
        f"last5_calls={stats.last5_calls} last5_ms={stats.last5_ms:.2f} "
        f"next43_calls={stats.next43_calls} next43_ms={stats.next43_ms:.2f}"
    )
    if stats.snapshot_calls:
        print(f"avg_snapshot_ms={stats.snapshot_ms / stats.snapshot_calls:.4f}")
    if stats.restore_calls:
        print(f"avg_restore_ms={stats.restore_ms / stats.restore_calls:.4f}")
    if stats.value_wide_calls:
        print(f"avg_value_wide_ms={stats.value_wide_ms / stats.value_wide_calls:.4f}")
    _print_counter("copy_counts", stats.copy_counts)
    print("copy_ms")
    for key, value in stats.copy_ms.most_common():
        print(f"  {key}: {value:.2f}")
    _print_counter("snapshot_callers", stats.snapshot_callers)
    _print_counter("restore_callers", stats.restore_callers)
    _print_counter("value_wide_changed_stones", stats.value_wide_changed_stones)
    _print_counter("value_wide_impacted_points", stats.value_wide_impacted_points)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=5)
    parser.add_argument("--width", type=int, default=15)
    parser.add_argument("--plies", type=int, default=4)
    args = parser.parse_args()

    print(f"audit depth={args.depth} width={args.width} plies={args.plies}")
    print_report("midgame", run_midgame(args.depth, args.width))
    print_report("selfplay", run_selfplay(args.plies, args.depth, args.width))


if __name__ == "__main__":
    main()
