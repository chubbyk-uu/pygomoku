# pygomoku

> 中文版 README：[README.cn.md](README.cn.md)

`pygomoku` is a free-rule Gomoku engine project written primarily in Python, with hot paths accelerated via native / Cython extensions.

The goal of this project is not to ship a demo-quality program, but to build:

- A free-rule (no forbidden moves) Gomoku engine
- A search program with solid practical strength and a sustainable iteration path
- A Python-first implementation that preserves a clear native acceleration path
- Human-vs-AI GUI play
- Gomocup-protocol support so it can play against other AIs

The immediate concrete goal is for `pygomoku` to reliably beat the in-repo opponent `zhou` (under `opponent/zhou/`) in real games.

This project can be understood as a `SlowRenju`-inspired, Python/Cython-oriented reimplementation of a free-rule Gomoku engine. See the acknowledgements section at the end.

OpenAI Codex was the primary engineering collaboration tool used during development.

This repository is released under the GNU GPL v3.0; the full text is in `LICENSE` at the repo root.

## Feature overview

- 15x15 free-rule Gomoku
- Current mainline engine (referred to internally as `classic`)
- Iterative deepening + Alpha-Beta + TT + candidate-move pruning
- VCF tactical search
- Optional Cython acceleration
- Pygame GUI for human-vs-AI play
- Gomocup protocol engine entry point
- Fixed-opening match script against the in-repo `zhou` opponent
- Full unit, search, protocol, and integration test coverage

## Project goals

This repository is currently focused on a very deliberate engineering trajectory:

1. Keep the current mainline engine (internally `classic`) stable, deterministic, and verifiable.
2. Continuously improve practical speed without breaking semantics.
3. Progressively migrate hot spots to Cython / native to accelerate search, evaluation, and tactical modules.
4. Validate with the GUI, the Gomocup protocol, and fixed-opening matches.

## Coordinate convention

The whole project uses `(x, y)` coordinates:

- `x` is the column
- `y` is the row

In other words, coordinates are "column first, then row".

This is worth flagging because the in-repo opponent `zhou` mostly uses `(row, col)` internally. The match scripts perform explicit conversions on the boundary, but when reading logs, analysing openings, or hand-crafting test positions, always remember the difference.

## Directory layout

The repository is currently organised roughly as follows:

```text
gomoku-py/
├── pygomoku/                   # Main engine code
│   ├── search/                 # root / alphabeta / movegen / ordering / tt
│   ├── eval/                   # local eval, global eval, caches
│   ├── patterns/               # patterns, buckets, line utilities
│   ├── threats/                # VCF / VCT / tactical board
│   ├── protocol/               # Gomocup protocol adapter
│   ├── gomocup_engine.py       # Gomocup protocol CLI entry
│   └── gui.py                  # Pygame GUI entry
├── opponent/
│   ├── run_pygomoku_vs_zhou.py # pygomoku vs zhou match script
│   └── zhou/                   # In-repo opponent program
├── benchmarks/                 # Performance and self-play smoke tests
├── tests/                      # Tests
├── setup.py                    # Cython extension build
└── pyproject.toml              # Project configuration
```

## Core components

### 1. Main engine `pygomoku/`

This is the heart of the repository.

- `pygomoku/search/` — search main loop
- `pygomoku/eval/` — position evaluation and incremental caches
- `pygomoku/patterns/` — patterns and bucket semantics
- `pygomoku/threats/` — VCF and other tactical modules
- `pygomoku/protocol/` — Gomocup protocol integration

### 2. GUI

`pygomoku/gui.py` provides a local human-vs-AI interface. It uses only the in-repo mainline engine; it no longer depends on swapping in external engine binaries.

### 3. Gomocup protocol entry

`pygomoku/gomocup_engine.py` exposes a stdin/stdout-based Gomocup engine entry point, making it easy to play protocol-level matches against other AIs.

### 4. Opponent program `zhou`

`opponent/zhou/` is the opponent program currently kept in-repo.

`opponent/run_pygomoku_vs_zhou.py` runs batched fixed-opening matches; it is an important practical validation tool at this stage.

### 5. Cython acceleration

Several hot-path modules ship `.pyx` extensions, e.g.:

- `patterns/_line_cy.pyx`
- `eval/_local_cy.pyx`
- `eval/_caches_cy.pyx`
- `search/_movegen_cy.pyx`
- `search/_ordering_cy.pyx`
- `threats/_threat_board_cy.pyx`

These extensions are a very important part of the project as it stands.

## Cython acceleration is strongly recommended

