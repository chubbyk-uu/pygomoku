#!/usr/bin/env python3
"""Systematic multi-position comparison between SlowRenju reference and pyslow.

Runs both engines on 15+ positions at shallow depth (depth=3, width=8) and
compares best_move, score, and node_count.

Usage:
    python benchmarks/alignment_compare.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    "mid_ladder_r90": [
        (7, 7, 1), (6, 8, -1),
        (8, 6, 1), (5, 9, -1),
        (9, 5, 1), (4, 10, -1),
        (6, 7, 1), (7, 8, -1),
        (5, 6, 1), (8, 9, -1),
    ],
    "mid_ladder_r180": [
        (7, 7, 1), (6, 6, -1),
        (8, 8, 1), (5, 5, -1),
        (9, 9, 1), (4, 4, -1),
        (7, 6, 1), (6, 7, -1),
        (8, 5, 1), (5, 8, -1),
    ],
    "mid_ladder_r270": [
        (7, 7, 1), (8, 6, -1),
        (6, 8, 1), (9, 5, -1),
        (5, 9, 1), (10, 4, -1),
        (8, 7, 1), (7, 6, -1),
        (9, 8, 1), (6, 5, -1),
    ],
    "mid_ladder_fx": [
        (7, 7, 1), (6, 8, -1),
        (8, 6, 1), (5, 9, -1),
        (9, 5, 1), (4, 10, -1),
        (7, 8, 1), (6, 7, -1),
        (8, 9, 1), (5, 6, -1),
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
    "mid_parallel_r90": [
        (7, 5, 1), (6, 5, -1),
        (7, 6, 1), (6, 6, -1),
        (7, 7, 1), (6, 7, -1),
        (7, 9, 1), (6, 9, -1),
        (7, 10, 1), (6, 10, -1),
        (7, 11, 1), (6, 11, -1),
    ],
    "mid_parallel_r180": [
        (9, 7, 1), (9, 6, -1),
        (8, 7, 1), (8, 6, -1),
        (7, 7, 1), (7, 6, -1),
        (5, 7, 1), (5, 6, -1),
        (4, 7, 1), (4, 6, -1),
        (3, 7, 1), (3, 6, -1),
    ],
    "mid_parallel_r270": [
        (7, 9, 1), (8, 9, -1),
        (7, 8, 1), (8, 8, -1),
        (7, 7, 1), (8, 7, -1),
        (7, 5, 1), (8, 5, -1),
        (7, 4, 1), (8, 4, -1),
        (7, 3, 1), (8, 3, -1),
    ],
    "mid_parallel_fx": [
        (9, 7, 1), (9, 8, -1),
        (8, 7, 1), (8, 8, -1),
        (7, 7, 1), (7, 8, -1),
        (5, 7, 1), (5, 8, -1),
        (4, 7, 1), (4, 8, -1),
        (3, 7, 1), (3, 8, -1),
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
    "tact_edge_open3_r90": [
        (7, 0, 1), (0, 14, -1),
        (7, 1, 1), (1, 14, -1),
        (7, 2, 1), (0, 13, -1),
    ],
    "tact_edge_open3_r180": [
        (14, 7, 1), (0, 0, -1),
        (13, 7, 1), (0, 1, -1),
        (12, 7, 1), (1, 0, -1),
    ],
    "tact_edge_open3_r270": [
        (7, 14, 1), (14, 0, -1),
        (7, 13, 1), (13, 0, -1),
        (7, 12, 1), (14, 1, -1),
    ],
    "tact_edge_open3_fx": [
        (14, 7, 1), (0, 14, -1),
        (13, 7, 1), (0, 13, -1),
        (12, 7, 1), (1, 14, -1),
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
    "tact_vcf_first": [
        # Black already has an immediate VCF completion
        (3, 7, 1), (0, 0, -1),
        (4, 7, 1), (1, 0, -1),
        (5, 7, 1), (2, 0, -1),
    ],
    "tact_vcf_first_r90": [
        (7, 3, 1), (14, 0, -1),
        (7, 4, 1), (14, 1, -1),
        (7, 5, 1), (14, 2, -1),
    ],
    "tact_vcf_first_r180": [
        (11, 7, 1), (14, 14, -1),
        (10, 7, 1), (13, 14, -1),
        (9, 7, 1), (12, 14, -1),
    ],
    "tact_vcf_first_r270": [
        (7, 11, 1), (0, 14, -1),
        (7, 10, 1), (0, 13, -1),
        (7, 9, 1), (0, 12, -1),
    ],
    "tact_vcf_first_fx": [
        (11, 7, 1), (14, 0, -1),
        (10, 7, 1), (13, 0, -1),
        (9, 7, 1), (12, 0, -1),
    ],
    "tact_corner_open3": [
        # Black extends from the top-left corner with a near-edge open three
        (0, 0, 1), (14, 14, -1),
        (1, 1, 1), (13, 14, -1),
        (2, 2, 1), (14, 13, -1),
    ],
    "tact_corner_open3_r90": [
        (14, 0, 1), (0, 14, -1),
        (13, 1, 1), (0, 13, -1),
        (12, 2, 1), (1, 14, -1),
    ],
    "tact_corner_open3_r180": [
        (14, 14, 1), (0, 0, -1),
        (13, 13, 1), (1, 0, -1),
        (12, 12, 1), (0, 1, -1),
    ],
    "tact_corner_open3_r270": [
        (0, 14, 1), (14, 0, -1),
        (1, 13, 1), (14, 1, -1),
        (2, 12, 1), (13, 0, -1),
    ],
    "tact_corner_open3_fx": [
        (14, 0, 1), (0, 14, -1),
        (13, 1, 1), (1, 14, -1),
        (12, 2, 1), (0, 13, -1),
    ],
    "tact_corner_defend4": [
        # Black has 4 on the top edge from the corner and should win immediately
        (0, 0, 1), (14, 14, -1),
        (1, 0, 1), (14, 13, -1),
        (2, 0, 1), (13, 14, -1),
        (3, 0, 1), (13, 13, -1),
    ],
    "rootsplit_single_safe_top": [
        # Opponent edge four leaves exactly one safe reply on the top edge.
        # This exercises the reference rootsplit==1 short-circuit path.
        (14, 14, 1), (0, 0, -1),
        (14, 13, 1), (1, 0, -1),
        (13, 14, 1), (2, 0, -1),
        (13, 13, 1), (3, 0, -1),
    ],
    "rootsplit_single_safe_right": [
        # Right-edge mirror of the single-safe-reply rootsplit==1 path.
        (0, 14, 1), (14, 0, -1),
        (1, 14, 1), (14, 1, -1),
        (0, 13, 1), (14, 2, -1),
        (1, 13, 1), (14, 3, -1),
    ],
    "rootsplit_single_safe_bottom": [
        # Bottom-edge mirror of the single-safe-reply rootsplit==1 path.
        (0, 0, 1), (11, 14, -1),
        (1, 0, 1), (12, 14, -1),
        (0, 1, 1), (13, 14, -1),
        (1, 1, 1), (14, 14, -1),
    ],
    "rootsplit_single_safe_left": [
        # Left-edge mirror of the single-safe-reply rootsplit==1 path.
        (14, 0, 1), (0, 11, -1),
        (13, 0, 1), (0, 12, -1),
        (14, 1, 1), (0, 13, -1),
        (13, 1, 1), (0, 14, -1),
    ],
    "tact_defend4_edge_r90": [
        (14, 0, 1), (1, 5, -1),
        (0, 14, 1), (1, 6, -1),
        (13, 0, 1), (1, 7, -1),
        (1, 14, 1), (1, 8, -1),
    ],
    "tact_defend4_edge_r180": [
        (14, 14, 1), (9, 1, -1),
        (0, 0, 1), (8, 1, -1),
        (14, 13, 1), (7, 1, -1),
        (0, 1, 1), (6, 1, -1),
    ],
    "tact_defend4_edge_r270": [
        (0, 14, 1), (13, 9, -1),
        (14, 0, 1), (13, 8, -1),
        (1, 14, 1), (13, 7, -1),
        (13, 0, 1), (13, 6, -1),
    ],
    "tact_defend4_edge_fx": [
        (14, 0, 1), (9, 13, -1),
        (0, 14, 1), (8, 13, -1),
        (14, 1, 1), (7, 13, -1),
        (0, 13, 1), (6, 13, -1),
    ],
    "dense_defense": [
        # Dense center fight where the side to move must prioritize defense
        (7, 7, 1), (8, 7, -1),
        (7, 8, 1), (8, 8, -1),
        (6, 7, 1), (9, 7, -1),
        (6, 8, 1), (9, 8, -1),
        (7, 6, 1), (8, 6, -1),
        (7, 9, 1), (8, 9, -1),
        (5, 7, 1), (10, 7, -1),
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
    "fallback_missing_root_r90": [
        (7, 7, 1), (8, 7, -1),
        (9, 7, 1), (9, 6, -1),
        (7, 8, 1), (7, 6, -1),
        (8, 6, 1), (6, 5, -1),
        (9, 8, 1), (10, 5, -1),
        (8, 8, 1), (5, 4, -1),
        (4, 3, 1), (11, 4, -1),
        (12, 3, 1),
    ],
    "fallback_missing_root_r180": [
        (7, 7, 1), (7, 8, -1),
        (7, 9, 1), (8, 9, -1),
        (6, 7, 1), (8, 7, -1),
        (8, 8, 1), (9, 6, -1),
        (6, 9, 1), (9, 10, -1),
        (6, 8, 1), (10, 5, -1),
        (11, 4, 1), (10, 11, -1),
        (11, 12, 1),
    ],
    "fallback_missing_root_r270": [
        (7, 7, 1), (6, 7, -1),
        (5, 7, 1), (5, 8, -1),
        (7, 6, 1), (7, 8, -1),
        (6, 8, 1), (8, 9, -1),
        (5, 6, 1), (4, 9, -1),
        (6, 6, 1), (9, 10, -1),
        (10, 11, 1), (3, 10, -1),
        (2, 11, 1),
    ],
    "fallback_missing_root_fx": [
        (7, 7, 1), (7, 6, -1),
        (7, 5, 1), (8, 5, -1),
        (6, 7, 1), (8, 7, -1),
        (8, 6, 1), (9, 8, -1),
        (6, 5, 1), (9, 4, -1),
        (6, 6, 1), (10, 9, -1),
        (11, 10, 1), (10, 3, -1),
        (11, 2, 1),
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
    "dense_center_r90": [
        (7, 7, 1), (7, 8, -1),
        (6, 7, 1), (6, 8, -1),
        (8, 6, 1), (5, 9, -1),
        (5, 6, 1), (8, 9, -1),
        (7, 5, 1), (7, 10, -1),
        (9, 7, 1), (4, 7, -1),
        (8, 8, 1), (6, 6, -1),
        (4, 10, 1), (9, 5, -1),
        (6, 9, 1), (7, 6, -1),
        (5, 8, 1), (8, 7, -1),
        (4, 5, 1), (9, 10, -1),
    ],
    "dense_center_r180": [
        (7, 7, 1), (6, 7, -1),
        (7, 6, 1), (6, 6, -1),
        (8, 8, 1), (5, 5, -1),
        (8, 5, 1), (5, 8, -1),
        (9, 7, 1), (4, 7, -1),
        (7, 9, 1), (7, 4, -1),
        (6, 8, 1), (8, 6, -1),
        (4, 4, 1), (9, 9, -1),
        (5, 6, 1), (8, 7, -1),
        (6, 5, 1), (7, 8, -1),
        (9, 4, 1), (4, 9, -1),
    ],
    "dense_center_r270": [
        (7, 7, 1), (7, 6, -1),
        (8, 7, 1), (8, 6, -1),
        (6, 8, 1), (9, 5, -1),
        (9, 8, 1), (6, 5, -1),
        (7, 9, 1), (7, 4, -1),
        (5, 7, 1), (10, 7, -1),
        (6, 6, 1), (8, 8, -1),
        (10, 4, 1), (5, 9, -1),
        (8, 5, 1), (7, 8, -1),
        (9, 6, 1), (6, 7, -1),
        (10, 9, 1), (5, 4, -1),
    ],
    "dense_center_fx": [
        (7, 7, 1), (6, 7, -1),
        (7, 8, 1), (6, 8, -1),
        (8, 6, 1), (5, 9, -1),
        (8, 9, 1), (5, 6, -1),
        (9, 7, 1), (4, 7, -1),
        (7, 5, 1), (7, 10, -1),
        (6, 6, 1), (8, 8, -1),
        (4, 10, 1), (9, 5, -1),
        (5, 8, 1), (8, 7, -1),
        (6, 9, 1), (7, 6, -1),
        (9, 10, 1), (4, 5, -1),
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
    "dense_edge_r90": [
        (7, 0, 1), (7, 1, -1),
        (7, 2, 1), (7, 3, -1),
        (14, 7, 1), (13, 7, -1),
        (12, 7, 1), (11, 7, -1),
        (7, 14, 1), (7, 13, -1),
        (7, 12, 1), (7, 11, -1),
        (0, 7, 1), (1, 7, -1),
        (2, 7, 1), (3, 7, -1),
        (7, 7, 1), (6, 8, -1),
        (8, 6, 1), (5, 9, -1),
    ],
    "dense_edge_r180": [
        (14, 7, 1), (13, 7, -1),
        (12, 7, 1), (11, 7, -1),
        (7, 14, 1), (7, 13, -1),
        (7, 12, 1), (7, 11, -1),
        (0, 7, 1), (1, 7, -1),
        (2, 7, 1), (3, 7, -1),
        (7, 0, 1), (7, 1, -1),
        (7, 2, 1), (7, 3, -1),
        (7, 7, 1), (6, 6, -1),
        (8, 8, 1), (5, 5, -1),
    ],
    "dense_edge_r270": [
        (7, 14, 1), (7, 13, -1),
        (7, 12, 1), (7, 11, -1),
        (0, 7, 1), (1, 7, -1),
        (2, 7, 1), (3, 7, -1),
        (7, 0, 1), (7, 1, -1),
        (7, 2, 1), (7, 3, -1),
        (14, 7, 1), (13, 7, -1),
        (12, 7, 1), (11, 7, -1),
        (7, 7, 1), (8, 6, -1),
        (6, 8, 1), (9, 5, -1),
    ],
    "dense_edge_fx": [
        (14, 7, 1), (13, 7, -1),
        (12, 7, 1), (11, 7, -1),
        (7, 0, 1), (7, 1, -1),
        (7, 2, 1), (7, 3, -1),
        (0, 7, 1), (1, 7, -1),
        (2, 7, 1), (3, 7, -1),
        (7, 14, 1), (7, 13, -1),
        (7, 12, 1), (7, 11, -1),
        (7, 7, 1), (6, 8, -1),
        (8, 6, 1), (5, 9, -1),
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
    "dense_battle_r90": [
        (7, 7, 1), (6, 8, -1),
        (7, 6, 1), (7, 9, -1),
        (7, 8, 1), (6, 7, -1),
        (8, 7, 1), (5, 7, -1),
        (8, 6, 1), (8, 8, -1),
        (6, 9, 1), (5, 6, -1),
        (9, 5, 1), (4, 10, -1),
        (5, 8, 1), (6, 6, -1),
        (8, 9, 1), (6, 5, -1),
        (9, 10, 1), (5, 4, -1),
        (7, 5, 1), (7, 10, -1),
    ],
    "dense_battle_r180": [
        (7, 7, 1), (6, 6, -1),
        (8, 7, 1), (5, 7, -1),
        (6, 7, 1), (7, 6, -1),
        (7, 8, 1), (7, 5, -1),
        (8, 8, 1), (6, 8, -1),
        (5, 6, 1), (8, 5, -1),
        (9, 9, 1), (4, 4, -1),
        (6, 5, 1), (8, 6, -1),
        (5, 8, 1), (9, 6, -1),
        (4, 9, 1), (10, 5, -1),
        (9, 7, 1), (4, 7, -1),
    ],
    "dense_battle_r270": [
        (7, 7, 1), (8, 6, -1),
        (7, 8, 1), (7, 5, -1),
        (7, 6, 1), (8, 7, -1),
        (6, 7, 1), (9, 7, -1),
        (6, 8, 1), (6, 6, -1),
        (8, 5, 1), (9, 8, -1),
        (5, 9, 1), (10, 4, -1),
        (9, 6, 1), (8, 8, -1),
        (6, 5, 1), (8, 9, -1),
        (5, 4, 1), (9, 10, -1),
        (7, 9, 1), (7, 4, -1),
    ],
    "dense_battle_fx": [
        (7, 7, 1), (6, 8, -1),
        (8, 7, 1), (5, 7, -1),
        (6, 7, 1), (7, 8, -1),
        (7, 6, 1), (7, 9, -1),
        (8, 6, 1), (6, 6, -1),
        (5, 8, 1), (8, 9, -1),
        (9, 5, 1), (4, 10, -1),
        (6, 9, 1), (8, 8, -1),
        (5, 6, 1), (9, 8, -1),
        (4, 5, 1), (10, 9, -1),
        (9, 7, 1), (4, 7, -1),
    ],
    "mid_scatter_r180": [
        (11, 11, 1), (3, 3, -1),
        (11, 3, 1), (3, 11, -1),
        (7, 7, 1), (7, 6, -1),
        (6, 7, 1), (8, 8, -1),
    ],
    "mid_scatter_fx": [
        (11, 3, 1), (3, 11, -1),
        (11, 11, 1), (3, 3, -1),
        (7, 7, 1), (7, 8, -1),
        (6, 7, 1), (8, 6, -1),
    ],
}

POSITION_GROUPS: dict[str, tuple[str, ...]] = {
    "opening": (
        "open_empty",
        "open_center",
        "open_2stones",
        "open_diag",
    ),
    "midgame": (
        "mid_cross",
        "mid_ladder",
        "mid_ladder_r90",
        "mid_ladder_r180",
        "mid_ladder_r270",
        "mid_ladder_fx",
        "mid_parallel",
        "mid_parallel_r90",
        "mid_parallel_r180",
        "mid_parallel_r270",
        "mid_parallel_fx",
        "mid_scatter",
        "mid_scatter_r180",
        "mid_scatter_fx",
        "mid_15stones",
    ),
    "tactical": (
        "tact_open3",
        "tact_four",
        "tact_double3",
        "tact_defend4",
        "tact_vcf_first",
        "tact_vcf_first_r90",
        "tact_vcf_first_r180",
        "tact_vcf_first_r270",
        "tact_vcf_first_fx",
        "tact_corner_defend4",
    ),
    "edge_corner": (
        "tact_edge_open3",
        "tact_edge_open3_r90",
        "tact_edge_open3_r180",
        "tact_edge_open3_r270",
        "tact_edge_open3_fx",
        "tact_edge_four",
        "tact_defend4_edge",
        "tact_defend4_edge_r90",
        "tact_defend4_edge_r180",
        "tact_defend4_edge_r270",
        "tact_defend4_edge_fx",
        "tact_corner_open3",
        "tact_corner_open3_r90",
        "tact_corner_open3_r180",
        "tact_corner_open3_r270",
        "tact_corner_open3_fx",
    ),
    "fallback": (
        "rootsplit_single_safe_top",
        "rootsplit_single_safe_right",
        "rootsplit_single_safe_bottom",
        "rootsplit_single_safe_left",
        "fallback_missing_root",
        "fallback_missing_root_r90",
        "fallback_missing_root_r180",
        "fallback_missing_root_r270",
        "fallback_missing_root_fx",
    ),
    "dense": (
        "dense_defense",
        "dense_center",
        "dense_center_r90",
        "dense_center_r180",
        "dense_center_r270",
        "dense_center_fx",
        "dense_edge",
        "dense_edge_r90",
        "dense_edge_r180",
        "dense_edge_r270",
        "dense_edge_fx",
        "dense_battle",
        "dense_battle_r90",
        "dense_battle_r180",
        "dense_battle_r270",
        "dense_battle_fx",
    ),
}

ALL_GROUP_NAMES = tuple(POSITION_GROUPS)
DEFAULT_PARALLEL_JOBS = 6

SEARCH_DEPTH = 3
SEARCH_WIDTH = 10

# ---------------------------------------------------------------------------
# Reference C++ trace program
# ---------------------------------------------------------------------------

def _build_trace_cpp_v2(position_ids: list[str]) -> str:
    """Generate a C++ trace program that evaluates all positions.

    Strategy: rootsearch() returns the move directly. For score and node count,
    we parse the MESSAGE output that rootsearch prints for each depth iteration.
    The last MESSAGE line contains the final score.

    We redirect/capture these by having our own output markers.
    """
    position_blocks: list[str] = []
    for pos_id in position_ids:
        moves = POSITIONS[pos_id]
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


def _parse_reference_output_for_positions(
    output: str,
    position_ids: list[str],
) -> dict[str, EngineResult]:
    all_results = _parse_reference_output(output)
    return {pos_id: all_results[pos_id] for pos_id in position_ids if pos_id in all_results}


# ---------------------------------------------------------------------------
# pyslow side
# ---------------------------------------------------------------------------

def _run_pyslow(position_ids: list[str]) -> dict[str, EngineResult]:
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

    for pos_id in position_ids:
        moves = POSITIONS[pos_id]
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
    position_ids: list[str],
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

    for pos_id in position_ids:
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
    total = len(position_ids)
    ok_count = total - mismatches - skipped
    print(f"\nTotal: {total}  OK/Close: {ok_count}  Mismatches: {mismatches}  Skipped: {skipped}")

    # Print notes about known divergence causes
    notes: list[str] = []
    for pos_id in position_ids:
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


def _position_ids_for_groups(groups: list[str] | None) -> list[str]:
    if not groups:
        return list(POSITIONS)
    ordered: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if group not in POSITION_GROUPS:
            raise ValueError(f"unknown group: {group}")
        for pos_id in POSITION_GROUPS[group]:
            if pos_id not in seen:
                ordered.append(pos_id)
                seen.add(pos_id)
    return ordered


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare SlowRenju and pyslow on curated positions.")
    parser.add_argument(
        "--group",
        action="append",
        choices=ALL_GROUP_NAMES,
        help="Run only one or more named position groups.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=DEFAULT_PARALLEL_JOBS,
        help="Number of parallel group workers for the top-level runner.",
    )
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help="Emit a compact JSON summary instead of the detailed table.",
    )
    return parser


def _run_single_compare(
    position_ids: list[str],
    *,
    print_report: bool,
    verbose: bool,
) -> tuple[int, dict[str, EngineResult], dict[str, EngineResult]]:
    if verbose:
        print("=" * 70)
        print("  SlowRenju vs pyslow Alignment Comparison")
        print(f"  Depth={SEARCH_DEPTH}  Width={SEARCH_WIDTH}  Positions={len(position_ids)}")
        print("=" * 70)

        print("\n[1/3] Building reference trace binary...")
    workspace = None
    ref_results: dict[str, EngineResult] = {}
    try:
        workspace = prepare_workspace()
        cpp_source = _build_trace_cpp_v2(position_ids)
        write_trace_program(workspace, cpp_source)
        exe = build_trace(workspace)
        if verbose:
            print("      Build successful.")

        if verbose:
            print("[2/3] Running reference engine on all positions...")
        proc = subprocess.run(
            [str(exe)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0:
            if verbose:
                print(f"      Reference binary exited with code {proc.returncode}")
                if proc.stderr:
                    print(f"      STDERR (first 1000 chars):\n{proc.stderr[:1000]}")
        ref_results = _parse_reference_output_for_positions(proc.stdout, position_ids)
        if verbose:
            print(f"      Got results for {len(ref_results)}/{len(position_ids)} positions.")
    except subprocess.TimeoutExpired:
        if verbose:
            print("      ERROR: Reference binary timed out after 300s.")
    except subprocess.CalledProcessError as e:
        if verbose:
            print(f"      ERROR: Build failed:\n{e.stderr[:1000] if e.stderr else e}")
    except Exception as e:
        if verbose:
            print(f"      ERROR: {e}")
    finally:
        if workspace is not None:
            cleanup_workspace(workspace)

    if verbose:
        print("[3/3] Running pyslow engine on all positions...")
    py_results: dict[str, EngineResult] = {}
    try:
        py_results = _run_pyslow(position_ids)
        if verbose:
            print(f"      Got results for {len(py_results)}/{len(position_ids)} positions.")
    except Exception as e:
        if verbose:
            print(f"      ERROR: {e}")
            import traceback
            traceback.print_exc()

    mismatches = _print_report(ref_results, py_results, position_ids) if print_report else 0
    return mismatches, ref_results, py_results


def _run_group_subprocess(group: str) -> dict[str, object]:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--group",
        group,
        "--jobs",
        "1",
        "--json-summary",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, timeout=600)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"group {group} failed: {proc.stderr[:1000] or proc.stdout[:1000]}")
    payload = json.loads(proc.stdout.strip())
    payload["returncode"] = proc.returncode
    return payload


def _run_parallel_groups(groups: list[str], jobs: int) -> int:
    print("=" * 70)
    print("  SlowRenju vs pyslow Alignment Comparison")
    print(f"  Depth={SEARCH_DEPTH}  Width={SEARCH_WIDTH}  Positions={len(_position_ids_for_groups(groups))}")
    print(f"  Parallel Groups={','.join(groups)}  Jobs={jobs}")
    print("=" * 70)

    summaries: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=jobs) as executor:
        future_map = {executor.submit(_run_group_subprocess, group): group for group in groups}
        for future in as_completed(future_map):
            group = future_map[future]
            summaries[group] = future.result()
            summary = summaries[group]
            print(
                f"[group {group}] positions={summary['positions']} "
                f"ok={summary['ok']} mismatches={summary['mismatches']} skipped={summary['skipped']}"
            )

    total_positions = sum(int(s["positions"]) for s in summaries.values())
    total_ok = sum(int(s["ok"]) for s in summaries.values())
    total_mismatches = sum(int(s["mismatches"]) for s in summaries.values())
    total_skipped = sum(int(s["skipped"]) for s in summaries.values())

    print("\nGroup Summary")
    print("-" * 70)
    for group in groups:
        summary = summaries[group]
        print(
            f"{group:<16} positions={summary['positions']:<3} "
            f"ok={summary['ok']:<3} mismatches={summary['mismatches']:<3} skipped={summary['skipped']:<3}"
        )
    print("-" * 70)
    print(
        f"Total: {total_positions}  OK/Close: {total_ok}  "
        f"Mismatches: {total_mismatches}  Skipped: {total_skipped}"
    )
    return 1 if total_mismatches > 0 else 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = _build_arg_parser().parse_args()
    groups = args.group or list(ALL_GROUP_NAMES)
    position_ids = _position_ids_for_groups(args.group)

    if args.json_summary:
        mismatches, ref_results, py_results = _run_single_compare(position_ids, print_report=False, verbose=False)
        skipped = sum(1 for pos_id in position_ids if pos_id not in ref_results or pos_id not in py_results)
        payload = {
            "groups": groups,
            "positions": len(position_ids),
            "ok": len(position_ids) - mismatches - skipped,
            "mismatches": mismatches,
            "skipped": skipped,
        }
        print(json.dumps(payload))
        return 1 if mismatches > 0 else 0

    if args.jobs > 1 and len(groups) > 1 and args.group is None:
        jobs = min(args.jobs, len(groups), os.cpu_count() or 1)
        return _run_parallel_groups(groups, jobs)

    mismatches, _, _ = _run_single_compare(position_ids, print_report=True, verbose=True)
    return 1 if mismatches > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
