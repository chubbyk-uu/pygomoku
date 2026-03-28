# Default Config Baselines

## Purpose

This document separates four similar but different concepts:

- the reference engine's default behavior
- `pyslow`'s engine-default behavior
- the current alignment and audit baseline
- the current interactive development entry defaults

These must not be mixed together.

## Reference Engine Defaults

This section describes the default behavior of the checked `SlowRenju` source and
the compiled reference path we currently align against.

Primary references:

- [`SlowRenju/Common/main.cpp`](../SlowRenju/Common/main.cpp)
- [`SlowRenju/Common/global_value.cpp`](../SlowRenju/Common/global_value.cpp)
- [`SlowRenju/AI/AIx.cpp`](../SlowRenju/AI/AIx.cpp)

### Root Search Defaults

For the checked Gomocup fixed-search build path, reference defaults are:

- `fixedsearch = 1`
- `searchdepth = 5`
- `searchwidth = 15`
- `ratio_num = 1`
- `ratio_den = 1`

This is the practical default used by the compiled `slowrenju_linux` path when
no explicit `INFO depth/width` override is sent.

If `fixedsearch` is turned off, the time-managed path falls back to:

- `depth = 24`
- `width = 60`

Source:

- [`main.cpp`](../SlowRenju/Common/main.cpp)
- [`global_value.cpp`](../SlowRenju/Common/global_value.cpp)

### Runtime Defaults

Reference globals initialize to:

- `computevcf = 1`
- `staticboard = 1`
- `nodelimit = 0`
- `nbest = 0`
- `timee = 30000000`
- `timel = 30000000`

Source:

- [`global_value.cpp`](../SlowRenju/Common/global_value.cpp#L20)

### Root VCF Defaults

Reference root search uses:

- root self-VCF immediate check depth `8`
- root opponent-VCF pressure check depth `7`
- root candidate filter also re-checks opponent VCF at depth `7`

Source:

- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L306)
- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L320)
- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L364)

### Non-root RTVCF Defaults

Reference source contains a non-root `RTVCF` branch, but it is not enabled in
the default checked build path.

- default status: `off`
- if enabled, the depth formula is `depth + 6 - 2 * DEPTH`
- semantics are not "return immediate win for self"; the branch is used as
  opponent-VCF pressure filtering inside normal search

Source:

- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L634)
- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L913)
- [`SlowRenju/VCF/VCF.cpp`](../SlowRenju/VCF/VCF.cpp#L22)

### Opening Special Cases

Reference source has:

- empty-board opening shortcut
- one-move center-response shortcut behind `if (N == 15)`

Important:

- our current compiled alignment harness follows the verified compiled path
- in that path, the one-move `if (N == 15)` shortcut is not part of the active
  baseline behavior
- therefore `open_center` is treated as a normal search case in the aligned
  Python implementation

## `pyslow` Engine Defaults

This section describes the current code defaults in `pyslow`.

Primary reference:

- [`pyslow/config.py`](../pyslow/config.py)

### Root Search Defaults

`pyslow` engine-default root search is:

- `depth = 24`
- `width = 60`
- `ratio_num = 1`
- `ratio_den = 1`

Source:

- [`config.py`](../pyslow/config.py#L171)

### Runtime Defaults

`pyslow` engine-default runtime options are:

- `compute_vcf = True`
- `nonroot_vcf = False`
- `static_board = True`
- `dynamic_board_margin = 4`

Notes:

- `compute_vcf=True` means root VCF behavior is enabled by default
- `nonroot_vcf=False` means reference-style non-root RTVCF pressure filtering is
  disabled by default, matching the reference default build path
- `dynamic_board_margin=4` is a Python-only runtime parameter, but it does not
  affect the default aligned behavior because `static_board=True` bypasses the
  dynamic root-window path entirely

Source:

- [`config.py`](../pyslow/config.py#L161)

### Root VCF Defaults

Current `pyslow` root VCF behavior matches the reference baseline:

- root self-VCF immediate check depth `8`
- root opponent-VCF pressure filter depth `7`

Source:

- [`root.py`](../pyslow/search/root.py#L188)
- [`root.py`](../pyslow/search/root.py#L255)

### Non-root RTVCF Behavior

Current `pyslow` behavior:

- default status: `off`
- if manually enabled, uses the reference-style depth formula:
  `int(depth + 6 - 2 * root_depth)`
- semantics follow reference search behavior:
  filter out candidate moves that fail to break opponent VCF pressure

Source:

- [`alphabeta.py`](../pyslow/search/alphabeta.py)

### Parameter Table Defaults

`pyslow` default `SLOWRENJU_PARA` is aligned with reference `para[]`.

Important confirmed point:

- `para[263] = 1000000.0`

Primary references:

- [`config.py`](../pyslow/config.py)
- [`global_value.cpp`](../SlowRenju/Common/global_value.cpp)

## Current Alignment And Audit Baseline

This section is not the engine default. It is the stable shallow baseline we use
for reference alignment, semantic audit, and fast local regression.

### Alignment Baseline

Current alignment baseline:

- `max_depth = 3`
- `root_width = 10`
- `ratio_num = 1`
- `ratio_den = 1`
- `compute_vcf = True`
- `nonroot_vcf = False`
- `static_board = True`
- `dynamic_board_margin = 4`

Notes:

- the fixed-position compare script should use this baseline
- the current compare set contains `70` positions
- [`alignment_compare.py`](../benchmarks/alignment_compare.py)
  now supports:
  - grouped runs via `--group`
  - grouped parallel execution via `--jobs`
  - default grouped parallel execution with `jobs=6`
- if a benchmark or test intentionally uses a different setting, it should say
  so explicitly
- because `static_board=True`, `dynamic_board_margin` is inactive in this
  baseline and therefore does not create reference drift

### Profiling Baseline

Current profiling baseline should stay the same as the alignment
baseline unless a benchmark explicitly says otherwise:

- `max_depth = 3`
- `root_width = 10`

## Current Interactive Development Entry Defaults

This section covers the defaults used by interactive entrypoints, not the
reference-alignment baseline.

Current interactive entry defaults:

- `max_depth = 5`
- `root_width = 20`
- GUI `SlowRenju` backend fixed search: `depth = 8`, `width = 24`
- opponent runner `SlowRenju` default fixed search: `depth = 5`, `width = 20`

Source:

- [`pyslow/gomocup_engine.py`](../pyslow/gomocup_engine.py)
- [`pyslow/gui.py`](../pyslow/gui.py)

Reason:

- current development work is using `5/20` as the practical default
- `5/20` is an interactive / development strength default, not an alignment
  baseline
- the GUI keeps a separate fixed `SlowRenju` backend default at `8/24`
- the opponent runner keeps a separate `SlowRenju` practical default at `5/20`
- it remains noticeably heavier than the audit baselines, so it is an interactive
  strength default, not an alignment or audit baseline
- the reference-alignment and semantic-audit baseline remains `3/10` on purpose
  for faster feedback and stable trace comparison

Coordinate convention for GUI / protocol / logs:

- coordinates are `(x, y)` = `(column, row)`
- this matches both current `pyslow` output and the checked reference trace
- do not read logged coordinates as `(row, column)`

Recent practical checkpoints for these defaults:

- `classic d5 w20` vs `zhou d5`, opening-set `9`:
  - result `9/0/0` as black and `9/0/0` as white
  - average engine time about `1539.62 ms/step`
- `classic d5 w30` vs `zhou d5`, opening-set `9`:
  - result `9/0/0` as black and `9/0/0` as white
  - average engine time about `1990.75 ms/step`
- GUI `SlowRenju d8 w24` reference check vs `zhou d5`, opening-set `9`:
  - result `9/0/0` as black and `9/0/0` as white
  - average engine time about `769.96 ms/step`
- `SlowRenju d10 w24` comparison check vs `zhou d5`, opening-set `9`:
  - result `9/0/0` as black and `9/0/0` as white
  - average engine time about `5009.70 ms/step`

## Rules For Future Changes

1. Do not call the alignment baseline or interactive defaults the engine default.
2. If root depth/width are changed for profiling or testing, record the exact
   values.
3. If `nonroot_vcf` is enabled for experiments, say so explicitly.
4. If interactive defaults are raised again, measure both fixed-search timing
   and short selfplay timing before changing docs.
5. If a future `VCT` module is added, document its defaults separately. It does
   not exist yet and therefore has no current default depth.

## Test Execution Defaults

Current recommended local test defaults:

- full-suite runs should use `python -m pytest -n auto -q`
- alignment-heavy runs should use `python -m pytest -m alignment -n auto -q`
- grouped test counts are currently `fast=39`, `alignment=89`, `integration=29`
- single-thread `pytest -q` is still valid, but it is not the preferred default
  because full-suite wall time is much worse
