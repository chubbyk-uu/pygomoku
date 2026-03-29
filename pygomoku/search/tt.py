"""Transposition table."""

from __future__ import annotations

from dataclasses import dataclass

from pygomoku.constants import HASHF_ALPHA, HASHF_BETA, HASHF_EMPTY, HASHF_EXACT


@dataclass(frozen=True)
class TTEntry:
    key: int = 0
    value: int = 0
    flag: int = HASHF_EMPTY
    depth: int = 0
    priority: int = 0
    best_move: int = -1


@dataclass(frozen=True)
class ProbeResult:
    value: int | None
    best_move: int
    hit: bool
    has_window: bool = False
    window_alpha: int = 0
    window_beta: int = 0


class TranspositionTable:
    def __init__(self, bucket_bits: int = 20) -> None:
        self.bucket_mask = (1 << bucket_bits) - 1
        self.buckets: list[list[TTEntry]] = [
            [TTEntry(), TTEntry()] for _ in range(1 << bucket_bits)
        ]

    def _bucket(self, key: int) -> list[TTEntry]:
        return self.buckets[key & self.bucket_mask]

    def store(self, entry: TTEntry) -> None:
        bucket = self._bucket(entry.key)
        slot = 0
        if bucket[0].flag != HASHF_EMPTY and bucket[0].priority > entry.priority:
            slot = 1
        bucket[slot] = entry

    def probe(self, key: int, depth: int, alpha: int, beta: int) -> ProbeResult:
        fallback_best_move = -1
        for entry in self._bucket(key):
            if entry.key != key:
                continue
            if entry.depth >= depth:
                if entry.flag == HASHF_EXACT:
                    return ProbeResult(value=entry.value, best_move=entry.best_move, hit=True)
                if entry.flag == HASHF_ALPHA:
                    if entry.value <= alpha:
                        return ProbeResult(value=entry.value, best_move=-1, hit=True)
                    return ProbeResult(
                        value=None,
                        best_move=entry.best_move,
                        hit=False,
                        has_window=True,
                        window_alpha=alpha,
                        window_beta=min(beta, entry.value + 1),
                    )
                if entry.flag == HASHF_BETA:
                    if entry.value >= beta:
                        return ProbeResult(value=entry.value, best_move=-1, hit=True)
                    return ProbeResult(
                        value=None,
                        best_move=entry.best_move,
                        hit=False,
                        has_window=True,
                        window_alpha=max(alpha, entry.value),
                        window_beta=beta,
                    )
            # depth insufficient: record best_move but continue to check the other slot
            fallback_best_move = entry.best_move
        return ProbeResult(value=None, best_move=fallback_best_move, hit=False)
