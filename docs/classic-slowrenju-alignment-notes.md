# Classic vs SlowRenju Alignment Notes

## Purpose

This document records the confirmed differences found while aligning
`pyslow` classic with the external `SlowRenju` reference.

It exists so that later `state` / `native` alignment work can reuse the same
evidence instead of rediscovering the same reference behavior.

The rules for entries in this document are:

- only record differences that were backed by direct source evidence or direct
  practical trace evidence
- separate diagnosis from landed fixes
- keep enough reproduction context to repeat the investigation later

## Terminology

- `reference`: the external `SlowRenju` engine in [`SlowRenju/`](../SlowRenju)
- `classic`: the Python production search path in [`pyslow/search/`](../pyslow/search)
- `state`: the flat-state Python reference layer in [`pyslow/core/reference/`](../pyslow/core/reference)
- `native`: the flat-state native execution path in [`pyslow/core/native_search.py`](../pyslow/core/native_search.py) and [`pyslow/core/_native_search_cy.pyx`](../pyslow/core/_native_search_cy.pyx)

## Current Alignment Status

Current practical status for classic vs `SlowRenju` under fixed search:

- opening-set `5`, `depth=5 width=15`, both colors
  - classic vs Zhou:
    - black: `5/0/0`
    - white: `4/1/0`
  - `SlowRenju` vs Zhou:
    - black: `5/0/0`
    - white: `4/1/0`
  - whole-game parity: `10/10`

- opening-set `9`, same fixed-search setup
  - classic vs Zhou:
    - black: `9/0/0`
    - white: `8/1/0`
  - `SlowRenju` vs Zhou:
    - black: `9/0/0`
    - white: `8/1/0`
  - whole-game parity:
    - black: `5/9`
    - white: `9/9`

Current reference baseline used for this phase:

- subrepo: [`SlowRenju/`](../SlowRenju)
- branch: `linux-fixed-d5w15`
- commit: `98be8f9`

Current unresolved whole-game residuals on opening-set `9`:

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

## Confirmed Differences And Landed Fixes

### 1. Zobrist stream did not match SlowRenju

Status:

- confirmed
- fixed in classic

Evidence:

- direct source evidence from:
  - [`SlowRenju/AI/Hash.cpp`](../SlowRenju/AI/Hash.cpp)
  - [`SlowRenju/Common/main.cpp`](../SlowRenju/Common/main.cpp)
  - [`SlowRenju/Headers/game.h`](../SlowRenju/Headers/game.h)

Confirmed reference behavior:

- `SlowRenju` uses libc-style `rand64()`
- zobrist is generated for `2 x (N*N+1)` entries
- the checked source uses compile-time `N=20`
- no side-to-move turn key is folded into `CurrentZobrist`
- the practical seed path is based on `srand(1232356)`

Classic drift before fix:

- classic used a different random stream shape
- classic used a turn key
- classic keyed `15x15` directly instead of matching the reference stream layout

Landed change:

- [`pyslow/zobrist.py`](../pyslow/zobrist.py)

Practical effect:

- critical root and TT traces started matching the reference much more closely
- several practical opening mismatches reduced immediately after this fix

### 2. TT capacity default was too small for practical alignment

Status:

- confirmed
- fixed in classic

Evidence:

- direct practical trace evidence on fixed openings
- not a claim that Python should mechanically copy the C table size
- but clear evidence that the old Python default was too small to preserve the
  practical reference behavior

Observed behavior:

- smaller classic TT settings caused practical move drift on opening positions
  where `SlowRenju` remained stable
- increasing TT size to `20` removed several persistent practical mismatches

Landed change:

- [`pyslow/search/tt.py`](../pyslow/search/tt.py)
- default `bucket_bits` raised to `20`

Important note:

- this was not justified by “bigger is better”
- it was justified by practical reference-alignment evidence on fixed openings

### 3. TT store priority did not match SlowRenju

Status:

- confirmed
- fixed in classic

Evidence:

- direct source evidence from:
  - [`SlowRenju/AI/AIx.cpp`](../SlowRenju/AI/AIx.cpp)
  - [`SlowRenju/Common/main.cpp`](../SlowRenju/Common/main.cpp)

