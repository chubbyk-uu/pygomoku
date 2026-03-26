"""Incremental evaluation caches."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyslow.constants import BOARD_SIZE
from pyslow.patterns.shapes import DIRECTION_IDS


def _new_board_matrix(default: int = 0) -> list[list[int]]:
    return [[default for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]


def _new_shape_cache() -> list[list[list[list[int]]]]:
    return [
        [
            [[0 for _ in DIRECTION_IDS] for _ in range(BOARD_SIZE)]
            for _ in range(BOARD_SIZE)
        ]
        for _ in range(2)
    ]


def _new_value_cache() -> list[list[list[int]]]:
    return [
        [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        for _ in range(2)
    ]


@dataclass
class EvalCaches:
    initialized: bool = False
    board_shadow: list[list[int]] = field(default_factory=_new_board_matrix)
    shape_cache: list[list[list[list[int]]]] = field(default_factory=_new_shape_cache)
    value_cache: list[list[list[int]]] = field(default_factory=_new_value_cache)
    attack_cache: list[list[list[int]]] = field(default_factory=_new_value_cache)

    def snapshot(self) -> tuple[
        bool,
        list[list[int]],
        list[list[list[list[int]]]],
        list[list[list[int]]],
        list[list[list[int]]],
    ]:
        return (
            self.initialized,
            [column[:] for column in self.board_shadow],
            [
                [[direction[:] for direction in row] for row in player]
                for player in self.shape_cache
            ],
            [[row[:] for row in player] for player in self.value_cache],
            [[row[:] for row in player] for player in self.attack_cache],
        )

    def restore_snapshot(
        self,
        snapshot: tuple[
            bool,
            list[list[int]],
            list[list[list[list[int]]]],
            list[list[list[int]]],
            list[list[list[int]]],
        ],
    ) -> None:
        initialized, board_shadow, shape_cache, value_cache, attack_cache = snapshot
        self.initialized = initialized
        self.board_shadow = [column[:] for column in board_shadow]
        self.shape_cache = [
            [[direction[:] for direction in row] for row in player]
            for player in shape_cache
        ]
        self.value_cache = [[row[:] for row in player] for player in value_cache]
        self.attack_cache = [[row[:] for row in player] for player in attack_cache]

    def copy(self) -> "EvalCaches":
        initialized, board_shadow, shape_cache, value_cache, attack_cache = self.snapshot()
        return EvalCaches(
            initialized=initialized,
            board_shadow=board_shadow,
            shape_cache=shape_cache,
            value_cache=value_cache,
            attack_cache=attack_cache,
        )

    def restore_from(self, other: "EvalCaches") -> None:
        self.restore_snapshot(other.snapshot())

    def reset(self) -> None:
        self.initialized = False
        self.board_shadow = _new_board_matrix()
        self.shape_cache = _new_shape_cache()
        self.value_cache = _new_value_cache()
        self.attack_cache = _new_value_cache()
