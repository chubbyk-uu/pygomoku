"""Threat-search result types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ThreatLevel(IntEnum):
    A3   = 1   # open three → up to 2 gain squares; extends to B4 after one response
    B4   = 2   # broken four → 1 forced reply
    A4   = 3   # open four → treat as immediate win (opponent can block only one end)
    WIN5 = 4   # five in a row → immediate win


@dataclass(frozen=True)
class AttackMove:
    move: int
    level: ThreatLevel
    defenses: tuple[int, ...]   # forced defender responses; empty for WIN5/A4
