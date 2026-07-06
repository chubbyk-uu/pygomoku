"""Tests for the VCT (Victory by Continuous Threats) module.

Covers:
  - ThreatBoardView.a3_gain_squares
  - ThreatBoardView.classify_attack_at
  - ThreatBoardView.collect_attack_moves
  - has_vct_trigger
  - VCTSearcher (OR/AND tree, memo, iterative deepening)
  - RootSearcher VCT integration (trigger, trace, accept/reject)
"""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from pygomoku.board import Board, move_to_xy, xy_to_move
from pygomoku.config import load_default_config
from pygomoku.search.root import RootSearcher, SearchLimits
from pygomoku.threats.threat_board import ThreatBoardView, has_vct_trigger
from pygomoku.threats.types import ThreatLevel
from pygomoku.threats.vct import VCTSearcher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_board(*moves: tuple[int, int, int]) -> Board:
    """Build a Board from a sequence of (x, y, side) tuples."""
    board = Board()
    for x, y, side in moves:
        assert board.side_to_move == side, f"expected side {side}, got {board.side_to_move}"
        board.play(xy_to_move(x, y), side)
    return board


def _board_from_stones(stones: list[tuple[int, int, int]], side_to_move: int = 1) -> Board:
    """Place arbitrary stones directly for tactical fixtures that are not
    naturally alternating (clustered same-colour groups). No winner/zobrist is
    derived, which is fine for VCT search on non-terminal positions."""
    board = Board()
    for x, y, side in stones:
        board.grid[y][x] = side
    board.side_to_move = side_to_move
    return board


def _root(vct_depth: int = 4, vct_on: bool = True) -> RootSearcher:
    config = load_default_config()
    config = replace(
        config,
        runtime=replace(config.runtime, compute_vct=vct_on, root_vct_depth=vct_depth),
    )
    return RootSearcher(config)


# ---------------------------------------------------------------------------
# ThreatBoardView.a3_gain_squares
# ---------------------------------------------------------------------------

class TestA3GainSquares:
    def test_three_in_a_row_returns_both_endpoints(self):
        # Black (7,7)(8,7)(9,7) with open ends → gain squares (6,7) and (10,7)
        board = _make_board((7, 7, 1), (0, 0, -1), (8, 7, 1), (1, 0, -1))
        view = ThreatBoardView.from_board(board.copy())
        view.play(xy_to_move(9, 7), 1)
        gains = set(move_to_xy(g) for g in view.a3_gain_squares(9, 7))
        view.undo()
        assert (6, 7) in gains
        assert (10, 7) in gains

    def test_three_in_a_row_blocked_one_side_returns_one_gain(self):
        # Black (5,7)(6,7)(7,7) with white at (3,7) two cells left →
        # a3() sees [W,_,B,B,B,_]: cells[i-2]=W so only right gain (8,7) returned.
        board = _make_board(
            (5, 7,  1), (3, 7, -1),
            (6, 7,  1), (0, 0, -1),
        )
        view = ThreatBoardView.from_board(board.copy())
        view.play(xy_to_move(7, 7), 1)
        gains = [move_to_xy(g) for g in view.a3_gain_squares(7, 7)]
        view.undo()
        assert (8, 7) in gains
        assert (4, 7) not in gains   # left extension leads to B4 not A4

    def test_no_a3_pattern_returns_empty(self):
        # Isolated stone — no open three
        board = _make_board((7, 7, 1), (0, 0, -1))
        view = ThreatBoardView.from_board(board.copy())
        view.play(xy_to_move(12, 12), 1)
        gains = view.a3_gain_squares(12, 12)
        view.undo()
        assert gains == ()


# ---------------------------------------------------------------------------
# ThreatBoardView.classify_attack_at
# ---------------------------------------------------------------------------

