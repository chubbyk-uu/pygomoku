"""Threat-focused board view and tactical helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from pygomoku.board import Board, move_to_xy, xy_to_move
from pygomoku.constants import BOARD_SIZE
from pygomoku.patterns.line import Line
from pygomoku.patterns.shapes import DIAGONAL_DOWN, DIAGONAL_UP, HORIZONTAL, VERTICAL
from pygomoku.threats.types import AttackMove, ThreatLevel

THREAT_DIRS: tuple[tuple[int, int], ...] = (
    (-2, -2), (-1, -1), (2, 2), (1, 1),
    (-2, 2), (-1, 1), (2, -2), (1, -1),
    (2, 0), (1, 0), (0, 2), (0, 1),
    (-2, 0), (-1, 0), (0, -2), (0, -1),
)

_THREAT_BOARD_BACKEND_MODE = os.getenv("PYSLOW_THREAT_BOARD_BACKEND", "auto").lower()
if _THREAT_BOARD_BACKEND_MODE != "python":
    try:
        from pygomoku.threats._threat_board_cy import build_views as _build_views_native
        from pygomoku.threats._threat_board_cy import broken_four_point_for_side_raw as _broken_four_point_for_side_native
        from pygomoku.threats._threat_board_cy import broken_four_reply_raw as _broken_four_reply_native
        from pygomoku.threats._threat_board_cy import threat_moves_grid as _threat_moves_native
        from pygomoku.threats._threat_board_cy import b4_count_raw as _b4_count_native
        from pygomoku.threats._threat_board_cy import has_a4_raw as _has_a4_native
        from pygomoku.threats._threat_board_cy import a3_gain_squares_raw as _a3_gain_squares_native
        from pygomoku.threats._threat_board_cy import a3r_count_raw as _a3r_count_native
    except ImportError:
        if _THREAT_BOARD_BACKEND_MODE == "cython":
            raise
        _build_views_native = None
        _broken_four_point_for_side_native = None
        _broken_four_reply_native = None
        _threat_moves_native = None
        _b4_count_native = None
        _has_a4_native = None
        _a3_gain_squares_native = None
        _a3r_count_native = None
else:
    _build_views_native = None
    _broken_four_point_for_side_native = None
    _broken_four_reply_native = None
    _threat_moves_native = None
    _b4_count_native = None
    _has_a4_native = None
    _a3_gain_squares_native = None
    _a3r_count_native = None


def _ga(value: int) -> int:
    return value & 0xFF


def _gb(value: int) -> int:
    return (value >> 8) & 0xFF


def _xy_order_key(move: int) -> tuple[int, int]:
    x, y = move_to_xy(move)
    return (x, y)


def _decode_line_move(board: Board, x: int, y: int, direction_index: int, encoded: int) -> int | None:
    raw = _ga(encoded)
    if direction_index == 1:
        tx, ty = x, raw
    elif direction_index == 2:
        tx, ty = raw, y
    elif direction_index == 3:
        tx, ty = x + y - raw, raw
    elif direction_index == 4:
        tx, ty = board.size - 1 + x - y - raw, board.size - 1 - raw
    else:
        return None
    if 0 <= tx < board.size and 0 <= ty < board.size:
        return xy_to_move(tx, ty)
    return None


@dataclass
class ThreatBoardView:
    board: Board
    x1: list[list[int]]
    x2: list[list[int]]
    x3: list[list[int]]
    x4: list[list[int]]
    _previous_sides: list[int] = field(default_factory=list)

    @classmethod
    def from_board(cls, board: Board) -> "ThreatBoardView":
        size = board.size
        grid = board.grid
        if _build_views_native is not None:
            x1, x2, x3, x4 = _build_views_native(grid, size)
            return cls(board=board, x1=x1, x2=x2, x3=x3, x4=x4)
        x1 = [[grid[y][x] for y in range(size)] for x in range(size)]
        x2 = [[grid[y][x] for x in range(size)] for y in range(size)]
        width = 2 * board.size - 1
        x3 = [[1024 for _ in range(size)] for _ in range(width)]
        x4 = [[1024 for _ in range(size)] for _ in range(width)]
        for p in range(width):
            if p < size:
                for i in range(p + 1):
                    x3[p][i] = grid[i][p - i]
                    x4[p][i] = grid[size - 1 - i][p - i]
            else:
                for i in range(p - size + 1, size):
                    x3[p][i] = grid[i][p - i]
                    x4[p][i] = grid[size - 1 - i][p - i]
        return cls(board=board, x1=x1, x2=x2, x3=x3, x4=x4)

    def _lines_for(self, x: int, y: int) -> tuple[Line, Line, Line, Line, int, int, int, int]:
        def _pad(values: list[int]) -> list[int]:
            return [1024, 1024, *values, 1024, 1024]

        return (
            Line(_pad(self.x1[x][:])),
            Line(_pad(self.x2[y][:])),
            Line(_pad(self.x3[x + y][:])),
            Line(_pad(self.x4[BOARD_SIZE - 1 - y + x][:])),
            y,
            x,
            y,
            BOARD_SIZE - 1 - y,
        )

    def _set_point(self, x: int, y: int, value: int) -> None:
        self.x1[x][y] = value
        self.x2[y][x] = value
        self.x3[x + y][y] = value
        self.x4[BOARD_SIZE - 1 - y + x][BOARD_SIZE - 1 - y] = value

    def play(self, move: int, side: int) -> None:
        previous_side = self.board.side_to_move
        self._previous_sides.append(previous_side)
        if previous_side != side:
            self.board.zobrist_key ^= self.board.zobrist_table.key_for_turn()
            self.board.side_to_move = side
        self.board.play(move, side)
        x, y = move_to_xy(move)
        self._set_point(x, y, side)

    def undo(self) -> None:
        previous_side = self._previous_sides.pop()
        played = self.board.undo()
        if self.board.side_to_move != previous_side:
            self.board.zobrist_key ^= self.board.zobrist_table.key_for_turn()
            self.board.side_to_move = previous_side
        x, y = move_to_xy(played.move)
        self._set_point(x, y, 0)

    def threat_moves(self, side: int) -> tuple[int, ...]:
        size = self.board.size
        grid = self.board.grid
        if _threat_moves_native is not None:
            return _threat_moves_native(grid, side, size)
        candidates: list[int] = []
        for x in range(size):
            for y in range(size):
                if grid[y][x] != 0:
                    continue
                for dx, dy in THREAT_DIRS:
                    xx = x + dx
                    yy = y + dy
                    if 0 <= xx < size and 0 <= yy < size and grid[yy][xx] == side:
                        candidates.append(xy_to_move(x, y))
                        break
        return tuple(candidates)

    def has_a4(self, x: int, y: int) -> bool:
        if _has_a4_native is not None:
            return _has_a4_native(self.x1, self.x2, self.x3, self.x4, x, y, self.board.size)
        l1, l2, l3, l4, p1, p2, p3, p4 = self._lines_for(x, y)
        return bool(l1.a4(p1) or l2.a4(p2) or l3.a4(p3) or l4.a4(p4))

    def has_a6(self, x: int, y: int) -> bool:
        if self.board.grid[y][x] == 0:
            return False
        l1, l2, l3, l4, p1, p2, p3, p4 = self._lines_for(x, y)
        return bool(l1.a6(p1) or l2.a6(p2) or l3.a6(p3) or l4.a6(p4))

    def has_a5(self, x: int, y: int) -> bool:
        if self.board.grid[y][x] == 0:
            return False
        l1, l2, l3, l4, p1, p2, p3, p4 = self._lines_for(x, y)
        return bool(l1.a5(p1) or l2.a5(p2) or l3.a5(p3) or l4.a5(p4))

    def a5test(self, x: int, y: int, side: int) -> bool:
        point = self.board.grid[y][x]
        if point == side:
            return self.has_a5(x, y)
        if point != 0:
            return False
        move = xy_to_move(x, y)
        self.play(move, side)
        try:
            return self.has_a5(x, y)
        finally:
            self.undo()

    def b4_count(self, x: int, y: int) -> int:
        if self.board.grid[y][x] == 0:
            return 0
        if _b4_count_native is not None:
            return _b4_count_native(self.x1, self.x2, self.x3, self.x4, x, y, self.board.size)
        l1, l2, l3, l4, p1, p2, p3, p4 = self._lines_for(x, y)
        return l1.b4(p1) + l2.b4(p2) + l3.b4(p3) + l4.b4(p4)

    def a3r_count(self, x: int, y: int) -> int:
        point = self.board.grid[y][x]
        if point == 0:
            return 0
        side = point
        if _a3r_count_native is not None:
            return _a3r_count_native(self.x1, self.x2, self.x3, self.x4, x, y, self.board.size)
        l1, l2, l3, l4, p1, p2, p3, p4 = self._lines_for(x, y)
        count = 0
        line_specs = (
            (l1, p1, lambda r: (x, r)),
            (l2, p2, lambda r: (r, y)),
            (l3, p3, lambda r: (x + y - r, r)),
            (l4, p4, lambda r: (BOARD_SIZE - 1 + x - y - r, BOARD_SIZE - 1 - r)),
        )
        for line, point_index, decode in line_specs:
            encoded = line.a3(point_index)
            if encoded <= 0:
                continue
            if encoded < 65536:
                rx, ry = decode(_ga(encoded))
                if side == 1 and self.a5test(rx, ry, side):
                    count -= 1
                count += 1
                continue
            r1x, r1y = decode(_ga(encoded))
            r2x, r2y = decode(_gb(encoded))
            if side == 1 and self.a5test(r1x, r1y, side) and self.a5test(r2x, r2y, side):
                count -= 1
            count += 1
        return count

    def is_double4(self, x: int, y: int) -> bool:
        return self.b4_count(x, y) >= 2

    def is_double3r(self, x: int, y: int) -> bool:
        return self.a3r_count(x, y) >= 2

    def broken_four_reply(self, x: int, y: int) -> int | None:
        move, _ = self._broken_four_reply_with_ambiguity(x, y)
        return move

    def _broken_four_reply_with_ambiguity(self, x: int, y: int) -> tuple[int | None, bool]:
        if _broken_four_reply_native is not None and "_lines_for" not in self.__dict__:
            reply, ambiguous = _broken_four_reply_native(self.x1, self.x2, self.x3, self.x4, x, y, self.board.size)
            return (None if reply < 0 else reply, bool(ambiguous))

        l1, l2, l3, l4, p1, p2, p3, p4 = self._lines_for(x, y)
        counts = (
            l1.b4p(p1),
            l2.b4p(p2),
            l3.b4p(p3),
            l4.b4p(p4),
        )
        directions = (1, 2, 3, 4)

        for encoded, direction in zip(counts, directions, strict=True):
            if encoded >= (1 << 16):
                return _decode_line_move(self.board, x, y, direction, encoded), True

        mask = 0
        for index, encoded in enumerate(counts):
            if encoded:
                mask |= 1 << index

        if mask == 0:
            return None, False
        if mask == 1:
            return _decode_line_move(self.board, x, y, 1, counts[0]), False
        if mask == 2:
            return _decode_line_move(self.board, x, y, 2, counts[1]), False
        if mask == 4:
            return _decode_line_move(self.board, x, y, 3, counts[2]), False
        if mask == 8:
            return _decode_line_move(self.board, x, y, 4, counts[3]), False
        if mask in (3, 5, 7, 9, 11, 13, 15):
            return _decode_line_move(self.board, x, y, 1, counts[0]), True
        if mask in (6, 10, 14):
            return _decode_line_move(self.board, x, y, 2, counts[1]), True
        if mask == 12:
            return _decode_line_move(self.board, x, y, 3, counts[2]), True
        return None, False

    def broken_four_point_for_side(self, side: int) -> tuple[int | None, bool]:
        if _broken_four_point_for_side_native is not None and "_broken_four_reply_with_ambiguity" not in self.__dict__:
            reply, ambiguous = _broken_four_point_for_side_native(
                self.board.grid,
                self.x1,
                self.x2,
                self.x3,
                self.x4,
                side,
                self.board.size,
            )
            return (None if reply < 0 else reply, bool(ambiguous))

        grid = self.board.grid
        size = self.board.size
        first_reply: int | None = None
        for x in range(size):
            for y in range(size):
                if grid[y][x] != side:
                    continue
                reply, local_ambiguous = self._broken_four_reply_with_ambiguity(x, y)
                if reply is None:
                    continue
                if local_ambiguous:
                    return reply, True
                if first_reply is None:
                    first_reply = reply
                elif reply != first_reply:
                    return reply, True
        if first_reply is None:
            return None, False
        return first_reply, False

    def a3_gain_squares(self, x: int, y: int) -> tuple[int, ...]:
        """Gain squares for all A3 patterns of the stone currently at (x, y).

        Gain squares are the empty cells where the attacker would extend the A3
        to create an A4 (open four).  Call this after playing the stone.
        """
        if _a3_gain_squares_native is not None:
            return _a3_gain_squares_native(self.x1, self.x2, self.x3, self.x4, x, y, self.board.size)
        l1, l2, l3, l4, p1, p2, p3, p4 = self._lines_for(x, y)
        size = self.board.size
        line_specs = (
            (l1, p1, lambda r: (x, r)),
            (l2, p2, lambda r: (r, y)),
            (l3, p3, lambda r: (x + y - r, r)),
            (l4, p4, lambda r: (BOARD_SIZE - 1 + x - y - r, BOARD_SIZE - 1 - r)),
        )
        seen: set[int] = set()
        gains: list[int] = []
        for line, pi, decode in line_specs:
            encoded = line.a3(pi)
            if encoded <= 0:
                continue
            raws = [_ga(encoded)]
            if encoded >= 65536:
                raws.append(_gb(encoded))
            for raw in raws:
                gx, gy = decode(raw)
                if 0 <= gx < size and 0 <= gy < size:
                    m = xy_to_move(gx, gy)
                    if m not in seen:
                        seen.add(m)
                        gains.append(m)
        return tuple(gains)

    def classify_attack_at(self, x: int, y: int, attacker: int, move: int) -> AttackMove | None:
        """Classify the threat created by a stone just placed at (x, y).

        Returns an AttackMove describing the strongest threat the stone creates,
        or None if it creates no forcing threat (A3 or stronger).
        """
        if self.board.winner == attacker:
            return AttackMove(move, ThreatLevel.WIN5, ())
        if self.has_a4(x, y):
            return AttackMove(move, ThreatLevel.A4, ())
        # Use _broken_four_reply_with_ambiguity to detect double-B4 (ambiguous)
        # which means the opponent cannot respond to both → treat as A4.
        reply, ambiguous = self._broken_four_reply_with_ambiguity(x, y)
        if ambiguous:
            return AttackMove(move, ThreatLevel.A4, ())
        if reply is not None:
            if self.board.is_legal_move(reply):
                return AttackMove(move, ThreatLevel.B4, (reply,))
            # Reply square occupied: shouldn't happen in normal play; treat as A4.
            return AttackMove(move, ThreatLevel.A4, ())
        gains = self.a3_gain_squares(x, y)
        legal = tuple(g for g in gains if self.board.is_legal_move(g))
        if legal:
            return AttackMove(move, ThreatLevel.A3, legal)
        return None

    def collect_attack_moves(self, attacker: int) -> tuple[AttackMove, ...]:
        """Return all forcing attack moves for *attacker*, sorted strongest first.

        Considers all candidate squares near existing stones (from threat_moves),
        trial-plays each, and classifies the resulting threat.
        """
        attacks: list[AttackMove] = []
        for move in self.threat_moves(attacker):
            if not self.board.is_legal_move(move):
                continue
            self.play(move, attacker)
            x, y = move_to_xy(move)
            attack = self.classify_attack_at(x, y, attacker, move)
            self.undo()
            if attack is not None:
                attacks.append(attack)
        attacks.sort(key=lambda a: -a.level.value)
        return tuple(attacks)

    def winning_threat_moves(self, side: int) -> tuple[int, ...]:
        wins: list[int] = []
        for move in self.threat_moves(side):
            self.play(move, side)
            x, y = move_to_xy(move)
            if self.board.winner == side or self.has_a4(x, y):
                wins.append(move)
            self.undo()
        return tuple(wins)

    def forcing_threat_moves(self, side: int) -> tuple[int, ...]:
        forcing: list[int] = []
        for move in self.threat_moves(side):
            self.play(move, side)
            x, y = move_to_xy(move)
            if self.broken_four_reply(x, y) is not None:
                forcing.append(move)
            self.undo()
        return tuple(forcing)


def has_vct_trigger(board: Board, side: int) -> bool:
    """Return True if *side* has a forcing threat worth exploring with VCT.

    Fires on:
      - Any move creating B4, A4, or WIN5 (direct forcing chain).
      - Any move creating dual-A3 in two different directions simultaneously
        (combination threat — neither alone is immediately forcing, but
        the defender cannot address both at once).
    """
    view = ThreatBoardView.from_board(board)
    for move in view.threat_moves(side):
        if not board.is_legal_move(move):
            continue
        view.play(move, side)
        x, y = move_to_xy(move)
        # B4 / A4 / WIN5 — any directly forcing pattern
        is_b4_plus = (
            view.board.winner == side
            or view.has_a4(x, y)
            or view.b4_count(x, y) >= 1
        )
        # Dual-A3: the move creates open-three patterns in ≥ 2 directions
        is_dual_a3 = not is_b4_plus and view.a3r_count(x, y) >= 2
        view.undo()
        if is_b4_plus or is_dual_a3:
            return True
    return False


def threat_moves(board: Board, side: int) -> tuple[int, ...]:
    return ThreatBoardView.from_board(board).threat_moves(side)


def has_open_four(board: Board, x: int, y: int) -> bool:
    return ThreatBoardView.from_board(board).has_a4(x, y)


def broken_four_reply(board: Board, x: int, y: int) -> int | None:
    return ThreatBoardView.from_board(board).broken_four_reply(x, y)


def winning_threat_moves(board: Board, side: int) -> tuple[int, ...]:
    return ThreatBoardView.from_board(board).winning_threat_moves(side)


def forcing_threat_moves(board: Board, side: int) -> tuple[int, ...]:
    return ThreatBoardView.from_board(board).forcing_threat_moves(side)
