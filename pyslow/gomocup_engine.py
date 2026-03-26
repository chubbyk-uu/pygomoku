"""Command-line Gomocup engine entrypoint."""

from __future__ import annotations

import sys

from pyslow.protocol.gomocup import GomocupProtocol
from pyslow.search.root import SearchLimits


def main() -> None:
    protocol = GomocupProtocol(search_limits=SearchLimits(max_depth=3, root_width=10))
    for line in sys.stdin:
        responses = protocol.handle_line(line)
        for response in responses:
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
        if protocol.ended:
            break


if __name__ == "__main__":
    main()
