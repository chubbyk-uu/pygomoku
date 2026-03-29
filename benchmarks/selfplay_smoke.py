"""Run a short self-play smoke benchmark using the current root searcher."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pygomoku.board import Board, move_to_xy
from pygomoku.config import load_default_config
from pygomoku.search.root import RootSearcher, SearchLimits


def run_selfplay(plies: int, depth: int, width: int, node_limit: int | None) -> None:
    board = Board()
    searcher = RootSearcher(load_default_config())
    durations_ms: list[float] = []
    node_counts: list[int] = []

    print(f"selfplay start: plies={plies} depth={depth} width={width} node_limit={node_limit}")
    for ply in range(plies):
        start = time.perf_counter()
        result = searcher.search(
            board,
            SearchLimits(max_depth=depth, root_width=width, node_limit=node_limit),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        x, y = move_to_xy(result.move)
        print(
            f"ply={ply + 1:02d} side={board.side_to_move:+d} move=({x},{y}) "
            f"score={result.score} depth={result.depth} nodes={result.nodes} "
            f"time_ms={elapsed_ms:.2f}"
        )
        durations_ms.append(elapsed_ms)
        node_counts.append(result.nodes)
        board.play(result.move)
        if board.winner != 0:
            print(f"winner={board.winner:+d} after ply={ply + 1}")
            break

    if durations_ms:
        total_ms = sum(durations_ms)
        avg_ms = total_ms / len(durations_ms)
        total_nodes = sum(node_counts)
        avg_nodes = total_nodes / len(node_counts)
        print(
            f"summary: played={len(durations_ms)} total_ms={total_ms:.2f} "
            f"avg_ms={avg_ms:.2f} total_nodes={total_nodes} avg_nodes={avg_nodes:.1f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plies", type=int, default=6)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--width", type=int, default=8)
    parser.add_argument("--node-limit", type=int, default=None)
    args = parser.parse_args()
    run_selfplay(args.plies, args.depth, args.width, args.node_limit)


if __name__ == "__main__":
    main()
