"""Search regression tests."""

from dataclasses import replace
from types import SimpleNamespace

from pygomoku.board import Board, move_to_xy, xy_to_move
from pygomoku.config import load_default_config
from pygomoku.eval.caches import EvalCaches
from pygomoku.eval.local import recompute_all
from pygomoku.search.alphabeta import AlphaBetaSearcher, SearchStats, _rootbonus, _compute_corner_state
from pygomoku.constants import HASHF_ALPHA, HASHF_EXACT, INF
from pygomoku.search.root import RootSearcher, SearchLimits, _fallback_ai_move, _new_classic_fallback_rng
from pygomoku.search.tt import TTEntry


POSITIONS: dict[str, list[tuple[int, int, int]]] = {
    "mid_ladder": [
        (7, 7, 1), (8, 8, -1),
        (6, 6, 1), (9, 9, -1),
        (5, 5, 1), (10, 10, -1),
        (7, 8, 1), (8, 7, -1),
        (6, 9, 1), (9, 6, -1),
    ],
    "tact_defend4": [
        (0, 0, 1), (7, 7, -1),
        (0, 1, 1), (8, 7, -1),
        (14, 14, 1), (9, 7, -1),
        (14, 13, 1), (10, 7, -1),
    ],
}


def _play_prefix(board: Board, moves: list[tuple[int, int, int]]) -> None:
    for x, y, side in moves:
        assert board.side_to_move == side
        board.play(xy_to_move(x, y), side)


def test_root_search_returns_center_on_empty_board() -> None:
    searcher = RootSearcher(load_default_config())
    result = searcher.search(Board())
    assert result.move == xy_to_move(7, 7)


def test_root_search_finds_immediate_winning_completion() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    board.play(xy_to_move(6, 7))
    searcher = RootSearcher(load_default_config())
    result = searcher.search(board, SearchLimits(max_depth=2, root_width=10))
    assert move_to_xy(result.move) in {(2, 7), (7, 7)}


def test_root_search_returns_legal_move_under_node_limit() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    searcher = RootSearcher(load_default_config())
    result = searcher.search(board, SearchLimits(max_depth=2, root_width=8, node_limit=10))
    assert board.is_legal_move(result.move)


def test_root_search_prefers_vcf_first_when_available() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    searcher = RootSearcher(load_default_config())
    result = searcher.search(board, SearchLimits(max_depth=2, root_width=8))
    assert move_to_xy(result.move) in {(2, 7), (6, 7)}


def test_root_search_matches_expected_one_move_reply() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    searcher = RootSearcher(load_default_config())
    result = searcher.search(board, SearchLimits(max_depth=4, root_width=8))
    assert move_to_xy(result.move) == (7, 4)
    assert result.score == -12


def test_root_search_matches_classic_opening_10_4_depth6_width15() -> None:
    board = Board()
    board.play(xy_to_move(10, 4))
    searcher = RootSearcher(load_default_config())
    result = searcher.search(board, SearchLimits(max_depth=6, root_width=15))
    assert move_to_xy(result.move) == (9, 4)
    assert result.score == -10


def test_classic_fallback_rng_matches_white_10_10_sequence() -> None:
    prefix_to_30 = [
        (10, 10, 1),
        (10, 9, -1),
        (9, 11, 1),
        (9, 10, -1),
        (11, 9, 1),
        (12, 8, -1),
        (8, 12, 1),
        (7, 13, -1),
        (8, 11, 1),
        (10, 11, -1),
        (11, 12, 1),
        (8, 9, -1),
        (10, 12, 1),
        (9, 12, -1),
        (8, 10, 1),
        (7, 9, -1),
        (8, 13, 1),
        (8, 14, -1),
        (9, 9, 1),
        (8, 8, -1),
        (11, 13, 1),
        (12, 14, -1),
        (11, 11, 1),
        (11, 10, -1),
        (12, 12, 1),
        (13, 13, -1),
        (13, 12, 1),
        (14, 12, -1),
        (12, 10, 1),
    ]
    prefix_to_32 = prefix_to_30 + [
        (13, 9, -1),
        (10, 8, 1),
    ]
    rng = _new_classic_fallback_rng()

    board = Board()
    _play_prefix(board, prefix_to_30)
    caches = EvalCaches()
    recompute_all(board, caches)
    assert move_to_xy(_fallback_ai_move(board, caches, board.side_to_move, rng=rng)) == (13, 9)

    board = Board()
    _play_prefix(board, prefix_to_32)
    caches = EvalCaches()
    recompute_all(board, caches)
    assert move_to_xy(_fallback_ai_move(board, caches, board.side_to_move, rng=rng)) == (9, 7)


