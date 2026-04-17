"""Run fixed-position search benchmarks for stable before/after comparisons."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pygomoku.board import Board, move_to_xy, xy_to_move
from pygomoku.config import load_default_config
from pygomoku.eval.global_eval import global_eval_backend_name
from pygomoku.eval.local import local_backend_name
from pygomoku.search.ordering import ordering_backend_name
from pygomoku.search.root import RootSearcher, SearchLimits


CASES: dict[str, list[tuple[int, int]]] = {
    "quiet4": [(7, 7), (7, 4), (8, 8), (6, 5)],
    "mid12": [(7, 7), (8, 7), (7, 8), (8, 8), (6, 7), (9, 7), (6, 8), (9, 8), (5, 7), (10, 7), (5, 8), (10, 8)],
}


def build_board(case_name: str) -> Board:
    board = Board()
    for x, y in CASES[case_name]:
        board.play(xy_to_move(x, y))
    return board


def run_case(case_name: str, depth: int, width: int, repeats: int) -> None:
    total_ms = 0.0
    total_nodes = 0
    last_result = None
    for _ in range(repeats):
        board = build_board(case_name)
        searcher = RootSearcher(load_default_config())
        start = time.perf_counter()
        result = searcher.search(board, SearchLimits(max_depth=depth, root_width=width))
        total_ms += (time.perf_counter() - start) * 1000.0
        total_nodes += result.nodes
        last_result = result

    assert last_result is not None
    avg_ms = total_ms / repeats
    avg_nodes = total_nodes / repeats
    print(
        f"case={case_name} depth={depth} width={width} repeats={repeats} "
        f"avg_ms={avg_ms:.2f} avg_nodes={avg_nodes:.1f} "
        f"move={move_to_xy(last_result.move)} score={last_result.score} depth_done={last_result.depth}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=sorted(CASES), default="quiet4")
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--width", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    print(
        f"backends global_eval={global_eval_backend_name()} "
        f"local={local_backend_name()} ordering={ordering_backend_name()}"
    )
    run_case(args.case, args.depth, args.width, args.repeats)


if __name__ == "__main__":
    main()
