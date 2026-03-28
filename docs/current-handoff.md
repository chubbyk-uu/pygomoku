# Current Handoff

## Current Goal

Priority 1 is still:

- align `classic` with the `SlowRenju` reference

Do not resume `state` / `native` alignment work until classic-vs-reference is
closed on the current practical baseline.

## Terminology

- `reference` = subrepo [`SlowRenju/`](../SlowRenju)
- `classic` = current Python production path under [`pyslow/search/`](../pyslow/search)
- `state` = Python flat-state reference layer under [`pyslow/core/reference/`](../pyslow/core/reference)
- `native` = native execution path under [`pyslow/core/native_search.py`](../pyslow/core/native_search.py)

## Active Reference Baseline

`SlowRenju/` is its own git repository.

Current reference checkout:

- branch: `linux-fixed-d5w15`
- commit: `98be8f9`

This branch includes:

- Linux build compatibility
- Linux timing-definition compatibility
- fixed `depth/width` search mode
- default fixed search `depth=5 width=15`

## Practical Baseline

Known aligned practical baseline:

- opening-set `5`, `depth=5 width=15`, both colors
- classic vs Zhou:
  - black `5/0/0`
  - white `4/1/0`
- reference vs Zhou:
  - black `5/0/0`
  - white `4/1/0`
- whole-game parity on this 5-opening set: `10/10`

Current extended check:

- opening-set `9`, `depth=5 width=15`, both colors
- classic vs Zhou:
  - black `9/0/0`
  - white `8/1/0`
- reference vs Zhou:
  - black `9/0/0`
  - white `8/1/0`

Summary is aligned on the 9-opening set, but whole-game parity is not.

## Current Alignment Status

Known whole-game residuals against `SlowRenju` on opening-set `9`:

- `black_0_2_2`
  - first differing move: `9`
  - classic: `BLACK (5,4)`
  - reference: `BLACK (4,5)`
- `black_1_2_12`
  - first differing move: `3`
  - classic: `BLACK (5,8)`
  - reference: `BLACK (4,10)`
- `black_2_12_2`
  - first differing move: `9`
  - classic: `BLACK (9,4)`
  - reference: `BLACK (10,5)`
- `black_3_12_12`
  - first differing move: `15`
  - classic: `BLACK (8,11)`
  - reference: `BLACK (10,10)`

Whole-game parity on opening-set `9`:

- black `5/9` aligned
- white `9/9` aligned

## Confirmed Classic Fixes Already Landed

These are already considered valid reference-backed fixes and should not be
reopened casually:

- zobrist stream aligned to `SlowRenju`
- no turn key in classic zobrist
- TT default raised to `20`
- TT store priority aligned to reference root semantics
- winning exact store `windepth + 10`
- root win-break behavior aligned to reference
- root fallback RNG state aligned to Gomocup `START` + first `RESTART`

Details are in:

- [classic-slowrenju-alignment-notes.md](./classic-slowrenju-alignment-notes.md)

## Confirmed New Findings

These are evidence-backed findings from the 9-opening investigation.

### 1. `black_1_2_12` is a nonroot top-wide boundary / tie-order problem

- direct reference source and trace evidence confirms drift at two exact
  sibling nodes under the root
- raw candidate sets match
- drift appears when entering the searched top-`15` list and then propagates
  through node-local `best_move`
- this is a real root cause category, but the globally correct repair
  condition is still not fully isolated

### 2. `black_0_2_2` is not a leaf-eval bug

- direct exact-position calls show classic can reproduce the same local
  `52 / -52` values as reference on the critical boards
- both engines use the same general mechanism of:
  - earlier negative-depth leaf exact store
  - later shallow-node exact hit
- the drift comes from that mechanism landing on different nodes in the
  ancestor chain
- the strongest current evidence points at nonroot equal-score tie-order plus
  `running_downf` threshold interaction on the `(4,5)` branch
- a naive tie-order patch was tested and reverted because it did not change
  practical 9-opening results

## Immediate Next Step

Continue from the opening-set `9` black residuals only:

1. keep `SlowRenju/` clean except short-lived trace edits
2. continue exact-position / exact-node trace work
3. close the remaining upstream condition on:
   - `black_0_2_2`
   - `black_2_12_2`
   - `black_3_12_12`
4. only change classic after direct reference source evidence or exact trace
   evidence on the same practical branch

## First Files To Read After Reopen

1. [current-handoff.md](./current-handoff.md)
2. [next-steps.md](./next-steps.md)
3. [classic-slowrenju-alignment-notes.md](./classic-slowrenju-alignment-notes.md)
