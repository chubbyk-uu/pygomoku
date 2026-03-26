"""Run a small set of timing and profiling benchmarks for the current engine."""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pyslow.board import Board
from pyslow.config import load_default_config
from pyslow.search.root import RootSearcher, SearchLimits


def run_selfplay_case(depth: int, width: int, plies: int) -> tuple[float, int]:
    board = Board()
    searcher = RootSearcher(load_default_config())
    total_ms = 0.0
    total_nodes = 0
    for _ in range(plies):
        start = time.perf_counter()
        result = searcher.search(board, SearchLimits(max_depth=depth, root_width=width))
        total_ms += (time.perf_counter() - start) * 1000.0
        total_nodes += result.nodes
        board.play(result.move)
        if board.winner != 0:
            break
    return total_ms, total_nodes


def profile_midgame(depth: int, width: int, top: int) -> str:
    from benchmarks.profile_search import run_search

    profiler = cProfile.Profile()
    profiler.enable()
    run_search(depth, width)
    profiler.disable()

    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("cumtime").print_stats(top)
    return stream.getvalue().rstrip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args()

    cases = (
        (2, 8, 6),
        (3, 10, 6),
        (6, 10, 4),
    )
    print("timing")
    for depth, width, plies in cases:
        total_ms, total_nodes = run_selfplay_case(depth, width, plies)
        print(
            f"depth={depth} width={width} plies={plies} total_ms={total_ms:.2f} "
            f"avg_ms={total_ms / plies:.2f} total_nodes={total_nodes}"
        )

    print("\nprofile")
    print(profile_midgame(depth=2, width=12, top=args.top))


if __name__ == "__main__":
    main()
