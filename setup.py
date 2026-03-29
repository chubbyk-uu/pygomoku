from __future__ import annotations

from pathlib import Path

from setuptools import Extension, find_packages, setup


def build_extensions() -> list[Extension]:
    extensions = []
    pyx_files = [
        ("pygomoku.patterns._line_cy", Path("pygomoku/patterns/_line_cy.pyx")),
        ("pygomoku.eval._local_cy", Path("pygomoku/eval/_local_cy.pyx")),
        ("pygomoku.eval._caches_cy", Path("pygomoku/eval/_caches_cy.pyx")),
        ("pygomoku.search._movegen_cy", Path("pygomoku/search/_movegen_cy.pyx")),
        ("pygomoku.search._ordering_cy", Path("pygomoku/search/_ordering_cy.pyx")),
        ("pygomoku.threats._threat_board_cy", Path("pygomoku/threats/_threat_board_cy.pyx")),
    ]
    for module_name, pyx in pyx_files:
        if pyx.exists():
            extensions.append(Extension(module_name, [str(pyx)]))
    if not extensions:
        return []
    try:
        from Cython.Build import cythonize
    except ImportError as exc:  # pragma: no cover - developer build path
        raise RuntimeError("Cython is required to build optional native extensions") from exc
    return cythonize(
        extensions,
        compiler_directives={"language_level": "3"},
    )


setup(
    packages=find_packages(include=["pygomoku", "pygomoku.*"]),
    ext_modules=build_extensions(),
)
