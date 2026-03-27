"""Search regression tests."""

from dataclasses import replace

from benchmarks.alignment_compare import POSITIONS
from pyslow.board import Board, move_to_xy, xy_to_move
from pyslow.config import load_default_config
from pyslow.eval.caches import EvalCaches
from pyslow.eval.local import recompute_all
from pyslow.search.alphabeta import AlphaBetaSearcher, SearchStats, _rootbonus
from pyslow.constants import HASHF_ALPHA, INF
from pyslow.search.root import RootSearcher, SearchLimits, _fallback_ai_move, _new_reference_fallback_rng
from pyslow.search.tt import TTEntry


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


def test_root_search_matches_reference_one_move_reply() -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    searcher = RootSearcher(load_default_config())
    result = searcher.search(board, SearchLimits(max_depth=3, root_width=8))
    assert move_to_xy(result.move) == (7, 4)
    assert result.score == -12


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


def test_root_allowed_moves_expand_to_square_window_like_reference() -> None:
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
    assert _rootbonus(board, 1, 1) > _rootbonus(board, 7, 7)


def test_rootbonus_corner_mode_still_rewards_near_edge_moves() -> None:
    board = Board()
    board.play(xy_to_move(0, 0))
    board.play(xy_to_move(14, 14))
    assert _rootbonus(board, 1, 1) > 0


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


def test_root_single_safe_move_matches_reference_score_semantics(monkeypatch) -> None:
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
    expected = _fallback_ai_move(board, caches, board.side_to_move, rng=_new_reference_fallback_rng())

    result = searcher.search(board, SearchLimits(max_depth=4, root_width=8))
    assert result.score == -INF
    assert result.depth == 0
    assert result.move == expected


def test_fallback_ai_move_uses_reference_seeded_tie_break() -> None:
    board = Board()
    for x, y, side in POSITIONS["tact_defend4"]:
        board.play(xy_to_move(x, y), side)
    caches = EvalCaches()
    recompute_all(board, caches)
    move_a = _fallback_ai_move(board, caches, board.side_to_move, rng=_new_reference_fallback_rng())
    move_b = _fallback_ai_move(board, caches, board.side_to_move, rng=_new_reference_fallback_rng())
    assert move_a == move_b
    assert move_to_xy(move_a) == (6, 7)


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


def test_root_iteration_budget_expands_when_line_is_unstable() -> None:
    budget = RootSearcher._iteration_budget_ms(30000.0, 10, 100, 20, 101, 101)
    assert budget == 30000.0 / 7.0 - 100.0


def test_root_iteration_budget_shrinks_when_line_is_stable() -> None:
    budget = RootSearcher._iteration_budget_ms(30000.0, 20, 100, 20, 100, 100)
    assert budget == 30000.0 / 15.0 - 100.0


def test_root_search_stops_early_under_time_budget(monkeypatch) -> None:
    board = Board()
    board.play(xy_to_move(7, 7))
    board.play(xy_to_move(6, 7))
    searcher = RootSearcher(load_default_config())

    timeline = iter([0.0, 0.03, 0.12])
    monkeypatch.setattr("pyslow.search.root.time.perf_counter", lambda: next(timeline))

    result = searcher.search(board, SearchLimits(max_depth=6, root_width=8, time_limit_ms=700.0))
    assert result.depth == 1


def test_root_search_uses_reference_ais_fallback_when_root_move_is_missing() -> None:
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
    assert move_to_xy(result.move) == (8, 4)


def test_root_search_matches_corrected_reference_on_simple_tt_alpha_seed() -> None:
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

    result = searcher.search(board, SearchLimits(max_depth=3, root_width=8))
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
        "pyslow.search.alphabeta.generate_candidates",
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


def test_alphabeta_leaf_matches_reference_sign_convention_on_simple_child_board() -> None:
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


def test_alphabeta_matches_reference_mid_ladder_nonroot_score() -> None:
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
    assert move_to_xy(move) == (7, 9)
    assert score == -47