class TestClassifyAttackAt:
    def test_win5_classified_correctly(self):
        board = _make_board(
            (5, 7, 1), (0, 0, -1),
            (6, 7, 1), (1, 0, -1),
            (7, 7, 1), (2, 0, -1),
            (8, 7, 1), (3, 0, -1),
        )
        view = ThreatBoardView.from_board(board.copy())
        view.play(xy_to_move(9, 7), 1)
        atk = view.classify_attack_at(9, 7, 1, xy_to_move(9, 7))
        view.undo()
        assert atk is not None
        assert atk.level == ThreatLevel.WIN5
        assert atk.defenses == ()

    def test_b4_classified_with_one_forced_reply(self):
        # Black (5,7)(6,7)(7,7) + white blocker (4,7) → playing (8,7) creates B4
        board = _make_board(
            (5, 7,  1), (4, 7, -1),
            (6, 7,  1), (0, 0, -1),
            (7, 7,  1), (1, 0, -1),
        )
        view = ThreatBoardView.from_board(board.copy())
        view.play(xy_to_move(8, 7), 1)
        atk = view.classify_attack_at(8, 7, 1, xy_to_move(8, 7))
        view.undo()
        assert atk is not None
        assert atk.level == ThreatLevel.B4
        assert len(atk.defenses) == 1
        assert move_to_xy(atk.defenses[0]) == (9, 7)

    def test_a3_classified_with_gain_squares(self):
        # Black (7,7)(8,7) → playing (9,7) creates horizontal A3
        board = _make_board((7, 7, 1), (0, 0, -1), (8, 7, 1), (1, 3, -1))
        view = ThreatBoardView.from_board(board.copy())
        view.play(xy_to_move(9, 7), 1)
        atk = view.classify_attack_at(9, 7, 1, xy_to_move(9, 7))
        view.undo()
        assert atk is not None
        assert atk.level == ThreatLevel.A3
        defense_coords = {move_to_xy(d) for d in atk.defenses}
        assert (10, 7) in defense_coords
        assert (6, 7) in defense_coords

    def test_no_threat_returns_none(self):
        board = _make_board((7, 7, 1), (0, 0, -1))
        view = ThreatBoardView.from_board(board.copy())
        view.play(xy_to_move(12, 12), 1)
        atk = view.classify_attack_at(12, 12, 1, xy_to_move(12, 12))
        view.undo()
        assert atk is None


# ---------------------------------------------------------------------------
# ThreatBoardView.collect_attack_moves
# ---------------------------------------------------------------------------

class TestCollectAttackMoves:
    def test_sorted_strongest_first(self):
        # Build a position that has both B4 and A3 attacks available
        board = _make_board(
            (5, 7,  1), (4, 7, -1),
            (6, 7,  1), (0, 0, -1),
            (7, 7,  1), (1, 3, -1),
            (7, 9,  1), (3, 1, -1),  # seeds for vertical A3
            (7, 10, 1), (13, 1, -1),
        )
        view = ThreatBoardView.from_board(board.copy())
        attacks = view.collect_attack_moves(1)
        assert len(attacks) > 0
        # Levels should be non-increasing (strongest first)
        for i in range(len(attacks) - 1):
            assert attacks[i].level >= attacks[i + 1].level

    def test_empty_when_no_threats(self):
        # Single isolated stone — no forcing moves
        board = _make_board((7, 7, 1), (0, 0, -1))
        view = ThreatBoardView.from_board(board.copy())
        # Play both stones far from any A3 pattern
        attacks = view.collect_attack_moves(1)
        # There should be no A3/B4 attacks on an almost-empty board
        # (isolated stone creates no patterns)
        assert all(a.level < ThreatLevel.A3 for a in attacks) or len(attacks) == 0


# ---------------------------------------------------------------------------
# has_vct_trigger
# ---------------------------------------------------------------------------

class TestHasVctTrigger:
    def test_quiet_position_no_trigger(self):
        # Only two stones far apart — no A3 or B4
        board = _make_board((7, 7, 1), (0, 0, -1))
        assert has_vct_trigger(board, 1) is False

    def test_b4_position_triggers(self):
        # Black (5,7)(6,7)(7,7) with white blocker at (4,7) — can create B4
        board = _make_board(
            (5, 7,  1), (4, 7, -1),
            (6, 7,  1), (0, 0, -1),
            (7, 7,  1), (1, 0, -1),
        )
        assert has_vct_trigger(board, 1) is True

    def test_dual_a3_triggers(self):
        # Black (6,7)(8,7)(7,6)(7,8) → playing (7,7) creates dual-A3
        board = _make_board(
            (6, 7,  1), (0, 0, -1),
            (8, 7,  1), (1, 3, -1),
            (7, 6,  1), (3, 1, -1),
            (7, 8,  1), (14, 14, -1),
        )
        assert has_vct_trigger(board, 1) is True


