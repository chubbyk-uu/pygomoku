# Next Steps

## Current State

`pyslow` is no longer a skeleton. The current codebase now has:

- working `15x15` freestyle board, undo, winner detection, zobrist
- parameter mapping aligned to `SlowRenju`
- `ValueWide`-style local caches and global eval
- normal move generation, TT, iterative deepening alpha-beta, root control
- working `VCF` and `ThreatBoardView`
- working Gomocup protocol adapter
- working pygame GUI
- benchmark/profile helpers

Recent audit update:

- another model added a git repository and committed the then-current project state
- three additional reference-alignment fixes were reviewed and confirmed as correct:
  - alpha-beta empty-candidate return uses `-INF-1`
  - VCF memo is cleared once per begin-depth layer
  - protocol edge cases now match reference source semantics more closely
- a systematic 16-position comparison script was added:
  - [alignment_compare.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py)
- current comparison result is:
  - 16/16 positions aligned
- the last two alignment issues are now closed:
  - `mid_ladder` was a real bug in `pyslow`
  - `open_center` was a Python-only shortcut mismatch against the compiled reference path
- concrete root causes fixed:
  - `para[263]` in [`config.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/config.py) was corrected from `6000.0` to the reference value `1000000.0`
  - non-root alpha-beta `downf` handling now matches reference sibling-accumulation semantics
  - the one-move center opening shortcut was removed from [`root.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/root.py) so the one-stone position follows the verified reference search path
- exact regression coverage was added for the resolved non-root ladder case:
  - [`tests/test_search.py`](/home/jerry/python-test/gomoku/slow_temp/tests/test_search.py)
  - `mid_ladder + (7,5)` now matches reference with `score=-47`, `move=(7,9)`

Current confidence level:

- for the current freestyle 15x15 scope and current compare set, branch alignment is closed
- treat the current search/eval semantics as the reference-aligned baseline
- subsequent work should focus on speed and search reach without changing behavior

The most important result is that alignment work is now driven by:

- direct reference traces
- branch-level checklist verification

Instead of relying only on “main flow looks similar”.

Relevant documents:

- [AGENTS.md](/home/jerry/python-test/gomoku/slow_temp/AGENTS.md)
- [reference-analysis.md](/home/jerry/python-test/gomoku/slow_temp/docs/reference-analysis.md)
- [search-flow.md](/home/jerry/python-test/gomoku/slow_temp/docs/search-flow.md)
- [vcf-design.md](/home/jerry/python-test/gomoku/slow_temp/docs/vcf-design.md)
- [branch-alignment-checklist.md](/home/jerry/python-test/gomoku/slow_temp/docs/branch-alignment-checklist.md)
- [acceleration-plan.md](/home/jerry/python-test/gomoku/slow_temp/docs/acceleration-plan.md)

## Work Order

### 1. Performance Analysis And Acceleration

Primary source of truth:

- [acceleration-plan.md](/home/jerry/python-test/gomoku/slow_temp/docs/acceleration-plan.md)

Rules:

- do not change semantics
- always keep Python fallback
- every speedup must have both:
  - semantic regression evidence
  - benchmark evidence

Execution order:

1. re-run hotspot measurement on the now-stable aligned baseline
2. optimize pure Python implementation first
3. increase practical root depth / width only after measuring post-optimization gains
4. only then consider native replacements for proven hotspots

Likely hotspots:

- `patterns/line`
- `eval/local`
- `threats/threat_board`
- `threats/vcf`
- board access hot paths

### 2. Search Reach Upgrade

After each performance round:

1. benchmark achievable `depth` / `width` increases under fixed time budgets
2. keep `alignment_compare.py` and targeted regression tests green
3. expand benchmark coverage before changing default limits

Immediate likely knobs:

- root iterative depth
- root width
- child width ratio
- VCF depth caps

### 3. Add VCT

Only after:

- checklist alignment is sufficiently stable
- VCF semantics are trusted
- current hotspots are understood

This is intentionally after alignment and acceleration preparation.

### 4. Continue Product-Level Work

After the above:

- improve GUI usability
- possibly add stronger selfplay / benchmark suites
- plan native backend boundaries more concretely

## Resume Advice

When resuming work later, do not start by re-analyzing the whole project.

Start here:

1. run [alignment_compare.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py) to confirm the baseline still stays `16/16`
2. read [acceleration-plan.md](/home/jerry/python-test/gomoku/slow_temp/docs/acceleration-plan.md)
3. profile the aligned baseline before changing any default search limits
4. after each speedup, re-run the alignment and regression suites
