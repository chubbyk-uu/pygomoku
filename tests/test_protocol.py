"""Protocol tests."""

from pyslow.protocol.gomocup import GomocupProtocol
from pyslow.search.root import SearchLimits


def _proto() -> GomocupProtocol:
    return GomocupProtocol(search_limits=SearchLimits(max_depth=2, root_width=8))


def test_protocol_start_accepts_15() -> None:
    proto = _proto()
    assert proto.handle_line("START 15") == ["OK"]


def test_protocol_start_rejects_other_sizes() -> None:
    proto = _proto()
    assert proto.handle_line("START 20") == ["ERROR Size error."]


def test_protocol_begin_returns_move() -> None:
    proto = _proto()
    proto.handle_line("START 15")
    response = proto.handle_line("BEGIN")
    assert response == ["7,7"]


def test_protocol_turn_returns_move() -> None:
    proto = _proto()
    proto.handle_line("START 15")
    response = proto.handle_line("TURN 7,7")
    assert len(response) == 1
    assert "," in response[0]


def test_protocol_turn_rejects_illegal_repeat_move() -> None:
    proto = _proto()
    proto.handle_line("START 15")
    proto.handle_line("TURN 7,7")
    assert proto.handle_line("TURN 7,7") == ["ERROR Illegal move."]


def test_protocol_about_returns_metadata() -> None:
    proto = _proto()
    response = proto.handle_line("ABOUT")
    assert len(response) == 1
    assert 'name="pyslow"' in response[0]


def test_protocol_takeback_undoes_last_move() -> None:
    proto = _proto()
    proto.handle_line("START 15")
    proto.handle_line("BEGIN")
    assert proto.handle_line("TAKEBACK") == ["OK"]


def test_protocol_board_mode_reconstructs_position() -> None:
    proto = _proto()
    proto.handle_line("START 15")
    assert proto.handle_line("BOARD") == []
    assert proto.handle_line("7,7,1") == []
    assert proto.handle_line("6,7,2") == []
    response = proto.handle_line("DONE")
    assert len(response) == 1
    assert "," in response[0]


def test_protocol_board_mode_reconstructs_interleaved_color_order_like_reference() -> None:
    proto = _proto()
    proto.handle_line("START 15")
    proto.handle_line("BOARD")
    for line in ("7,7,1", "5,5,2", "6,7,1", "5,6,2"):
        assert proto.handle_line(line) == []
    proto.handle_line("DONE")
    assert [(entry.move % 15, entry.move // 15, entry.side) for entry in proto.board.move_history[:4]] == [
        (7, 7, 1),
        (5, 5, -1),
        (6, 7, 1),
        (5, 6, -1),
    ]


def test_protocol_info_static_updates_runtime() -> None:
    proto = _proto()
    proto.handle_line("INFO static 0")
    assert not proto.config.runtime.static_board


def test_protocol_info_compute_vcf_updates_runtime() -> None:
    proto = _proto()
    proto.handle_line("INFO compute_vcf 0")
    assert not proto.config.runtime.compute_vcf


def test_protocol_info_max_node_zero_means_unlimited() -> None:
    proto = _proto()
    proto.handle_line("INFO max_node 0")
    assert proto.node_limit is None


def test_protocol_info_timeout_turn_zero_matches_reference_floor() -> None:
    proto = _proto()
    proto.handle_line("INFO timeout_turn 0")
    assert proto.timeout_turn_ms == 200.0


def test_protocol_info_timeout_match_zero_matches_reference_large_default() -> None:
    proto = _proto()
    proto.handle_line("INFO timeout_match 0")
    assert proto.time_left_ms == 99999999.0


def test_protocol_search_move_falls_back_if_engine_returns_illegal_move(monkeypatch) -> None:
    proto = _proto()
    proto.handle_line("START 15")
    proto.board.play(112)

    class FakeResult:
        def __init__(self) -> None:
            self.move = 112
            self.score = 0
            self.depth = 1
            self.nodes = 1

    monkeypatch.setattr(proto.searcher, "search", lambda board, limits: FakeResult())
    response = proto._search_move()
    assert response != "7,7"