def test_root_fallback_uses_classic_rng_on_white_10_10_turn_32() -> None:
    prefix_to_30 = [
        (10, 10, 1),
        (10, 9, -1),
        (9, 11, 1),
        (9, 10, -1),
        (11, 9, 1),
        (12, 8, -1),
        (8, 12, 1),
        (7, 13, -1),
        (8, 11, 1),
        (10, 11, -1),
        (11, 12, 1),
        (8, 9, -1),
        (10, 12, 1),
        (9, 12, -1),
        (8, 10, 1),
        (7, 9, -1),
        (8, 13, 1),
        (8, 14, -1),
        (9, 9, 1),
        (8, 8, -1),
        (11, 13, 1),
        (12, 14, -1),
        (11, 11, 1),
        (11, 10, -1),
        (12, 12, 1),
        (13, 13, -1),
        (13, 12, 1),
        (14, 12, -1),
        (12, 10, 1),
    ]
    prefix_to_32 = prefix_to_30 + [
        (13, 9, -1),
        (10, 8, 1),
    ]
    board = Board()
    _play_prefix(board, prefix_to_30)
    searcher = RootSearcher(load_default_config())
    caches = EvalCaches()
    recompute_all(board, caches)
    assert move_to_xy(_fallback_ai_move(board, caches, board.side_to_move, rng=searcher._fallback_rng)) == (13, 9)

    board = Board()
    _play_prefix(board, prefix_to_32)
    searcher.tt.store(
        TTEntry(
            key=board.zobrist_key,
            value=-20000,
            flag=HASHF_EXACT,
            depth=5,
            priority=999,
            best_move=-1,
        )
    )
    result = searcher.search(board, SearchLimits(max_depth=5, root_width=15))
    assert move_to_xy(result.move) == (9, 7)
    assert result.score == -20000


def test_root_allowed_moves_use_dynamic_board_margin_when_enabled() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    board.play(xy_to_move(7, 8))
    config = load_default_config()
    config = replace(config, runtime=replace(config.runtime, static_board=False, dynamic_board_margin=1))
    searcher = RootSearcher(config)
    allowed = searcher._root_allowed_moves(board)
    assert allowed is not None
    assert xy_to_move(6, 6) in allowed
    assert xy_to_move(0, 0) not in allowed


def test_root_allowed_moves_expand_to_square_window_like_current_engine() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(7, 8))
    board.play(xy_to_move(7, 9))
    board.play(xy_to_move(10, 9))
    config = load_default_config()
    config = replace(config, runtime=replace(config.runtime, static_board=False, dynamic_board_margin=1))
    searcher = RootSearcher(config)
    allowed = searcher._root_allowed_moves(board)
    assert allowed is not None
    xs = [move_to_xy(move)[0] for move in allowed]
    ys = [move_to_xy(move)[1] for move in allowed]
    assert max(xs) - min(xs) == max(ys) - min(ys)


def test_alphabeta_uses_vcf_shortcut_on_tactical_win() -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    caches = EvalCaches()
    recompute_all(board, caches)
    searcher = AlphaBetaSearcher(load_default_config())
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        2,
        -20000,
        20000,
        8,
        stats=SearchStats(),
    )
    assert move_to_xy(move) in {(2, 7), (6, 7)}
    assert score >= 15000


