"""Subprocess integration tests for the protocol engine entrypoint."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def test_gomocup_engine_begin_returns_coordinate() -> None:
    root = Path(__file__).resolve().parents[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "pygomoku.gomocup_engine"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=root,
    )
    try:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write("START 15\n")
        process.stdin.write("BEGIN\n")
        process.stdin.write("END\n")
        process.stdin.flush()

        first = process.stdout.readline().strip()
        second = process.stdout.readline().strip()
        assert first == "OK"
        assert second == "7,7"
    finally:
        process.terminate()
        process.wait(timeout=1.0)