Confirmed reference behavior:

- `SlowRenju` stores TT entries with:
  - `priority = moven * 10 + depth`
- `moven` is the root-search move count for the actual game turn
- it is not the recursive hypothetical subtree move count

Classic drift before fix:

- classic used recursive `board.move_count` inside TT store priority
- deeper hypothetical descendants therefore received larger priorities than in
  the reference
- this changed which persistent TT entries survived and later got reused

Landed change:

- [`pyslow/search/alphabeta.py`](../pyslow/search/alphabeta.py)
- `priority_base` is now fixed at root entry and passed through recursion

Practical effect:

- key practical positions such as the `(4,10)` line stopped drifting in the
  same way as before
- classic vs `SlowRenju` summary alignment improved materially

### 4. Winning TT store depth boost (`windepth`) was missing

Status:

- confirmed
- fixed in classic

Evidence:

- direct source evidence from [`SlowRenju/AI/AIx.cpp`](../SlowRenju/AI/AIx.cpp)

Confirmed reference behavior:

- if the stored result is a winning/loss exact result beyond the original
  window, `SlowRenju` forces `hashf=EXACT` and adds `windepth=10`

Classic drift before fix:

- classic did not mirror this exact-store depth boost

Landed change:

- [`pyslow/search/alphabeta.py`](../pyslow/search/alphabeta.py)

Important note:

- this was a source-backed alignment fix
- it was not the single largest practical root cause, but it is real reference
  behavior and should be kept when aligning `state` and `native`

### 5. Root win-break behavior differed from SlowRenju

Status:

- confirmed
- fixed in classic

Evidence:

- direct source evidence from [`SlowRenju/AI/AIx.cpp`](../SlowRenju/AI/AIx.cpp)
- direct practical trace evidence on the earliest black residual:
  - opening `(4,4)`
  - first differing move `19`

Confirmed reference behavior:

- in the root child loop, when `nbest == 0`, `SlowRenju` stops the current root
  iteration as soon as a child returns `score >= WIN`

Classic drift before fix:

- classic kept searching later root children even after a winning root child
  had already been found
- this allowed a later child with slightly different win score to overwrite the
  move chosen by `SlowRenju`

Minimal practical reproduction:

Prefix before the differing black move:

1. `BLACK (4,4)`
2. `WHITE (6,4)`
3. `BLACK (5,5)`
4. `WHITE (6,6)`
5. `BLACK (5,3)`
6. `WHITE (5,6)`
7. `BLACK (6,3)`
8. `WHITE (6,7)`
9. `BLACK (4,3)`
10. `WHITE (3,3)`
11. `BLACK (3,5)`
12. `WHITE (2,6)`
13. `BLACK (4,5)`
14. `WHITE (4,6)`
15. `BLACK (3,6)`
16. `WHITE (6,5)`
17. `BLACK (6,8)`
18. `WHITE (5,4)`

Observed search result before fix:

- classic: `(7,4) 19989`
- `SlowRenju`: `(5,2) 19988`

Root cause trace:

- classic root child order already matched the reference
- `(5,2)` was also the first winning child in classic
- but classic kept searching and later overwrote it with `(7,4)`
- `SlowRenju` stopped on the first root winning child

Landed change:

- [`pyslow/search/alphabeta.py`](../pyslow/search/alphabeta.py)
- root loop now breaks on `root and score >= WIN`

Practical effect:

- the entire black `(4,4)` game now matches `SlowRenju`
- black-side whole-game parity across the 5-opening Zhou set is now complete

### 6. Root fallback RNG state did not match SlowRenju Gomocup flow

Status:

- confirmed
- fixed in classic

Evidence:

- direct source evidence from:
  - [`SlowRenju/Common/main.cpp`](../SlowRenju/Common/main.cpp)
  - [`SlowRenju/AI/AIs.cpp`](../SlowRenju/AI/AIs.cpp)
- direct practical trace evidence on the last white residual:
  - opening `(10,10)`
  - first differing move `32`

Confirmed reference behavior:

- `SlowRenju` seeds the process RNG with `srand(1232356)` in `main()`
- in Gomocup mode it calls `InitHash()` on `START`
- then the first `_sync_full_board()`-style search path triggers `RESTART`,
  which calls `InitHash()` again
