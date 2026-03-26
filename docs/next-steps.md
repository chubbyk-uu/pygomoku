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
  - 14/16 positions aligned
  - `open_center` is a reference-trace construction artifact, not a `pyslow` bug
  - `mid_ladder` still has a real score mismatch to investigate

Current confidence level:

- branch alignment is strong, but not yet complete enough to declare full reference equivalence
- do not treat the previous “all items verified” commit message as final truth
- the remaining work should continue from the unresolved comparison residuals, not from broad re-analysis

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

### 1. Finish Remaining Checklist Alignment

Primary source of truth:

- [branch-alignment-checklist.md](/home/jerry/python-test/gomoku/slow_temp/docs/branch-alignment-checklist.md)

Continue from the remaining unchecked items, with this priority:

1. investigate the systematic-compare residual `mid_ladder`
2. re-check any checklist item whose confidence came only from local reasoning rather than corrected reference trace
3. continue branch-level comparison for root / alpha-beta / movegen edge paths
4. continue protocol/runtime comparison only after search-score residuals are understood

Method:

- prefer corrected minimal reference trace harnesses
- fix the earliest diverging layer
- add one regression test for each non-obvious branch
- when a systematic compare mismatch is found, do not mark any surrounding checklist item as complete until that mismatch is explained

Reference harness helper:

- [reference_trace.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/reference_trace.py)

Important note:

- temporary `/tmp/slowrenju-trace-*` build directories are disposable
- only the methodology in the repo should be treated as persistent
- the harness itself must set `S=15; boardSize=15;`
- the `open_center` mismatch in [alignment_compare.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py) is caused by reference compile-time `N==20`, so that one opening shortcut is intentionally not treated as a `pyslow` bug

### 2. Performance Analysis And Acceleration

Primary source of truth:

- [acceleration-plan.md](/home/jerry/python-test/gomoku/slow_temp/docs/acceleration-plan.md)

Rules:

- do not change semantics
- always keep Python fallback
- every speedup must have both:
  - semantic regression evidence
  - benchmark evidence

Execution order:

1. re-run hotspot measurement after alignment work stabilizes
2. optimize pure Python implementation first
3. only then consider native replacements

Likely hotspots:

- `patterns/line`
- `eval/local`
- `threats/threat_board`
- `threats/vcf`
- board access hot paths

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

1. read [branch-alignment-checklist.md](/home/jerry/python-test/gomoku/slow_temp/docs/branch-alignment-checklist.md)
2. run [alignment_compare.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py) and start from `mid_ladder`
3. use [reference_trace.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/reference_trace.py) when branch semantics are uncertain
4. after the remaining comparison residuals are explained, continue from the first unchecked or downgraded checklist item
5. after checklist work is stable, switch to [acceleration-plan.md](/home/jerry/python-test/gomoku/slow_temp/docs/acceleration-plan.md)
