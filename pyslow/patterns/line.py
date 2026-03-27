"""Directional line extraction and pattern helpers."""

from __future__ import annotations

from dataclasses import dataclass

from pyslow.board import Board
from pyslow.constants import BLACK, BOARD_SIZE, EMPTY, WHITE
from pyslow.patterns.shape_table import SHAPE_TABLE
from pyslow.patterns.shapes import (
    DIAGONAL_DOWN,
    DIAGONAL_UP,
    HORIZONTAL,
    PackedShape,
    VERTICAL,
)

_SENTINEL = 1024


def _comb(x: int, y: int) -> int:
    return (x << 8) | (y - 2)


def _comc(x: int, y: int, z: int) -> int:
    return _comb(_comb(x, y), z)


def _comd(x: int, y: int, z: int, w: int) -> int:
    return _comb(_comc(x, y, z), w)


@dataclass
class Line:
    cells: list[int]

    @classmethod
    def from_board(cls, board: Board, pivot: int, direction: int) -> "Line":
        size = board.size
        grid = board.grid
        cells = [_SENTINEL] * (size + 4)
        if direction == HORIZONTAL:
            for y in range(size):
                cells[y + 2] = grid[y][pivot]
        elif direction == VERTICAL:
            row = grid[pivot]
            for x in range(size):
                cells[x + 2] = row[x]
        elif direction == DIAGONAL_DOWN:
            if pivot < size:
                for i in range(pivot + 1):
                    cells[i + 2] = grid[i][pivot - i]
            else:
                start = pivot - size + 1
                for i in range(start, size):
                    cells[i + 2] = grid[i][pivot - i]
        elif direction == DIAGONAL_UP:
            if pivot < size:
                for i in range(pivot + 1):
                    cells[i + 2] = grid[size - 1 - i][pivot - i]
            else:
                start = pivot - size + 1
                for i in range(start, size):
                    cells[i + 2] = grid[size - 1 - i][pivot - i]
        else:
            raise ValueError(f"invalid direction: {direction}")
        return cls(cells=cells)

    def shape(self, point_index: int, freestyle: bool = True) -> PackedShape:
        """Return the packed directional shape for an occupied point on this line."""
        p = point_index + 2
        stone = self.cells[p]
        if stone not in (BLACK, WHITE):
            return PackedShape(0)

        if stone == BLACK:
            trt = self._shape_table_lookup(p, BLACK, foul_or_nosix=not freestyle)
        else:
            trt = self._shape_table_lookup(p, WHITE, foul_or_nosix=False)
        return PackedShape(((trt & 0xF0) << 12) | (trt & 0xF))

    def _shape_table_lookup(self, p: int, stone: int, foul_or_nosix: bool) -> int:
        ssp = 0
        si = 0
        sj = 0

        forward_masks = (16, 8, 4, 2, 1)
        backward_masks = (32, 64, 128, 256, 512)

        for offset, mask in enumerate(forward_masks, start=1):
            value = self.cells[p + offset]
            if value == EMPTY:
                continue
            if value == stone:
                ssp |= mask
            else:
                sj = offset - 1
                break
        else:
            sj = 5

        for offset, mask in enumerate(backward_masks, start=1):
            value = self.cells[p - offset]
            if value == EMPTY:
                continue
            if value == stone:
                ssp |= mask
            else:
                si = offset - 1
                break
        else:
            si = 5

        ssp >>= 5 - sj
        table_index = (1 << si) * ((1 << sj) + 62) - 63 + ssp
        row = 1 if foul_or_nosix else 0
        return SHAPE_TABLE[row][table_index]

    def a4(self, point_index: int) -> int:
        p = point_index + 2
        x0 = self.cells[p]
        if x0 == EMPTY:
            return 0
        xmin = max(2, p - 3)
        xmax = min(BOARD_SIZE - 2, p)
        for i in range(xmin, xmax + 1):
            if self.cells[i] + self.cells[i + 1] + self.cells[i + 2] + self.cells[i + 3] != 4 * x0:
                continue
            if self.cells[i - 1] == EMPTY and self.cells[i + 4] == EMPTY:
                return 1
        return 0

    def a6(self, point_index: int) -> int:
        p = point_index + 2
        if self.cells[p] != BLACK:
            return 0
        xmin = max(2, p - 5)
        xmax = min(BOARD_SIZE - 4, p)
        for i in range(xmin, xmax + 1):
            if (
                self.cells[i]
                + self.cells[i + 1]
                + self.cells[i + 2]
                + self.cells[i + 3]
                + self.cells[i + 4]
                + self.cells[i + 5]
            ) == 6:
                return 1
        return 0

    def a5(self, point_index: int) -> int:
        p = point_index + 2
        x0 = self.cells[p]
        if x0 == EMPTY:
            return 0
        xmin = max(2, p - 4)
        xmax = min(BOARD_SIZE - 3, p)
        for i in range(xmin, xmax + 1):
            if (
                self.cells[i]
                + self.cells[i + 1]
                + self.cells[i + 2]
                + self.cells[i + 3]
                + self.cells[i + 4]
            ) == 5 * x0:
                return 1
        return 0

    def b4(self, point_index: int) -> int:
        p = point_index + 2
        x0 = self.cells[p]
        if x0 == EMPTY:
            return 0
        xmin = max(2, p - 4)
        xmax = min(BOARD_SIZE - 3, p)
        for i in range(xmin, xmax + 1):
            if sum(self.cells[i + k] for k in range(5)) != 4 * x0:
                continue
            shape = (
                (self.cells[i] << 4)
                + (self.cells[i + 1] << 3)
                + (self.cells[i + 2] << 2)
                + (self.cells[i + 3] << 1)
                + self.cells[i + 4]
            )
            if x0 == WHITE:
                shape = -shape
            if shape in (0x1E, 0x0F):
                return 1
            elif shape == 0x1D:
                if i <= BOARD_SIZE - 7 and self.cells[i + 5] == EMPTY and self.cells[i + 6] == x0 and self.cells[i + 7] == x0 and self.cells[i + 8] == x0:
                    if p == i + 4:
                        return 2
                return 1
            elif shape == 0x1B:
                if i <= BOARD_SIZE - 6 and self.cells[i + 5] == EMPTY and self.cells[i + 6] == x0 and self.cells[i + 7] == x0:
                    if p == i + 4 or p == i + 3:
                        return 2
                return 1
            elif shape == 0x17:
                if i <= BOARD_SIZE - 5 and self.cells[i + 5] == EMPTY and self.cells[i + 6] == x0:
                    if p == i + 4 or p == i + 3 or p == i + 2:
                        return 2
                return 1
        return 0

    def b4p(self, point_index: int) -> int:
        p = point_index + 2
        x0 = self.cells[p]
        if x0 == EMPTY:
            return 0
        xmin = max(2, p - 4)
        xmax = min(BOARD_SIZE - 3, p)
        for i in range(xmin, xmax + 1):
            if sum(self.cells[i + k] for k in range(5)) != 4 * x0:
                continue
            shape = (
                (self.cells[i] << 4)
                + (self.cells[i + 1] << 3)
                + (self.cells[i + 2] << 2)
                + (self.cells[i + 3] << 1)
                + self.cells[i + 4]
            )
            if x0 == WHITE:
                shape = -shape
            if shape == 0x1E:
                if self.cells[i - 1] == EMPTY:
                    return _comc(1, i - 1, i + 4)
                return _comb(1, i + 4)
            if shape == 0x1D:
                if i <= BOARD_SIZE - 7 and self.cells[i + 5] == x0 and self.cells[i + 6] == x0 and self.cells[i + 7] == x0:
                    if p == i + 4 and self.cells[i + 3] == EMPTY:
                        return _comc(1, i + 3, i + 5)
                if self.cells[i + 3] == EMPTY:
                    return _comb(1, i + 3)
            if shape == 0x1B:
                if i <= BOARD_SIZE - 6 and self.cells[i + 5] == EMPTY and self.cells[i + 6] == x0 and self.cells[i + 7] == x0:
                    if (p == i + 4 or p == i + 3) and self.cells[i + 2] == EMPTY:
                        return _comc(1, i + 2, i + 5)
                if self.cells[i + 2] == EMPTY:
                    return _comb(1, i + 2)
            if shape == 0x17:
                if i <= BOARD_SIZE - 5 and self.cells[i + 5] == EMPTY and self.cells[i + 6] == x0:
                    if (p == i + 4 or p == i + 3 or p == i + 2) and self.cells[i + 1] == EMPTY:
                        return _comc(1, i + 1, i + 5)
                if self.cells[i + 1] == EMPTY:
                    return _comb(1, i + 1)
            if shape == 0x0F:
                if self.cells[i + 5] == EMPTY:
                    return _comc(1, i, i + 5)
                return _comb(1, i)
        return 0

    def a3(self, point_index: int) -> int:
        p = point_index + 2
        x0 = self.cells[p]
        if x0 == EMPTY:
            return 0
        xmin = max(2, p - 3)
        xmax = min(BOARD_SIZE - 2, p)
        for i in range(xmin, xmax + 1):
            num1 = self.cells[i] + self.cells[i + 1] + self.cells[i + 2] + self.cells[i + 3]
            num2 = self.cells[i] * self.cells[i + 1] * self.cells[i + 2] * self.cells[i + 3]
            if num1 != 3 * x0 or num2 != 0:
                continue
            shape = (
                (self.cells[i] << 3)
                + (self.cells[i + 1] << 2)
                + (self.cells[i + 2] << 1)
                + self.cells[i + 3]
            )
            if x0 == WHITE:
                shape = -shape
            if shape == 0x0E:
                if self.cells[i - 1] == EMPTY and self.cells[i - 2] != x0 and self.cells[i + 4] != x0:
                    if self.cells[i - 2] == EMPTY and self.cells[i + 4] == EMPTY:
                        return _comc(1, i - 1, i + 3)
                    if self.cells[i - 2] == EMPTY:
                        return _comb(1, i - 1)
                    if self.cells[i + 4] == EMPTY:
                        return _comb(1, i + 3)
            if shape == 0x0D:
                if self.cells[i - 1] == EMPTY and self.cells[i + 4] == EMPTY:
                    return _comb(1, i + 2)
            if shape == 0x0B:
                if self.cells[i - 1] == EMPTY and self.cells[i + 4] == EMPTY:
                    return _comb(1, i + 1)
        return 0

    def a3pb(self, point_index: int) -> int:
        p = point_index + 2
        x0 = self.cells[p]
        if x0 == EMPTY:
            return 0
        xmin = max(2, p - 3)
        xmax = min(BOARD_SIZE - 2, p)
        for i in range(xmin, xmax + 1):
            num1 = self.cells[i] + self.cells[i + 1] + self.cells[i + 2] + self.cells[i + 3]
            num2 = self.cells[i] * self.cells[i + 1] * self.cells[i + 2] * self.cells[i + 3]
            if num1 != 3 * x0 or num2 != 0:
                continue
            shape = (
                (self.cells[i] << 3)
                + (self.cells[i + 1] << 2)
                + (self.cells[i + 2] << 1)
                + self.cells[i + 3]
            )
            if x0 == WHITE:
                shape = -shape
            if shape == 0x0E:
                if self.cells[i - 1] == EMPTY and self.cells[i - 2] != x0 and self.cells[i + 4] != x0:
                    if self.cells[i - 2] == EMPTY and self.cells[i + 4] == EMPTY:
                        return _comc(1, i - 1, i + 3)
                    if self.cells[i - 2] == EMPTY:
                        return _comd(1, i - 1, i - 2, i + 3)
                    if self.cells[i + 4] == EMPTY:
                        return _comd(1, i + 3, i - 1, i + 4)
            if shape == 0x0D:
                if self.cells[i - 1] == EMPTY and self.cells[i + 4] == EMPTY:
                    return _comd(1, i + 2, i - 1, i + 4)
            if shape == 0x0B:
                if self.cells[i - 1] == EMPTY and self.cells[i + 4] == EMPTY:
                    return _comd(1, i + 1, i - 1, i + 4)
        return 0
