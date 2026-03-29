"""Zobrist hashing support for the classic engine."""

from __future__ import annotations

import ctypes
import operator
from dataclasses import dataclass

from pygomoku.constants import BLACK, BOARD_AREA, WHITE

_DEFAULT_SEED = 1232356
_MASK64 = (1 << 64) - 1
_CLASSIC_HASH_N = 20
_CLASSIC_HASH_AREA = _CLASSIC_HASH_N * _CLASSIC_HASH_N + 1


def _classic_rand64_sequence(seed: int, count: int) -> tuple[int, ...]:
    """Build the classic zobrist stream on the local libc."""

    libc = ctypes.CDLL(None)
    libc.srand.argtypes = [ctypes.c_uint]
    libc.rand.restype = ctypes.c_int
    libc.srand(seed)

    values: list[int] = []
    for _ in range(count):
        value = libc.rand() & 0xFFFFFFFF
        value = operator.xor(value, (libc.rand() & 0xFFFFFFFF) << 15) & _MASK64
        value = operator.xor(value, (libc.rand() & 0xFFFFFFFF) << 30) & _MASK64
        value = operator.xor(value, (libc.rand() & 0xFFFFFFFF) << 45) & _MASK64
        value = operator.xor(value, (libc.rand() & 0xFFFFFFFF) << 60) & _MASK64
        values.append(value)
    return tuple(values)


@dataclass(frozen=True)
class ZobristTable:
    black: tuple[int, ...]
    white: tuple[int, ...]
    turn: int

    @classmethod
    def build(cls, seed: int = _DEFAULT_SEED) -> "ZobristTable":
        # The classic engine keeps the `N=20` hash stream shape, then
        # indexes them using the runtime board size (`S=15` for Gomocup).
        # To align the exact zobrist stream, we must consume the same number
        # of `rand64()` draws even though freestyle play only uses the first
        # 225 board indices.
        values = _classic_rand64_sequence(seed, _CLASSIC_HASH_AREA * 2)
        black = values[:_CLASSIC_HASH_AREA]
        white = values[_CLASSIC_HASH_AREA : _CLASSIC_HASH_AREA * 2]
        # The classic zobrist key does not encode side-to-move.
        return cls(black=black, white=white, turn=0)

    def key_for(self, move: int, side: int) -> int:
        if side == BLACK:
            return self.black[move]
        if side == WHITE:
            return self.white[move]
        raise ValueError(f"invalid side: {side}")

    def key_for_turn(self) -> int:
        return self.turn


DEFAULT_ZOBRIST = ZobristTable.build()
