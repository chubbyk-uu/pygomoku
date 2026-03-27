# Performance Roadmap

## Purpose

This document turns the current profiling evidence into an execution plan.

It answers three questions:

1. how complete the current profiling evidence is
2. which hotspots should be optimized first, and how
3. which native path is the best fallback if pure Python optimization is not enough

This document is intentionally stricter than the generic
[`acceleration-plan.md`](/home/jerry/python-test/gomoku/slow_temp/docs/acceleration-plan.md).
`acceleration-plan.md` defines rules. This file defines the concrete next
execution order.

## Current Baseline

Semantic baseline:

- [`alignment_compare.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py)
  currently matches `70/70`
- development baseline remains:
  - `max_depth = 3`
  - `root_width = 10`
  - `compute_vcf = True`
  - `nonroot_vcf = False`

Current performance evidence:

- `python benchmarks/hotspot_report.py --top 30`
- `PYTHONPATH=. python benchmarks/profile_search.py --depth 3 --width 10 --top 40`

Observed timing:

- `depth=2 width=8 plies=6` -> about `197 ms/ply`
- `depth=3 width=10 plies=6` -> about `741 ms/ply`
- `depth=6 width=10 plies=4` -> about `12922 ms/ply`

## How Complete The Current Profiling Is

## Short Answer

Useful, but not complete.

The current profiling is good enough to choose the first optimization batch.
It is not yet complete enough to justify a native rewrite.

## What The Current Profiling Covers Well

### 1. Root-to-leaf search on a real in-scope workload

[`profile_search.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/profile_search.py)
profiles a full root search on a fixed midgame board. This is a valid search
workload, not a synthetic microbenchmark.

It is good for identifying:

- hottest call paths under real search
- interaction between search, local eval, global eval, VCF, movegen and board
  access
- cumulative cost concentration

### 2. Shallow-to-deeper timing trend

[`hotspot_report.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/hotspot_report.py)
runs several depth/width settings and gives a rough growth curve.

It is good for identifying:

- how fast cost explodes as search depth rises
- whether the engine is still dominated by Python overhead at practical depths

## What The Current Profiling Does Not Cover Well

### 1. It is cProfile-only

`cProfile` is useful for cumulative call cost, but weak for:

- line-level attribution
- allocation pressure
- branch-specific cold/hot split
- distinguishing interpreter overhead from real algorithmic work

### 2. It uses very few boards

Current profiling is mainly built around:

- one fixed midgame board
- one small selfplay timing loop

This is enough to choose a first batch, but not enough to claim that later
optimization decisions are globally optimal.

### 3. It does not isolate TT-heavy or fallback-heavy workloads

The current scripts do not separately profile:

- transposition-heavy boards
- VCF-dominant boards
- fallback / rootsplit-heavy boards
- stop / node-limit heavy workloads

### 4. It does not yet compare backend candidates

There is no current benchmark harness for:

- Python baseline vs Python rewrite
- Python baseline vs native backend
- backend A vs backend B

## Decision

Current profiling is complete enough for:

- first-batch pure Python optimization
- choosing the first 2 to 3 hotspot modules

Current profiling is not complete enough for:

- deciding to migrate the main hotspot to native immediately
- deciding which native backend to adopt permanently

## Current Hotspots

The current evidence consistently points to the following hotspot stack:

### Tier 1: Immediate Hotspots

1. [`pyslow/eval/local.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/eval/local.py)
   - `compute_direction_shape`
   - `recompute_all`
   - `recompute_point_caches`
   - `value_wide_compute`

2. [`pyslow/patterns/line.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/patterns/line.py)
   - `from_board`
   - `shape`
   - `_shape_table_lookup`

3. [`pyslow/board.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/board.py)
   - `at`
   - `in_bounds`

These dominate the current cumulative time and are hit by both normal search and
VCF-related paths.

### Tier 2: Secondary Hotspots

4. [`pyslow/eval/global_eval.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/eval/global_eval.py)
   - `evaluate_board`
   - `_evaluate_last5_branch`

5. [`pyslow/threats/vcf.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/threats/vcf.py)
   - `search`
   - `_search_attacker`
   - `_search_defender`

6. [`pyslow/threats/threat_board.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/threats/threat_board.py)
   - `threat_moves`
   - `winning_threat_moves`
   - `_broken_four_reply_with_ambiguity`

### Tier 3: Search Shell

7. [`pyslow/search/alphabeta.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/alphabeta.py)
8. [`pyslow/search/movegen.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/movegen.py)

These show up high in cumulative time because they sit above the real inner
loops, but right now they do not look like the best first direct optimization
targets.

## Priority Order

## Priority 0: Freeze Semantics

Before optimizing anything:

- keep [`alignment_compare.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py)
  green at `70/70`
- keep:
  - `tests/test_search.py`
  - `tests/test_movegen.py`
  - `tests/test_protocol.py`
  - `tests/test_config.py`
  green

No speedup is allowed to change:

- move choice
- score
- fallback semantics
- VCF result semantics
- candidate ordering semantics where reference alignment depends on it

## Priority 1: Pure Python Micro-Architecture Cleanup

This is the current recommended first batch.

### 1. `board.py`

Targets:

- reduce `board.at()` call overhead
- reduce `in_bounds()` call overhead
- reduce repeated nested attribute lookups on `board.grid`

