"""Packed shape definitions and shape decoding."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ShapeLabel(IntEnum):
    L0 = 0
    L1S = 1
    L1 = 2
    L2S = 3
    L2BB = 4
    L2B = 5
    L2 = 6
    L3S = 7
    L3B = 8
    L3 = 9
    L4S = 10
    L4 = 11
    L5 = 12
    L6 = 13


HORIZONTAL = 0
VERTICAL = 1
DIAGONAL_DOWN = 2
DIAGONAL_UP = 3

DIRECTION_IDS: tuple[int, int, int, int] = (
    HORIZONTAL,
    VERTICAL,
    DIAGONAL_DOWN,
    DIAGONAL_UP,
)


@dataclass(frozen=True)
class PackedShape:
    raw: int = 0

    @property
    def label(self) -> int:
        return (self.raw >> 16) & 0xF

    @property
    def aux(self) -> int:
        return self.raw & 0xF
