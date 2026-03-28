# Acceleration Plan

## Current Position

This document still defines the acceleration rules, but acceleration is not the
current top priority.

Current project priority order is:

1. align `classic` with the external `SlowRenju` reference
2. only then resume large-scale acceleration work

So this document is now a deferred-plan document, not the immediate work order.

## Terminology

### `reference`

The external C reference engine:

- [`SlowRenju/`](../SlowRenju)

### `classic`

The current Python production path:

- [`pyslow/search/`](../pyslow/search)
- [`pyslow/eval/`](../pyslow/eval)

## Rule Before Any New Performance Work

No new acceleration work should become primary until the following is true:

1. classic is aligned with `SlowRenju`
2. the kept runtime path is stable enough to profile and optimize

This rule exists because optimizing a drifting path is wasted work.

## Core Principles

When acceleration resumes, every change must still satisfy all 3 conditions:

1. semantics must not change
2. Python fallback must remain available
3. both correctness and performance evidence are required

## Allowed Acceleration Routes

The project still allows two broad routes.

### 1. Python-side structural speedups

Examples:

- reduce temporary allocations
- reduce repeated scans
- flatten hot data access
- merge hot loops
- replace generic helpers with hot-path-specific logic

### 2. Native module acceleration

Examples:

- Cython
- small C/C++ extensions

But the rule remains:

- do not move only loops while leaving data on Python object graphs
- move data path plus hot compute chain together

## What Is Explicitly Not The Current Task

Right now, the following are not first-priority tasks:

- broad new native performance work
- speculative root-level throughput tuning
- changing default search limits to chase speed alone
- introducing faster-but-different semantics

These only make sense after the alignment sequence is complete.

## Deferred Performance Targets

Once alignment work is finished, the acceleration target remains:

- keep equivalent semantics
- significantly improve throughput
- move practical search reach toward at least `depth=8 width=20`

## Future Work Order After Alignment

When the project returns to acceleration work, do it in this order:

1. profile the corrected classic baseline again
2. re-identify the hottest aligned path
3. optimize one hotspot family at a time
4. re-run correctness checks after each change
5. only keep speedups that preserve aligned semantics

## Validation Rules

When acceleration resumes, every kept change should be validated with:

- `pytest -q`
- `python benchmarks/alignment_compare.py`
- fixed representative benchmark runs
- practical persistent-session opponent checks when needed
