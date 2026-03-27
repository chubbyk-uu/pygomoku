"""Pygame human-vs-engine GUI using an in-process search worker."""

from __future__ import annotations

from dataclasses import dataclass
import argparse
from pathlib import Path
import queue
import shlex
import subprocess
import threading
from typing import Protocol, Sequence

from pyslow.board import Board, move_to_xy, xy_to_move
from pyslow.config import load_default_config
from pyslow.constants import BLACK, BOARD_SIZE, EMPTY, WHITE
from pyslow.search.root import SearchLimits
from pyslow.search.root import RootSearcher


DEFAULT_DEPTH = 5
DEFAULT_WIDTH = 15
DEFAULT_GOMOCUP_TIMEOUT_TURN_MS = 1500
DEFAULT_GOMOCUP_TIME_LEFT_MS = 30000
DEFAULT_GOMOCUP_CANDIDATES = (
    Path("SlowRenju/slowrenju_linux"),
)
GOMOCUP_TIME_PRESETS: tuple[tuple[int, int], ...] = (
    (1500, 30000),
    (3000, 60000),
)


@dataclass(frozen=True)
class GuiLayout:
    left_margin: int = 70
    top_margin: int = 96
    cell_size: int = 40
    right_panel: int = 320
    bottom_margin: int = 50

    @property
    def board_pixels(self) -> int:
        return self.cell_size * (BOARD_SIZE - 1)

    @property
    def width(self) -> int:
        return self.left_margin + self.board_pixels + self.right_panel

    @property
    def height(self) -> int:
        return self.top_margin + self.board_pixels + self.bottom_margin

    @property
    def board_left(self) -> int:
        return self.left_margin

    @property
    def board_top(self) -> int:
        return self.top_margin


def _wrap_text(text: str, max_chars: int) -> list[str]:
    if not text:
        return [""]
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def default_search_limits() -> SearchLimits:
    return SearchLimits(max_depth=DEFAULT_DEPTH, root_width=DEFAULT_WIDTH)


def detect_default_gomocup_command() -> str | None:
    for candidate in DEFAULT_GOMOCUP_CANDIDATES:
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


def compute_undo_steps(move_sides: Sequence[int], human_side: int) -> int:
    if not move_sides:
        return 0
    if len(move_sides) == 1:
        return 1
    if move_sides[-1] == -human_side:
        return 2
    return 1


def pixel_to_cell(pos: tuple[int, int], layout: GuiLayout) -> tuple[int, int] | None:
    px, py = pos
    half = layout.cell_size // 2
    x0 = layout.board_left
    y0 = layout.board_top
    x1 = x0 + layout.board_pixels
    y1 = y0 + layout.board_pixels
    if px < x0 - half or px > x1 + half or py < y0 - half or py > y1 + half:
        return None
    x = round((px - x0) / layout.cell_size)
    y = round((py - y0) / layout.cell_size)
    if 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE:
        return (x, y)
    return None


def last_move_cell(board: Board) -> tuple[int, int] | None:
    if not board.move_history:
        return None
    return move_to_xy(board.move_history[-1].move)


class EngineWorker:
    def __init__(self, backend: "EngineBackend") -> None:
        self._queue: queue.Queue[tuple[int, str, object]] = queue.Queue()
        self._lock = threading.Lock()
        self._generation = 0
        self._active_threads = 0
        self._backend = backend

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def new_generation(self) -> int:
        with self._lock:
            self._generation += 1
            generation = self._generation
        self._clear_queue()
        return generation

    def search_async(self, generation: int, board: Board, limits: SearchLimits) -> None:
        with self._lock:
            self._active_threads += 1
        thread = threading.Thread(
            target=self._run_search,
            args=(generation, board.copy(), limits),
            daemon=True,
        )
        thread.start()

    def _run_search(self, generation: int, board: Board, limits: SearchLimits) -> None:
        try:
            move = self._backend.find_best_move(board, limits)
            self._queue.put((generation, "move", move))
        except Exception as exc:  # pragma: no cover - defensive guard for GUI runtime
            self._queue.put((generation, "error", str(exc)))
        finally:
            with self._lock:
                self._active_threads -= 1

    def poll(self) -> list[tuple[int, str, object]]:
        responses: list[tuple[int, str, object]] = []
        while True:
            try:
                responses.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return responses

    def close(self) -> None:
        self.new_generation()
        self._backend.close()


class EngineBackend(Protocol):
    def find_best_move(self, board: Board, limits: SearchLimits) -> int: ...

    def close(self) -> None: ...


class LocalEngineBackend:
    def __init__(self) -> None:
        self._config = load_default_config()
        self._searcher = RootSearcher(self._config)

    def find_best_move(self, board: Board, limits: SearchLimits) -> int:
        return self._searcher.search(board, limits).move

    def close(self) -> None:
        return