- later `rootsearch()` may return `abval.second == -1` and fall back to
  `AIs()`
- `AIs()` breaks ties with process-global `rand() % casen`
- therefore the fallback tie-break stream in practical play starts after two
  `InitHash()` passes, not one

Classic drift before fix:

- classic already mirrored the fallback scoring logic itself
- but its reference fallback RNG state only matched one post-`InitHash()`
  stream
- under persistent Gomocup play this produced the wrong tie-break result on
  fallback turns, even when the search score and fallback candidate set already
  matched the reference

Minimal practical reproduction:

Residual line before the differing white move:

1. `BLACK (10,10)`
2. `WHITE (10,9)`
3. `BLACK (9,11)`
4. `WHITE (9,10)`
5. `BLACK (11,9)`
6. `WHITE (12,8)`
7. `BLACK (8,12)`
8. `WHITE (7,13)`
9. `BLACK (8,11)`
10. `WHITE (10,11)`
11. `BLACK (11,12)`
12. `WHITE (8,9)`
13. `BLACK (10,12)`
14. `WHITE (9,12)`
15. `BLACK (8,10)`
16. `WHITE (7,9)`
17. `BLACK (8,13)`
18. `WHITE (8,14)`
19. `BLACK (9,9)`
20. `WHITE (8,8)`
21. `BLACK (11,13)`
22. `WHITE (12,14)`
23. `BLACK (11,11)`
24. `WHITE (11,10)`
25. `BLACK (12,12)`
26. `WHITE (13,13)`
27. `BLACK (13,12)`
28. `WHITE (14,12)`
29. `BLACK (12,10)`
30. `WHITE (13,9)`
31. `BLACK (10,8)`

Observed search result before fix:

- classic persistent session: `(11,7) -20000`
- fresh classic search on the same board often looked “better” and returned
  `(9,7)`, but that was not the practical target
- `SlowRenju` Gomocup session: `(9,7) -20000`

Root cause trace:

- both engines reached a practical root-fallback turn
- on the reference side, the real process trace showed `MESSAGE Er...` at move
  `30` and move `32`, proving `rootsearch()` fell back to `AIs()`
- classic also reached a fallback turn, but its process-local reference RNG
  stream was offset from the reference
- that offset came from missing the second `InitHash()` consumption caused by
  the initial Gomocup `RESTART`

Landed change:

- [`pyslow/search/root.py`](../pyslow/search/root.py)
- `_ReferenceFallbackRng` state now mirrors the Gomocup-process stream after
  `START` plus the first `RESTART` / `InitHash()` pair

Practical effect:

- the last residual game `white_4_10_10` now matches `SlowRenju`
- whole-game parity across the full 5-opening Zhou set is now complete

## Confirmed Differences Found During Opening-Set `9` Investigation

These items are evidence-backed findings from the current 9-opening work.

Important:

- they are confirmed diagnosis
- they are not all landed fixes yet
- only the already landed fixes above should be treated as corrected baseline

### 7. `black_1_2_12` is a nonroot top-wide boundary / tie-order drift

Status:

- confirmed
- not yet safely fixed

Evidence:

- direct reference source evidence from [`SlowRenju/AI/AIx.cpp`](../SlowRenju/AI/AIx.cpp)
- direct practical trace evidence on the exact root and its first two sibling
  branches

Confirmed behavior:

- root raw candidate ordering itself is not the main problem on this residual
- raw nonroot candidate sets at the critical sibling nodes match
- drift appears when entering the searched top-`15` list
- node-local `best_move` propagation then amplifies that difference

Current conclusion:

- this is a real root-cause category
- but the globally correct repair condition is still not fully isolated
- a naive global ordering patch is not justified yet

### 8. `black_0_2_2` is not a leaf-eval mismatch

Status:

- confirmed
- not yet safely fixed

Evidence:

- direct exact-position calls in classic
- direct reference Gomocup trace on the matching branch

Confirmed behavior:

- classic can reproduce the same local `52 / -52` values as reference on the
  critical exact boards
- both engines use the same general mechanism of:
  - earlier negative-depth leaf exact store
  - later shallow-node exact hit
