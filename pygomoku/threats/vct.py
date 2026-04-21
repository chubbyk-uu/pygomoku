"""Victory by Continuous Threats (VCT) search.

Algorithm: iterative-deepening OR/AND tree (Threat-Space Search).

  OR-node  (attacker's turn): try every forcing move; any branch that the
           AND-node judges as "found" makes the whole OR-node "found".
  AND-node (defender's turn): try every candidate defense; the OR-node must
           find a win after EVERY defense — if any defense survives, the
           attacker has not won.

Depth semantics: each unit corresponds to one attacker move + one defender
response.  depth=0 at the OR-node means "only immediate wins count".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from pygomoku.board import Board, move_to_xy
from pygomoku.threats.threat_board import ThreatBoardView
from pygomoku.threats.types import AttackMove, ThreatLevel

NO_MOVE: Final[int] = -1
_OR_NODE: Final[int] = 0
_AND_NODE: Final[int] = 1


@dataclass(frozen=True)
class VCTResult:
    move: int     # first attacker move of the winning sequence; -1 if not found
    found: bool
    solved: bool  # True = search is exhaustive at this depth (no deeper search needed)


@dataclass(frozen=True)
class _MemoEntry:
    depth: int
    result: VCTResult


class VCTSearcher:
    def __init__(self) -> None:
        self._memo: dict[tuple[int, int, int, int], _MemoEntry] = {}

    def search(self, board: Board, side: int, depth: int) -> VCTResult:
        """Search for a VCT win for *side* up to *depth* rounds."""
        if depth <= 0:
            return VCTResult(NO_MOVE, False, False)
        if board.winner != 0:
            return VCTResult(NO_MOVE, False, True)
        view = ThreatBoardView.from_board(board.copy())
        self._memo.clear()
        result = VCTResult(NO_MOVE, False, False)
        for d in range(1, depth + 1):
            result = self._or_node(view, side, d)
            if result.found or result.solved:
                return result
        return result

    # ------------------------------------------------------------------
    # Memoization helpers
    # ------------------------------------------------------------------

    def _memo_lookup(self, node: int, attacker: int, depth: int, key: int) -> VCTResult | None:
        entry = self._memo.get((node, attacker, depth, key))
        if entry is not None:
            return entry.result
        # A shallower "found" win is still valid at a greater depth.
        for d in range(1, depth):
            entry = self._memo.get((node, attacker, d, key))
            if entry is not None and entry.result.found:
                return entry.result
        return None

    def _store(self, node: int, attacker: int, depth: int, key: int, result: VCTResult) -> VCTResult:
        self._memo[(node, attacker, depth, key)] = _MemoEntry(depth=depth, result=result)
        return result

    # ------------------------------------------------------------------
    # OR-node: attacker's turn
    # ------------------------------------------------------------------

    def _or_node(self, view: ThreatBoardView, attacker: int, depth: int) -> VCTResult:
        if depth <= 0:
            return VCTResult(NO_MOVE, False, False)
        if view.board.winner == attacker:
            return VCTResult(NO_MOVE, True, True)
        if view.board.winner == -attacker:
            return VCTResult(NO_MOVE, False, True)

        key = view.board.zobrist_key
        cached = self._memo_lookup(_OR_NODE, attacker, depth, key)
        if cached is not None:
            return cached

        attacks = view.collect_attack_moves(attacker)
        if not attacks:
            # No forcing moves available → search space exhausted.
            return self._store(_OR_NODE, attacker, depth, key, VCTResult(NO_MOVE, False, True))

        solved = True
        for attack in attacks:
            # WIN5 and A4 are immediate wins — no need to enter the AND-node.
            if attack.level >= ThreatLevel.A4:
                return self._store(_OR_NODE, attacker, depth, key,
                                   VCTResult(attack.move, True, True))

            view.play(attack.move, attacker)
            defenses = self._collect_defenses(view, attack, attacker)
            and_result = self._and_node(view, attacker, depth, defenses)
            view.undo()

            if and_result.found:
                return self._store(_OR_NODE, attacker, depth, key,
                                   VCTResult(attack.move, True, True))
            if not and_result.solved:
                solved = False

        return self._store(_OR_NODE, attacker, depth, key,
                           VCTResult(NO_MOVE, False, solved))

    # ------------------------------------------------------------------
    # AND-node: defender's turn
    # ------------------------------------------------------------------

    def _and_node(
        self,
        view: ThreatBoardView,
        attacker: int,
        depth: int,
        defenses: tuple[int, ...],
    ) -> VCTResult:
        """All candidate defenses must fail for the attacker to win."""
        if not defenses:
            # Attacker's threat has no valid defense.
            return VCTResult(NO_MOVE, True, True)

        key = view.board.zobrist_key
        cached = self._memo_lookup(_AND_NODE, attacker, depth, key)
        if cached is not None:
            return cached

        solved = True
        for d_move in defenses:
            if not view.board.is_legal_move(d_move):
                continue

            view.play(d_move, -attacker)
            dx, dy = move_to_xy(d_move)

            # Defender wins immediately via WIN5 or A4.
            if view.board.winner == -attacker or view.has_a4(dx, dy):
                view.undo()
                return self._store(_AND_NODE, attacker, depth, key,
                                   VCTResult(NO_MOVE, False, True))

            or_result = self._or_node(view, attacker, depth - 1)
            view.undo()

            if not or_result.found:
                # This defense survives → attacker cannot force a win here.
                return self._store(_AND_NODE, attacker, depth, key,
                                   VCTResult(NO_MOVE, False, or_result.solved))
            if not or_result.solved:
                solved = False

        # Every defense failed → attacker wins regardless.
        return self._store(_AND_NODE, attacker, depth, key,
                           VCTResult(NO_MOVE, True, solved))

    # ------------------------------------------------------------------
    # Defense candidate generation
    # ------------------------------------------------------------------

    def _collect_defenses(
        self,
        view: ThreatBoardView,
        attack: AttackMove,
        attacker: int,
    ) -> tuple[int, ...]:
        """Collect candidate defender moves after the attacker just played *attack*.

        Priority order:
          1. Defender's own immediate wins (WIN5 / A4) — if any exist, try first.
          2. Forced squares from the attack (B4 reply or A3 gain squares).
          3. Defender's own B4 moves (create a counter-forcing sequence).
          4. Defender's own A3 moves (create a slower counter-sequence).
        """
        defender = -attacker
        forced = list(attack.defenses)

        counter_wins: list[int] = []
        counter_b4: list[int] = []
        counter_a3: list[int] = []

        for m in view.threat_moves(defender):
            if not view.board.is_legal_move(m):
                continue
            view.play(m, defender)
            dx, dy = move_to_xy(m)
            if view.board.winner == defender or view.has_a4(dx, dy):
                counter_wins.append(m)
            else:
                b4 = view.b4_count(dx, dy)
                if b4 >= 1:
                    counter_b4.append(m)
                elif view.a3r_count(dx, dy) >= 1:
                    counter_a3.append(m)
            view.undo()

        seen: set[int] = set()
        result: list[int] = []
        for m in counter_wins + forced + counter_b4 + counter_a3:
            if m not in seen and view.board.is_legal_move(m):
                result.append(m)
                seen.add(m)
        return tuple(result)
