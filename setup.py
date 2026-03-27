from __future__ import annotations

from pathlib import Path

from setuptools import Extension, find_packages, setup


def build_extensions() -> list[Extension]:
    extensions = []
    pyx_files = [
        ("pyslow.patterns._line_cy", Path("pyslow/patterns/_line_cy.pyx")),
        ("pyslow.eval._local_cy", Path("pyslow/eval/_local_cy.pyx")),
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
    packages=find_packages(include=["pyslow", "pyslow.*"]),
    ext_modules=build_extensions(),
)
