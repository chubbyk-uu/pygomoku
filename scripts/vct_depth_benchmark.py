"""VCT depth benchmark: find minimum required depth and measure timing."""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pygomoku.board import Board, xy_to_move
from pygomoku.threats.vcf import VCFSearcher
from pygomoku.threats.vct import VCTSearcher


def _make_board(*moves: tuple[int, int, int]) -> Board:
    board = Board()
    for x, y, side in moves:
        assert board.side_to_move == side, f"expected {side}, got {board.side_to_move} at ({x},{y})"
        board.play(xy_to_move(x, y), side)
    return board


def benchmark(name: str, board: Board, side: int = 1, max_depth: int = 8) -> None:
    vcf = VCFSearcher().search(board, side, 20)
    print(f"\n{'='*60}")
    print(f"Position: {name}")
    print(f"  VCF: found={vcf.found}")

    for depth in range(1, max_depth + 1):
        t0 = time.perf_counter()
        r = VCTSearcher().search(board, side, depth)
        elapsed = (time.perf_counter() - t0) * 1000
        marker = " ← FOUND" if r.found else ""
        print(f"  depth={depth}: found={r.found} solved={r.solved} {elapsed:6.1f}ms{marker}")
        if r.found or r.solved:
            break


# ---------------------------------------------------------------------------
# Position 1: classic dual-A3 (the existing test position)
# ---------------------------------------------------------------------------
pos_dual_a3 = _make_board(
    (6, 7,  1), (0, 0, -1),
    (8, 7,  1), (1, 3, -1),
    (7, 6,  1), (3, 1, -1),
    (7, 8,  1), (14, 14, -1),
)

# ---------------------------------------------------------------------------
# Position 2: B4 -> forced -> A4 (should require depth=2)
# ---------------------------------------------------------------------------
# Black horizontal triple (5,7)(6,7)(7,7), white blocks left (4,7)
# Black vertical pair (8,5)(8,6) — after B4(8,7) & forced W@(9,7),
# vertical (8,5)(8,6)(8,7) → play (8,8) → A4
pos_b4_a4 = _make_board(
    (5, 7,  1), (4, 7, -1),
    (6, 7,  1), (0,  0, -1),
    (7, 7,  1), (14, 0, -1),
    (8, 5,  1), (0, 14, -1),
    (8, 6,  1), (14,14, -1),
)

# ---------------------------------------------------------------------------
# Position 3: "B4 sealed, then A3 chain" — designed to need depth=4
# (B4 in direction-H sealed by forced reply, then B4 in direction-V sealed,
#  then a newly created A3 pair leads to A4 in direction-D)
#
# Black: horiz triple (5,7)(6,7)(7,7), white at (4,7)
#         vert triple (7,9)(7,10)(7,11), white at (7,12) and (7,8)
#         diagonal pair (9,5)(10,4) — far away, contributing diagonal threats
# Idea: after horiz B4 → forced W@(9,7); vert B4 → forced W@(7,6)? ...
# Let's try: vert triple w/ one end blocked forces toward diagonal A4.
# ---------------------------------------------------------------------------
# Actually let's just try a position where MANY threats exist and see what depth is needed:
pos_complex = _make_board(
    # Black has threats in horizontal and vertical but not combined yet
    (7, 7,  1), (0,  0, -1),
    (6, 7,  1), (14, 0, -1),
    (8, 7,  1), (0, 14, -1),
    (7, 6,  1), (14,14, -1),
    (7, 8,  1), (0,  2, -1),  # vertical pair (7,6)(7,7)(7,8) — but (7,7) is center
    (5, 6,  1), (14, 2, -1),  # diagonal seeds
    (9, 8,  1), (0,  4, -1),
)

# ---------------------------------------------------------------------------
# Position 4: "two B4 buildups requiring depth=4"
# Black has two separate B4-capable formations in different directions.
# After each B4 the defender is forced, but neither alone yields A4.
# After BOTH B4 sequences are played and defended, a NEW A4 appears
# from the combined patterns in a diagonal.
#
# Black: (5,7)(6,7)(7,7) horiz, white (4,7); (7,9)(7,10)(7,11) vert, white (7,12)
# Black: (9,9) — diagonal seed
# After horiz B4(8,7) → W@(9,7): board has (5-8,7) sealed left by (4,7) and right by (9,7)
# After vert  B4(7,8) → W@(7,6) (wait, W@(7,12) blocks bottom, so (7,8) extends up):
#   (7,8)(7,9)(7,10)(7,11) with (7,7)... (7,7) is black! So this is 5-in-col (7,7)-(7,11) = WIN5
# That's too easy. Need (7,7) to NOT be in vert column.
# ---------------------------------------------------------------------------

# Let's place vert triple in a different column:
# Black: (5,7)(6,7)(7,7) horiz with W(4,7); (9,5)(9,6)(9,7) vert with W(9,8)
# Both blocked on one side. Do they combine?
pos_two_b4 = _make_board(
    (5, 7,  1), (4, 7,  -1),
    (6, 7,  1), (9, 8,  -1),
    (7, 7,  1), (0,  0, -1),
    (9, 5,  1), (14, 0, -1),
    (9, 6,  1), (0, 14, -1),
    (9, 7,  1), (14,14, -1),
)

# ---------------------------------------------------------------------------
# Position 5: realistic mid-game position with multiple threats
# ---------------------------------------------------------------------------
pos_midgame = _make_board(
    (7, 7,  1), (7,  8, -1),
    (6, 6,  1), (8,  6, -1),
    (8, 8,  1), (6,  8, -1),
    (5, 5,  1), (9,  9, -1),
    (6, 7,  1), (8,  7, -1),
    (7, 6,  1), (7,  9, -1),
    (5, 7,  1), (9,  7, -1),
    (7, 5,  1), (7, 10, -1),
    (5, 9,  1), (9,  5, -1),
)

# ---------------------------------------------------------------------------
# Position 6: attempt at genuine depth=4
# Setup: two "broken" B4-chains that combine into dual-A3 only after 2 rounds
#
# Black: row 7 has (4,7)(5,7)(6,7) with white blocking right at (7,7)
#        col 10 has (10,4)(10,5)(10,6) with white blocking right at (10,7) - wait diff axis
#
# Actually: horizontal B4 in row 7: need (3,7)W and (8,7) open so playing creates b4
# Then separately: diagonal stones (5,5)(6,6) + future (7,7)... but (7,7)W blocks.
#
# Let me try: after horiz B4(8,7) forced W@(9,7),
# then diagonal A3: (6,6)(7,7)... (7,7)=W. Can't use.
#
# Final attempt: two completely separate B4 chains that "fork" via a distant diagonal
# ---------------------------------------------------------------------------
pos_depth4_attempt = _make_board(
    # Horizontal triple with left blocked
    (5, 7,  1), (4,  7, -1),
    (6, 7,  1), (0,  0, -1),
    (7, 7,  1), (14, 0, -1),
    # Vertical triple with top blocked
    (8, 5,  1), (8,  4, -1),
    (8, 6,  1), (0, 14, -1),
    # Diagonal seed
    (9, 8,  1), (14,14, -1),
    (10, 9, 1), (0,  2, -1),
)

if __name__ == "__main__":
    benchmark("Dual A3 (classic)", pos_dual_a3)
    benchmark("B4 → forced → A4", pos_b4_a4)
    benchmark("Complex (many threats)", pos_complex)
    benchmark("Two B4 builds", pos_two_b4)
    benchmark("Mid-game", pos_midgame)
    benchmark("Depth-4 attempt", pos_depth4_attempt)