def test_alphabeta_skips_vcf_shortcut_when_runtime_disables_it(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(3, 7))
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(4, 7))
    board.play(xy_to_move(1, 0))
    board.play(xy_to_move(5, 7))
    board.play(xy_to_move(2, 0))
    caches = EvalCaches()
    recompute_all(board, caches)
    config = load_default_config()
    config = replace(config, runtime=replace(config.runtime, compute_vcf=False))
    searcher = AlphaBetaSearcher(config)

    def fail_search(*args: object, **kwargs: object) -> object:
        raise AssertionError("VCF should not be queried when disabled")

    monkeypatch.setattr(searcher.vcf, "search", fail_search)
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        2,
        -20000,
        20000,
        8,
        stats=SearchStats(),
    )
    assert move != -1
    assert isinstance(score, int)


def test_rootbonus_prefers_low_height_moves() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 8))
    # Pre-existing stones are all at height >= 6; is_corner is determined per candidate.
    # (1,1): h=1 → is_corner=True; (7,7): h=7 → is_corner=False
    assert _rootbonus(board, 1, 1, is_corner=True) > _rootbonus(board, 7, 7, is_corner=False)


def test_rootbonus_corner_mode_still_rewards_near_edge_moves() -> None:
    board = Board()
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(14, 14))
    # Stone at (0,0) has h=0 → pre_corner=True for all candidates.
    assert _rootbonus(board, 1, 1, is_corner=True) > 0


def test_rootbonus_precomputed_is_corner_matches_full_scan() -> None:
    """_compute_corner_state + per-candidate formula gives same is_corner as a full board scan."""

    def full_scan_is_corner(board: Board, cx: int, cy: int) -> bool:
        """Reference: scan the board (including candidate stone at cx,cy) for corner state."""
        half = 0
        for xx in range(board.size):
            for yy in range(board.size):
                if board.grid[yy][xx] == 0:
                    continue
                h = min(xx, yy, board.size - 1 - xx, board.size - 1 - yy)
                if h <= 1:
                    return True
                if h == 2:
                    half += 1
                    if half >= 2:
                        return True
        return False

    cases: list[tuple[list[tuple[int, int]], list[tuple[int, int]]]] = [
        # (pre-existing moves, candidate positions to test — must not overlap with pre-existing)
        ([], [(7, 7), (0, 0), (1, 1), (2, 2)]),
        ([(7, 7), (8, 8)], [(1, 1), (0, 0), (3, 3), (2, 2)]),
        ([(0, 0), (14, 14)], [(1, 1), (7, 7), (2, 2)]),
        ([(2, 7), (7, 2)], [(2, 2), (3, 3), (1, 1), (7, 7)]),
    ]

    for existing_moves, candidates in cases:
        board = Board()
        for i, (ex, ey) in enumerate(existing_moves):
            board.play(xy_to_move(ex, ey), 1 if i % 2 == 0 else -1)

        pre_corner, pre_half = _compute_corner_state(board)

        for cx, cy in candidates:
            # Simulate playing the candidate to get the full board state for the reference scan.
            board.play(xy_to_move(cx, cy), board.side_to_move)
            expected = full_scan_is_corner(board, cx, cy)
            board.undo()

            h = min(cx, cy, board.size - 1 - cx, board.size - 1 - cy)
            got = pre_corner or h <= 1 or (h == 2 and pre_half >= 1)
            assert got == expected, (
                f"is_corner mismatch for candidate ({cx},{cy}) on board {existing_moves}: "
                f"precomputed={got}, full_scan={expected}"
            )


