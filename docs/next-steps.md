# Next Steps

## Current State

### Priority 1. Optimize `classic` without changing semantics

Whole-game alignment against `SlowRenju` is not fully closed, but active work
is temporarily shifting to performance work on the kept `classic` path.

Current reference baseline:

- `SlowRenju/` subrepo
- branch: `linux-fixed-d5w15`
- commit: `98be8f9`

Current practical status:

- opening-set `5`, `depth=5 width=15`, both colors
  - classic vs Zhou:
    - black `5/0/0`
    - white `4/1/0`
  - reference vs Zhou:
    - black `5/0/0`
    - white `4/1/0`
  - whole-game parity: `10/10`

- opening-set `9`, `depth=5 width=15`, both colors
  - classic vs Zhou:
    - black `9/0/0`
    - white `8/1/0`
  - reference vs Zhou:
    - black `9/0/0`
    - white `8/1/0`
  - summary aligned, whole-game parity incomplete

Current known whole-game mismatches against `SlowRenju` on opening-set `9`:

- `black_0_2_2`
  - first differing move `9`
  - classic `BLACK (5,4)`
  - reference `BLACK (4,5)`
- `black_1_2_12`
  - first differing move `3`
  - classic `BLACK (5,8)`
  - reference `BLACK (4,10)`
- `black_2_12_2`
  - first differing move `9`
  - classic `BLACK (9,4)`
  - reference `BLACK (10,5)`
- `black_3_12_12`
  - first differing move `15`
  - classic `BLACK (8,11)`
  - reference `BLACK (10,10)`

The current rule is unchanged:

- do not make speculative fixes
- only change classic when a difference from `SlowRenju` is backed by:
  - direct source evidence, or
  - direct trace evidence on the same minimal practical position
- do not change semantics while optimizing speed

Current development defaults:

- interactive / CLI defaults: `depth=5 width=20`
- GUI `SlowRenju` backend fixed search: `depth=8 width=24`
- opponent runner `SlowRenju` default fixed search: `depth=5 width=20`
- checked practical alignment baseline: `depth=5 width=15`

## What Has Already Been Fixed In Classic

The following major alignment fixes have already landed because they were backed
by direct `SlowRenju` source or trace evidence:

- zobrist random stream now follows the `SlowRenju`-style libc `rand64()`
- zobrist no longer includes a turn key
- zobrist stream size now matches the `SlowRenju` reference board stream shape
- TT default size raised to `20`
- TT store priority now follows reference root-search move-count semantics
- winning TT store depth boost now follows `windepth + 10`
- root win-break behavior follows the reference
- root fallback RNG state follows Gomocup `START` + first `RESTART`

These fixes are the reason 5-opening whole-game parity is now complete.

## Confirmed New Findings From Opening-Set `9`

### 1. `black_1_2_12` is a confirmed nonroot top-wide drift

Confirmed:

- root candidate generation itself is not the problem
- raw nonroot candidate sets match
- drift appears when entering the searched top-`15` list and then propagates
  through node-local `best_move`

Not yet finished:

- the globally correct repair condition is still not fully isolated

### 2. `black_0_2_2` is a deeper persistent-search drift

Confirmed:

- classic can reproduce the same local `52 / -52` values as reference on the
  critical exact boards
- the practical drift is not explained by leaf eval alone
- both engines use the same general mechanism of:
  - earlier negative-depth leaf exact store
  - later shallow-node exact hit
- the current strongest evidence is that the branch diverges because nonroot
  equal-score tie-order interacts with cumulative `running_downf`

Not yet finished:

- the exact upstream condition that makes classic land this mechanism on a
  different node than reference is still not fully closed

### 3. `black_2_12_2` likely belongs to the same family as `black_0_2_2`

Current evidence:

- mirrored edge opening
- first differing move also at `9`
- same kind of edge-adjacent drift

Still needs exact trace closure.

### 4. `black_3_12_12` remains a separate class

Confirmed:

- root initial ordering is not enough to explain this residual
- the drift appears later, after deeper search score propagation

This one should not be forced into the same explanation as the move-9 edge
residuals without direct evidence.

## Current Work Order

### 1. Optimize classic speed on the current semantic baseline

Immediate task:

1. profile the current `classic` path
2. optimize Python or native hotspots only if behavior remains unchanged
3. use `depth=5 width=20` as the development default for practical checks
4. keep the current `d5 w15` residual list as an open issue, not as the active task

Do not:

- change search semantics to chase speed
- “improve” classic by intuition and call it alignment
- treat edge residual guesses as proven causes without direct evidence

### 2. Keep regression practical and parallel

Use parallel pytest by default for broad runs:

- full suite: `python -m pytest -n auto -q`
- fast subset: `python -m pytest -m fast -q`
- alignment subset: `python -m pytest -m alignment -n auto -q`
- integration subset: `python -m pytest -m integration -q`
- current grouped counts: `fast=39`, `alignment=89`, `integration=29`

Single-thread full-suite runs are noticeably slower and should not be the
default local workflow.

### 3. Revisit classic-vs-reference residuals only when justified

If alignment work resumes:

1. continue from the four black residuals above
2. keep using exact practical prefixes and persistent Gomocup flow
3. treat fresh one-shot search only as a diagnosis aid
4. only land code changes after direct source / trace evidence

## Documents To Read Before Resuming

Read these first:

1. [current-handoff.md](./current-handoff.md)
2. [classic-slowrenju-alignment-notes.md](./classic-slowrenju-alignment-notes.md)
3. [acceleration-plan.md](./acceleration-plan.md)

Then:

1. rerun the current practical Zhou regression if needed
2. pick the earliest unresolved residual in opening-set `9`
3. continue from the first differing exact node, not from broad speculation