Likely methods:

- inline access inside the hottest callers
- cache `grid`, `size`, local variables inside tight loops
- replace tiny helper calls with direct indexed access in hotspot-only code

Risk:

- low semantic risk
- moderate maintainability risk if inlining is done everywhere

Mitigation:

- only inline inside proven hotspot loops
- keep public helper methods intact for non-hot code

### 2. `patterns/line.py`

Targets:

- reduce `Line.from_board()` construction cost
- reduce repeated shape extraction overhead

Likely methods:

- avoid rebuilding temporary Python lists where fixed-size scans are enough
- keep line extraction in flat local variables
- reduce helper layering between `from_board`, `shape`, and lookup

Risk:

- medium semantic risk because shape encoding is fragile

Mitigation:

- add module-level before/after trace comparisons on the same handpicked points
- do not change shape encoding or bucket mapping

### 3. `eval/local.py`

Targets:

- reduce repeated direction recomputation cost
- reduce cache update overhead
- reduce `value_wide_compute()` Python loop overhead

Likely methods:

- flatten loops
- cut temporary tuple/list creation
- move repeated branching out of inner loops
- prebind commonly used locals

Risk:

- medium semantic risk because this touches the core eval cache path

Mitigation:

- verify pointwise outputs for:
  - `compute_direction_shape`
  - `move_value`
  - `attack_level`
  - cache snapshots before/after move/undo

## Priority 2: Secondary Python Optimization

Only after Priority 1 is measured.

### 4. `global_eval.py`

Reason:

- currently heavy, but partly downstream of `local.py`
- may get cheaper automatically once local eval is cheaper

### 5. `threat_board.py`

Reason:

- important, but current cost is smaller than local eval and line scanning
- should be revisited after Tier 1 results are measured

### 6. `vcf.py`

Reason:

- tactically important
- still expensive
- but riskier than board/line/local because tactical semantics are branch-heavy

## Priority 3: Re-evaluate Search Limits

Only after measurable speedup lands.

Then evaluate:

- whether default `depth=3 width=10` can be raised safely
- whether practical root width can increase first
- whether VCF caps should be revisited

This must be benchmark-driven, not guess-driven.

## Native Strategy

## Short Answer

Not yet.

Current recommendation:

- do not go native first
- finish at least one pure Python optimization batch first

## If Native Becomes Necessary

### Recommendation Ranking

#### 1. PyO3 / Rust with `abi3`

Best for long-term distributable compatibility.

Why:

- good cross-platform story
- works on macOS, Linux, Windows
- `abi3` can reduce wheel fragmentation across Python versions
- strong implementation safety for complex logic
- clean boundary for isolated hotspot modules

Tradeoffs:

- requires Rust toolchain for source builds
- more engineering overhead than Cython

Best use:

- stable isolated hotspots after Python semantics are frozen
- modules like `line`, `local eval`, or `threat_board`

#### 2. Cython

Best for the fastest iteration on loop-heavy hotspots.

Why:

- straightforward for translating Python loops to typed loops
- works on macOS, including Apple Silicon, as long as a C toolchain exists
- lower rewrite cost for existing Python code

Tradeoffs:

- wheel compatibility is usually per-Python-version unless extra work is done
- less elegant when logic gets complex
- can drift into “Python with type annotations everywhere” without a clean
  module boundary

Best use:

- first native experiment on a very hot, very local loop
- especially if the target is numeric/array-like and branch-light

#### 3. Plain C/C++ Extension

Possible, but not preferred as the first native path.

Tradeoffs:

- highest manual maintenance cost
- lowest safety
- packaging burden without a clear advantage over PyO3 or Cython here

## Compatibility Answer For Apple Systems

Yes, both Cython and PyO3 can support Apple systems.

If the question is:

- "which one can run on Apple?"
  - both can

If the question is:

- "which one has the highest long-term packaging compatibility?"
  - PyO3 with `abi3` is the stronger answer

If the question is:

- "which one is easiest to try quickly on current hotspots?"
  - Cython is the easier first experiment

## Current Recommendation

For this project, the best staged choice is:

1. pure Python optimization first
2. if native is still needed, prefer:
   - PyO3 for a durable production backend
   - Cython only if a quick hotspot experiment is needed earlier

## Risk Register

### Risk 1: Semantic drift in eval / line code

Highest-risk modules:

- `patterns/line.py`
- `eval/local.py`

Mitigation:

- add narrow equivalence tests before each optimization batch
- re-run `70/70` compare after every landed batch

### Risk 2: Measuring the wrong hotspot

Mitigation:

- re-profile after every meaningful optimization batch
- do not keep using stale hotspot order after performance changes

### Risk 3: Native path adds packaging friction too early

Mitigation:

- keep Python backend first-class
- avoid native until pure Python gains are measured
- prefer isolated backend modules with runtime fallback

### Risk 4: Improving node count but not wall time

Mitigation:

- always measure wall time, not just node count
- keep fixed workload timing benchmarks

## Immediate Next Step

The next practical task should be:

1. keep the current `70/70` semantic baseline frozen
2. start with Priority 1 pure Python optimization
3. first target:
   - `board.py`
   - `patterns/line.py`
4. re-profile
5. only then decide whether `eval/local.py` or a native experiment is next
