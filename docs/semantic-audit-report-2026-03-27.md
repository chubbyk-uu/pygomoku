# Semantic Audit Report (2026-03-27)

## Purpose

This report re-audits `pyslow` against `SlowRenju` before performance work.
The goal is to answer one question clearly:

- within the current project scope, are there still semantic differences that
  materially affect the aligned engine baseline?

Scope of this audit:

- `15x15` freestyle Gomoku only
- current alignment baseline: `depth=3`, `width=10`
- reference-aligned defaults documented in
  [`default-config-baselines.md`](/home/jerry/python-test/gomoku/slow_temp/docs/default-config-baselines.md)
- no code changes to core engine logic during the audit itself

## Audit Method

This audit used four sources of evidence:

1. existing branch checklist and reference-analysis documents
2. current fixed-position compare via
   [`alignment_compare.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py)
3. fresh audit script output from
   [`semantic_audit.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/semantic_audit.py)
4. fresh regression test run on key config/search/movegen/protocol suites

Fresh machine evidence gathered in this audit:

- `python benchmarks/alignment_compare.py`
  - current result: `70/70`
  - alignment baseline: `depth=3`, `width=10`
  - trace harness now seeds `srand(1232356)` like reference `main.cpp`
  - compare set is now grouped and can run in parallel
- `python benchmarks/semantic_audit.py`
  - alignment compare return code `0`
  - `nonroot_vcf` enabled vs disabled caused no change on the original fixed audit
    positions
  - protocol snapshot matched current intended behavior
- `pytest -q tests/test_config.py tests/test_search.py tests/test_movegen.py tests/test_protocol.py`
  - result: `59 passed`

## Executive Summary

### Conclusion

For the current in-scope target:

- `15x15`
- freestyle Gomoku
- current alignment baseline
- current fixed-position compare set

there is no fresh evidence of an unresolved semantic mismatch affecting the
baseline engine behavior.

### Strongest positive evidence

- fixed-position compare is now `70/70`
- recent root and non-root search residuals have been closed with reference
  traces, not by local guesswork
- protocol/config/search/movegen regression suites all passed in this audit

### Important caveat

This does **not** mean `pyslow` is feature-complete relative to the entire
reference repository. It means:

- the current phase-1 target behavior appears aligned
- the remaining known differences are mostly out-of-scope, inactive-by-default,
  or intentional product-scope reductions

## Detailed Findings

## 1. In-Scope Baseline Differences Affecting Current Behavior

### Finding

No confirmed open difference was reproduced in this audit for the current
baseline.

### Evidence

- `alignment_compare.py` at `depth=3`, `width=10` now returns `70/70`
- no changed positions when `nonroot_vcf` was toggled on for the original fixed audit
  positions
- search and protocol regression suites passed

### Status

- no action required before performance work

## 2. Out-of-Scope Or Intentional Differences Still Present

These are real differences relative to the full reference repository, but they
are not current baseline semantic defects.

### 2.1 Board Size Support

Reference supports a range of board sizes.
`pyslow` currently supports only `15x15`.

Evidence:

