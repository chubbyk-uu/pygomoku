# Acceleration Plan

## Current Position

This document defines the current optimization rules for the kept `classic`
path.

Current project priority order is:

1. keep `classic` semantics stable
2. improve `classic` speed
3. leave the remaining `d5 w15` alignment residuals open until direct evidence
   justifies resuming them

So this is now an active work-order document, not just a deferred plan.

## Terminology

### `reference`

The external C reference engine:

- [`SlowRenju/`](../SlowRenju)

### `classic`

The current Python production path:

- [`pyslow/search/`](../pyslow/search)
- [`pyslow/eval/`](../pyslow/eval)

## Core Principles

Every kept optimization must still satisfy all 3 conditions:

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

- speculative residual-alignment surgery without new direct evidence
- introducing faster-but-different semantics

These only make sense after the evidence bar is met.

## Current Performance Targets

The current target is:

- keep equivalent semantics
- significantly improve throughput
- move practical search reach toward at least `depth=8 width=20`

## Work Order

Do the work in this order:

1. profile the corrected classic baseline again
2. re-identify the hottest aligned path
3. optimize one hotspot family at a time
4. re-run correctness checks after each change
5. only keep speedups that preserve aligned semantics

## Validation Rules

Every kept change should be validated with:

- `python -m pytest -n auto -q`
- `python benchmarks/alignment_compare.py`
- fixed representative benchmark runs
- practical persistent-session opponent checks when needed

Recommended local test commands:

- full suite: `python -m pytest -n auto -q`
- fast subset: `python -m pytest -m fast -q`
- alignment subset: `python -m pytest -m alignment -n auto -q`
- integration subset: `python -m pytest -m integration -q`
