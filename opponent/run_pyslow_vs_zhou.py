"""Run fixed-opening matches between a Gomocup engine and zhou.

Coordinate convention:
- Gomocup engines use (x, y) == (col, row)
- zhou uses (row, col)

This script stores both forms in the output records to avoid ambiguity.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
ZHOU_SRC = REPO_ROOT / "opponent" / "zhou" / "src"
DEFAULT_MAX_MOVES = 120
DEFAULT_PARALLEL = 10
DEFAULT_ENGINE_TYPE = "pyslow"
DEFAULT_PYSLOW_CMD = f"{shlex.quote(sys.executable)} -m pyslow.gomocup_engine"

FIXED_OPENINGS_5: list[tuple[int, int]] = [
    (7, 7),
    (4, 4),
    (4, 10),
    (10, 4),
    (10, 10),
]

FIXED_OPENINGS_9: list[tuple[int, int]] = [
    (2, 2),
    (2, 12),
    (12, 2),
    (12, 12),
    (4, 4),
    (10, 4),
    (4, 10),
    (10, 10),
    (7, 7),
]

OPENING_SETS: dict[str, list[tuple[int, int]]] = {
    "5": FIXED_OPENINGS_5,
    "9": FIXED_OPENINGS_9,
}


@dataclass(frozen=True)
class MatchTask:
    engine_color: str
    opening_index: int
    opening_xy: tuple[int, int]

    @property
    def slice_key(self) -> str:
        x, y = self.opening_xy
        return f"{self.engine_color.lower()}_{self.opening_index}_{x}_{y}"


def _ensure_paths() -> None:
    repo_root = str(REPO_ROOT)
    zhou_src = str(ZHOU_SRC)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    if zhou_src not in sys.path:
        sys.path.insert(0, zhou_src)


def _json_ready(value: Any) -> Any:
    if hasattr(value, "__dict__"):
        return {key: _json_ready(val) for key, val in value.__dict__.items()}
    if isinstance(value, dict):
        return {str(key): _json_ready(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


class _GomocupEngine:
    def __init__(
        self,
        *,
        command: str,
        name: str,
        color: str,
        depth: int | None = None,
        width: int | None = None,
        timeout_turn_ms: int | None = None,
        time_left_ms: int | None = None,
    ) -> None:
        self._command = command
        self._name = name
        self._color = color
        self._depth = depth
        self._width = width
        self._timeout_turn_ms = timeout_turn_ms
        self._time_left_ms = time_left_ms
        self._proc: subprocess.Popen[str] | None = None
        self._known_move_count = 0
        self._initialized = False
        self.last_stats: dict[str, Any] | None = None
        self.last_trace: dict[str, Any] | None = None

    def _ensure_process(self) -> subprocess.Popen[str]:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            return proc
        argv = shlex.split(self._command)
        if not argv:
            raise ValueError("empty Gomocup command")
        env = dict(os.environ)
        pythonpath = env.get("PYTHONPATH")
        repo_root = str(REPO_ROOT)
        env["PYTHONPATH"] = repo_root if not pythonpath else f"{repo_root}:{pythonpath}"
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=REPO_ROOT,
            env=env,
        )
        self._send_line("START 15")
        response = self._read_meaningful_line()
        if response != "OK":
            raise RuntimeError(f"{self._name} START failed: {response}")
        self._known_move_count = 0
        self._initialized = False
        return self._proc

    def _send_line(self, line: str) -> None:
        proc = self._ensure_process()
        assert proc.stdin is not None
        proc.stdin.write(line + "\n")
        proc.stdin.flush()

    def _read_meaningful_line(self) -> str:
        proc = self._ensure_process()
        assert proc.stdout is not None
        while True:
            line = proc.stdout.readline()
            if not line:
                stderr = ""
                if proc.stderr is not None:
                    stderr = proc.stderr.read()
                raise RuntimeError(f"{self._name} exited unexpectedly: {stderr.strip()}")
            text = line.strip()
            if not text:
                continue
            if text.upper().startswith("MESSAGE"):
                continue
            return text

    def _configure(self) -> None:
        if self._depth is not None:
            self._send_line(f"INFO depth {self._depth}")
        if self._width is not None:
            self._send_line(f"INFO width {self._width}")
        if self._timeout_turn_ms is not None:
            self._send_line(f"INFO timeout_turn {self._timeout_turn_ms}")
        if self._time_left_ms is not None:
            self._send_line(f"INFO time_left {self._time_left_ms}")

    def _restart(self) -> None:
        self._send_line("RESTART")
        response = self._read_meaningful_line()
        if response != "OK":
            raise RuntimeError(f"{self._name} RESTART failed: {response}")
        self._configure()
        self._known_move_count = 0
        self._initialized = True

    def _sync_full_board(self, board: Any) -> str:
        from pyslow.board import move_to_xy

        if not self._initialized:
            self._ensure_process()
        self._restart()
        self._send_line("BOARD")
        engine_side = board.side_to_move
        for played in board.move_history:
            x, y = move_to_xy(played.move)
            side = 1 if played.side == engine_side else 2
            self._send_line(f"{x},{y},{side}")
        self._send_line("DONE")
        self._known_move_count = board.move_count
        return self._read_meaningful_line()

    def find_best_move(self, board: Any) -> tuple[int, int] | None:
        from pyslow.board import move_to_xy

        if not self._initialized:
            response = self._sync_full_board(board)
        elif board.move_count == self._known_move_count + 1 and board.move_history:
            last = board.move_history[-1]
            x, y = move_to_xy(last.move)
            self._send_line(f"TURN {x},{y}")
            response = self._read_meaningful_line()
            self._known_move_count = board.move_count
        else:
            response = self._sync_full_board(board)
        if "," not in response:
            raise RuntimeError(f"unexpected {self._name} move response: {response}")
        x_str, y_str = response.split(",", 1)
        self.last_trace = {
            "engine": self._name,
            "color": self._color,
            "command": self._command,
            "depth": self._depth,
            "width": self._width,
            "timeout_turn_ms": self._timeout_turn_ms,
            "time_left_ms": self._time_left_ms,
        }
        self.last_stats = None
        self._known_move_count = board.move_count + 1
        return (int(x_str), int(y_str))

    def close(self) -> None:
        proc = self._proc
        if proc is None:
            return
        if proc.poll() is None:
            try:
                self._send_line("END")
            except Exception:
                pass
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._proc = None
        self._known_move_count = 0
        self._initialized = False


class _PyslowDirectEngine:
    def __init__(self, *, depth: int, width: int, color: str, name: str) -> None:
        _ensure_paths()
        from dataclasses import replace

        from pyslow.config import load_default_config
        from pyslow.search.root import RootSearcher, SearchLimits

        base = load_default_config()
        config = replace(base, root_search=replace(base.root_search, depth=depth, wide=width))
        self._searcher = RootSearcher(config)
        self._limits = SearchLimits(max_depth=depth, root_width=width)
        self._color = color
        self._name = name
        self.last_stats: dict[str, Any] | None = None
        self.last_trace: dict[str, Any] | None = None

    def find_best_move(self, board: Any) -> tuple[int, int] | None:
        from pyslow.board import move_to_xy

        result = self._searcher.search(board, self._limits)
        self.last_stats = {
            "score": result.score,
            "depth": result.depth,
            "nodes": result.nodes,
        }
        self.last_trace = {
            "engine": self._name,
            "color": self._color,
            "mode": "direct",
        }
        return move_to_xy(result.move) if result.move >= 0 else None

    def close(self) -> None:
        return


class _ZhouEngine:
    def __init__(self, depth: int, color: str) -> None:
        _ensure_paths()

        from gomoku.ai.searcher import AISearcher
        from gomoku.config import Player

        ai_player = Player.BLACK if color == "BLACK" else Player.WHITE
        self._searcher = AISearcher(depth=depth, ai_player=ai_player)
        self._color = color
        self.last_stats: dict[str, Any] | None = None
        self.last_trace: dict[str, Any] | None = None

    def find_best_move(self, board: Any) -> tuple[int, int] | None:
        move = self._searcher.find_best_move(board)
        self.last_stats = None
        self.last_trace = _json_ready(self._searcher.last_decision_trace)
        if move is None:
            return None
        row, col = move
        return (col, row)

    def close(self) -> None:
        self._searcher.close()


def _play_task(
    task: MatchTask,
    *,
    engine_type: str,
    engine_command: str,
    engine_name: str,
    pyslow_depth: int,
    pyslow_width: int,
    zhou_depth: int,
    max_moves: int,
) -> dict[str, Any]:
    _ensure_paths()
    from pyslow.board import Board as PyslowBoard
    from pyslow.board import xy_to_move
    from pyslow.constants import BLACK as PYSLOW_BLACK
    from pyslow.constants import WHITE as PYSLOW_WHITE
    from gomoku.board import Board as ZhouBoard
    from gomoku.config import Player as ZhouPlayer

    engine_is_black = task.engine_color == "BLACK"
    if engine_type == "pyslow":
        command = f"{engine_command} --depth {pyslow_depth} --width {pyslow_width}"
        engine_impl = _GomocupEngine(
            command=command,
            name=engine_name,
            color=task.engine_color,
        )
    elif engine_type == "pyslow-direct":
        engine_impl = _PyslowDirectEngine(
            depth=pyslow_depth,
            width=pyslow_width,
            color=task.engine_color,
            name=engine_name,
        )
    else:
        raise ValueError(f"unsupported engine_type: {engine_type}")
    zhou_engine = _ZhouEngine(
        depth=zhou_depth,
        color="WHITE" if engine_is_black else "BLACK",
    )

    pyslow_board = PyslowBoard()
    zhou_board = ZhouBoard()
    move_records: list[dict[str, Any]] = []
    times_engine: list[float] = []
    times_zhou: list[float] = []

    opening_x, opening_y = task.opening_xy
    opening_row, opening_col = opening_y, opening_x
    pyslow_board.play(xy_to_move(opening_x, opening_y), PYSLOW_BLACK)
    zhou_board.place(opening_row, opening_col, ZhouPlayer.BLACK)
    move_records.append(
        {
            "move_no": 1,
            "engine": engine_name if engine_is_black else "zhou",
            "player": "BLACK",
            "x": opening_x,
            "y": opening_y,
            "row": opening_row,
            "col": opening_col,
            "opening_fixed": True,
            "elapsed_ms": 0.0,
            "stats": None,
            "trace": None,
        }
    )

    current_black = False
    move_no = 1

    try:
        while True:
            current_player_name = "BLACK" if current_black else "WHITE"
            engine_turn = (current_black and engine_is_black) or ((not current_black) and (not engine_is_black))
            engine = engine_impl if engine_turn else zhou_engine
            active_board = pyslow_board if engine_turn else zhou_board

            t0 = time.perf_counter()
            move_xy = engine.find_best_move(active_board)
            elapsed = time.perf_counter() - t0

            if engine_turn:
                times_engine.append(elapsed)
            else:
                times_zhou.append(elapsed)

            if move_xy is None:
                winner = "DRAW"
                winner_engine = "DRAW"
                break

            x, y = move_xy
            row, col = y, x
            pyslow_side = PYSLOW_BLACK if current_black else PYSLOW_WHITE
            zhou_side = ZhouPlayer.BLACK if current_black else ZhouPlayer.WHITE

            pyslow_board.play(xy_to_move(x, y), pyslow_side)
            placed = zhou_board.place(row, col, zhou_side)
            if not placed:
                raise RuntimeError(f"zhou board rejected legal move {(row, col)} from {engine.__class__.__name__}")

            move_records.append(
                {
                    "move_no": move_no + 1,
                    "engine": engine_name if engine_turn else "zhou",
                    "player": current_player_name,
                    "x": x,
                    "y": y,
                    "row": row,
                    "col": col,
                    "opening_fixed": False,
                    "elapsed_ms": round(elapsed * 1000, 3),
                    "stats": _json_ready(engine.last_stats),
                    "trace": _json_ready(engine.last_trace),
                }
            )
            move_no += 1

            if pyslow_board.winner != 0:
                winner = current_player_name
                if (winner == "BLACK" and engine_is_black) or (winner == "WHITE" and not engine_is_black):
                    winner_engine = engine_name
                else:
                    winner_engine = "zhou"
                break
            if move_no >= max_moves or pyslow_board.move_count >= pyslow_board.size * pyslow_board.size:
                winner = "DRAW"
                winner_engine = "DRAW"
                break

            current_black = not current_black
    finally:
        engine_impl.close()
        zhou_engine.close()

    return {
        "slice_key": task.slice_key,
        "engine_color": task.engine_color,
        "opening_index": task.opening_index,
        "opening_xy": [opening_x, opening_y],
        "opening_row_col": [opening_row, opening_col],
        "winner": winner,
        "winner_engine": winner_engine,
        "num_moves": move_no,
        "avg_ms_engine": round((sum(times_engine) / len(times_engine) * 1000) if times_engine else 0.0, 3),
        "avg_ms_zhou": round((sum(times_zhou) / len(times_zhou) * 1000) if times_zhou else 0.0, 3),
        "moves": move_records,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _default_output(engine_name: str, color: str) -> Path:
    return REPO_ROOT / "opponent" / f"{engine_name}_vs_zhou_{color.lower()}.json"


def _build_payload(
    *,
    engine_name: str,
    engine_type: str,
    opening_set: str,
    openings: list[tuple[int, int]],
    engine_color: str,
    pyslow_depth: int,
    pyslow_width: int,
    zhou_depth: int,
    max_moves: int,
    games: list[dict[str, Any]],
) -> dict[str, Any]:
    ordered_games = sorted(games, key=lambda item: item["opening_index"])
    wins_engine = sum(1 for game in ordered_games if game["winner_engine"] == engine_name)
    wins_zhou = sum(1 for game in ordered_games if game["winner_engine"] == "zhou")
    draws = sum(1 for game in ordered_games if game["winner_engine"] == "DRAW")
    return {
        "matchup": f"{engine_name}_vs_zhou",
        "opening_set": opening_set,
        "openings_xy": [list(move) for move in openings],
        "engine_name": engine_name,
        "engine_type": engine_type,
        "engine_color": engine_color,
        "params": {
            "pyslow_depth": pyslow_depth,
            "pyslow_width": pyslow_width,
            "zhou_depth": zhou_depth,
            "max_moves": max_moves,
        },
        "summary": {
            "wins_engine": wins_engine,
            "wins_zhou": wins_zhou,
            "draws": draws,
            "games": len(ordered_games),
        },
        "games": ordered_games,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opening-set", choices=sorted(OPENING_SETS), default="5")
    parser.add_argument("--engine-type", choices=("pyslow", "pyslow-direct"), default=DEFAULT_ENGINE_TYPE)
    parser.add_argument("--engine-cmd", type=str, default=None)
    parser.add_argument("--engine-name", type=str, default=None)
    parser.add_argument("--pyslow-depth", type=int, default=5)
    parser.add_argument("--pyslow-width", type=int, default=15)
    parser.add_argument("--zhou-depth", type=int, default=5)
    parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL)
    parser.add_argument("--max-moves", type=int, default=DEFAULT_MAX_MOVES)
    parser.add_argument("--colors", choices=("both", "black", "white"), default="both")
    parser.add_argument("--output-black", type=Path, default=None)
    parser.add_argument("--output-white", type=Path, default=None)
    parser.add_argument("--limit-openings", type=int, default=None)
    args = parser.parse_args()

    openings = OPENING_SETS[args.opening_set]
    if args.limit_openings is not None:
        openings = openings[: args.limit_openings]

    engine_command = args.engine_cmd
    if engine_command is None:
        engine_command = DEFAULT_PYSLOW_CMD
    engine_name = args.engine_name or args.engine_type
    output_black = args.output_black or _default_output(engine_name, "black")
    output_white = args.output_white or _default_output(engine_name, "white")

    tasks: list[MatchTask] = []
    if args.colors in {"both", "black"}:
        tasks.extend(MatchTask("BLACK", idx, opening) for idx, opening in enumerate(openings))
    if args.colors in {"both", "white"}:
        tasks.extend(MatchTask("WHITE", idx, opening) for idx, opening in enumerate(openings))

    results_by_color: dict[str, list[dict[str, Any]]] = {"BLACK": [], "WHITE": []}

    with ProcessPoolExecutor(max_workers=args.parallel) as executor:
        futures = {
            executor.submit(
                _play_task,
                task,
                engine_type=args.engine_type,
                engine_command=engine_command,
                engine_name=engine_name,
                pyslow_depth=args.pyslow_depth,
                pyslow_width=args.pyslow_width,
                zhou_depth=args.zhou_depth,
                max_moves=args.max_moves,
            ): task
            for task in tasks
        }
        for future in as_completed(futures):
            task = futures[future]
            result = future.result()
            results_by_color[task.engine_color].append(result)
            print(
                f"[done] {engine_name}={task.engine_color:<5} "
                f"opening#{task.opening_index} {task.opening_xy} "
                f"winner={result['winner_engine']} moves={result['num_moves']}",
                flush=True,
            )

    if args.colors in {"both", "black"}:
        payload_black = _build_payload(
            engine_name=engine_name,
            engine_type=args.engine_type,
            opening_set=args.opening_set,
            openings=openings,
            engine_color="BLACK",
            pyslow_depth=args.pyslow_depth,
            pyslow_width=args.pyslow_width,
            zhou_depth=args.zhou_depth,
            max_moves=args.max_moves,
            games=results_by_color["BLACK"],
        )
        _write_json(output_black, payload_black)
        print(f"wrote black results to {output_black}")

    if args.colors in {"both", "white"}:
        payload_white = _build_payload(
            engine_name=engine_name,
            engine_type=args.engine_type,
            opening_set=args.opening_set,
            openings=openings,
            engine_color="WHITE",
            pyslow_depth=args.pyslow_depth,
            pyslow_width=args.pyslow_width,
            zhou_depth=args.zhou_depth,
            max_moves=args.max_moves,
            games=results_by_color["WHITE"],
        )
        _write_json(output_white, payload_white)
        print(f"wrote white results to {output_white}")


if __name__ == "__main__":
    main()