This project **can run without compiling Cython**, because the Python fallback path is preserved.

However:

- Without compilation, things work functionally.
- Without compilation, the engine is meaningfully slower.
- In search, local evaluation, candidate generation, and tactical judgement — the hottest paths — the pure-Python version is far weaker in practice.

This has been verified in the repo: temporarily moving the compiled `.so` files out of `pygomoku/` still leaves `tests/test_config.py` and `tests/test_search.py` passing, confirming the Python fallback is usable; it is simply too slow to be a normal runtime mode.

In practice:

- If you are only reading code or doing small functional checks, you can skip compilation.
- If you intend to run deeper searches, GUI matches, batch tests, or fight `zhou`, **compile Cython first**.

Put plainly:

- The Python fallback "runs."
- The Cython build is what makes it actually "usable."

## Environment requirements

Recommended environment:

- Python 3.11 or newer
- Linux or macOS
- A working C/C++ toolchain
- `pip`

Common Python dependencies:

- `Cython`
- `pytest`
- `pytest-xdist`
- `pygame`

## Installation

### Basic install

Editable install of the main package is recommended:

```bash
pip install -e .
```

If you need the GUI:

```bash
pip install -e ".[gui]"
```

For development and testing, install at least:

```bash
pip install -U pip setuptools wheel
pip install cython pytest pytest-xdist pygame
pip install -e ".[gui]"
```

After the steps above, most commands in this README can be run directly without prefixing `PYTHONPATH=.`.

## Building Cython extensions

### Linux

Prepare the build environment first.

On Debian / Ubuntu the usual way is:

```bash
sudo apt update
sudo apt install -y build-essential python3-dev
python -m pip install -U pip setuptools wheel cython
```

Then build at the repo root:

```bash
python setup.py build_ext --inplace
```

If you intend to run matches, it is strongly recommended to also build `zhou`'s Cython extensions:

```bash
python opponent/zhou/setup.py build_ext --inplace
```

### macOS

Install Apple's command-line build tools first:

```bash
xcode-select --install
python -m pip install -U pip setuptools wheel cython
```

Then build at the repo root:

```bash
python setup.py build_ext --inplace
```

And build `zhou` as well:

```bash
python opponent/zhou/setup.py build_ext --inplace
```

### Notes on the build

After compilation, hot-path modules generate native extension files; the runtime will prefer these compiled modules.

If you modify a `.pyx` file, you generally need to rebuild:

```bash
python setup.py build_ext --inplace
```

## Running the GUI

The GUI entry point is:

```bash
python -m pygomoku.gui
```

You can also pass explicit search parameters:

```bash
python -m pygomoku.gui --depth 6 --width 20
```

The default depth on user-facing entry points is `6`. This is because the mainline has fixed the iteration boundary of `max_depth`: the depth you pass in is now the depth that actually gets completed. To keep the default real search strength close to the configuration used before that fix, the default `pygomoku` depth across GUI / Gomocup / match scripts is uniformly `6`.

If `pygame` isn't installed, the GUI won't start.

## Running the Gomocup protocol engine

The CLI protocol entry is:

```bash
python -m pygomoku.gomocup_engine
```

With fixed search parameters:

```bash
python -m pygomoku.gomocup_engine --depth 6 --width 20
```

This path is suitable for:

- Plugging into a Gomocup-protocol environment
- Protocol-level matches against other AIs
- Being launched as an engine subprocess by match scripts

## Tests

### Recommended

The tests are grouped by purpose; parallel runs are preferred.

Full regression:

```bash
python -m pytest -n auto -q
```

### Test groups

Fast tests:

```bash
python -m pytest -m fast -q
```

Search / evaluation / tactical tests:

```bash
python -m pytest -m alignment -n auto -q
```

Protocol / GUI / integration tests:

```bash
python -m pytest -m integration -n auto -q
```

### Basic smoke

If you just want a quick check that mainline isn't broken:

```bash
python -m pytest tests/test_config.py tests/test_search.py tests/test_protocol.py -n auto -q
```

GUI smoke:

```bash
python -m pytest tests/test_gui.py -q
```

## Matches against `zhou`

A very important goal at this stage is decisively beating the in-repo `zhou` in match play.

Match script:

```bash
python opponent/run_pygomoku_vs_zhou.py --help
```

### Quick fixed-opening match

```bash
python opponent/run_pygomoku_vs_zhou.py \
  --engine-type pygomoku-direct \
  --opening-set 5 \
  --pygomoku-depth 6 \
  --pygomoku-width 20 \
  --zhou-depth 5 \
  --parallel 10 \
  --colors both
```