def test_root_vcf_filter_keeps_only_moves_that_break_opponent_vcf(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    searcher = RootSearcher(load_default_config())
    safe = xy_to_move(7, 8)
    risky = xy_to_move(6, 8)

    class FakeResult:
        def __init__(self, found: bool) -> None:
            self.found = found
            self.move = -1

    def fake_search(trial_board: Board, side: int, depth: int) -> FakeResult:
        if trial_board.move_count == board.move_count:
            return FakeResult(depth == 7)
        return FakeResult(trial_board.move_history[-1].move != safe)

    monkeypatch.setattr(searcher.vcf, "search", fake_search)
    filtered = searcher._apply_opponent_vcf_filter(board, board.side_to_move, {safe, risky})
    assert filtered == {safe}


def test_root_vcf_filter_returns_empty_when_no_safe_move_found(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    searcher = RootSearcher(load_default_config())
    allowed = {xy_to_move(7, 8), xy_to_move(6, 8)}

    class FakeResult:
        def __init__(self, found: bool) -> None:
            self.found = found
            self.move = -1

    def fake_search(trial_board: Board, side: int, depth: int) -> FakeResult:
        if trial_board.move_count == board.move_count:
            return FakeResult(True)
        return FakeResult(True)

    monkeypatch.setattr(searcher.vcf, "search", fake_search)
    filtered = searcher._apply_opponent_vcf_filter(board, board.side_to_move, allowed)
    assert filtered == set()


def test_root_returns_only_safe_move_when_vcf_filter_leaves_single_choice(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    searcher = RootSearcher(load_default_config())
    safe = xy_to_move(7, 8)
    risky = xy_to_move(6, 8)

    class FakeResult:
        def __init__(self, found: bool) -> None:
            self.found = found
            self.move = -1

    def fake_search(trial_board: Board, side: int, depth: int) -> FakeResult:
        if trial_board.move_count == board.move_count:
            return FakeResult(depth == 7)
        return FakeResult(trial_board.move_history[-1].move != safe)

    monkeypatch.setattr(searcher.vcf, "search", fake_search)
    result = searcher.search(board, SearchLimits(max_depth=4, root_width=8))
    assert result.move == safe
    assert result.score == 0
    assert result.depth == 0


def test_root_single_safe_move_matches_expected_score_semantics(monkeypatch) -> None:
    board = Board()
    seq = [
        (14, 14, 1),
        (0, 0, -1),
        (14, 13, 1),
        (1, 0, -1),
        (13, 14, 1),
        (2, 0, -1),
        (13, 13, 1),
        (3, 0, -1),
    ]
    for x, y, side in seq:
        assert board.side_to_move == side
        board.play(xy_to_move(x, y))
    searcher = RootSearcher(load_default_config())
    result = searcher.search(board, SearchLimits(max_depth=3, root_width=10))
    assert result.move == xy_to_move(4, 0)
    assert result.score == 0
    assert result.depth == 0


def test_root_uses_ais_fallback_when_vcf_filter_leaves_no_root_moves(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    searcher = RootSearcher(load_default_config())

    class FakeResult:
        def __init__(self, found: bool) -> None:
            self.found = found
            self.move = -1

    def fake_search(trial_board: Board, side: int, depth: int) -> FakeResult:
        if trial_board.move_count == board.move_count and side == board.side_to_move:
            return FakeResult(False)
        return FakeResult(True)

    monkeypatch.setattr(searcher.vcf, "search", fake_search)
    caches = EvalCaches()
    recompute_all(board, caches)
    expected = _fallback_ai_move(board, caches, board.side_to_move, rng=_new_classic_fallback_rng())

    result = searcher.search(board, SearchLimits(max_depth=4, root_width=8))
    assert result.score == -INF
    assert result.depth == 0
    assert result.move == expected


def test_fallback_ai_move_uses_seeded_tie_break() -> None:
    board = Board()
    for x, y, side in POSITIONS["tact_defend4"]:
        board.play(xy_to_move(x, y), side)
    caches = EvalCaches()
    recompute_all(board, caches)
    move_a = _fallback_ai_move(board, caches, board.side_to_move, rng=_new_classic_fallback_rng())
    move_b = _fallback_ai_move(board, caches, board.side_to_move, rng=_new_classic_fallback_rng())
    assert move_a == move_b
    assert move_to_xy(move_a) == (11, 7)


def test_root_skips_vcf_paths_when_runtime_disables_it(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(6, 7))
    config = load_default_config()
    config = replace(config, runtime=replace(config.runtime, compute_vcf=False))
    searcher = RootSearcher(config)

    def fail_search(*args: object, **kwargs: object) -> object:
        raise AssertionError("VCF should not be queried when disabled")

    monkeypatch.setattr(searcher.vcf, "search", fail_search)
    result = searcher.search(board, SearchLimits(max_depth=2, root_width=8))
    assert board.is_legal_move(result.move)


def test_root_search_stops_early_under_time_budget(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(6, 7))
    searcher = RootSearcher(load_default_config())

    timeline = iter([0.0, 0.0, 0.2])
    monkeypatch.setattr("pygomoku.search.root.time", SimpleNamespace(perf_counter=lambda: next(timeline)))
    monkeypatch.setattr("pygomoku.search.alphabeta.time", SimpleNamespace(perf_counter=lambda: 0.0))

    result = searcher.search(board, SearchLimits(max_depth=6, root_width=8, time_limit_ms=100.0))
    assert result.depth == 1


def test_root_search_with_none_time_limit_matches_limit_free_search() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(7, 4))
    searcher = RootSearcher(load_default_config())

    without_time_limit = searcher.search(board, SearchLimits(max_depth=3, root_width=8))
    explicit_none = searcher.search(board, SearchLimits(max_depth=3, root_width=8, time_limit_ms=None))

    assert explicit_none.move == without_time_limit.move
    assert explicit_none.score == without_time_limit.score
    assert explicit_none.depth == without_time_limit.depth


def test_alphabeta_returns_zero_when_deadline_expired_at_entry(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    searcher = AlphaBetaSearcher(load_default_config())

    monkeypatch.setattr("pygomoku.search.alphabeta.time", SimpleNamespace(perf_counter=lambda: 1.0))
    stats = SearchStats(deadline_s=0.5)
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        3,
        -INF,
        INF,
        8,
        stats=stats,
    )
    assert stats.stop is True
    assert (score, move) == (0, -1)


def test_alphabeta_returns_zero_when_deadline_expires_on_periodic_check(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    searcher = AlphaBetaSearcher(load_default_config())

    monkeypatch.setattr("pygomoku.search.alphabeta.time", SimpleNamespace(perf_counter=lambda: 1.0))
    stats = SearchStats(nodes=255, deadline_s=0.5)
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        3,
        -INF,
        INF,
        8,
        stats=stats,
    )
    assert stats.stop is True
    assert (score, move) == (0, -1)


def test_root_search_reports_completed_depth_without_overshooting_limit() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(7, 4))
    searcher = RootSearcher(load_default_config())

    result = searcher.search(board, SearchLimits(max_depth=3, root_width=8))
    assert result.depth == 3


def test_root_search_uses_classic_ais_fallback_when_root_move_is_missing() -> None:
    board = Board()
    sequence = [
        (1, (7, 7)),
        (-1, (7, 6)),
        (1, (7, 5)),
        (-1, (6, 5)),
        (1, (8, 7)),
        (-1, (6, 7)),
        (1, (6, 6)),
        (-1, (5, 8)),
        (1, (8, 5)),
        (-1, (5, 4)),
        (1, (8, 6)),
        (-1, (4, 9)),
        (1, (3, 10)),
        (-1, (4, 3)),
        (1, (3, 2)),
    ]
    for side, (x, y) in sequence:
        board.play(xy_to_move(x, y), side)

    searcher = RootSearcher(load_default_config())
    result = searcher.search(board, SearchLimits(max_depth=3, root_width=10))
    assert board.is_legal_move(result.move)
    assert move_to_xy(result.move) == (8, 8)


def test_root_search_matches_expected_value_on_simple_tt_alpha_seed() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))

    searcher = RootSearcher(load_default_config())
    searcher.tt.store(
        TTEntry(
            key=board.zobrist_key,
            value=123,
            flag=HASHF_ALPHA,
            depth=4,
            priority=board.move_count * 10 + 4,
            best_move=xy_to_move(7, 8),
        )
    )

    result = searcher.search(board, SearchLimits(max_depth=4, root_width=8))
    assert move_to_xy(result.move) == (6, 6)
    assert result.score == 13
    assert result.depth == 4


