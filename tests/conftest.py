"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest


_FAST_FILES = {
    "test_board.py",
    "test_config.py",
    "test_patterns.py",
    "test_tt.py",
    "test_zobrist.py",
}

_ALIGNMENT_FILES = {
    "test_eval.py",
    "test_movegen.py",
    "test_search.py",
    "test_vcf.py",
}

_INTEGRATION_FILES = {
    "test_gomocup_engine.py",
    "test_gui.py",
    "test_protocol.py",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        filename = Path(str(item.fspath)).name
        if filename in _FAST_FILES:
            item.add_marker(pytest.mark.fast)
        if filename in _ALIGNMENT_FILES:
            item.add_marker(pytest.mark.alignment)
        if filename in _INTEGRATION_FILES:
            item.add_marker(pytest.mark.integration)
