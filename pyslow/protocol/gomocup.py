"""Gomocup protocol adapter."""

from __future__ import annotations

from dataclasses import replace

from pyslow.board import Board, xy_to_move
from pyslow.config import EngineConfig, RuntimeOptions, load_default_config
from pyslow.search.root import RootSearcher, SearchLimits


ABOUT_TEXT = (
    'name="pyslow", version="0.1", author="OpenAI", country="China", '
    'www="https://example.invalid/"'
)


class GomocupProtocol:
    def __init__(self, config: EngineConfig | None = None, search_limits: SearchLimits | None = None) -> None:
        self.config = config or load_default_config()
        self.default_limits = search_limits
        self.board = Board()
        self.searcher = RootSearcher(self.config)
        self.board_mode = False
        self.board_lines: list[tuple[int, int, int]] = []
        self.timeout_turn_ms: float | None = None
        self.time_left_ms: float | None = None
        self.node_limit: int | None = None
        self.ended = False

    def handle_line(self, line: str) -> list[str]:
        raw = line.strip()
        if not raw:
            return []

        if self.board_mode:
            if raw.upper() == "DONE":
                self.board_mode = False
                return self._handle_board_done()
            parts = raw.split(",")
            if len(parts) != 3:
                return ["ERROR Board format error."]
            x, y, side = (int(part.strip()) for part in parts)
            self.board_lines.append((x, y, side))
            return []

        parts = raw.split()
        command = parts[0].upper()

        if command == "START":
            if len(parts) != 2:
                return ["ERROR Size error."]
            size = int(parts[1])
            if size != 15:
                return ["ERROR Size error."]
            self._reset_engine()
            return ["OK"]

        if command == "RECTSTART":
            if len(parts) != 2 or "," not in parts[1]:
                return ["ERROR Size error."]
            sx, sy = (int(part) for part in parts[1].split(",", 1))
            if sx != 15 or sy != 15:
                return ["ERROR Size error."]
            self._reset_engine()
            return ["OK"]

        if command == "RESTART":
            self._reset_engine()
            return ["OK"]

        if command == "BEGIN":
            return [self._search_move()]

        if command == "TURN":
            if len(parts) != 2 or "," not in parts[1]:
                return ["ERROR Turn format error."]
            x, y = (int(part) for part in parts[1].split(",", 1))
            move = xy_to_move(x, y)
            if not self.board.is_legal_move(move):
                return ["ERROR Illegal move."]
            self._play_xy(x, y, self.board.side_to_move)
            return [self._search_move()]

        if command == "BOARD":
            self.board_mode = True
            self.board_lines.clear()
            return []

        if command == "INFO":
            self._handle_info(parts[1:])
            return []

        if command == "TAKEBACK":
            if not self.board.move_history:
                return ["ERROR Takeback error."]
            self.board.undo()
            return ["OK"]

        if command == "ABOUT":
            return [ABOUT_TEXT]

        if command == "END":
            self.ended = True
            return []

        return [f"UNKNOWN {command}"]

    def _reset_engine(self) -> None:
        self.board = Board()
        self.searcher = RootSearcher(self.config)
        self.board_mode = False
        self.board_lines.clear()

    def _play_xy(self, x: int, y: int, side: int) -> None:
        self.board.side_to_move = side
        self.board.play(xy_to_move(x, y), side)

    def _handle_board_done(self) -> list[str]:
        black_moves = [(x, y) for x, y, side in self.board_lines if side == 1]
        white_moves = [(x, y) for x, y, side in self.board_lines if side != 1]
        if not (len(black_moves) == len(white_moves) or len(black_moves) == len(white_moves) + 1):
            self.board_lines.clear()
            return ["ERROR Board error."]

        self.board = Board()
        move_pairs: list[tuple[int, int, int]] = []
        move_pairs.extend((x, y, 1) for x, y in black_moves)
        move_pairs.extend((x, y, -1) for x, y in white_moves)
        move_pairs.sort(key=lambda item: (0 if item[2] == 1 else 1, item[1], item[0]))

        for idx in range(max(len(black_moves), len(white_moves))):
            if idx < len(black_moves):
                x, y = black_moves[idx]
                self._play_xy(x, y, 1)
            if idx < len(white_moves):
                x, y = white_moves[idx]
                self._play_xy(x, y, -1)

        self.board_lines.clear()
        return [self._search_move()]

    def _handle_info(self, args: list[str]) -> None:
        if len(args) < 2:
            return
        key = args[0].lower()
        value = args[1]
        if key == "timeout_turn":
            parsed = float(value)
            self.timeout_turn_ms = 200.0 if parsed == 0 else parsed
        elif key == "timeout_match":
            parsed = float(value)
            self.time_left_ms = 99999999.0 if parsed == 0 else parsed
        elif key == "time_left":
            self.time_left_ms = float(value)
        elif key == "max_node":
            parsed = int(value)
            self.node_limit = None if parsed <= 0 else parsed
        elif key == "compute_vcf":
            runtime = replace(self.config.runtime, compute_vcf=bool(int(value)))
            self.config = replace(self.config, runtime=runtime)
            self.searcher = RootSearcher(self.config)
        elif key == "static":
            runtime = replace(self.config.runtime, static_board=bool(int(value) % 2))
            self.config = replace(self.config, runtime=runtime)
            self.searcher = RootSearcher(self.config)

    def _search_move(self) -> str:
        if self.default_limits is None:
            limits = SearchLimits(
                max_depth=self.config.root_search.depth,
                root_width=self.config.root_search.wide,
                node_limit=self.node_limit,
                time_limit_ms=self.timeout_turn_ms or self.time_left_ms,
            )
        else:
            limits = SearchLimits(
                max_depth=self.default_limits.max_depth,
                root_width=self.default_limits.root_width,
                node_limit=self.node_limit if self.node_limit is not None else self.default_limits.node_limit,
                time_limit_ms=self.timeout_turn_ms or self.time_left_ms or self.default_limits.time_limit_ms,
            )
        result = self.searcher.search(self.board, limits)
        move = result.move
        if not self.board.is_legal_move(move):
            legal_moves = [move for move in range(self.board.size * self.board.size) if self.board.is_legal_move(move)]
            if not legal_moves:
                raise ValueError("engine produced no legal move on non-terminal board")
            move = legal_moves[0]
        x = move % self.board.size
        y = move // self.board.size
        self._play_xy(x, y, self.board.side_to_move)
        return f"{x},{y}"
