from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest


_BACKEND_PROBE = r"""
import json

import pygomoku.threats.threat_board as tb
from pygomoku.board import Board, xy_to_move
from pygomoku.threats.threat_board import ThreatBoardView, has_vct_trigger


def place(board, points, side):
    for x, y in points:
        board.side_to_move = side
        board.play(xy_to_move(x, y), side)


board = Board()
place(board, [(5, 7), (6, 7), (7, 7), (4, 3), (4, 4), (4, 5), (4, 6)], 1)
place(board, [(9, 7)], -1)
view = ThreatBoardView.from_board(board)

trigger_board = Board()
for x, y, side in (
    (6, 7, 1), (0, 0, -1),
    (8, 7, 1), (1, 3, -1),
    (7, 6, 1), (3, 1, -1),
    (7, 8, 1), (14, 14, -1),
):
    trigger_board.play(xy_to_move(x, y), side)

print(json.dumps({
    "native": tb._a3r_count_native is not None,
    "a3r_count": view.a3r_count(7, 7),
    "is_double3r": view.is_double3r(7, 7),
    "has_vct_trigger": has_vct_trigger(trigger_board, 1),
}, sort_keys=True))
"""


def _run_backend_probe(backend: str) -> dict[str, object]:
    env = os.environ.copy()
    env["PYSLOW_THREAT_BOARD_BACKEND"] = backend
    env["PYTHONPATH"] = os.getcwd()
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(_BACKEND_PROBE)],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    return json.loads(result.stdout)


def test_threat_board_a3r_count_backends_match_a5test_adjustment() -> None:
    try:
        from pygomoku.threats._threat_board_cy import a3r_count_raw  # noqa: F401
    except ImportError:
        pytest.skip("compiled threat-board Cython helper is unavailable")

    python_result = _run_backend_probe("python")
    cython_result = _run_backend_probe("cython")

    assert python_result["native"] is False
    assert cython_result["native"] is True
    assert python_result == {
        "native": False,
        "a3r_count": 0,
        "is_double3r": False,
        "has_vct_trigger": True,
    }
    assert cython_result == {
        "native": True,
        "a3r_count": 0,
        "is_double3r": False,
        "has_vct_trigger": True,
    }