def test_alphabeta_returns_zero_when_node_limit_stops_at_entry() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    searcher = AlphaBetaSearcher(load_default_config())
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        3,
        -INF,
        INF,
        8,
        stats=SearchStats(node_limit=0),
    )
    assert (score, move) == (0, -1)


def test_alphabeta_returns_zero_when_node_limit_stops_at_entry_even_for_root_call() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    searcher = AlphaBetaSearcher(load_default_config())
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        3,
        -INF,
        INF,
        8,
        stats=SearchStats(node_limit=0),
        root=True,
    )
    assert (score, move) == (0, -1)


def test_alphabeta_returns_negative_inf_when_candidate_list_is_empty(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(6, 7))
    caches = EvalCaches()
    recompute_all(board, caches)
    searcher = AlphaBetaSearcher(load_default_config())

    monkeypatch.setattr(
        "pygomoku.search.alphabeta.generate_candidates",
        lambda *args, **kwargs: type(
            "Generated",
            (),
            {"candidates": (), "single_forcing": False, "hostile_threat": False, "win_priority": False},
        )(),
    )
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        3,
        -INF,
        INF,
        8,
        stats=SearchStats(),
    )
    assert (score, move) == (-INF - 1, -1)


def test_alphabeta_leaf_matches_expected_sign_convention_on_simple_child_board() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(8, 7))
    board.play(xy_to_move(6, 8))
    caches = EvalCaches()
    recompute_all(board, caches)
    searcher = AlphaBetaSearcher(load_default_config())
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        0,
        -INF,
        INF,
        8,
        stats=SearchStats(),
    )
    assert move == -1
    assert score == -1