# ---------------------------------------------------------------------------
# VCTSearcher: core search
# ---------------------------------------------------------------------------

class TestVCTSearcher:
    def test_returns_not_found_on_depth_zero(self):
        board = _make_board(
            (5, 7,  1), (4, 7, -1),
            (6, 7,  1), (0, 0, -1),
            (7, 7,  1), (1, 0, -1),
        )
        r = VCTSearcher().search(board, 1, 0)
        assert r.found is False

    def test_returns_solved_on_terminal_board(self):
        board = _make_board(
            (5, 7,  1), (0, 0, -1),
            (6, 7,  1), (1, 0, -1),
            (7, 7,  1), (2, 0, -1),
            (8, 7,  1), (3, 0, -1),
            (9, 7,  1),  # black wins; no further move
        )
        r = VCTSearcher().search(board, 1, 4)
        assert r.solved is True

    def test_dual_a3_win_that_vcf_misses(self):
        # Black (6,7)(8,7)(7,6)(7,8): playing (7,7) creates two A3 patterns.
        # Defender cannot block both gain-square pairs simultaneously.
        # VCF finds no win (no B4 chain); VCT finds win at depth 2.
        from pygomoku.threats.vcf import VCFSearcher
        board = _make_board(
            (6, 7,  1), (0, 0, -1),
            (8, 7,  1), (1, 3, -1),
            (7, 6,  1), (3, 1, -1),
            (7, 8,  1), (14, 14, -1),
        )
        assert VCFSearcher().search(board, 1, 8).found is False
        r = VCTSearcher().search(board, 1, 4)
        assert r.found is True
        assert move_to_xy(r.move) == (7, 7)

    def test_no_win_when_defender_survives(self):
        # Black (5,7)(6,7)(7,7) with white blocker (4,7): single B4 chain
        # but no further threats → VCT exhausts search and reports no win.
        board = _make_board(
            (5, 7,  1), (4, 7, -1),
            (6, 7,  1), (0, 1, -1),
            (7, 7,  1), (1, 1, -1),
        )
        r = VCTSearcher().search(board, 1, 8)
        assert r.found is False
        assert r.solved is True  # search is exhaustive

    def test_iterative_deepening_returns_early_on_find(self):
        # The dual-A3 win is at depth 2; the searcher should return before depth 6.
        board = _make_board(
            (6, 7,  1), (0, 0, -1),
            (8, 7,  1), (1, 3, -1),
            (7, 6,  1), (3, 1, -1),
            (7, 8,  1), (14, 14, -1),
        )
        r = VCTSearcher().search(board, 1, 6)
        assert r.found is True   # found early, not failed at depth 6

    def test_memo_cleared_between_calls(self):
        board = _make_board(
            (6, 7,  1), (0, 0, -1),
            (8, 7,  1), (1, 3, -1),
            (7, 6,  1), (3, 1, -1),
            (7, 8,  1), (14, 14, -1),
        )
        searcher = VCTSearcher()
        r1 = searcher.search(board, 1, 4)
        r2 = searcher.search(board, 1, 4)   # second call reuses same searcher
        assert r1.found == r2.found
        assert r1.move == r2.move

    def test_open_four_not_instant_win_when_defender_has_five(self):
        # Black open three (6,7)(7,7)(8,7); white already holds an open four
        # (1,1)-(4,4). Extending to an open four is NOT an instant VCT win —
        # the defender moves next and completes five first — so the OR-node
        # must not shortcut an A4 attack to a win here.
        board = _board_from_stones([
            (6, 7, 1), (7, 7, 1), (8, 7, 1),
            (1, 1, -1), (2, 2, -1), (3, 3, -1), (4, 4, -1),
        ])
        r = VCTSearcher().search(board, 1, 4)
        assert r.found is False

    def test_four_attack_not_refuted_by_defender_counter_open_four(self):
        # Black plays (8,7): a forcing four (5,6,7,8 on row 7, blocked left by
        # white (4,7)) plus a column three (8,5)(8,6)(8,7). White's only counter
        # is an open four on the (1,1)-(3,3) diagonal, but a defender open four
        # cannot refute a B4 attack (the four completes five first), so the
        # four -> open-four chain is a real VCT win at (8,7).
        board = _board_from_stones([
            (5, 7, 1), (6, 7, 1), (7, 7, 1), (8, 5, 1), (8, 6, 1),
            (4, 7, -1), (1, 1, -1), (2, 2, -1), (3, 3, -1),
        ])
        r = VCTSearcher().search(board, 1, 4)
        assert r.found is True
        assert move_to_xy(r.move) == (8, 7)


