# Branch Alignment Checklist

## Purpose

This checklist is for verifying that `pyslow` is aligned with `SlowRenju` not only on the main path, but also on:

- fallback paths
- early-return paths
- forced tactical branches
- runtime/config branches
- error or empty-candidate branches

The goal is to avoid a false sense of alignment caused by only checking the "normal" search flow.

## Current Audit Status

The checklist is strong evidence of branch-level progress, but it is not the final source of truth by itself.

Most recent systematic comparison status:

- [alignment_compare.py](/home/jerry/python-test/gomoku/slow_temp/benchmarks/alignment_compare.py) now compares 70 fixed positions
- current result: `70/70`
- the compare set now includes:
  - opening
  - midgame
  - tactical / VCF-first
  - edge / corner
  - fallback / `rootsplit`
  - dense positions
- transformed positions in the set were mechanically checked against their base
  positions to eliminate hand-copy drift

Therefore:

- branch-level alignment is now closed for the current 70-position compare set
- future work should treat semantic alignment as a regression target, not as an
  open investigation item

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
- [x] verify remaining stop interaction around root return against reference trace
  verified: with nodelimit=50 on fallback position, both engines return move=68 via AIs() fallback.
  pyslow detects empty candidates earlier (before iteration) while reference enters one iteration; end result identical.
- [x] explain and eliminate the former systematic-compare score residual on `mid_ladder`
  root cause:
  `pyslow` had incorrect `downf` semantics in non-root alpha-beta.
  Reference accumulates `downf` across siblings and carries the remainder
  forward; Python incorrectly recomputed `downf` from the parent base for each
  child. This changed `depthdown`, PVS shape, and TT interaction, producing the
  false near-win score on `mid_ladder`.

### Alpha-Beta

- [x] TT exact/alpha/beta probe behavior roughly aligned
- [x] depthdown/downf/ATDOWN/rootbonus path present
- [x] entry stop/node-limit returns `(0,-1)` for both root and non-root like reference `gvstop` early return
- [x] empty-candidate path returns `(-INF,-1)`
- [x] known fallback position matches reference at `rootsearch()` level and `AIs()` fallback
- [x] verify stop/node-limit/time-stop return path against reference trace
  verified: node-limit triggers gvstop/stats.stop, alphabeta returns (0,-1) in both engines,
  root breaks iteration and falls back to AIs()/_fallback_ai_move() identically.
- [x] verify whether `mid_ladder` score divergence comes from alpha-beta propagation, window behavior, or search-extension semantics
  resolved:
  the exact non-root divergence at `mid_ladder + (7,5)` was fixed by matching
  reference `downf` accumulation semantics. Exact child result now matches
  reference: `score=-47`, `move=(7,9)`.

### Candidate Generation

- [x] `coverdir[32]` domain aligned
- [x] `hsflag`, `sglflag`, `winpri` path present
- [x] known fallback position hostile-three extension now matches corrected reference bonus targets `(8,4)` and `(8,8)`
- [x] verify hostile-three extension (`A3pb -> +10000`) on concrete positive reference positions
- [x] verify positions where reference keeps zero candidates
  verified: zero candidates at non-root is practically unreachable (ATTACKVALUE+DEFENDVALUE always positive
  for covered cells with neighbors). At root level, VCF filter can zero out candidates triggering AIs() fallback.
  Return value diff: reference -20001 vs pyslow -20000; both well below -WIN, no behavioral impact.
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
- [x] verify whether `mid_ladder` score divergence depends on candidate ordering / top-width retention under depth=3,width=8
  result:
  candidate retention was not the root cause after corrected trace analysis.
  The decisive mismatch was search-extension state propagation, not movegen.

### ValueWide

- [x] key point values for the known fallback position matched by trace
- [x] floating `depth-depthdown` search-depth semantics aligned with reference; do not truncate before recursive call
- [x] verify `ComputeShape1b` packed shape values against reference trace on handpicked points
- [x] verify `ComputeValue1b` bucket outputs against reference trace on handpicked points
- [x] verify `attack1bWide` outputs on threat/fork/four positions against reference trace
- [x] verify `ValueWideCompute` incremental update path against reference snapshots
- [x] rule out `ValueWide` / eval mismatch as the cause of `mid_ladder` score divergence by pointwise trace on that exact position
  result:
  `ValueWide` / eval were not the root cause of the remaining residual.

### Global Eval

- [x] main `LAST5`/`NEXT43` structure present
- [x] verify recursive branch returns on handpicked forced positions
- [x] verify extreme-value and terminal-return edge cases against reference trace
- [x] rule out `global_eval` branch mismatch as the cause of `mid_ladder` score divergence on the exact ladder position
  result:
  the resolved mismatch was in alpha-beta search state, not global eval.

### VCF / Threat Board

- [x] begin depth cap and shallow-first begin behavior
- [x] core `B4p(c)` / `B4p(-c)` branch structure
- [x] `VCFd_hash(begin=1,...)` three-way result mapping aligned on found / solved-negative / unsolved positions
- [x] verify memo/hm-equivalent branches on repeated tactical states
  verified on 5 positions: canonicalization defines same equivalence classes (sorted attacker/defender sets),
  depth filtering matches (immediate return for found/solved, depth-exact gate for not-found).
  Memo clear timing differs (pyslow once per search vs reference per-level) but safe due to depth guard.
  All 5 positions produce identical VCF results and matching memo entry counts.
- [x] verify begin/finish/unsolved semantics against reference trace
- [x] verify remaining `line4v` tactical predicates on handpicked positions
- [x] determine whether `mid_ladder` enters a tactical / VCF path in `pyslow` but not in reference
  result:
  no. The residual stayed on the normal search path.

### Protocol / Runtime

- [x] `compute_vcf` runtime flag wired through
- [x] source-level `static_board`, `time_left`, `timeout_turn`, `timeout_match`, `max_node` semantics aligned and regression-covered
- [x] `BOARD ... DONE` reconstruction order aligned with reference source semantics
- [x] verify remaining runtime/protocol behavior against a compiled reference engine process
  verified: all 16 existing protocol tests pass. START/BEGIN/TURN/BOARD/INFO/TAKEBACK/ABOUT/END
  all behave consistently with reference main.cpp. Minor safe differences: pyslow rejects unknown
  commands (reference ignores), pyslow guards TAKEBACK on empty board (reference has a bug there),
  pyslow restricts to 15x15 only (intentional phase-1 scope).

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

For future residuals, use this stricter workflow:

1. Run `alignment_compare.py` and confirm the mismatch reproduces.
2. Trace the exact position in both engines at the same `depth,width`.
3. Compare, in order:
- root exit path
- whether VCF/special path fired
- root candidate list and scores
- child alpha-beta return values
- leaf/global eval values
4. Only mark the related checklist item complete after the residual is either:
- eliminated, or
- proven to be a harness/trace artifact

## Notes

- Direct reference traces are especially important for fallback and branch behavior.
- Main-path similarity is not sufficient evidence of full alignment.
- When in doubt, compare returned move semantics first, then drill into buckets/attacks/candidates.
- `fflag` / foul-related branches belong to non-freestyle rule paths and are intentionally out of scope for current `pyslow` alignment work.