- reference START path accepts `size<=N && size>=5`
  - [`SlowRenju/Common/main.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Common/main.cpp#L93)
- `pyslow` rejects any size other than `15`
  - [`pyslow/protocol/gomocup.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/protocol/gomocup.py#L50)
- audit protocol snapshot:
  - `START 15 -> OK`
  - `START 20 -> ERROR Size error.`

Status:

- intentional phase-1 scope difference

Recommended action:

- no fix before performance work
- only revisit if multi-size support becomes a project goal

### 2.2 Renju / Foul Logic

Reference contains Renju and foul-related branches.
`pyslow` phase 1 does not support Renju.

Evidence:

- reference has `FOUL`, `fflag`, foul-related manual/opening code paths
  - [`SlowRenju/Headers/game.h`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Headers/game.h#L39)
  - [`SlowRenju/AI/AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L194)
  - [`SlowRenju/Common/main.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Common/main.cpp#L248)
- project scope docs explicitly exclude Renju for phase 1
  - [`reference-analysis.md`](/home/jerry/python-test/gomoku/slow_temp/docs/reference-analysis.md#L8)
  - [`search-flow.md`](/home/jerry/python-test/gomoku/slow_temp/docs/search-flow.md#L9)

Status:

- intentional out-of-scope difference

Recommended action:

- no fix before performance work
- if Renju is added later, treat it as a separate semantic project

### 2.3 Dynamic Root Window Parameter Exists Only In Python

`dynamic_board_margin` is a Python runtime parameter. Reference does not expose
that exact parameter in the same way.

Evidence:

- Python runtime defaults include `dynamic_board_margin = 4`
  - [`pyslow/config.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/config.py)
- but current default is also `static_board = True`
- root code bypasses dynamic windowing entirely when `static_board=True`
  - [`pyslow/search/root.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/root.py#L139)

Status:

- inactive under current baseline
- not a current semantic drift source

Recommended action:

- no change needed before performance work
- if `static_board=False` becomes part of baseline later, re-audit against
  reference expectations at that time

### 2.4 Non-root RTVCF Is Default-Off In Both Baselines

Reference source has a non-root `RTVCF` branch, but default checked reference
build path does not enable it. `pyslow` now mirrors this by default.

Evidence:

- reference source keeps `RTVCF` disabled in the checked build path
  - [`SlowRenju/AI/AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L36)
  - [`SlowRenju/VCF/VCF.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/VCF/VCF.cpp#L22)
- `pyslow` default runtime sets `nonroot_vcf = False`
  - [`pyslow/config.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/config.py)
- if enabled manually, `pyslow` now follows reference-style formula and
  opponent-pressure filtering semantics
- audit script found no fixed-position changes when enabling it on the original audit
  positions

Status:

- aligned by default
- no current residual difference proven on the fixed audit set

Recommended action:

- no baseline fix needed
- if future positions start depending on this branch, add a dedicated reference
  trace and regression test

### 2.5 Fallback Move Tie-Break Randomness

This item is now closed.

Evidence:

- reference `AIs()` stores all equally best moves and then returns
  `move_temp[rand() % casen]`
  - [`SlowRenju/AI/AIs.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIs.cpp#L24)
- the checked trace harness is built with local `g++`, so the effective tie-break
  behavior follows the host libc `rand()` state after `InitHash()` has consumed
  its initialization draws
- Python fallback now mirrors that seeded libc-based tie-break state for the
  aligned harness path
  - [`pyslow/search/root.py`](/home/jerry/python-test/gomoku/slow_temp/pyslow/search/root.py#L19)
- exact fallback positions now align:
  - `tact_defend4 -> (6,7)` in `alignment_compare.py`
  - fallback regression test for the two-way tie position passes

Status:

- closed
- no residual difference currently known on fallback tie handling

## 3. Protocol-Level Differences

The current audit did not reproduce a protocol mismatch affecting the intended
baseline behavior.

Fresh evidence:

- audit protocol snapshot:
  - unknown command returns `[]`
  - empty `TAKEBACK` returns `OK`
  - size `20` is rejected
- regression suite:
  - `tests/test_protocol.py` passed in full

Remaining protocol difference relative to the full reference product:

- size support is intentionally narrower in `pyslow` because current scope is
  fixed to `15x15`

Status:

- no baseline semantic defect found

## 4. What I Would Still Watch Closely

These are not proven current bugs, but they are the highest-value watch points
for future regressions:

1. any future decision to enable `static_board=False` by default
2. any future decision to enable `nonroot_vcf=True` by default
3. any future benchmark set that includes fallback-heavy or protocol-edge cases
   beyond the current 70-position compare

## Recommended Repair Priority

### Priority 0: Before Performance Work

Do not change engine semantics again unless a fresh mismatch is reproduced.
Current evidence supports treating the current implementation as the semantic
baseline.

### Priority 1: Performance Work

Proceed to performance optimization with the current semantic baseline frozen.
Every speedup should re-run:

- [`alignment_compare.py`](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py)
- `tests/test_config.py`
- `tests/test_search.py`
- `tests/test_movegen.py`
- `tests/test_protocol.py`

## Final Judgement

For the current project scope, I do not see evidence of a still-open semantic
mismatch that should block performance work.

The previously noted fallback `AIs()` tie randomness is now aligned. Everything
else found in this audit is either:

- already aligned in the active baseline
- inactive by default
- or intentionally out of current scope
