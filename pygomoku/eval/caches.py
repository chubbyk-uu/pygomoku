"""Incremental evaluation caches."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from pygomoku.constants import BOARD_SIZE
from pygomoku.patterns.shapes import DIRECTION_IDS


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
        from pygomoku.eval._caches_cy import copy_board_shadow as _copy_board_shadow_native
        from pygomoku.eval._caches_cy import copy_shape_cache as _copy_shape_cache_native
        from pygomoku.eval._caches_cy import copy_value_cache as _copy_value_cache_native
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


@dataclass(frozen=True)
class EvalSnapshot:
    initialized: bool
    board_shadow: list[list[int]]
    shape_log_len: int
    value_log_len: int


@dataclass
class EvalCaches:
    initialized: bool = False
    board_shadow: list[list[int]] = field(default_factory=_new_board_matrix)
    shape_cache: list[list[list[list[int]]]] = field(default_factory=_new_shape_cache)
    value_cache: list[list[list[int]]] = field(default_factory=_new_value_cache)
    attack_cache: list[list[list[int]]] = field(default_factory=_new_value_cache)
    _shape_log: list[tuple[int, int, int, int, int]] = field(default_factory=list, repr=False)
    _value_log: list[tuple[int, int, int, int, int]] = field(default_factory=list, repr=False)
    _active_snapshot_count: int = field(default=0, repr=False)

    def set_shape_value(self, player: int, x: int, y: int, direction: int, value: int) -> None:
        shape_col = self.shape_cache[player][x][y]
        old_value = shape_col[direction]
        if old_value == value:
            return
        if self._active_snapshot_count:
            self._shape_log.append((player, x, y, direction, old_value))
        shape_col[direction] = value

    def snapshot(self) -> EvalSnapshot:
        """Capture evaluator-owned incremental state for later restore.

        This is an internal undo mechanism for evaluator update paths. Shape
        writes are tracked through ``set_shape_value()`` / ``_shape_log``;
        value/attack writes are tracked through evaluator recomputation paths
        that append to ``_value_log`` before mutating the caches.

        Direct external writes to ``value_cache`` / ``attack_cache`` are not
        part of this contract and are not guaranteed to be restored.
        """
        self._active_snapshot_count += 1
        return EvalSnapshot(
            initialized=self.initialized,
            board_shadow=_copy_board_shadow_any(self.board_shadow),
            shape_log_len=len(self._shape_log),
            value_log_len=len(self._value_log),
        )

    def restore_snapshot(self, snapshot: EvalSnapshot) -> None:
        """Restore a snapshot captured through the evaluator logging contract."""
        self.initialized = snapshot.initialized
        self.board_shadow = _copy_board_shadow_any(snapshot.board_shadow)
        while len(self._shape_log) > snapshot.shape_log_len:
            player, x, y, direction, old_value = self._shape_log.pop()
            self.shape_cache[player][x][y][direction] = old_value
        while len(self._value_log) > snapshot.value_log_len:
            player, x, y, old_bucket, old_attack = self._value_log.pop()
            self.value_cache[player][x][y] = old_bucket
            self.attack_cache[player][x][y] = old_attack
        if self._active_snapshot_count:
            self._active_snapshot_count -= 1

    def copy(self) -> "EvalCaches":
        return EvalCaches(
            initialized=self.initialized,
            board_shadow=_copy_board_shadow_any(self.board_shadow),
            shape_cache=_copy_shape_cache_any(self.shape_cache),
            value_cache=_copy_value_cache_any(self.value_cache),
            attack_cache=_copy_value_cache_any(self.attack_cache),
        )

    def restore_from(self, other: "EvalCaches") -> None:
        self.initialized = other.initialized
        self.board_shadow = _copy_board_shadow_any(other.board_shadow)
        self.shape_cache = _copy_shape_cache_any(other.shape_cache)
        self.value_cache = _copy_value_cache_any(other.value_cache)
        self.attack_cache = _copy_value_cache_any(other.attack_cache)
        self._shape_log.clear()
        self._value_log.clear()
        self._active_snapshot_count = 0

    def reset(self) -> None:
        self.initialized = False
        self.board_shadow = _new_board_matrix()
        self.shape_cache = _new_shape_cache()
        self.value_cache = _new_value_cache()
        self.attack_cache = _new_value_cache()
        self._shape_log.clear()
        self._value_log.clear()
        self._active_snapshot_count = 0
