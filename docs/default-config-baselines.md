# Default Config Baselines

## Purpose

This document separates three similar but different concepts:

- the reference engine's default behavior
- `pyslow`'s engine-default behavior
- the current development baseline used for alignment, testing, and profiling

These must not be mixed together.

## Reference Engine Defaults

This section describes the default behavior of the checked `SlowRenju` source and
the compiled reference path we currently align against.

Primary references:

- [`SlowRenju/Common/main.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Common/main.cpp)
- [`SlowRenju/Common/global_value.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Common/global_value.cpp)
- [`SlowRenju/AI/AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp)

### Root Search Defaults

Reference command-line entry launches:

- `depth = 24`
- `width = 60`
- `ratio_num = 1`
- `ratio_den = 1`

Source:

- [`main.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Common/main.cpp#L527)

### Runtime Defaults

Reference globals initialize to:

- `computevcf = 1`
- `staticboard = 1`
- `nodelimit = 0`
- `nbest = 0`
- `timee = 30000000`
- `timel = 30000000`

Source:

- [`global_value.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Common/global_value.cpp#L20)

### Root VCF Defaults

Reference root search uses:

- root self-VCF immediate check depth `8`
- root opponent-VCF pressure check depth `7`
- root candidate filter also re-checks opponent VCF at depth `7`

Source:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L306)
- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L320)
- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L364)

### Non-root RTVCF Defaults

Reference source contains a non-root `RTVCF` branch, but it is not enabled in
the default checked build path.

- default status: `off`
- if enabled, the depth formula is `depth + 6 - 2 * DEPTH`
- semantics are not "return immediate win for self"; the branch is used as
  opponent-VCF pressure filtering inside normal search

Source:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L634)
- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L913)
- [`SlowRenju/VCF/VCF.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/VCF/VCF.cpp#L22)

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

- [`pyslow/config.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/config.py)

### Root Search Defaults

`pyslow` engine-default root search is:

- `depth = 24`
- `width = 60`
- `ratio_num = 1`
- `ratio_den = 1`

Source:

- [`config.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/config.py#L171)

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

- [`config.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/config.py#L161)

### Root VCF Defaults

Current `pyslow` root VCF behavior matches the reference baseline:

- root self-VCF immediate check depth `8`
- root opponent-VCF pressure filter depth `7`

Source:

- [`root.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/root.py#L188)
- [`root.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/root.py#L255)

### Non-root RTVCF Behavior

Current `pyslow` behavior:

- default status: `off`
- if manually enabled, uses the reference-style depth formula:
  `int(depth + 6 - 2 * root_depth)`
- semantics follow reference search behavior:
  filter out candidate moves that fail to break opponent VCF pressure

Source:

- [`alphabeta.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/alphabeta.py)

### Parameter Table Defaults

`pyslow` default `SLOWRENJU_PARA` is aligned with reference `para[]`.

Important confirmed point:

- `para[263] = 1000000.0`

Primary references:

- [`config.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/config.py)
- [`global_value.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Common/global_value.cpp)

## Current Development Baseline

This section is not the engine default. It is the working baseline we use for
development comparisons and local experiments.

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
- if a benchmark or test intentionally uses a different setting, it should say
  so explicitly
- because `static_board=True`, `dynamic_board_margin` is inactive in this
  baseline and therefore does not create reference drift

### Profiling Baseline

Current profiling baseline should stay the same as the development alignment
baseline unless a benchmark explicitly says otherwise:

- `max_depth = 3`
- `root_width = 10`

CLI / GUI defaults are intentionally not treated as part of the development
baseline yet. They can be revisited after performance work improves practical
search reach.

## Rules For Future Changes

1. Do not call the development baseline the engine default.
2. If root depth/width are changed for profiling or testing, record the exact
   values.
3. If `nonroot_vcf` is enabled for experiments, say so explicitly.
4. If a future `VCT` module is added, document its defaults separately. It does
   not exist yet and therefore has no current default depth.