# ---------------------------------------------------------------------------
# RootSearcher VCT integration
# ---------------------------------------------------------------------------

class TestRootVCTIntegration:
    def test_vct_not_triggered_when_disabled(self):
        board = _make_board(
            (6, 7,  1), (0, 0, -1),
            (8, 7,  1), (1, 3, -1),
            (7, 6,  1), (3, 1, -1),
            (7, 8,  1), (14, 14, -1),
        )
        searcher = _root(vct_on=False)
        searcher.search(board, SearchLimits(max_depth=3, root_width=10))
        assert searcher.last_trace["used_vct"] is False
        assert searcher.last_trace["vct_triggered"] is False

    def test_vct_not_triggered_on_quiet_position(self):
        # Isolated stones — no trigger
        board = _make_board((7, 7, 1), (0, 0, -1))
        searcher = _root(vct_depth=4)
        searcher.search(board, SearchLimits(max_depth=3, root_width=10))
        assert searcher.last_trace["used_vct"] is True
        assert searcher.last_trace["vct_triggered"] is False

    def test_vct_triggered_and_accepted_on_dual_a3_win(self):
        # The dual-A3 position: VCT wins and the verify step accepts it.
        board = _make_board(
            (6, 7,  1), (0, 0, -1),
            (8, 7,  1), (1, 3, -1),
            (7, 6,  1), (3, 1, -1),
            (7, 8,  1), (14, 14, -1),
        )
        searcher = _root(vct_depth=4)
        result = searcher.search(board, SearchLimits(max_depth=4, root_width=20))
        t = searcher.last_trace
        assert t["vct_triggered"] is True
        assert t["vct_found"] is True
        assert t["vct_accepted"] is True
        assert t["tactical_path"] == "vct"
        assert move_to_xy(result.move) == (7, 7)
        assert result.score == 20000

    def test_vct_triggered_but_finds_no_win(self):
        # B4 trigger fires (can create B4) but VCT search finds no forced win.
        board = _make_board(
            (5, 7,  1), (4, 7, -1),
            (6, 7,  1), (0, 1, -1),
            (7, 7,  1), (1, 1, -1),
        )
        searcher = _root(vct_depth=6)
        searcher.search(board, SearchLimits(max_depth=4, root_width=20))
        t = searcher.last_trace
        assert t["vct_triggered"] is True
        assert t["vct_found"] is False
        assert t["vct_accepted"] is False
        assert t["tactical_path"] == "alphabeta"

    def test_vct_rejected_when_opponent_has_immediate_counter(self):
        # Black has B4 trigger. White has OPEN4 across the board.
        # Fake VCT returns an innocuous move; verify rejects it.
        board = _make_board(
            (5, 7,  1), (10, 5, -1),
            (6, 7,  1), (11, 5, -1),
            (7, 7,  1), (12, 5, -1),
            (0, 1,  1), (13, 5, -1),
            (0, 2,  1), (4, 7,  -1),
        )
        searcher = _root(vct_depth=4)
        searcher.vct.search = lambda _b, _s, _d: SimpleNamespace(
            move=xy_to_move(2, 14), found=True, solved=True
        )
        searcher.search(board, SearchLimits(max_depth=4, root_width=20))
        t = searcher.last_trace
        assert t["vct_found"] is True
        assert t["vct_accepted"] is False
        assert t["vct_reject_reason"] in {"opponent_forcing", "opponent_vcf"}
        assert t["tactical_path"] == "alphabeta"

    def test_vcf_takes_priority_over_vct(self):
        # When VCF finds a win, VCT should not even be invoked.
        board = _make_board(
            (5, 7,  1), (0, 0, -1),
            (6, 7,  1), (1, 0, -1),
            (7, 7,  1), (2, 0, -1),
            (8, 7,  1), (3, 0, -1),
        )
        searcher = _root(vct_depth=4)
        searcher.search(board, SearchLimits(max_depth=4, root_width=20))
        t = searcher.last_trace
        assert t["vcf_found"] is True
        assert t["used_vct"] is False
        assert t["tactical_path"] == "vcf"

    def test_last_trace_is_none_before_first_search(self):
        searcher = _root()
        assert searcher.last_trace is None


