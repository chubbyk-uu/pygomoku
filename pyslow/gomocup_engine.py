"""Command-line Gomocup engine entrypoint."""

from __future__ import annotations

import sys

from pyslow.protocol.gomocup import GomocupProtocol
from pyslow.search.root import SearchLimits

DEFAULT_DEPTH = 5
DEFAULT_WIDTH = 15


def main() -> None:
    protocol = GomocupProtocol(search_limits=SearchLimits(max_depth=DEFAULT_DEPTH, root_width=DEFAULT_WIDTH))
    for line in sys.stdin:
        responses = protocol.handle_line(line)
        for response in responses:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
        if protocol.ended:
            break


if __name__ == "__main__":
    main()
