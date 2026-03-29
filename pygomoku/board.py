"""Board state and move application."""

from __future__ import annotations

from dataclasses import dataclass, field

from pygomoku.constants import BLACK, BOARD_AREA, BOARD_SIZE, EMPTY, WHITE
from pygomoku.types import Move, PlayedMove
from pygomoku.zobrist import DEFAULT_ZOBRIST, ZobristTable

_DIRECTIONS: tuple[tuple[int, int], ...] = ((1, 0), (0, 1), (1, 1), (1, -1))


def xy_to_move(x: int, y: int) -> Move:
    """Convert 0-based board coordinates to a flat move index."""
    if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
        raise ValueError(f"coordinates out of range: {(x, y)}")
    return y * BOARD_SIZE + x


def move_to_xy(move: Move) -> tuple[int, int]:
    """Convert a flat move index to 0-based board coordinates."""
    if not (0 <= move < BOARD_AREA):
        raise ValueError(f"move out of range: {move}")
    return move % BOARD_SIZE, move // BOARD_SIZE


@dataclass
class Board:
    """Freestyle 15x15 Gomoku board with deterministic make/unmake semantics."""

    size: int = BOARD_SIZE
    grid: list[list[int]] = field(
        default_factory=lambda: [[EMPTY for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    )
    move_history: list[PlayedMove] = field(default_factory=list)
    side_to_move: int = BLACK
    winner: int = EMPTY
    zobrist_table: ZobristTable = field(default_factory=lambda: DEFAULT_ZOBRIST)
    zobrist_key: int = 0

    def __post_init__(self) -> None:
        if self.size != BOARD_SIZE:
            raise ValueError(f"only {BOARD_SIZE}x{BOARD_SIZE} boards are supported")
        if len(self.grid) != self.size or any(len(row) != self.size for row in self.grid):
            raise ValueError("grid dimensions do not match board size")
        if self.side_to_move == WHITE and self.zobrist_key == 0 and not self.move_history:
            self.zobrist_key = self.zobrist_table.key_for_turn()

    @property
    def move_count(self) -> int:
        return len(self.move_history)

    def copy(self) -> "Board":
        return Board(
            size=self.size,
            grid=[row[:] for row in self.grid],
            move_history=self.move_history[:],
            side_to_move=self.side_to_move,
            winner=self.winner,
            zobrist_table=self.zobrist_table,
            zobrist_key=self.zobrist_key,
        )

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE

    def at(self, x: int, y: int) -> int:
        if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
            raise ValueError(f"coordinates out of range: {(x, y)}")
        return self.grid[y][x]

    def is_legal_move(self, move: Move) -> bool:
        if self.winner != EMPTY:
            return False
        if not (0 <= move < BOARD_AREA):
            return False
        x, y = move_to_xy(move)
        return self.grid[y][x] == EMPTY

    def play(self, move: Move, side: int | None = None) -> PlayedMove:
        if side is None:
            side = self.side_to_move
        if side not in (BLACK, WHITE):
            raise ValueError(f"invalid side: {side}")
        if side != self.side_to_move:
            raise ValueError(f"wrong side to move: expected {self.side_to_move}, got {side}")
        if not self.is_legal_move(move):
            raise ValueError(f"illegal move: {move}")

        x, y = move_to_xy(move)
        self.grid[y][x] = side
        played = PlayedMove(move=move, side=side)
        self.move_history.append(played)
        self.zobrist_key ^= self.zobrist_table.key_for_turn()
        self.zobrist_key ^= self.zobrist_table.key_for(move, side)
        if self._is_winning_move(x, y, side):
            self.winner = side
        self.side_to_move = -side
        return played

    def undo(self) -> PlayedMove:
        if not self.move_history:
            raise ValueError("cannot undo from empty history")
        played = self.move_history.pop()
        x, y = move_to_xy(played.move)
        self.grid[y][x] = EMPTY
        self.zobrist_key ^= self.zobrist_table.key_for(played.move, played.side)
        self.zobrist_key ^= self.zobrist_table.key_for_turn()
        self.side_to_move = played.side
        self.winner = EMPTY
        return played

    def replay(self, moves: list[Move], first_side: int = BLACK) -> None:
        self.reset()
        self.side_to_move = first_side
        for move in moves:
            self.play(move)

    def reset(self) -> None:
        for y in range(self.size):
            for x in range(self.size):
                self.grid[y][x] = EMPTY
        self.move_history.clear()
        self.side_to_move = BLACK
        self.winner = EMPTY
        self.zobrist_key = 0

    def occupied_moves(self) -> tuple[Move, ...]:
        return tuple(played.move for played in self.move_history)

    def _is_winning_move(self, x: int, y: int, side: int) -> bool:
        return any(self._count_aligned(x, y, side, dx, dy) >= 5 for dx, dy in _DIRECTIONS)

    def _count_aligned(self, x: int, y: int, side: int, dx: int, dy: int) -> int:
        total = 1
        total += self._count_one_side(x, y, side, dx, dy)
        total += self._count_one_side(x, y, side, -dx, -dy)
        return total

    def _count_one_side(self, x: int, y: int, side: int, dx: int, dy: int) -> int:
        count = 0
        cx = x + dx
        cy = y + dy
        grid = self.grid
        while 0 <= cx < BOARD_SIZE and 0 <= cy < BOARD_SIZE and grid[cy][cx] == side:
            count += 1
            cx += dx
            cy += dy
        return count