class TestA3EndpointDefenses:
    """Regression for the b785d36 port: an A3 attack's defense set must include
    the endpoints of the open four each gain would create, not just the gain
    squares. Omitting them let VCT report false-positive wins in Freestyle.

    These three positions were surfaced by a pygomoku-internal differential
    scan and independently corroborated by rust_gomoku HEAD (which carries the
    fix): the correct Freestyle verdict is no forced win at depth 5, but a real
    (deeper) win at depth 6. Before the fix, depth-5 search wrongly reported a
    win because the quiet endpoint defense was never generated."""

    CASES = (
        (1, [(1, 0, 1), (3, 0, -1), (1, 3, 1), (14, 3, -1), (7, 4, 1), (6, 5, 1),
             (10, 5, -1), (12, 7, -1), (5, 8, -1), (9, 8, 1), (3, 9, -1), (4, 10, 1),
             (5, 10, 1), (0, 12, 1), (12, 12, -1), (14, 13, -1)]),
        (-1, [(4, 0, 1), (12, 0, 1), (4, 1, -1), (5, 1, -1), (14, 1, 1), (1, 3, 1),
              (5, 4, -1), (9, 4, -1), (11, 5, 1), (5, 6, -1), (5, 7, 1), (10, 7, -1),
              (4, 8, 1), (0, 12, -1), (9, 13, -1), (7, 14, 1)]),
        (-1, [(3, 0, -1), (9, 0, -1), (3, 1, 1), (11, 2, -1), (14, 3, 1), (1, 4, -1),
              (8, 6, -1), (12, 6, 1), (8, 9, -1), (5, 10, -1), (6, 10, -1), (13, 11, 1),
              (5, 12, 1), (12, 12, 1), (3, 13, 1), (7, 14, 1)]),
    )

    @pytest.mark.parametrize("side, stones", CASES)
    def test_no_false_positive_vct_at_depth5(self, side, stones):
        board = _board_from_stones(stones, side_to_move=side)
        assert VCTSearcher().search(board.copy(), side, 5).found is False

    @pytest.mark.parametrize("side, stones", CASES)
    def test_real_deeper_win_still_found_at_depth6(self, side, stones):
        board = _board_from_stones(stones, side_to_move=side)
        assert VCTSearcher().search(board.copy(), side, 6).found is True

    def test_a3_defenses_include_open_four_endpoint(self):
        # Black open three (6,7)(7,7)(8,7) on an otherwise empty board. Playing
        # a gain makes an open four; its five-completion endpoints must appear
        # in the A3 defense set alongside the gain squares.
        view = ThreatBoardView.from_board(
            _board_from_stones([(6, 7, 1), (7, 7, 1)], side_to_move=1)
        )
        view.play(xy_to_move(8, 7), 1)
        atk = view.classify_attack_at(8, 7, 1, xy_to_move(8, 7))
        assert atk is not None and atk.level == ThreatLevel.A3
        # Gains are (5,7) and (9,7). The quiet endpoint defenses are (4,7) and
        # (10,7) — the outer five-completion of each open four the gain makes —
        # which the pre-fix gain-only defense set omitted.
        assert xy_to_move(5, 7) in atk.defenses
        assert xy_to_move(9, 7) in atk.defenses
        assert xy_to_move(4, 7) in atk.defenses
        assert xy_to_move(10, 7) in atk.defenses
