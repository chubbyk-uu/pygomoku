from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap

import pytest

from pygomoku.board import Board, move_to_xy
from pygomoku.threats.threat_board import ThreatBoardView


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


def _black_view(points):
    board = Board()
    for x, y in points:
        board.grid[y][x] = 1
    return ThreatBoardView.from_board(board.copy())


def test_b4p_jump_four_does_not_report_spurious_second_five() -> None:
    # Row 7 = X X X _ X _ X X (black 3,4,5,7,9,10; 6,8,11 empty). Anchor (7,7)
    # sits between the two gaps. Only (6,7) completes a five; playing (8,7)
    # leaves 7,8,9,10 — four, not five — because col 11 is empty. The b4p 0x1D
    # jump-four branch must not treat this as a two-point (ambiguous) threat.
    view = _black_view([(3, 7), (4, 7), (5, 7), (7, 7), (9, 7), (10, 7)])
    reply, ambiguous = view.broken_four_point_for_side(1)
    assert ambiguous is False
    rep = view.broken_four_reply(7, 7)
    assert rep is not None
    rx, ry = move_to_xy(rep)
    assert (rx, ry) == (6, 7)
    played = _black_view([(3, 7), (4, 7), (5, 7), (7, 7), (9, 7), (10, 7)])
    played.play(rep, 1)
    assert played.has_a5(rx, ry)  # the reported reply really completes five


def test_b4p_real_jump_four_reports_both_five_points() -> None:
    # Adding col 11 makes a real jump four X X X _ X _ X X X: both (6,7) and
    # (8,7) complete a five, so the threat is genuinely ambiguous (two points).
    view = _black_view([(3, 7), (4, 7), (5, 7), (7, 7), (9, 7), (10, 7), (11, 7)])
    _, ambiguous = view.broken_four_point_for_side(1)
    assert ambiguous is True