class GomocupEngineBackend:
    def __init__(self, command: str, *, timeout_turn_ms: int, time_left_ms: int) -> None:
        self._command = command
        self._timeout_turn_ms = timeout_turn_ms
        self._time_left_ms = time_left_ms
        self._proc: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()

    def _ensure_process(self) -> subprocess.Popen[str]:
        proc = self._proc
        if proc is not None and proc.poll() is None:
            return proc
        argv = shlex.split(self._command)
        if not argv:
            raise ValueError("empty Gomocup command")
        self._proc = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._send_line("START 15")
        self._read_meaningful_line()
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
                raise RuntimeError(f"Gomocup engine exited unexpectedly: {stderr.strip()}")
            text = line.strip()
            if not text:
                continue
            if text.upper().startswith("MESSAGE"):
                continue
            return text

    def find_best_move(self, board: Board, limits: SearchLimits) -> int:
        with self._lock:
            self._send_line("RESTART")
            self._read_meaningful_line()
            self._send_line(f"INFO timeout_turn {self._timeout_turn_ms}")
            self._send_line(f"INFO time_left {self._time_left_ms}")
            self._send_line(f"INFO max_node {limits.node_limit or 0}")
            self._send_line("BOARD")
            engine_side = board.side_to_move
            for index, played in enumerate(board.move_history):
                x, y = move_to_xy(played.move)
                side = 1 if played.side == engine_side else 2
                self._send_line(f"{x},{y},{side}")
            self._send_line("DONE")
            response = self._read_meaningful_line()
            if "," not in response:
                raise RuntimeError(f"unexpected Gomocup move response: {response}")
            x_str, y_str = response.split(",", 1)
            return xy_to_move(int(x_str), int(y_str))

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


