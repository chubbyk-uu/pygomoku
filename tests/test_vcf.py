"""VCF tactical tests."""

from pyslow.board import Board, move_to_xy, xy_to_move
from pyslow.threats.threat_board import ThreatBoardView, forcing_threat_moves, threat_moves, winning_threat_moves
from pyslow.threats.vcf import VCFResult, VCFSearcher, _MemoEntry


def test_threat_moves_use_expected_vcf_offsets() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    moves = threat_moves(board, 1)
    assert xy_to_move(9, 7) in moves
    assert xy_to_move(7, 9) in moves
    assert xy_to_move(5, 5) in moves
    assert xy_to_move(5, 4) not in moves


def test_threat_moves_only_expand_from_current_side_stones() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(0, 0))
    moves = set(threat_moves(board, 1))
    assert xy_to_move(9, 7) in moves
    assert xy_to_move(1, 0) not in moves


def test_threat_moves_follow_expected_xy_scan_order() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    moves = threat_moves(board, 1)
    coords = [move_to_xy(move) for move in moves[:4]]
    assert coords == sorted(coords)


def test_winning_threat_moves_detect_open_four_creation() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    wins = set(winning_threat_moves(board, 1))
    assert xy_to_move(6, 7) in wins


def test_forcing_threat_moves_detect_broken_four_continuations() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(6, 7))
    forcing = set(forcing_threat_moves(board, 1))
    assert xy_to_move(5, 7) in forcing


def test_vcf_search_finds_immediate_forcing_threat() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    result = VCFSearcher().search(board, 1, depth=2)
    assert result.found
    assert result.solved
    assert move_to_xy(result.move) in {(2, 7), (6, 7)}


def test_vcf_begin_result_mapping_matches_expected_on_found_position() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    for depth in (1, 2, 4, 8):
        result = VCFSearcher().search(board, 1, depth)
        assert result.found
        assert result.solved
        assert result.move == xy_to_move(2, 7)


def test_vcf_search_reports_inconclusive_at_zero_depth() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    result = VCFSearcher().search(board, 1, depth=0)
    assert not result.found
    assert not result.solved
    assert result.move == -1


def test_vcf_search_can_report_solved_negative() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    result = VCFSearcher().search(board, board.side_to_move, depth=1)
    assert not result.found
    assert result.move == -1
    assert result.solved


def test_vcf_begin_result_mapping_matches_expected_on_negative_and_unsolved_positions() -> None:
    solved_negative = Board()
    solved_negative.play(xy_to_move(7, 7))
    solved_negative.play(xy_to_move(8, 7))
    for depth in (1, 2, 4, 8):
        result = VCFSearcher().search(solved_negative, solved_negative.side_to_move, depth)
        assert not result.found
        assert result.solved
        assert result.move == -1

    quiet = Board()
    quiet.play(xy_to_move(7, 7))
    result = VCFSearcher().search(quiet, quiet.side_to_move, 0)
    assert not result.found
    assert not result.solved
    assert result.move == -1


def test_vcf_sequence_key_is_order_invariant_within_side_lists() -> None:
    key1 = VCFSearcher._canonical_sequence_key((10, 3, 7), (8, 2))
    key2 = VCFSearcher._canonical_sequence_key((7, 10, 3), (2, 8))
    assert key1 == key2


def test_vcf_begin_depth_is_capped_as_expected() -> None:
    assert VCFSearcher._normalize_begin_depth(8) == 5
    assert VCFSearcher._normalize_begin_depth(6) == 4
    assert VCFSearcher._normalize_begin_depth(4) == 4