def test_alphabeta_matches_expected_mid_ladder_nonroot_score() -> None:
    board = Board()
    for x, y, side in POSITIONS["mid_ladder"]:
        board.play(xy_to_move(x, y), side)
    board.play(xy_to_move(7, 5), 1)
    caches = EvalCaches()
    recompute_all(board, caches)
    searcher = AlphaBetaSearcher(load_default_config())
    score, move = searcher.search(
        board,
        caches,
        board.side_to_move,
        3.0,
        -20002,
        20002,
        8,
        opo=1,
        ply=1,
        stats=SearchStats(),
        downf=1,
    )
    assert move_to_xy(move) == (12, 12)
    assert score == -43


# Forced-move regression: with tactical search (VCF/VCT) disabled, the root must
# still return the actual winning forcing move, not the first one in scan order.
# Selecting candidates[0] under preserve_scan_order=True (the root) used to pick a
# blunder here; only surfaces without VCF/VCT since they would otherwise find the
# win. Mirrors the Rust regression in src/search/root.rs.
_WIN_PRIORITY_BLUNDER_MOVES = [
    (7, 7), (6, 8), (7, 8), (7, 6), (6, 7), (8, 7),
    (8, 8), (5, 6), (8, 9), (9, 8), (10, 9), (9, 10),
    (7, 9), (9, 9), (9, 7), (6, 10), (7, 10), (7, 11),
    (8, 10), (6, 6), (8, 6), (5, 7), (6, 5), (5, 9),
    (4, 8), (3, 2), (5, 8), (9, 11), (9, 12), (6, 11),
    (6, 12),
]


def test_root_win_priority_selects_winning_move_without_tactics() -> None:
    from pygomoku.constants import WIN

    config = load_default_config()
    config = replace(
        config,
        runtime=replace(config.runtime, compute_vcf=False, compute_vct=False),
    )

    for move_count, expected in [(25, (5, 8)), (31, (8, 11))]:
        board = Board()
        for x, y in _WIN_PRIORITY_BLUNDER_MOVES[:move_count]:
            board.play(xy_to_move(x, y))
        searcher = RootSearcher(config)
        result = searcher.search(board, SearchLimits(max_depth=4, root_width=20))
        assert move_to_xy(result.move) == expected, (
            f"wrong win-priority move after {move_count} moves"
        )
        assert result.score >= WIN
