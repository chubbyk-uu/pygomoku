#!/usr/bin/env python3
"""High-level semantic audit for pyslow vs SlowRenju baseline.

This script does not change engine code. It collects a few focused signals:

- current alignment_compare result on the agreed development baseline
- current engine-default runtime options
- whether enabling nonroot_vcf changes the fixed comparison set
- protocol edge behaviors that are known to differ or be intentionally scoped
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.alignment_compare import POSITIONS
from pyslow.board import Board
from pyslow.config import load_default_config
from pyslow.protocol.gomocup import GomocupProtocol
from pyslow.search.root import RootSearcher, SearchLimits


def _run_alignment_compare() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, str(ROOT / "benchmarks" / "alignment_compare.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=300,
    )
    combined = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, combined


def _fixed_position_summaries(nonroot_vcf: bool) -> dict[str, tuple[tuple[int, int], int, int]]:
    cfg = load_default_config()
    cfg = replace(cfg, runtime=replace(cfg.runtime, nonroot_vcf=nonroot_vcf))
    searcher = RootSearcher(cfg)
    result: dict[str, tuple[tuple[int, int], int, int]] = {}
    for name, seq in POSITIONS.items():
        board = Board()
        for x, y, side in seq:
            board.play(y * 15 + x, side)
        found = searcher.search(board, SearchLimits(max_depth=3, root_width=10))
        result[name] = ((found.move % 15, found.move // 15), found.score, found.nodes)
    return result


def _protocol_snapshot() -> dict[str, object]:
    proto = GomocupProtocol()
    return {
        "start_15": proto.handle_line("START 15"),
        "start_20": proto.handle_line("START 20"),
        "takeback_empty": proto.handle_line("TAKEBACK"),
        "unknown_command": proto.handle_line("FOOBAR"),
    }


def main() -> None:
    cfg = load_default_config()
    align_code, align_output = _run_alignment_compare()

    nonroot_off = _fixed_position_summaries(nonroot_vcf=False)
    nonroot_on = _fixed_position_summaries(nonroot_vcf=True)
    changed_positions = sorted(
        name
        for name in POSITIONS
        if nonroot_off[name] != nonroot_on[name]
    )

    report = {
        "engine_defaults": {
            "root_depth": cfg.root_search.depth,
            "root_width": cfg.root_search.wide,
            "ratio_num": cfg.root_search.ratio_num,
            "ratio_den": cfg.root_search.ratio_den,
            "compute_vcf": cfg.runtime.compute_vcf,
            "nonroot_vcf": cfg.runtime.nonroot_vcf,
            "static_board": cfg.runtime.static_board,
            "dynamic_board_margin": cfg.runtime.dynamic_board_margin,
        },
        "development_baseline": {
            "root_depth": 3,
            "root_width": 10,
            "compute_vcf": True,
            "nonroot_vcf": False,
            "static_board": True,
            "dynamic_board_margin": cfg.runtime.dynamic_board_margin,
        },
        "alignment_compare": {
            "returncode": align_code,
            "ok": align_code == 0,
        },
        "nonroot_vcf_fixed_set_changes": changed_positions,
        "protocol_snapshot": _protocol_snapshot(),
    }

    print("=== Semantic Audit Summary ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("\n=== alignment_compare tail ===")
    tail = align_output.strip().splitlines()[-25:]
    print("\n".join(tail))


if __name__ == "__main__":
    main()