def test_vcf_begin_search_checks_shallower_depths_first(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    searcher = VCFSearcher()
    depths: list[int] = []

    def fake_search_attacker(view, side, depth, attacker_moves, defender_moves):
        depths.append(depth)
        return VCFResult(move=-1, found=False, solved=(depth == 1))

    monkeypatch.setattr(searcher, "_search_attacker", fake_search_attacker)
    result = searcher.search(board, 1, depth=2)
    assert depths == [1]
    assert not result.found
    assert result.solved


def test_vcf_memo_key_uses_sequence_state() -> None:
    searcher = VCFSearcher()
    key = (1, (3, 7), (2,))
    searcher._memo[key] = _MemoEntry(depth=2, result=VCFResult(move=10, found=True, solved=True))
    assert searcher._memo[key].result.move == 10


def test_vcf_inconclusive_memo_is_depth_specific() -> None:
    searcher = VCFSearcher()
    key = (1, (), ())
    searcher._memo[key] = _MemoEntry(depth=2, result=VCFResult(move=-1, found=False, solved=False))
    assert searcher._memo[key].depth == 2
    assert not searcher._memo[key].result.solved


def test_vcf_skips_generic_threat_scan_when_opponent_b4_exists(monkeypatch) -> None:
    board = Board()
    searcher = VCFSearcher()
    view = ThreatBoardView.from_board(board)

    def fake_b4(side: int) -> tuple[int | None, bool]:
        if side == 1:
            return (None, False)
        return (xy_to_move(7, 7), True)

    def fail_moves(_side: int) -> tuple[int, ...]:
        raise AssertionError("generic threat scan should be skipped")

    monkeypatch.setattr(view, "broken_four_point_for_side", fake_b4)
    monkeypatch.setattr(view, "winning_threat_moves", fail_moves)
    monkeypatch.setattr(view, "threat_moves", fail_moves)
    result = searcher._search_attacker(view, 1, 3, (), ())
    assert not result.found
    assert result.solved


def test_vcf_returns_solved_negative_after_forced_opponent_b4_line(monkeypatch) -> None:
    board = Board()
    searcher = VCFSearcher()
    view = ThreatBoardView.from_board(board)

    monkeypatch.setattr(
        view,
        "broken_four_point_for_side",
        lambda side: (xy_to_move(7, 7), False) if side == -1 else (None, False),
    )
    monkeypatch.setattr(view, "has_a4", lambda x, y: False)

    def fake_defender(*args, **kwargs) -> VCFResult:
        return VCFResult(move=-1, found=False, solved=True)

    monkeypatch.setattr(searcher, "_search_defender", fake_defender)
    monkeypatch.setattr(view, "winning_threat_moves", lambda side: (_ for _ in ()).throw(AssertionError("should not scan generic wins")))
    monkeypatch.setattr(view, "threat_moves", lambda side: (_ for _ in ()).throw(AssertionError("should not scan generic threats")))
    result = searcher._search_attacker(view, 1, 3, (), ())
    assert not result.found
    assert result.solved


def test_vcf_direct_b4_uses_low_word_even_when_reply_is_ambiguous(monkeypatch) -> None:
    board = Board()
    searcher = VCFSearcher()
    view = ThreatBoardView.from_board(board)

    monkeypatch.setattr(
        view,
        "broken_four_point_for_side",
        lambda side: (xy_to_move(7, 7), True) if side == 1 else (None, False),
    )
    result = searcher._search_attacker(view, 1, 3, (), ())
    assert result.found
    assert result.solved
    assert result.move == xy_to_move(7, 7)


def test_threat_board_view_reports_direct_b4_point_for_side() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    move, ambiguous = ThreatBoardView.from_board(board).broken_four_point_for_side(1)
    assert move_to_xy(move) in {(2, 7), (7, 7)}
    assert isinstance(ambiguous, bool)


def test_threat_board_view_reports_broken_four_reply_flag_shape() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    move, ambiguous = ThreatBoardView.from_board(board).broken_four_point_for_side(1)
    assert move_to_xy(move) in {(2, 7), (7, 7)}
    assert isinstance(ambiguous, bool)


def test_broken_four_point_for_side_preserves_expected_scan_order() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    move, _ = ThreatBoardView.from_board(board).broken_four_point_for_side(1)
    assert move_to_xy(move) == (7, 7)


def test_broken_four_point_for_side_returns_current_reply_on_conflict(monkeypatch) -> None:
    board = Board()
    view = ThreatBoardView.from_board(board)
    replies = iter(
        (
            (xy_to_move(2, 2), False),
            (xy_to_move(4, 4), False),
        )
    )

    def fake_reply(x: int, y: int) -> tuple[int | None, bool]:
        if (x, y) == (0, 0):
            return next(replies)
        if (x, y) == (1, 0):
            return next(replies)
        return (None, False)

    monkeypatch.setattr(view, "_broken_four_reply_with_ambiguity", fake_reply)
    view.board.grid[0][0] = 1
    view.board.grid[0][1] = 1
    view.x1[0][0] = 1
    view.x1[1][0] = 1
    move, ambiguous = view.broken_four_point_for_side(1)
    assert move == xy_to_move(4, 4)
    assert ambiguous is True


def test_broken_four_reply_combines_direction_conflicts_as_expected(monkeypatch) -> None:
    board = Board()
    view = ThreatBoardView.from_board(board)

    class FakeLine:
        def __init__(self, value: int) -> None:
            self.value = value

        def b4p(self, _point_index: int) -> int:
            return self.value

    monkeypatch.setattr(
        view,
        "_lines_for",
        lambda x, y: (
            FakeLine(3),   # direction 1 reply -> y = 3
            FakeLine(5),   # direction 2 reply -> x = 5
            FakeLine(0),
            FakeLine(0),
            0,
            0,
            0,
            0,
        ),
    )
    move, ambiguous = view._broken_four_reply_with_ambiguity(2, 2)
    assert move == xy_to_move(2, 3)
    assert ambiguous is True


def test_threat_board_view_detects_a5_for_existing_stone() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    board.play(xy_to_move(8, 0))
    board.play(xy_to_move(7, 7))
    view = ThreatBoardView.from_board(board)
    assert view.has_a5(5, 7)


def test_threat_board_view_counts_b4_for_stone() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    view = ThreatBoardView.from_board(board)
    assert view.b4_count(5, 7) >= 1


def test_threat_board_view_b4_and_double4_match_expected_on_cross_position() -> None:
    board = Board()
    for idx, (x, y) in enumerate(
        [(5, 7), (0, 0), (6, 7), (2, 0), (7, 7), (4, 0), (8, 7), (6, 0), (7, 5), (8, 0), (7, 6), (10, 0), (7, 8)]
    ):
        board.play(xy_to_move(x, y), 1 if idx % 2 == 0 else -1)
    view = ThreatBoardView.from_board(board)
    assert not view.has_a5(7, 7)
    assert not view.has_a6(7, 7)
    assert view.b4_count(7, 7) == 2
    assert view.is_double4(7, 7)
    assert not view.is_double3r(7, 7)


def test_threat_board_view_a3r_and_double3r_match_expected_on_cross_position() -> None:
    board = Board()
    for idx, (x, y) in enumerate([(6, 7), (0, 0), (8, 7), (2, 0), (7, 7), (4, 0), (7, 6), (6, 0), (7, 8)]):
        board.play(xy_to_move(x, y), 1 if idx % 2 == 0 else -1)
    view = ThreatBoardView.from_board(board)
    assert not view.has_a5(7, 7)
    assert not view.has_a6(7, 7)
    assert view.b4_count(7, 7) == 0
    assert view.a3r_count(7, 7) == 2
    assert view.is_double3r(7, 7)
    assert not view.is_double4(7, 7)


def test_threat_board_view_a5test_for_empty_completion() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    view = ThreatBoardView.from_board(board)
    original_side = view.board.side_to_move
    original_key = view.board.zobrist_key
    assert view.a5test(7, 7, 1)
    assert view.board.side_to_move == original_side
    assert view.board.zobrist_key == original_key


def test_threat_board_view_detects_double4() -> None:
    board = Board()
    for x, y in ((5, 7), (6, 7), (7, 7), (9, 7), (7, 5), (7, 6), (7, 9)):
        board.side_to_move = 1
        board.play(xy_to_move(x, y), 1)
    view = ThreatBoardView.from_board(board)
    assert view.is_double4(7, 7)


def test_threat_board_view_detects_double3r() -> None:
    board = Board()
    for x, y in ((6, 7), (7, 7), (8, 7), (7, 6), (7, 8)):
        board.side_to_move = 1
        board.play(xy_to_move(x, y), 1)
    view = ThreatBoardView.from_board(board)
    assert view.is_double3r(7, 7)


def test_threat_board_view_play_undo_keeps_views_in_sync() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    original_key = board.zobrist_key
    original_side = board.side_to_move
    view = ThreatBoardView.from_board(board)
    move = xy_to_move(6, 7)
    view.play(move, -1)
    assert view.board.at(6, 7) == -1
    assert view.x1[6][7] == -1
    assert view.x2[7][6] == -1
    view.undo()
    assert view.board.at(6, 7) == 0
    assert view.x1[6][7] == 0
    assert view.x2[7][6] == 0
    assert view.board.side_to_move == original_side
    assert view.board.zobrist_key == original_key
