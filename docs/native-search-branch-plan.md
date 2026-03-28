# Native Search Branch Plan

## Purpose

This document tracks the current `native-search-core` branch after the project
priority changed.

The branch still contains the native-search work, but the immediate project
goal is now:

1. align `classic` with the external `SlowRenju` reference
2. only then align `state` and `native` to that corrected classic baseline

So this document now serves two purposes:

- keep the native branch architecture and file-retention plan clear
- record that native alignment is currently second priority, not first

## Terminology

Use these names consistently.

### `reference`

The external C reference engine:

- [`SlowRenju/`](../SlowRenju)

This is the current behavior target for the classic-alignment phase.

### `classic`

The Python production search path:

- [`pyslow/search/alphabeta.py`](../pyslow/search/alphabeta.py)
- [`pyslow/search/root.py`](../pyslow/search/root.py)
- [`pyslow/search/movegen.py`](../pyslow/search/movegen.py)
- [`pyslow/eval/`](../pyslow/eval)

This is the current `pyslow` runtime baseline.

### `state`

The flat-state Python reference layer:

- [`pyslow/core/reference/`](../pyslow/core/reference)

This is a branch-local semantic comparison asset, not the current product
behavior target.

### `native`

The flat-state native execution path:

- [`pyslow/core/native_search.py`](../pyslow/core/native_search.py)
- [`pyslow/core/_native_search_cy.pyx`](../pyslow/core/_native_search_cy.pyx)

Its long-term role is still the high-throughput execution path, but it must be
aligned after classic has been fully corrected against `SlowRenju`.

## Current Branch Status

### What Is Already Completed

The branch already has a real native search line:

- flat search state in [`pyslow/core/search_state.py`](../pyslow/core/search_state.py)
- native local update / undo path
- native movegen / ordering path
- native leaf eval path
- native TT fast path
- native root backend
- nonroot `VCF` wired into native search
- runtime root backends reduced to `classic` and `native`

The branch also already separated reference-only assets:

- [`pyslow/core/reference/`](../pyslow/core/reference)

This means the branch is not a prototype anymore. It already has:

- a flat semantic data model
- a reference-only state layer
- a real native execution line

### What Has Been Proven

These facts have already been established:

1. native control-plane downshift has real performance value
2. native correctness must be restored block by block
3. reference/state remains necessary for branch-level comparison
4. runtime product paths on this branch are only `classic` and `native`

### Current Native Situation

Native is functional, but it is not the current source of truth.

At the moment:

- native functionality is largely present
- native still does not fully align with classic on all practical cases
- that work is intentionally paused behind the classic-vs-reference alignment

The correct future order is:

1. finish classic-vs-`SlowRenju`
2. re-baseline classic
3. align state to classic
4. align native to classic
5. then resume native performance work

## Current Classic-vs-Reference Situation

This branch now also carries the in-progress classic alignment work, because it
is the active engineering branch.

Current practical status:

- classic Zhou summary now matches `SlowRenju` under fixed `d5 w15` vs Zhou `d5`
- current `SlowRenju` reference baseline is the subrepo branch
  `linux-fixed-d5w15` at commit `98be8f9`
- opening-set `5` whole-game parity is complete
- opening-set `9` summary is aligned, but whole-game parity is not

Current known remaining whole-game residuals on opening-set `9`:

- `black_0_2_2`
  - first differing move `9`
  - classic: `BLACK (5,4)`
  - reference: `BLACK (4,5)`
- `black_1_2_12`
  - first differing move `3`
  - classic: `BLACK (5,8)`
  - reference: `BLACK (4,10)`
- `black_2_12_2`
  - first differing move `9`
  - classic: `BLACK (9,4)`
  - reference: `BLACK (10,5)`
- `black_3_12_12`
  - first differing move `15`
  - classic: `BLACK (8,11)`
  - reference: `BLACK (10,10)`

Important rule:

- no classic change should land unless it is backed by direct `SlowRenju`
  source evidence or direct trace evidence

The detailed record of confirmed classic-vs-`SlowRenju` differences and landed
fixes is maintained in:

- [classic-slowrenju-alignment-notes.md](./classic-slowrenju-alignment-notes.md)

This rule also applies to later state/native alignment.

## File Retention Plan

Not every file introduced on this branch is a final production-path file.

### Expected Long-Term Core Assets

- [`pyslow/core/search_state.py`](../pyslow/core/search_state.py)
- [`pyslow/core/native_search.py`](../pyslow/core/native_search.py)
- [`pyslow/core/_native_search_cy.pyx`](../pyslow/core/_native_search_cy.pyx)
- flat/native helpers that remain shared by the final native line

### Expected Reference / Comparison Assets

- [`pyslow/core/reference/`](../pyslow/core/reference)

These remain useful for:

- semantic comparison
- branch-level debugging
- native fallback/reference checks

### Expected Transitional / Shrinkable Code

- temporary bridge helpers used only while native is being re-aligned
- temporary callback paths from native into Python reference helpers
- trace/debug code used only for alignment work

These should be removed once their comparison role is complete.

## Current Priority Order

### Step 1. Finish classic-vs-`SlowRenju`

This is the active task now.

Work style:

1. pick the earliest unresolved residual game
2. isolate the first differing exact node on the practical path
3. compare classic trace against `SlowRenju`
4. change classic only after direct evidence

### Step 2. Align `state` to corrected classic

This comes after Step 1.

Target:

- make `state` match corrected classic semantics exactly

### Step 3. Align `native` to corrected classic

This comes after Step 2.

Target:

- keep native behavior equal to corrected classic

### Step 4. Resume native performance work

Only after Steps 1-3 are completed.

Then the branch can return to its original acceleration goal:

- maintain equivalent semantics
- harden the remaining native hot path
- increase throughput on top of corrected behavior

## Working Rule

Do not optimize a semantically drifting path.

For the rest of this branch:

1. fix semantic drift first
2. re-baseline behavior
3. only then optimize the corrected path
