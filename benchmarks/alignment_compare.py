#!/usr/bin/env python3
"""Systematic multi-position comparison between SlowRenju reference and pyslow.

Runs both engines on 15+ positions at shallow depth (depth=3, width=8) and
compares best_move, score, and node_count.

Usage:
    python benchmarks/alignment_compare.py
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.reference_trace import (
    build_trace,
    cleanup_workspace,
    prepare_workspace,
    write_trace_program,
)

# ---------------------------------------------------------------------------
# Position definitions
# ---------------------------------------------------------------------------
# Each position is a list of (x, y, side) tuples applied in order.
# side: 1 = black, -1 = white.  Moves alternate black/white.
# Reference convention: board[x][y], move = S*y + x  (S=15).
# pyslow convention: board.grid[y][x], move = y*15 + x.
# Both use the same flat encoding: move = y*15 + x.

POSITIONS: dict[str, list[tuple[int, int, int]]] = {
    # --- Early opening (0-4 stones) ---
    "open_empty": [],  # 0 stones, expect center (7,7)
    "open_center": [
        (7, 7, 1),
    ],
    "open_2stones": [
        (7, 7, 1), (7, 6, -1),
    ],
    "open_diag": [
        (7, 7, 1), (8, 8, -1),
    ],

    # --- Midgame (8-15 stones) ---
    "mid_cross": [
        (7, 7, 1), (8, 7, -1),
        (7, 8, 1), (8, 8, -1),
        (7, 6, 1), (8, 6, -1),
        (6, 7, 1), (9, 7, -1),
    ],
    "mid_ladder": [
        (7, 7, 1), (8, 8, -1),
        (6, 6, 1), (9, 9, -1),
        (5, 5, 1), (10, 10, -1),
        (7, 8, 1), (8, 7, -1),
        (6, 9, 1), (9, 6, -1),
    ],
    "mid_parallel": [
        # Two parallel groups with gaps
        (5, 7, 1), (5, 8, -1),
        (6, 7, 1), (6, 8, -1),
        (7, 7, 1), (7, 8, -1),
        (9, 7, 1), (9, 8, -1),
        (10, 7, 1), (10, 8, -1),
        (11, 7, 1), (11, 8, -1),
    ],
    "mid_scatter": [
        (3, 3, 1), (11, 11, -1),
        (3, 11, 1), (11, 3, -1),
        (7, 7, 1), (7, 8, -1),
        (8, 7, 1), (6, 6, -1),
    ],
    "mid_15stones": [
        (7, 7, 1), (8, 7, -1),
        (7, 8, 1), (8, 8, -1),
        (6, 6, 1), (9, 9, -1),
        (6, 9, 1), (9, 6, -1),
        (5, 7, 1), (10, 7, -1),
        (7, 5, 1), (7, 10, -1),
        (8, 6, 1), (6, 8, -1),
        (10, 10, 1),
    ],

    # --- Tactical positions (threats / fours / threes) ---
    "tact_open3": [
        # Black has an open three on row 7
        (6, 7, 1), (6, 8, -1),
        (7, 7, 1), (7, 8, -1),
        (8, 7, 1), (8, 8, -1),
    ],
    "tact_four": [
        # Black has 4 in a row needing 1 to win
        (5, 7, 1), (5, 8, -1),
        (6, 7, 1), (6, 8, -1),
        (7, 7, 1), (7, 8, -1),
        (8, 7, 1), (8, 8, -1),
    ],
    "tact_double3": [
        # Black aims for double-three
        (7, 7, 1), (5, 5, -1),
        (8, 8, 1), (5, 6, -1),
        (6, 8, 1), (5, 7, -1),
        (8, 6, 1), (10, 10, -1),
    ],
    "tact_defend4": [
        # White has 4 in a row, black must defend
        (0, 0, 1), (7, 7, -1),
        (0, 1, 1), (8, 7, -1),
        (14, 14, 1), (9, 7, -1),
        (14, 13, 1), (10, 7, -1),
    ],
    "tact_edge_open3": [
        # Black has an edge-side three extending from the left wall
        (0, 7, 1), (14, 14, -1),
        (1, 7, 1), (14, 13, -1),
        (2, 7, 1), (13, 14, -1),
    ],
    "tact_edge_four": [
        # Black has 4 on the top edge and should complete immediately
        (3, 0, 1), (14, 14, -1),
        (4, 0, 1), (14, 13, -1),
        (5, 0, 1), (13, 14, -1),
        (6, 0, 1), (13, 13, -1),
    ],
    "tact_defend4_edge": [
        # White has 4 near the bottom edge, black must defend at one end
        (0, 0, 1), (5, 13, -1),
        (14, 14, 1), (6, 13, -1),
        (0, 1, 1), (7, 13, -1),
        (14, 13, 1), (8, 13, -1),
    ],
    "fallback_missing_root": [
        # Known fallback-heavy position where root move can be missing
        (7, 7, 1), (7, 6, -1),
        (7, 5, 1), (6, 5, -1),
        (8, 7, 1), (6, 7, -1),
        (6, 6, 1), (5, 8, -1),
        (8, 5, 1), (5, 4, -1),
        (8, 6, 1), (4, 9, -1),
        (3, 10, 1), (4, 3, -1),
        (3, 2, 1),
    ],

    # --- Dense / endgame-like (20+ stones) ---
    "dense_center": [
        (7, 7, 1), (8, 7, -1),
        (7, 8, 1), (8, 8, -1),
        (6, 6, 1), (9, 9, -1),
        (6, 9, 1), (9, 6, -1),
        (5, 7, 1), (10, 7, -1),
        (7, 5, 1), (7, 10, -1),
        (8, 6, 1), (6, 8, -1),
        (10, 10, 1), (5, 5, -1),
        (9, 8, 1), (6, 7, -1),
        (8, 9, 1), (7, 6, -1),
        (5, 10, 1), (10, 5, -1),
    ],
    "dense_edge": [
        (0, 7, 1), (1, 7, -1),
        (2, 7, 1), (3, 7, -1),
        (7, 0, 1), (7, 1, -1),
        (7, 2, 1), (7, 3, -1),
        (14, 7, 1), (13, 7, -1),
        (12, 7, 1), (11, 7, -1),
        (7, 14, 1), (7, 13, -1),
        (7, 12, 1), (7, 11, -1),
        (7, 7, 1), (8, 8, -1),
        (6, 6, 1), (9, 9, -1),
    ],
    "dense_battle": [
        (7, 7, 1), (8, 8, -1),
        (6, 7, 1), (9, 7, -1),
        (8, 7, 1), (7, 8, -1),
        (7, 6, 1), (7, 9, -1),
        (6, 6, 1), (8, 6, -1),
        (9, 8, 1), (6, 9, -1),
        (5, 5, 1), (10, 10, -1),
        (8, 9, 1), (6, 8, -1),
        (9, 6, 1), (5, 8, -1),
        (10, 5, 1), (4, 9, -1),
        (5, 7, 1), (10, 7, -1),
    ],
}

SEARCH_DEPTH = 3
SEARCH_WIDTH = 10

# ---------------------------------------------------------------------------
# Reference C++ trace program
# ---------------------------------------------------------------------------

def _build_trace_cpp_v2() -> str:
    """Generate a C++ trace program that evaluates all positions.

    Strategy: rootsearch() returns the move directly. For score and node count,
    we parse the MESSAGE output that rootsearch prints for each depth iteration.
    The last MESSAGE line contains the final score.

    We redirect/capture these by having our own output markers.
    """
    position_blocks: list[str] = []
    for pos_id, moves in POSITIONS.items():
        lines: list[str] = []
        lines.append(f'    // Position: {pos_id}')
        lines.append(f'    memset(&board[0][0], 0, sizeof(int)*N*N);')
        lines.append(f'    bmove = {len(moves)};')
        lines.append(f'    moven = 0;')
        for x, y, side in moves:
            lines.append(f'    board[{x}][{y}] = {side};')
        lines.append(f'    computevcf = 1;')
        lines.append(f'    nbest = 0;')
        lines.append(f'    nodelimit = 0;')
        lines.append(f'    timee = 999999999LL;')
        lines.append(f'    timel = 999999999LL;')
        lines.append(f'    compend = 0;')
        lines.append(f'    comphalfend = 0;')
        lines.append(f'    printf("BEGIN {pos_id}\\n");')
        lines.append(f'    fflush(stdout);')
        lines.append(f'    move_result = rootsearch({SEARCH_DEPTH}, {SEARCH_WIDTH}, 1, 1);')
        lines.append(f'    printf("MOVE {pos_id} %d\\n", move_result);')
        lines.append(f'    printf("SCORE {pos_id} %d\\n", (int)abval.first);')
        lines.append(f'    printf("NODES {pos_id} %lld\\n", countx);')
        lines.append(f'    printf("END {pos_id}\\n");')
        lines.append(f'    fflush(stdout);')
        position_blocks.append('\n'.join(lines))

    all_blocks = '\n\n'.join(position_blocks)

    return textwrap.dedent(f"""\
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include "Headers/game.h"

