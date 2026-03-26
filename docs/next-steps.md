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

1. `VCF` repeated-state / `hm` / `Reorder` equivalent branches
2. remaining root / alpha-beta stop interaction edge cases
3. remaining protocol/runtime behavior against a compiled reference engine process
4. if needed, more extreme movegen branch cases that do not naturally appear in random freestyle positions

Method:

- prefer corrected minimal reference trace harnesses
- fix the earliest diverging layer
- add one regression test for each non-obvious branch

Reference harness helper:

- [reference_trace.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/reference_trace.py)

Important note:

- temporary `/tmp/slowrenju-trace-*` build directories are disposable
- only the methodology in the repo should be treated as persistent

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
2. continue from the first unchecked item
3. use [reference_trace.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/reference_trace.py) when branch semantics are uncertain
4. after checklist work is stable, switch to [acceleration-plan.md](/home/jerry/python-test/gomoku/slow_temp/docs/acceleration-plan.md)
