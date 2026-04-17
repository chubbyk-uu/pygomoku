"""Gomocup protocol adapter."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, TypeVar

from pygomoku.board import Board, xy_to_move
from pygomoku.config import EngineConfig, load_default_config
from pygomoku.search.root import RootSearcher, SearchLimits


ABOUT_TEXT = (
    'name="pygomoku", version="0.1", author="OpenAI", country="China", '
    'www="https://example.invalid/"'
)

_T = TypeVar("_T")


class GomocupProtocol:
    def __init__(self, config: EngineConfig | None = None, search_limits: SearchLimits | None = None) -> None:
        self.config = config or load_default_config()
        self.default_limits = search_limits
        self.board = Board()
        self._searcher: RootSearcher | None = None
        self.board_mode = False
        self.board_lines: list[tuple[int, int, int]] = []
        self.timeout_turn_ms: float | None = None
        self.time_left_ms: float | None = None
        self.node_limit: int | None = None
        self.ended = False

    @property
    def searcher(self) -> RootSearcher:
        if self._searcher is None:
            self._searcher = RootSearcher(self.config)
        return self._searcher

    @searcher.setter
    def searcher(self, value: RootSearcher) -> None:
        self._searcher = value

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
            parsed = self._parse_many(parts, int)
            if parsed is None:
                return ["ERROR Board format error."]
            x, y, side = parsed
            if not self._in_bounds(x, y):
                return ["ERROR Board format error."]
            self.board_lines.append((x, y, side))
            return []

        parts = raw.split()
        command = parts[0].upper()

        if command == "START":
            if len(parts) != 2:
                return ["ERROR Size error."]
            size = self._parse_one(parts[1], int)
            if size is None:
                return ["ERROR Size error."]
            if size != 15:
                return ["ERROR Size error."]
            self._reset_engine()
            return ["OK"]

        if command == "RECTSTART":
            if len(parts) != 2 or "," not in parts[1]:
                return ["ERROR Size error."]
            parsed = self._parse_many(parts[1].split(",", 1), int)
            if parsed is None:
                return ["ERROR Size error."]
            sx, sy = parsed
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
            parsed = self._parse_many(parts[1].split(",", 1), int)
            if parsed is None:
                return ["ERROR Turn format error."]
            x, y = parsed
            try:
                move = xy_to_move(x, y)
            except ValueError:
                return ["ERROR Turn format error."]
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
            if self.board.move_history:
                self.board.undo()
            return ["OK"]

        if command == "ABOUT":
            return [ABOUT_TEXT]

        if command == "END":
            self.ended = True
            return []

        return []

    def _reset_engine(self) -> None:
        self.board = Board()
        self._searcher = None
        self.board_mode = False
        self.board_lines.clear()

    @staticmethod
    def _parse_one(raw: str, parser: Callable[[str], _T]) -> _T | None:
        try:
            return parser(raw)
        except ValueError:
            return None

    @classmethod
    def _parse_many(cls, values: list[str], parser: Callable[[str], _T]) -> tuple[_T, ...] | None:
        parsed: list[_T] = []
        for value in values:
            item = cls._parse_one(value.strip(), parser)
            if item is None:
                return None
            parsed.append(item)
        return tuple(parsed)

    @staticmethod
    def _in_bounds(x: int, y: int) -> bool:
        return 0 <= x < 15 and 0 <= y < 15

    def _play_xy(self, x: int, y: int, side: int) -> None:
        self.board.side_to_move = side
        self.board.play(xy_to_move(x, y), side)

    def _handle_board_done(self) -> list[str]:
        black_moves = [(x, y) for x, y, side in self.board_lines if side == 1]
        white_moves = [(x, y) for x, y, side in self.board_lines if side != 1]
        sfn = len(black_moves)
        opn = len(white_moves)

        if sfn == opn:
            # Engine plays as black (side 1, first mover)
            first_side_moves = black_moves
            second_side_moves = white_moves
        elif sfn == opn - 1:
            # Engine plays as white (side -1, second mover)
            # Here `sfn==opn-1` means the opponent (white/side=2) moved first.
            first_side_moves = white_moves
            second_side_moves = black_moves
        else:
            self.board_lines.clear()
            return ["ERROR Board error."]

        self.board = Board()
        try:
            for idx in range(max(len(first_side_moves), len(second_side_moves))):
                if idx < len(first_side_moves):
                    x, y = first_side_moves[idx]
                    self._play_xy(x, y, self.board.side_to_move)
                if idx < len(second_side_moves):
                    x, y = second_side_moves[idx]
                    self._play_xy(x, y, self.board.side_to_move)
        except ValueError:
            self.board = Board()
            self.board_lines.clear()
            return ["ERROR Board error."]

        self.board_lines.clear()
        return [self._search_move()]

    def _handle_info(self, args: list[str]) -> None:
        if len(args) < 2:
            return
        key = args[0].lower()
        value = args[1]
        if key == "timeout_turn":
            parsed = self._parse_one(value, float)
            if parsed is None:
                return
            self.timeout_turn_ms = 200.0 if parsed == 0 else parsed
        elif key == "timeout_match":
            parsed = self._parse_one(value, float)
            if parsed is None:
                return
            self.time_left_ms = 99999999.0 if parsed == 0 else parsed
        elif key == "time_left":
            parsed = self._parse_one(value, float)
            if parsed is None:
                return
            self.time_left_ms = parsed
        elif key == "max_node":
            parsed = self._parse_one(value, int)
            if parsed is None:
                return
            self.node_limit = None if parsed <= 0 else parsed
        elif key == "compute_vcf":
            parsed = self._parse_one(value, int)
            if parsed is None:
                return
            runtime = replace(self.config.runtime, compute_vcf=bool(parsed))
            self.config = replace(self.config, runtime=runtime)
            self._searcher = None
        elif key == "static":
            parsed = self._parse_one(value, int)
            if parsed is None:
                return
            runtime = replace(self.config.runtime, static_board=bool(parsed % 2))
            self.config = replace(self.config, runtime=runtime)
            self._searcher = None

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