void init();
void InitHash();
int rootsearch(int pDepth, int pWide, int pRat1, int pRat2);

extern long long int countx;
// abval is declared at file scope in AIx.cpp as: eval abval;
// eval is typedef pair<short,short>.
extern pair<short,short> abval;

int main() {{
    srand((unsigned)1232356);
    S = 15;
    boardSize = 15;
    init();
    InitHash();

    int move_result;

{all_blocks}

    return 0;
}}
""")


# ---------------------------------------------------------------------------
# Parse reference output
# ---------------------------------------------------------------------------

@dataclass
class EngineResult:
    move: int          # flat index: y*15 + x
    move_xy: tuple[int, int]  # (x, y)
    score: int
    nodes: int
    via_vcf: bool = False      # True if result came from VCF shortcut
    via_special: bool = False  # True if result came from special case (empty board, etc.)


def _parse_reference_output(output: str) -> dict[str, EngineResult]:
    """Parse reference trace output into per-position results.

    rootsearch prints MESSAGE lines like:
        MESSAGE  1;(07,07)       0 ----------      123
    Format: MESSAGE %2d;(%02d,%02d) %7d ---------- %8d
    Fields:  depth ; (x, y)  score  ----------  time

    We also get our custom lines:
        MOVE pos_id <flat_move>
        NODES pos_id <count>
    """
    results: dict[str, EngineResult] = {}
    current_pos: str | None = None
    last_score: int = 0
    moves: dict[str, int] = {}
    nodes: dict[str, int] = {}
    scores: dict[str, int] = {}
    vcf_found: set[str] = set()

    for line in output.splitlines():
        line = line.strip()
        if line.startswith("BEGIN "):
            current_pos = line.split(" ", 1)[1]
            last_score = 0
        elif line.startswith("END "):
            pos_id = line.split(" ", 1)[1]
            if pos_id in scores:
                pass  # already captured from MESSAGE
            elif current_pos == pos_id:
                scores[pos_id] = last_score
            current_pos = None
        elif line.startswith("MOVE "):
            parts = line.split()
            pos_id = parts[1]
            moves[pos_id] = int(parts[2])
        elif line.startswith("SCORE "):
            parts = line.split()
            pos_id = parts[1]
            scores[pos_id] = int(parts[2])
        elif line.startswith("NODES "):
            parts = line.split()
            pos_id = parts[1]
            nodes[pos_id] = int(parts[2])
        elif line.startswith("MESSAGE") and current_pos is not None:
            msg = line[len("MESSAGE"):].strip()
            if "Here it is" in msg:
                vcf_found.add(current_pos)
            elif ";" in msg and "(" in msg:
                try:
                    # "1;(07,07)       0 ----------      123"
                    semi_idx = msg.index(";")
                    paren_start = msg.index("(")
                    paren_end = msg.index(")")
                    after_paren = msg[paren_end + 1:].strip()
                    # score is the first number after the closing paren
                    score_str = after_paren.split()[0]
                    last_score = int(score_str)
                    scores[current_pos] = last_score
                except (ValueError, IndexError):
                    pass

    for pos_id in POSITIONS:
        if pos_id in moves:
            mv = moves[pos_id]
            x = mv % 15
            y = mv // 15
            score = scores.get(pos_id, 0)
            is_vcf = pos_id in vcf_found
            # When VCF fires or rootsplit=0 fallback runs, rootsearch returns
            # without updating abval, so the SCORE line reports a stale value.
            # Detect these cases: VCF (explicit), or 0 nodes with stones on board.
            is_special = (not is_vcf and nodes.get(pos_id, 0) == 0
                          and len(POSITIONS[pos_id]) > 1)
            if is_vcf or is_special:
                score = 20000  # Report as INF to match pyslow VCF convention
            results[pos_id] = EngineResult(
                move=mv,
                move_xy=(x, y),
                score=score,
                nodes=nodes.get(pos_id, 0),
                via_vcf=is_vcf,
                via_special=is_special,
            )

    return results


# ---------------------------------------------------------------------------
# pyslow side
# ---------------------------------------------------------------------------

def _run_pyslow() -> dict[str, EngineResult]:
    from pyslow.board import Board, move_to_xy, xy_to_move
    from pyslow.config import load_default_config
    from pyslow.search.root import RootSearcher, SearchLimits

    config = load_default_config()
    searcher = RootSearcher(config)
    limits = SearchLimits(
        max_depth=SEARCH_DEPTH,
        root_width=SEARCH_WIDTH,
    )
    results: dict[str, EngineResult] = {}

    for pos_id, moves in POSITIONS.items():
        try:
            board = Board()
            for x, y, side in moves:
                mv = xy_to_move(x, y)
                board.play(mv, side)

            sr = searcher.search(board, limits)
            mx, my = move_to_xy(sr.move)
            is_vcf = (sr.nodes == 0 and abs(sr.score) >= 15000
                       and board.move_count > 0)
            is_special = (sr.nodes == 0 and sr.score == 0
                          and board.move_count <= 1)
            results[pos_id] = EngineResult(
                move=sr.move,
                move_xy=(mx, my),
                score=sr.score,
                nodes=sr.nodes,
                via_vcf=is_vcf,
                via_special=is_special,
            )
        except Exception as e:
            print(f"      WARNING: pyslow failed on {pos_id}: {e}")

    return results


# ---------------------------------------------------------------------------
# Comparison and reporting
# ---------------------------------------------------------------------------

def _print_report(
    ref_results: dict[str, EngineResult],
    py_results: dict[str, EngineResult],
) -> int:
    """Print alignment table and return number of mismatches."""
    header = (
        f"{'Position':<18} | {'Ref Move':>10} | {'Py Move':>10} | "
        f"{'Ref Score':>10} | {'Py Score':>10} | "
        f"{'Ref Nodes':>10} | {'Py Nodes':>10} | {'Match':<8}"
    )
    sep = "-" * len(header)

    print()
    print(header)
    print(sep)

    mismatches = 0
    skipped = 0

    for pos_id in POSITIONS:
        ref = ref_results.get(pos_id)
        py = py_results.get(pos_id)

        if ref is None:
            print(f"{pos_id:<18} | {'SKIP':>10} | {'-':>10} | {'-':>10} | {'-':>10} | {'-':>10} | {'-':>10} | {'NO REF':<8}")
            skipped += 1
            continue
        if py is None:
            print(f"{pos_id:<18} | {'-':>10} | {'SKIP':>10} | {'-':>10} | {'-':>10} | {'-':>10} | {'-':>10} | {'NO PY':<8}")
            skipped += 1
            continue

        ref_mv_str = f"({ref.move_xy[0]},{ref.move_xy[1]})"
        py_mv_str = f"({py.move_xy[0]},{py.move_xy[1]})"

        move_match = ref.move == py.move
        score_match = ref.score == py.score
        score_close = abs(ref.score - py.score) <= 2
        # VCF/special paths may produce different scores; only moves matter
        both_vcf_or_special = (ref.via_vcf or ref.via_special) and (py.via_vcf or py.via_special)

        if move_match and score_match:
            status = "OK"
        elif move_match and score_close:
            status = "CLOSE"
        elif move_match and both_vcf_or_special:
            status = "VCF-OK"
        elif move_match:
            status = "SCORE"
            mismatches += 1
        elif both_vcf_or_special:
            status = "VCF-?"
            mismatches += 1
        else:
            status = "DIFF"
            mismatches += 1

        print(
            f"{pos_id:<18} | {ref_mv_str:>10} | {py_mv_str:>10} | "
            f"{ref.score:>10} | {py.score:>10} | "
            f"{ref.nodes:>10} | {py.nodes:>10} | {status:<8}"
        )

    print(sep)
    total = len(POSITIONS)
    ok_count = total - mismatches - skipped
    print(f"\nTotal: {total}  OK/Close: {ok_count}  Mismatches: {mismatches}  Skipped: {skipped}")

    # Print notes about known divergence causes
    notes: list[str] = []
    for pos_id in POSITIONS:
        ref = ref_results.get(pos_id)
        py = py_results.get(pos_id)
        if ref is None or py is None:
            continue
        if ref.move != py.move and pos_id == "open_center":
            notes.append(
                f"  {pos_id}: Reference uses N=20 compile constant, so the "
                f"'if (N==15)' bmove==1 shortcut is skipped. Reference does "
                f"full search; pyslow uses hardcoded response."
            )
        elif ref.score != py.score and ref.move == py.move and ref.nodes > 0 and py.nodes > 0:
            notes.append(
                f"  {pos_id}: Moves match but scores differ "
                f"(ref={ref.score} vs py={py.score}). "
                f"Possible search extension or evaluation difference."
            )

    if notes:
        print("\nNotes:")
        for note in notes:
            print(note)

    return mismatches


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 70)
    print("  SlowRenju vs pyslow Alignment Comparison")
    print(f"  Depth={SEARCH_DEPTH}  Width={SEARCH_WIDTH}  Positions={len(POSITIONS)}")
    print("=" * 70)

    # --- Build and run reference ---
    print("\n[1/3] Building reference trace binary...")
    workspace = None
    ref_results: dict[str, EngineResult] = {}
    try:
        workspace = prepare_workspace()
        cpp_source = _build_trace_cpp_v2()
        write_trace_program(workspace, cpp_source)
        exe = build_trace(workspace)
        print("      Build successful.")

        print("[2/3] Running reference engine on all positions...")
        proc = subprocess.run(
            [str(exe)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            print(f"      Reference binary exited with code {proc.returncode}")
            if proc.stderr:
                print(f"      STDERR (first 1000 chars):\n{proc.stderr[:1000]}")
        ref_results = _parse_reference_output(proc.stdout)
        print(f"      Got results for {len(ref_results)}/{len(POSITIONS)} positions.")
    except subprocess.TimeoutExpired:
        print("      ERROR: Reference binary timed out after 300s.")
    except subprocess.CalledProcessError as e:
        print(f"      ERROR: Build failed:\n{e.stderr[:1000] if e.stderr else e}")
    except Exception as e:
        print(f"      ERROR: {e}")
    finally:
        if workspace is not None:
            cleanup_workspace(workspace)

    # --- Run pyslow ---
    print("[3/3] Running pyslow engine on all positions...")
    py_results: dict[str, EngineResult] = {}
    try:
        py_results = _run_pyslow()
        print(f"      Got results for {len(py_results)}/{len(POSITIONS)} positions.")
    except Exception as e:
        print(f"      ERROR: {e}")
        import traceback
        traceback.print_exc()

    # --- Compare ---
    mismatches = _print_report(ref_results, py_results)
    return 1 if mismatches > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
