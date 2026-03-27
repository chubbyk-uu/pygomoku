# Performance Roadmap

## Current Stable Baseline

Semantic stability:

- [`alignment_compare.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py)
  stays `70/70`
- current broad regression pass is `155 passed`

Interactive defaults:

- GUI / Gomocup entry defaults: `depth=5`, `width=15`
- alignment / semantic-audit baseline remains `depth=3`, `width=10`

Representative current timings:

- `PYTHONPATH=. python benchmarks/profile_search.py --depth 5 --width 15 --top 10`
  - current stable search time is about `0.51s`
- `python benchmarks/selfplay_smoke.py --depth 5 --width 15 --plies 4`
  - current average is about `1463 ms/ply`

## What Has Already Landed

Pure Python wins:

- board and line-path cleanup
- move generation cleanup
- `shape_cache` snapshot/restore changed from whole-cache deep copy to undo-log

Optional native backends already landed:

- `patterns/line`
- local-eval point-shape helpers
- `movegen`
- `ordering`
- `threat_board` hot helpers
- local-eval update kernel used by `value_wide_compute`

These are no longer “planned”; they are part of the current baseline.

## Current Bottlenecks

The remaining wall is no longer generic Python overhead. It is concentrated in:

1. [`pyslow/eval/local.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/eval/local.py)
   - `value_wide_compute`
   - `compute_bucket_and_attack`
   - `compute_direction_shape`

2. [`pyslow/search/movegen.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/movegen.py)
   - `generate_candidates`

3. [`pyslow/eval/global_eval.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/eval/global_eval.py)
   - `evaluate_board`
   - `last5 / next43` related paths

4. [`pyslow/eval/caches.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/eval/caches.py)
   - remaining snapshot / restore work outside the resolved `shape_cache` copy path

5. [`pyslow/threats/vcf.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/threats/vcf.py)
   - recursive tactical search

`VCF` is no longer the first wall after the landed attacker-scan and threat-board wins.

## Cost-Model Rules

Recent failed experiments showed that “hot function” is not enough reason to
change code. Every next optimization should start from a cost model:

1. decide whether the hotspot is dominated by:
   - Python object churn
   - bulk copying
   - arithmetic / scan loops
   - recursive control flow
2. only then choose:
   - Python rewrite
   - undo-log / patch strategy
   - native kernel
   - no change

Do not repeat these now-invalid patterns:

- thin wrapper Cythonization around a still-Python object graph
- `flat + nested` double-write cache experiments
- lazy-property cache rebuild experiments
- fresh isolated replay used as a substitute for in-game persistent search
- Gomocup runners that `RESTART` the engine before every move

## Priority Order

### Priority 1: Local Eval / Movegen / Ordering Subsystem

Primary target:

- reduce the remaining cost of local cache updates and root candidate generation

Near-term focus:

- inspect `value_wide_compute` sub-costs before each new native step
- keep `movegen / ordering` changes tied to measured wins, not guesswork

### Priority 2: Global Eval / Remaining Cache Strategy

Primary target:

- avoid expensive cache work that still survives after `shape_cache` undo-log

Rules:

- measure exact copy / restore contribution first
- prefer patch-style restore only where changed-point counts justify it

### Priority 3: VCF / Threat Search

Primary target:

- tactical recursion cost after the eval/cache layer is cheaper

Reason:

- `VCF` is hot, but still downstream of eval/cache costs on practical searches

## Native Strategy From Here

Keep:

- search shell
- protocol
- GUI
- root/alphabeta orchestration

in Python unless profiling later proves otherwise.

Prefer:

- small, data-oriented native kernels
- Python fallback always available
- one hotspot family at a time

Current best candidate family:

1. local-eval kernels
2. movegen / ordering kernels where measurable gains still remain
3. global-eval helpers only if they still remain large after local-eval work
4. VCF / threat helpers after that

## Validation Rules

Every performance change must keep all of these green:

- [`alignment_compare.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py)
  at `70/70`
- current regression suite
- fixed search timing:
  - `profile_search --depth 5 --width 15`
- practical timing:
  - `selfplay_smoke --depth 5 --width 15`

## Replay And GUI Notes

When checking GUI or protocol behavior:

- coordinates are `(x, y)` = `(column, row)`
- for in-game move verification, prefer persistent-searcher replay over fresh
  isolated single-position replay

Fresh replay is still useful, but it is not a drop-in substitute for the GUI's
real search path once TT and persistent search state are involved.

## Search-Reach Goal

The next practical acceleration target is not just “a bit faster”.

The current goal is:

1. keep `depth=5 width=15` comfortably practical
2. move the stable Python engine toward at least `depth=8 width=20`
3. compare practical opponent results only under protocol-correct persistent engine sessions
