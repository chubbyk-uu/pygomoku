"""Optional helper for building a minimal SlowRenju trace harness.

This is not part of the default test suite.
It exists to support branch-alignment work when a `pyslow` position needs to
be compared directly against a small reference executable.

Important:
- most trace programs should explicitly set `S=15; boardSize=15;` before `init()`
- otherwise reference globals may stay uninitialized and produce misleading results
"""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SLOW = ROOT / "SlowRenju"


FILES = [
    "Headers/game.h",
    "Common/global_value.cpp",
    "Shape/ShapeList.cpp",
    "Shape/line.cpp",
    "Shape/line4v.cpp",
    "Value/ValueWide.cpp",
    "Value/ValueW.cpp",
    "Value/ValueB.cpp",
    "AI/Hash.cpp",
    "AI/AIs.cpp",
    "VCF/VCF.cpp",
    "AI/AIx.cpp",
]


def _rewrite_cpp_text(text: str) -> str:
    text = text.replace(r"..\Headers\game.h", "../Headers/game.h")
    text = text.replace("#include <Windows.h>", "")
    text = text.replace("typedef unsigned __int64 U64;", "typedef unsigned long long U64;")
    return text


def _compat_patch(rel_path: str, text: str) -> str:
    if rel_path == "Value/ValueWide.cpp" and "#include <cstring>" not in text:
        text = text.replace("#include <assert.h>\n", "#include <assert.h>\n#include <cstring>\n")
    if rel_path == "AI/Hash.cpp" and "#include <cstring>" not in text:
        text = text.replace("#include <ctime>\n", "#include <ctime>\n#include <cstring>\n")
    if rel_path == "AI/AIx.cpp":
        text = text.replace("#include <fstream>\n", "")
        if "#include <cstring>" not in text:
            text = text.replace("#include <cmath>\n", "#include <cmath>\n#include <cstring>\n#include <cstdio>\n")
        compat = (
            "#define printf_s printf\n"
            "#define sprintf_s snprintf\n"
            "#define strcat_s(dst,sz,src) strcat(dst,src)\n"
        )
        text = compat + text
    if rel_path == "VCF/VCF.cpp":
        text = text.replace(
            "static unordered_map<wstring, int, str_hash, equal_to<wstring>, allocator<pair<wstring,int>>> hm;",
            "static unordered_map<wstring, int, str_hash> hm;",
        )
        text = text.replace(
            "unordered_map<wstring, int, str_hash, equal_to<wstring>, allocator<pair<wstring,int>>>::iterator iter;",
            "unordered_map<wstring, int, str_hash>::iterator iter;",
        )
    return text


def prepare_workspace() -> Path:
    tmpdir = Path(tempfile.mkdtemp(prefix="slowrenju-trace-"))
    for rel in FILES:
        src = SLOW / rel
        dst = tmpdir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = _rewrite_cpp_text(src.read_text(errors="ignore"))
        text = _compat_patch(rel, text)
        dst.write_text(text)
    return tmpdir


def write_trace_program(workspace: Path, program_text: str) -> Path:
    trace_cpp = workspace / "trace.cpp"
    trace_cpp.write_text(program_text)
    return trace_cpp


def build_trace(workspace: Path, output_name: str = "trace") -> Path:
    output = workspace / output_name
    cmd = [
        "g++",
        "-std=c++17",
        "-O0",
        str(workspace / "trace.cpp"),
        *(str(workspace / rel) for rel in FILES),
        f"-I{workspace}",
        "-o",
        str(output),
    ]
    subprocess.run(cmd, check=True, cwd=ROOT)
    return output


def cleanup_workspace(workspace: Path) -> None:
    shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(
        "This module is a helper library. Import it and generate a concrete trace program for the position you want to compare."
    )
