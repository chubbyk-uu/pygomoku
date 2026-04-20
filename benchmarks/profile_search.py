"""Profile a fixed search scenario and print the hottest functions."""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pygomoku.board import Board, xy_to_move
from pygomoku.config import load_default_config
from pygomoku.search.root import RootSearcher, SearchLimits


def build_midgame_board() -> Board:
    board = Board()
    moves = [
        (7, 7), (8, 7),
        (7, 8), (8, 8),
        (6, 7), (9, 7),
        (6, 8), (9, 8),
        (5, 7), (10, 7),
        (5, 8), (10, 8),
    ]
    for x, y in moves:
        board.play(xy_to_move(x, y))
    return board


def run_search(depth: int, width: int) -> None:
    board = build_midgame_board()
    searcher = RootSearcher(load_default_config())
    searcher.search(board, SearchLimits(max_depth=depth, root_width=width))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--width", type=int, default=12)
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    profiler = cProfile.Profile()
    profiler.enable()
    run_search(args.depth, args.width)
    profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).sort_stats("cumtime")
    stats.print_stats(args.top)
    print(stream.getvalue().rstrip())


if __name__ == "__main__":
    main()
