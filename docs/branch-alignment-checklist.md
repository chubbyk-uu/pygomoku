# Branch Alignment Checklist

## Purpose

This checklist is for verifying that `pyslow` is aligned with `SlowRenju` not only on the main path, but also on:

- fallback paths
- early-return paths
- forced tactical branches
- runtime/config branches
- error or empty-candidate branches

The goal is to avoid a false sense of alignment caused by only checking the "normal" search flow.

## Rules

1. Do not mark a branch as aligned only because the surrounding main logic looks similar.
2. Prefer direct reference trace comparison when a branch changes the returned move or returned score.
3. If `pyslow` and `SlowRenju` differ, first identify whether the difference comes from:
- upstream evaluation semantics
- candidate generation semantics
- root/search fallback semantics
- tactical module semantics
4. Do not patch around a mismatch unless the patch is explicitly justified as a temporary stopgap.
5. If a temporary stopgap is used, record:
- why it was needed
- why it does not match the reference
- what root cause still needs to be fixed

## Verified Cases

### Root Fallback

Reference behavior discovered by direct trace:

- `alphabeta(...)` can return `move == -1`
- `rootsearch(...)` then falls back to `AIs()`
- it does not fall back to center
- it does not fall back to the first legal move

Verified reference trace position:

- after moves:
  - black `(7,7)`
  - white `(7,6)`
  - black `(7,5)`
  - white `(6,5)`
  - black `(8,7)`
  - white `(6,7)`
  - black `(6,6)`
  - white `(5,8)`
  - black `(8,5)`
  - white `(5,4)`
  - black `(8,6)`
  - white `(4,9)`
  - black `(3,10)`
  - white `(4,3)`
  - black `(3,2)`
- reference `alphabeta` returned `-1`
- reference `AIs()` returned `(8,4)`
- with corrected trace initialization (`S=15; boardSize=15`), reference `alphabeta(10,3,...)` returns `score=-20000, move=-1`
- with corrected trace initialization, reference `rootsearch(3,10,1,1)` returns `(8,4)`

Current `pyslow` status:

- aligned

## Checklist

### Root Search

- [x] empty-board opening shortcut
- [x] one-move opening reply set
- [x] root `VCF first`
- [x] opponent VCF pressure filter
- [x] time/stability budget split
- [x] `best_move == -1` fallback uses `AIs()` semantics
- [x] `rootmove/rootsplit==1` behavior aligned
- [x] dynamic-board square-window behavior aligned
- [x] `rootsplit<=0` empty-rootmove path aligned back to `AIs()` fallback semantics
- [ ] verify remaining stop interaction around root return against reference trace

### Alpha-Beta

- [x] TT exact/alpha/beta probe behavior roughly aligned
- [x] depthdown/downf/ATDOWN/rootbonus path present
- [x] entry stop/node-limit returns `(0,-1)` for both root and non-root like reference `gvstop` early return
- [x] empty-candidate path returns `(-INF,-1)`
- [x] known fallback position matches reference at `rootsearch()` level and `AIs()` fallback
- [ ] verify stop/node-limit/time-stop return path against reference trace

### Candidate Generation

- [x] `coverdir[32]` domain aligned
- [x] `hsflag`, `sglflag`, `winpri` path present
- [x] known fallback position hostile-three extension now matches corrected reference bonus targets `(8,4)` and `(8,8)`
- [x] verify hostile-three extension (`A3pb -> +10000`) on concrete positive reference positions
- [ ] verify positions where reference keeps zero candidates
- [x] verify positions where reference keeps exactly one candidate
- [x] `preferred_move` / TT best move injection works on corrected simple root trace at shallow depths
  corrected trace update:
  reference `rootsearch(3,8,1,1)` on the simple TT-alpha seeded two-stone position searches depths `1..4` and returns `(6,6), 13`
  corrected reference depth-4 root candidate scores are:
  - `(8,6)=11`
  - `(6,6)=13`
  - `(6,8)=13`
  and reference tie-break keeps `(6,6)`
  `pyslow` now matches this corrected root result when called with `SearchLimits(max_depth=3, root_width=8)`
- [x] corrected simple TT-alpha seeded two-stone root result aligned

### ValueWide

- [x] key point values for the known fallback position matched by trace
- [x] floating `depth-depthdown` search-depth semantics aligned with reference; do not truncate before recursive call
- [x] verify `ComputeShape1b` packed shape values against reference trace on handpicked points
- [x] verify `ComputeValue1b` bucket outputs against reference trace on handpicked points
- [x] verify `attack1bWide` outputs on threat/fork/four positions against reference trace
- [x] verify `ValueWideCompute` incremental update path against reference snapshots

### Global Eval

- [x] main `LAST5`/`NEXT43` structure present
- [x] verify recursive branch returns on handpicked forced positions
- [x] verify extreme-value and terminal-return edge cases against reference trace

### VCF / Threat Board

- [x] begin depth cap and shallow-first begin behavior
- [x] core `B4p(c)` / `B4p(-c)` branch structure
- [x] `VCFd_hash(begin=1,...)` three-way result mapping aligned on found / solved-negative / unsolved positions
- [ ] verify memo/hm-equivalent branches on repeated tactical states
- [x] verify begin/finish/unsolved semantics against reference trace
- [x] verify remaining `line4v` tactical predicates on handpicked positions

### Protocol / Runtime

- [x] `compute_vcf` runtime flag wired through
- [x] source-level `static_board`, `time_left`, `timeout_turn`, `timeout_match`, `max_node` semantics aligned and regression-covered
- [x] `BOARD ... DONE` reconstruction order aligned with reference source semantics
- [ ] verify remaining runtime/protocol behavior against a compiled reference engine process

## Recommended Workflow

For any suspected mismatch:

1. Reproduce the position in `pyslow`.
2. Record:
- side to move
- candidate list
- chosen move
- score
- tactical/fallback state
3. Reproduce the same position in a minimal `SlowRenju` trace harness.
4. Compare the smallest layer that already diverges:
- ValueWide
- movegen
- alphabeta
- root fallback
- VCF
5. Fix the earliest diverging layer.
6. Add:
- one regression test in `tests/`
- one checklist note here if the branch was non-obvious

## Notes

- Direct reference traces are especially important for fallback and branch behavior.
- Main-path similarity is not sufficient evidence of full alignment.
- When in doubt, compare returned move semantics first, then drill into buckets/attacks/candidates.
- `fflag` / foul-related branches belong to non-freestyle rule paths and are intentionally out of scope for current `pyslow` alignment work.
