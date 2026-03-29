"""Command-line Gomocup engine entrypoint."""

from __future__ import annotations

import argparse
import sys

from pygomoku.protocol.gomocup import GomocupProtocol
from pygomoku.search.root import SearchLimits

DEFAULT_DEPTH = 5
DEFAULT_WIDTH = 20


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    args = parser.parse_args()

    protocol = GomocupProtocol(
        search_limits=SearchLimits(max_depth=args.depth, root_width=args.width),
    )
    for line in sys.stdin:
        responses = protocol.handle_line(line)
        for response in responses:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
        if protocol.ended:
            break


if __name__ == "__main__":
    main()
