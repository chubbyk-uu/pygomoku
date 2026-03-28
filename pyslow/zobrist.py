"""Zobrist hashing support aligned to SlowRenju."""

from __future__ import annotations

import ctypes
import operator
from dataclasses import dataclass

from pyslow.constants import BLACK, BOARD_AREA, WHITE

_DEFAULT_SEED = 1232356
_MASK64 = (1 << 64) - 1
_REFERENCE_HASH_N = 20
_REFERENCE_HASH_AREA = _REFERENCE_HASH_N * _REFERENCE_HASH_N + 1


def _reference_rand64_sequence(seed: int, count: int) -> tuple[int, ...]:
    """Mirror SlowRenju's InitHash rand64() stream on the local libc."""

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
        # SlowRenju's desktop build compiles hash tables with `N=20`, then
        # indexes them using the runtime board size (`S=15` for Gomocup).
        # To align the exact zobrist stream, we must consume the same number
        # of `rand64()` draws even though freestyle play only uses the first
        # 225 board indices.
        values = _reference_rand64_sequence(seed, _REFERENCE_HASH_AREA * 2)
        black = values[:_REFERENCE_HASH_AREA]
        white = values[_REFERENCE_HASH_AREA : _REFERENCE_HASH_AREA * 2]
        # SlowRenju's CurrentZobrist does not encode side-to-move.
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
