# Reference Analysis For `pyslow`

## Purpose

This document is now a compact index for the `SlowRenju` reference material
that is still relevant to active work.

It used to contain a large amount of early-stage analysis. That content is no
longer the best source of truth because the project has moved into:

1. keeping `classic` as the only runtime path
2. practical performance work on `classic`
3. deferred re-entry into unresolved reference residuals only when justified

Use the focused documents below instead of rebuilding understanding from a
single oversized analysis file.

## Current Source Of Truth

### Project priority and current work order

- [next-steps.md](./next-steps.md)
- [acceleration-plan.md](./acceleration-plan.md)
- [classic-slowrenju-alignment-notes.md](./classic-slowrenju-alignment-notes.md)

### Active reference checkout

The live `SlowRenju` reference used by current alignment work is the subrepo:

- [`SlowRenju/`](../SlowRenju)
- branch: `linux-fixed-d5w15`
- commit: `98be8f9`

### Reference defaults and runtime baselines

- [default-config-baselines.md](./default-config-baselines.md)

Use that document when the question is specifically about:

- checked `SlowRenju` fixed-search defaults
- current `classic` interactive defaults
- GUI `SlowRenju` backend defaults
- opponent-runner default search settings

### Search structure and control flow

- [search-flow.md](./search-flow.md)

### Parameter and evaluation semantics

- [parameter-mapping.md](./parameter-mapping.md)
- [pattern-bucket-mapping.md](./pattern-bucket-mapping.md)

### Tactical search

- [vcf-design.md](./vcf-design.md)

## How To Use This Folder Now

If the task is:

- practical classic-vs-reference alignment
  - start from [next-steps.md](./next-steps.md)
- classic performance work without semantic changes
  - start from [acceleration-plan.md](./acceleration-plan.md)
- reference behavior details
  - read the focused spec files listed above

## Archived Material

Historical audit and roadmap snapshots were moved to:

- [archive/README.md](./archive/README.md)

Those files remain useful as historical evidence, but they should not be
treated as the current project plan.
