"""Normal search candidate generation."""

from __future__ import annotations

from dataclasses import dataclass

from pyslow.board import Board, move_to_xy, xy_to_move
from pyslow.config import EngineConfig
from pyslow.constants import BOARD_SIZE, EMPTY, WIN
from pyslow.eval.caches import EvalCaches
from pyslow.eval.local import attack_level, move_value
from pyslow.patterns.line import Line
from pyslow.patterns.shapes import DIAGONAL_DOWN, DIAGONAL_UP, HORIZONTAL, VERTICAL

_COVER_DIRS: tuple[tuple[int, int], ...] = (
    (-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1),
    (-2, -2), (-2, -1), (-2, 0), (-2, 1), (-2, 2), (-1, -2), (-1, 2), (0, -2),
    (0, 2), (1, -2), (1, 2), (2, -2), (2, -1), (2, 0), (2, 1), (2, 2),
    (-3, -3), (-3, 0), (-3, 3), (0, -3), (0, 3), (3, -3), (3, 0), (3, 3),
)

_COVER_NEIGHBORS: tuple[tuple[int, ...], ...] = tuple(
    tuple(
        yy * BOARD_SIZE + xx
        for dx, dy in _COVER_DIRS
        for xx, yy in ((move % BOARD_SIZE + dx, move // BOARD_SIZE + dy),)
        if 0 <= xx < BOARD_SIZE and 0 <= yy < BOARD_SIZE
    )
    for move in range(BOARD_SIZE * BOARD_SIZE)
)


def _ga(value: int) -> int:
    return value & 0xFF


def _gb(value: int) -> int:
    return (value >> 8) & 0xFF


def _gc(value: int) -> int:
    return (value >> 16) & 0xFF


def _decode_bonus_targets(move: int, direction_index: int, encoded: int) -> tuple[int, ...]:
    x, y = move_to_xy(move)
    raw = (_ga(encoded), _gb(encoded))
    if encoded >= (1 << 24):
        raw = raw + (_gc(encoded),)
    targets: list[int] = []
    for value in raw:
        if direction_index == 1:
            tx, ty = x, value
        elif direction_index == 2:
            tx, ty = value, y
        elif direction_index == 3:
            tx, ty = x + y - value, value
        elif direction_index == 4:
            tx, ty = BOARD_SIZE - 1 + x - y - value, BOARD_SIZE - 1 - value
        else:
            continue
        if 0 <= tx < BOARD_SIZE and 0 <= ty < BOARD_SIZE:
            targets.append(xy_to_move(tx, ty))
    return tuple(targets)


def _apply_hostile_three_extension(board: Board, move: int, side: int, vbw_map: dict[int, float]) -> None:
    x, y = move_to_xy(move)
    hostile_side = -side
    line_specs = (
        (Line.from_board(board, x, HORIZONTAL), y, 1),
        (Line.from_board(board, y, VERTICAL), x, 2),
        (Line.from_board(board, x + y, DIAGONAL_DOWN), y, 3),
        (Line.from_board(board, BOARD_SIZE - 1 - y + x, DIAGONAL_UP), BOARD_SIZE - 1 - y, 4),
    )
    encoded = 0
    direction = 0
    for line, point_index, direction_id in line_specs:
        if point_index + 1 < BOARD_SIZE and line.cells[point_index + 2 + 1] == hostile_side:
            encoded = line.a3pb(point_index + 1)
        elif point_index - 1 >= 0 and line.cells[point_index + 2 - 1] == hostile_side:
            encoded = line.a3pb(point_index - 1)
        if encoded > 0:
            direction = direction_id
            break
    if direction == 0:
        return
    for target in _decode_bonus_targets(move, direction, encoded):
        vbw_map[target] = vbw_map.get(target, 0) + 10000


@dataclass(frozen=True)
class Candidate:
    move: int
    order_score: float
    self_attack: int
    opp_attack: int


@dataclass(frozen=True)
class CandidateGenerationResult:
    candidates: tuple[Candidate, ...]
    single_forcing: bool
    hostile_threat: bool
    win_priority: bool


def covered_moves(board: Board) -> tuple[int, ...]:
    if board.move_count == 0:
        return (xy_to_move(BOARD_SIZE // 2, BOARD_SIZE // 2),)

    grid = board.grid
    seen = bytearray(BOARD_SIZE * BOARD_SIZE)
    covered: list[int] = []
    for played in board.move_history:
        for candidate in _COVER_NEIGHBORS[played.move]:
            if not seen[candidate]:
                x = candidate % BOARD_SIZE
                y = candidate // BOARD_SIZE
                if grid[y][x] == EMPTY:
                    seen[candidate] = 1
                    covered.append(candidate)
    covered.sort()
    return tuple(covered)


def generate_candidates(
    board: Board,
    caches: EvalCaches,
    side: int,
    config: EngineConfig,
    *,
    wide: int | None = None,
    root_allowed_moves: set[int] | None = None,
    preferred_move: int = -1,
) -> CandidateGenerationResult:
    moves = covered_moves(board)
    if wide is None:
        wide = config.root_search.wide

    vbw_map: dict[int, int] = {}
    self_attack_map: dict[int, int] = {}
    opp_attack_map: dict[int, int] = {}
    at1pri = 0
    at2pri = 0
    sglflag = 0
    hsflag = 0

    for move in moves:
        x = move % BOARD_SIZE
        y = move // BOARD_SIZE
        vbw = int(move_value(caches, x, y, side, config))
        att1 = attack_level(caches, x, y, side)
        att2 = attack_level(caches, x, y, -side)
        vbw_map[move] = vbw
        self_attack_map[move] = att1
        opp_attack_map[move] = att2
        if vbw <= 0:
            at2pri = max(at2pri, att2)
            continue
        if att2 == 6 or att1 >= 5:
            sglflag += 1
        elif att2 == 5:
            hsflag = move + 1
        at1pri = max(at1pri, att1)
        at2pri = max(at2pri, att2)

    winpri = at1pri == 6 or (at1pri == 5 and at2pri <= 5)
    if not sglflag and hsflag:
        _apply_hostile_three_extension(board, hsflag - 1, side, vbw_map)
    candidates: list[Candidate] = []

    for move in moves:
        vbw = vbw_map[move]
        if root_allowed_moves is not None and move not in root_allowed_moves:
            vbw -= 5000
        if hsflag:
            vbw -= 5000
            if self_attack_map.get(move, 0) >= 4:
                vbw += 8000
        if vbw <= 0:
            continue
        score = vbw - 300000000
        if move == preferred_move:
            score = 100
        if score >= WIN:
            candidates = [
                Candidate(
                    move=move,
                    order_score=score,
                    self_attack=self_attack_map[move],
                    opp_attack=opp_attack_map[move],
                )
            ]
            break
        if score <= -WIN and score >= -200000000:
            continue
        if score > -200000000 or (-300000000 <= score <= 250000000):
            candidates.append(
                Candidate(
                    move=move,
                    order_score=score,
                    self_attack=self_attack_map[move],
                    opp_attack=opp_attack_map[move],
                )
            )

    candidates.sort(key=lambda candidate: (-candidate.order_score, candidate.move))
    if winpri and candidates:
        return CandidateGenerationResult((candidates[0],), False, bool(hsflag), True)
    if sglflag and candidates:
        return CandidateGenerationResult((candidates[0],), True, bool(hsflag), winpri)
    return CandidateGenerationResult(tuple(candidates), False, bool(hsflag), winpri)
