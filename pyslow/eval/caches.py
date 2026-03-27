"""Incremental evaluation caches."""

from __future__ import annotations

import os
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


def _copy_board_shadow(board_shadow: list[list[int]]) -> list[list[int]]:
    return [column[:] for column in board_shadow]


def _copy_shape_cache(shape_cache: list[list[list[list[int]]]]) -> list[list[list[list[int]]]]:
    return [
        [[direction[:] for direction in row] for row in player]
        for player in shape_cache
    ]


def _copy_value_cache(cache: list[list[list[int]]]) -> list[list[list[int]]]:
    return [[row[:] for row in player] for player in cache]


_CACHES_BACKEND_MODE = os.getenv("PYSLOW_CACHES_BACKEND", "auto").lower()
if _CACHES_BACKEND_MODE != "python":
    try:
        from pyslow.eval._caches_cy import copy_board_shadow as _copy_board_shadow_native
        from pyslow.eval._caches_cy import copy_shape_cache as _copy_shape_cache_native
        from pyslow.eval._caches_cy import copy_value_cache as _copy_value_cache_native
    except ImportError:
        if _CACHES_BACKEND_MODE == "cython":
            raise
        _copy_board_shadow_native = None
        _copy_shape_cache_native = None
        _copy_value_cache_native = None
else:
    _copy_board_shadow_native = None
    _copy_shape_cache_native = None
    _copy_value_cache_native = None


def caches_backend_name() -> str:
    return "cython" if _copy_board_shadow_native is not None else "python"


def _copy_board_shadow_any(board_shadow: list[list[int]]) -> list[list[int]]:
    if _copy_board_shadow_native is not None:
        return _copy_board_shadow_native(board_shadow)
    return _copy_board_shadow(board_shadow)


def _copy_shape_cache_any(shape_cache: list[list[list[list[int]]]]) -> list[list[list[list[int]]]]:
    if _copy_shape_cache_native is not None:
        return _copy_shape_cache_native(shape_cache)
    return _copy_shape_cache(shape_cache)


def _copy_value_cache_any(cache: list[list[list[int]]]) -> list[list[list[int]]]:
    if _copy_value_cache_native is not None:
        return _copy_value_cache_native(cache)
    return _copy_value_cache(cache)


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
            _copy_board_shadow_any(self.board_shadow),
            _copy_shape_cache_any(self.shape_cache),
            _copy_value_cache_any(self.value_cache),
            _copy_value_cache_any(self.attack_cache),
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
        self.board_shadow = _copy_board_shadow_any(board_shadow)
        self.shape_cache = _copy_shape_cache_any(shape_cache)
        self.value_cache = _copy_value_cache_any(value_cache)
        self.attack_cache = _copy_value_cache_any(attack_cache)

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
