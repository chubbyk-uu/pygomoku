"""Shared type declarations."""

from __future__ import annotations

from dataclasses import dataclass


Move = int


@dataclass(frozen=True)
class PlayedMove:
    move: Move
    side: int