`pygomoku-direct` calls the Python engine entry point in-process, which is convenient for fast local validation. This path has been minimally exercised end-to-end.

### Using the Gomocup protocol entry for matches

```bash
python opponent/run_pygomoku_vs_zhou.py \
  --engine-type pygomoku \
  --opening-set 5 \
  --pygomoku-depth 6 \
  --pygomoku-width 20 \
  --zhou-depth 5 \
  --parallel 10 \
  --colors both
```

`pygomoku` here means launching a standard Gomocup-protocol engine process via `python -m pygomoku.gomocup_engine`. It is closer to an external match environment, but the Gomocup-protocol path has not been specifically optimised yet, so it is somewhat slower. This path has also been minimally exercised end-to-end.

### Expanding to 9 fixed openings

```bash
python opponent/run_pygomoku_vs_zhou.py \
  --engine-type pygomoku-direct \
  --opening-set 9 \
  --pygomoku-depth 6 \
  --pygomoku-width 20 \
  --zhou-depth 5 \
  --parallel 18 \
  --colors both
```

### Fixed-opening sets

The match script uses fixed first moves, in `(x, y)` coordinates in the range `0..14`. That is, `(7, 7)` is tengen.

To reiterate: `(x, y)` here means "column, row", not the "row, column" convention that `zhou` tends to use internally.

`--opening-set 5` covers these 5 first moves:

- `(7, 7)`
- `(4, 4)`
- `(4, 10)`
- `(10, 4)`
- `(10, 10)`

`--opening-set 9` adds 4 more corner-leaning positions on top of the 5 above:

- `(2, 2)`
- `(2, 12)`
- `(12, 2)`
- `(12, 12)`
- `(4, 4)`
- `(10, 4)`
- `(4, 10)`
- `(10, 10)`
- `(7, 7)`

Combined with `--colors both`, each fixed opening is tested with `pygomoku` playing both black and white.

### Output

By default the script writes the black and white results to separate JSON files under `opponent/`, for later comparison and analysis.

### Common arguments

- `--engine-type`: pick `pygomoku-direct` or `pygomoku`. The former calls the Python engine entry directly; the latter launches a Gomocup-protocol process via `python -m pygomoku.gomocup_engine`.
- `--opening-set`: pick a fixed-opening set; currently `5` and `9` are supported.
- `--pygomoku-depth`: `pygomoku`'s search depth, default 6.
- `--pygomoku-width`: `pygomoku` root candidate width, default 20. Larger usually means more search but slower.
- `--zhou-depth`: `zhou`'s search depth, default 5.
- `--parallel`: number of parallel match processes. Controls batch throughput and machine load.
- `--colors`: choose `black`, `white`, or `both`.
- `--limit-openings`: take only the first N fixed openings — useful for quick smoke runs.
- `--max-moves`: per-game move cap, default 120, to avoid pathological games dragging on forever.
- `--output-black` / `--output-white`: explicit JSON output paths for the black-side and white-side results.

## Performance and debugging

The repository ships a handful of performance and smoke scripts:

- `benchmarks/profile_search.py`
- `benchmarks/hotspot_report.py`
- `benchmarks/selfplay_smoke.py`
- `benchmarks/cache_audit.py`

For example:

```bash
python benchmarks/profile_search.py --depth 2 --width 12 --top 25
python benchmarks/hotspot_report.py --top 20
python benchmarks/selfplay_smoke.py
```

If you haven't run `pip install -e .` yet, scripts launched directly from a subdirectory (like `profile_search.py`) may need to be run as:

```bash
PYTHONPATH=. python benchmarks/profile_search.py --depth 2 --width 12 --top 25
```

## Development notes

- Treat the current mainline engine as the single source of semantic truth — internally it is still called `classic`.
- Stabilise semantics before optimising performance.
- When changing hot paths, keep the Python fallback intact whenever possible.
- "Feels stronger" is not sufficient evidence — back changes with tests, benchmarks, or match results.
- For broad test runs, prefer parallel: `python -m pytest -n auto -q`.

## Acknowledgements

Thanks to the [SlowRenju](https://github.com/wind23/SlowRenju) project on GitHub.

Although this project has by now converged onto its own Python mainline engine, it can still be understood as a `SlowRenju`-inspired, Python/Cython-oriented reimplementation of a free-rule Gomoku engine. Many of the key concepts in this repository were not designed from scratch — they were absorbed and digested from that mature prior work before being landed here. Internally this mainline is still referred to as `classic`.
