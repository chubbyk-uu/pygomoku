"""GUI helper tests that do not require pygame."""

import time
from pyslow.constants import BLACK, WHITE
from pyslow.gui import GomokuGuiApp, GuiLayout, compute_undo_steps, default_search_limits, pixel_to_cell


def test_default_gui_search_limits_match_current_playable_settings() -> None:
    limits = default_search_limits()
    assert limits.max_depth == 5
    assert limits.root_width == 10


def test_compute_undo_steps_rewinds_full_pair_after_ai_move() -> None:
    assert compute_undo_steps([BLACK, WHITE], BLACK) == 2
    assert compute_undo_steps([BLACK, WHITE, BLACK], WHITE) == 2


def test_compute_undo_steps_rewinds_single_move_when_last_move_is_human() -> None:
    assert compute_undo_steps([BLACK], BLACK) == 1
    assert compute_undo_steps([BLACK, WHITE, BLACK], BLACK) == 1


def test_pixel_to_cell_maps_board_centers() -> None:
    layout = GuiLayout()
    pos = (layout.left_margin + 7 * layout.cell_size, layout.top_margin + 8 * layout.cell_size)
    assert pixel_to_cell(pos, layout) == (7, 8)


def test_pixel_to_cell_rejects_outside_positions() -> None:
    layout = GuiLayout()
    assert pixel_to_cell((10, 10), layout) is None


def test_gui_app_white_start_receives_engine_opening_move() -> None:
    app = GomokuGuiApp(depth=2, width=8)
    try:
        app.start_game(WHITE)
        deadline = time.time() + 3.0
        while app.engine_busy and time.time() < deadline:
            app.poll_engine()
            time.sleep(0.01)
        assert not app.engine_busy
        assert len(app.board.move_history) == 1
    finally:
        app.close()


def test_gui_app_black_move_receives_engine_reply() -> None:
    app = GomokuGuiApp(depth=2, width=8)
    try:
        app.start_game(BLACK)
        assert app.human_play(7, 7)
        deadline = time.time() + 3.0
        while app.engine_busy and time.time() < deadline:
            app.poll_engine()
            time.sleep(0.01)
        assert not app.engine_busy
        assert len(app.board.move_history) == 2
    finally:
        app.close()


def test_gui_replay_black_sequence_does_not_stick_busy() -> None:
    app = GomokuGuiApp(depth=2, width=8)
    black_moves = [(7, 7), (7, 5), (8, 7), (6, 6), (8, 5), (8, 6)]
    try:
        app.start_game(BLACK)
        for xy in black_moves:
            if not app.human_play(*xy):
                break
            deadline = time.time() + 3.0
            while app.engine_busy and time.time() < deadline:
                app.poll_engine()
                time.sleep(0.01)
            assert not app.engine_busy
            if app.board.winner != 0:
                break
        assert not app.engine_busy
        assert app.board.winner != 0 or len(app.board.move_history) >= 2
    finally:
        app.close()


def test_poll_engine_clears_busy_on_error_response() -> None:
    app = GomokuGuiApp()
    try:
        app.engine_busy = True
        app.engine = type(
            "FakeEngine",
            (),
            {
                "poll": lambda self: [(app._engine_generation, "error", "boom")],
                "close": lambda self: None,
            },
        )()
        app.poll_engine()
        assert not app.engine_busy
        assert app.status_text == "Engine error: boom"
    finally:
        app.close()