class GomokuGuiApp:
    def __init__(
        self,
        *,
        depth: int = DEFAULT_DEPTH,
        width: int = DEFAULT_WIDTH,
        gomocup_command: str | None = None,
    ) -> None:
        self.layout = GuiLayout()
        self.board = Board()
        self.human_side: int | None = None
        self.search_limits = SearchLimits(max_depth=depth, root_width=width)
        self.status_text = "Choose black or white to start."
        self.engine_busy = False
        self.gomocup_command = gomocup_command or detect_default_gomocup_command()
        self.gomocup_timeout_turn_ms = DEFAULT_GOMOCUP_TIMEOUT_TURN_MS
        self.gomocup_time_left_ms = DEFAULT_GOMOCUP_TIME_LEFT_MS
        self.engine_mode = "local"
        self.engine = EngineWorker(self._build_backend())
        self._engine_generation = 0

    def _build_backend(self) -> EngineBackend:
        if self.engine_mode == "gomocup":
            if not self.gomocup_command:
                raise ValueError("Gomocup command is not configured")
            return GomocupEngineBackend(
                self.gomocup_command,
                timeout_turn_ms=self.gomocup_timeout_turn_ms,
                time_left_ms=self.gomocup_time_left_ms,
            )
        return LocalEngineBackend()

    def switch_engine_mode(self) -> None:
        if not self.gomocup_command:
            self.status_text = "No Gomocup command configured."
            return
        self.engine.close()
        self.engine_mode = "gomocup" if self.engine_mode == "local" else "local"
        self.engine = EngineWorker(self._build_backend())
        self._engine_generation = self.engine.new_generation()
        self.engine_busy = False
        self.status_text = f"Engine mode: {self.engine_mode}."

    def cycle_gomocup_time_preset(self) -> None:
        current = (self.gomocup_timeout_turn_ms, self.gomocup_time_left_ms)
        try:
            index = GOMOCUP_TIME_PRESETS.index(current)
        except ValueError:
            index = -1
        next_timeout, next_time_left = GOMOCUP_TIME_PRESETS[(index + 1) % len(GOMOCUP_TIME_PRESETS)]
        self.gomocup_timeout_turn_ms = next_timeout
        self.gomocup_time_left_ms = next_time_left
        if self.engine_mode == "gomocup":
            self.engine.close()
            self.engine = EngineWorker(self._build_backend())
            self._engine_generation = self.engine.new_generation()
            self.engine_busy = False
        self.status_text = f"Gomocup time set to {next_timeout}/{next_time_left} ms."

    def close(self) -> None:
        self.engine.close()

    def reset_board(self) -> None:
        self.board = Board()
        self.status_text = "Game reset."
        self.engine_busy = False
        self._engine_generation = self.engine.new_generation()

    def start_game(self, human_side: int) -> None:
        self.human_side = human_side
        self.reset_board()
        if human_side == BLACK:
            self.status_text = "You are black. Your move."
        else:
            self.status_text = "You are white. Engine thinking..."
            self.engine_busy = True
            self.engine.search_async(self._engine_generation, self.board, self.search_limits)

    def undo(self) -> None:
        if self.human_side is None or self.engine_busy:
            return
        steps = compute_undo_steps([played.side for played in self.board.move_history], self.human_side)
        for _ in range(steps):
            if not self.board.move_history:
                break
            self.board.undo()
        self._engine_generation = self.engine.new_generation()
        self.status_text = "Undo."

    def restart(self) -> None:
        if self.human_side is None:
            return
        human_side = self.human_side
        self.start_game(human_side)

    def human_play(self, x: int, y: int) -> bool:
        if self.human_side is None or self.engine_busy:
            return False
        if self.board.winner != EMPTY or self.board.side_to_move != self.human_side:
            return False
        move = xy_to_move(x, y)
        if not self.board.is_legal_move(move):
            self.status_text = f"Illegal move at ({x},{y})."
            return False
        self.board.play(move)
        if self.board.winner == self.human_side:
            self.status_text = "You win."
            return True
        self.status_text = "Engine thinking..."
        self.engine_busy = True
        self.engine.search_async(self._engine_generation, self.board, self.search_limits)
        return True

    def poll_engine(self) -> None:
        responses = self.engine.poll()
        if not responses:
            return
        for generation, kind, payload in responses:
            if generation != self._engine_generation:
                continue
            if kind == "error":
                self.status_text = f"Engine error: {payload}"
                self.engine_busy = False
                continue
            move = int(payload)
            if self.board.is_legal_move(move):
                self.board.play(move)
                x, y = move_to_xy(move)
            else:
                self.status_text = "Engine returned an illegal move."
                self.engine_busy = False
                continue
            if self.human_side is not None and self.board.winner == -self.human_side:
                self.status_text = f"Engine wins with ({x},{y})."
            else:
                self.status_text = f"Engine played ({x},{y}). Your move."
            self.engine_busy = False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=DEFAULT_DEPTH)
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--gomocup-cmd", type=str, default=None)
    args = parser.parse_args()

    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise SystemExit("pygame is required for the GUI. Install it with `pip install pygame`.") from exc

    pygame.init()
    pygame.display.set_caption("pyslow Gomoku")

    app = GomokuGuiApp(depth=args.depth, width=args.width, gomocup_command=args.gomocup_cmd)
    layout = app.layout
    screen = pygame.display.set_mode((layout.width, layout.height))
    clock = pygame.time.Clock()

    bg = (238, 200, 140)
    grid_color = (65, 42, 20)
    black_color = (24, 24, 24)
    white_color = (245, 245, 245)
    red = (170, 40, 40)
    blue = (30, 80, 150)
    panel = (246, 234, 206)
    text = (30, 22, 12)

    title_font = pygame.font.SysFont("arial", 26, bold=True)
    body_font = pygame.font.SysFont("arial", 20)
    small_font = pygame.font.SysFont("arial", 16)

    def draw_board() -> tuple[object, object]:
        screen.fill(bg)
        button_width = 138
        button_gap = 16
        total_button_width = button_width * 2 + button_gap
        button_left = layout.board_left + (layout.board_pixels - total_button_width) // 2
        black_button = pygame.Rect(button_left, 18, button_width, 36)
        white_button = pygame.Rect(button_left + button_width + button_gap, 18, button_width, 36)
        engine_button = pygame.Rect(layout.left_margin + layout.board_pixels + 34, 20, 220, 28)
        time_button = pygame.Rect(layout.left_margin + layout.board_pixels + 34, 52, 220, 28)
        pygame.draw.rect(
            screen,
            panel,
            (
                layout.left_margin + layout.board_pixels + 20,
                layout.top_margin - 28,
                layout.right_panel - 40,
                layout.board_pixels + 56,
            ),
            border_radius=8,
        )

        x0 = layout.board_left
        y0 = layout.board_top
        for idx in range(BOARD_SIZE):
            offset = idx * layout.cell_size
            pygame.draw.line(screen, grid_color, (x0, y0 + offset), (x0 + layout.board_pixels, y0 + offset), 1)
            pygame.draw.line(screen, grid_color, (x0 + offset, y0), (x0 + offset, y0 + layout.board_pixels), 1)
            label = small_font.render(str(idx), True, text)
            screen.blit(label, (x0 + offset - label.get_width() // 2, y0 - 28))
            screen.blit(label, (x0 - 28, y0 + offset - label.get_height() // 2))

        for star_x, star_y in ((3, 3), (7, 7), (11, 3), (3, 11), (11, 11)):
            cx = x0 + star_x * layout.cell_size
            cy = y0 + star_y * layout.cell_size
            pygame.draw.circle(screen, grid_color, (cx, cy), 4)

        for move_index, played in enumerate(app.board.move_history, start=1):
            x, y = move_to_xy(played.move)
            cx = x0 + x * layout.cell_size
            cy = y0 + y * layout.cell_size
            color = black_color if played.side == BLACK else white_color
            pygame.draw.circle(screen, color, (cx, cy), layout.cell_size // 2 - 3)
            pygame.draw.circle(screen, grid_color, (cx, cy), layout.cell_size // 2 - 3, 1)
            num_color = white_color if played.side == BLACK else black_color
            label = small_font.render(str(move_index), True, num_color)
            screen.blit(label, (cx - label.get_width() // 2, cy - label.get_height() // 2))

        marked = last_move_cell(app.board)
        if marked is not None:
            mx, my = marked
            cx = x0 + mx * layout.cell_size
            cy = y0 + my * layout.cell_size
            pygame.draw.circle(screen, red, (cx, cy), layout.cell_size // 2 - 1, 3)

        header = title_font.render("pyslow Gomoku", True, text)
        screen.blit(header, (layout.left_margin + layout.board_pixels + 34, 92))

        lines = [
            f"Engine mode: {app.engine_mode}",
            f"Depth: {app.search_limits.max_depth}",
            f"Width: {app.search_limits.root_width}",
            f"Side: {'Black' if app.human_side == BLACK else 'White' if app.human_side == WHITE else '-'}",
            f"Gomocup: {'ready' if app.gomocup_command else 'missing'}",
            f"G-time: {app.gomocup_timeout_turn_ms}/{app.gomocup_time_left_ms}",
            "Left top is (0,0)",
            "",
            "Controls:",
            "U: undo",
            "R: restart",
            "E: switch engine",
            "T: gomocup time",
            "",
        ]
        lines.extend(_wrap_text(app.status_text, 22))
        base_x = layout.left_margin + layout.board_pixels + 34
        base_y = 144
        for idx, line in enumerate(lines):
            surf = body_font.render(line, True, red if "win" in line.lower() else text)
            screen.blit(surf, (base_x, base_y + idx * 28))

        pygame.draw.rect(screen, black_color if app.human_side == BLACK else blue, black_button, border_radius=6)
        pygame.draw.rect(screen, white_color if app.human_side == WHITE else (225, 225, 225), white_button, border_radius=6)
        pygame.draw.rect(screen, grid_color, black_button, 1, border_radius=6)
        pygame.draw.rect(screen, grid_color, white_button, 1, border_radius=6)
        black_label = body_font.render("Play Black", True, white_color)
        white_label = body_font.render("Play White", True, black_color)
        screen.blit(black_label, (black_button.centerx - black_label.get_width() // 2, black_button.centery - black_label.get_height() // 2))
        screen.blit(white_label, (white_button.centerx - white_label.get_width() // 2, white_button.centery - white_label.get_height() // 2))
        pygame.draw.rect(screen, blue if app.engine_mode == "gomocup" else panel, engine_button, border_radius=6)
        pygame.draw.rect(screen, grid_color, engine_button, 1, border_radius=6)
        engine_text = "Switch to Gomocup" if app.engine_mode == "local" else "Switch to Local"
        engine_label = small_font.render(engine_text, True, text)
        screen.blit(engine_label, (engine_button.centerx - engine_label.get_width() // 2, engine_button.centery - engine_label.get_height() // 2))
        pygame.draw.rect(screen, panel, time_button, border_radius=6)
        pygame.draw.rect(screen, grid_color, time_button, 1, border_radius=6)
        time_text = f"Time {app.gomocup_timeout_turn_ms}/{app.gomocup_time_left_ms}"
        time_label = small_font.render(time_text, True, text)
        screen.blit(time_label, (time_button.centerx - time_label.get_width() // 2, time_button.centery - time_label.get_height() // 2))

        return black_button, white_button, engine_button, time_button

    running = True
    try:
        while running:
            black_button, white_button, engine_button, time_button = draw_board()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_u:
                        app.undo()
                    elif event.key == pygame.K_r:
                        app.restart()
                    elif event.key == pygame.K_e:
                        app.switch_engine_mode()
                    elif event.key == pygame.K_t:
                        app.cycle_gomocup_time_preset()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if black_button.collidepoint(event.pos):
                        app.start_game(BLACK)
                    elif white_button.collidepoint(event.pos):
                        app.start_game(WHITE)
                    elif engine_button.collidepoint(event.pos):
                        app.switch_engine_mode()
                    elif time_button.collidepoint(event.pos):
                        app.cycle_gomocup_time_preset()
                    else:
                        cell = pixel_to_cell(event.pos, layout)
                        if cell is not None:
                            app.human_play(*cell)

            app.poll_engine()
            draw_board()
            pygame.display.flip()
            clock.tick(60)
    finally:
        app.close()
        pygame.quit()


if __name__ == "__main__":
    main()
