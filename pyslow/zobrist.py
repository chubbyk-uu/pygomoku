"""Zobrist hashing support."""

from __future__ import annotations

import random
from dataclasses import dataclass

from pyslow.constants import BLACK, BOARD_AREA, BOARD_SIZE, WHITE

_DEFAULT_SEED = 1232356


@dataclass(frozen=True)
class ZobristTable:
    black: tuple[int, ...]
    white: tuple[int, ...]
    turn: int

    @classmethod
    def build(cls, seed: int = _DEFAULT_SEED) -> "ZobristTable":
        rng = random.Random(seed)
        black = tuple(rng.getrandbits(64) for _ in range(BOARD_AREA))
        white = tuple(rng.getrandbits(64) for _ in range(BOARD_AREA))
        turn = rng.getrandbits(64)
        return cls(black=black, white=white, turn=turn)

    def key_for(self, move: int, side: int) -> int:
        if side == BLACK:
            return self.black[move]
        if side == WHITE:
            return self.white[move]
        raise ValueError(f"invalid side: {side}")

    def key_for_turn(self) -> int:
        return self.turn


DEFAULT_ZOBRIST = ZobristTable.build()