- so that mechanism itself is not the bug

Current strongest diagnosis:

- the engines land that mechanism on different nodes in the ancestor chain
- the current strongest evidence is that this is driven by nonroot equal-score
  tie-order interacting with cumulative `running_downf`
- on the critical `(4,5)` branch, a one-slot order difference is enough to
  cross the `downf >= 15` threshold and lower the first-search depth by `1`

Important caution:

- a direct tie-order patch was tested and reverted
- it matched the diagnosed local mechanism but did not change the practical
  opening-set `9` black results
- therefore this diagnosis is real but still incomplete as a repair condition

### 9. `black_2_12_2` likely belongs to the same family as `black_0_2_2`

Status:

- plausible
- not yet fully closed

Current evidence:

- mirrored edge opening
- first differing move also at `9`
- same kind of edge-adjacent drift signature

Still required:

- direct exact-node trace closure equivalent to `black_0_2_2`

### 10. `black_3_12_12` remains a separate unresolved class

Status:

- confirmed as separate
- not yet closed

Evidence:

- practical trace and root ordering inspection

Confirmed behavior:

- root initial ordering alone does not explain this residual
- the drift appears later, after deeper score propagation

Current conclusion:

- do not force this residual into the same explanation as the move-9 edge
  residuals without direct evidence

## Important Diagnostic Conclusions

These are confirmed conclusions from the investigation and should not be
forgotten later.

### A. Not every “better result” is a valid alignment fix

Several experiments produced behavior that looked stronger or closer on some
small sample, but were not backed by reference evidence.

Those should not be reused as “known fixes”.

### B. Practical whole-game drift can remain even when fixed-position compare stays green

`alignment_compare 70/70` remained aligned while practical whole-game drift was
still present.

Interpretation:

- fixed-position compare is necessary
- practical persistent-session trace is also necessary

### C. Persistent TT behavior matters

Several important classic-vs-reference differences only appeared under
persistent practical turn sequences, not under fresh one-shot search.

This means:

- fresh one-shot search is useful for diagnosis
- but it is not enough to validate reference alignment by itself

### D. Do not assume reference uses fresh TT

`SlowRenju` does not simply clear TT every turn.

If a fresh-search experiment happens to look closer to the reference on one
position, that is only a diagnosis hint, not a specification.

### E. Do not assume the fallback RNG starts immediately after one InitHash

In practical Gomocup play, the reference process consumes RNG during both:

1. `START`
2. the first `RESTART` used by full-board sync

So a fallback trace that only mirrors one post-`InitHash()` RNG state is still
wrong, even if the fallback scoring logic itself already matches.

### F. Do not treat a locally correct mechanism as a globally safe fix

During opening-set `9` work, some exact-node diagnoses were real and directly
evidence-backed, but the corresponding naive global patch still failed to
change practical whole-game results.

Interpretation:

- local mechanism proof is necessary
- but a landed classic fix still needs practical confirmation on the real
  persistent search path

## What State / Native Alignment Should Reuse Later

When aligning `state` and `native` to classic later, the following behavior
should be treated as part of the corrected classic baseline:

1. the corrected zobrist stream semantics
2. no turn key in zobrist
3. TT default size `20`
4. TT store priority based on root move count, not recursive move count
5. winning exact-store depth boost (`windepth + 10`)
6. root win-break on first `score >= WIN`
7. reference fallback RNG state aligned to Gomocup `START` + first `RESTART`

Any later `state` / `native` drift should be checked against these corrected
classic rules first.

## Remaining Open Items

Current classic-vs-`SlowRenju` status on the checked `d5 w15` practical
baseline:

- opening-set `5`: fully aligned
- opening-set `9`: four black-side whole-game residuals remain

Immediate unresolved items:

1. close the remaining upstream condition on `black_0_2_2`
2. confirm whether `black_2_12_2` is the same root-cause family or only looks
   mirrored
3. close `black_1_2_12` with a globally safe repair condition instead of a
   node-local explanation only
4. treat `black_3_12_12` as a separate class until direct evidence says
   otherwise

If new drift appears later, use the same workflow:

1. isolate first differing root turn
2. compare practical persistent-session behavior
3. only then trace source-level behavior in the reference
