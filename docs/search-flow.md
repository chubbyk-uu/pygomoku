# Search Flow For `pyslow`

## Purpose

This document specifies how `pyslow` should reproduce the normal search architecture of `SlowRenju` for phase 1.

Scope:

- only `15x15` freestyle Gomoku
- no Renju rule branches
- preserve search structure and control flow as much as practical
- preserve interfaces needed by later native acceleration

Primary references:

- [`SlowRenju/AI/AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp)
- [`SlowRenju/AI/Hash.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/Hash.cpp)
- [`SlowRenju/Value/ValueWide.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Value/ValueWide.cpp)
- [`SlowRenju/Value/ValueW.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Value/ValueW.cpp)

## Core Search Model

The reference engine uses:

- iterative deepening
- alpha-beta
- transposition table
- strong move ordering
- reduced-width candidate generation
- tactical VCF checks before and around normal search

The Python port should preserve this overall shape. Phase 1 should not substitute a generic minimax or MCTS skeleton.

## Root Search Responsibilities

Reference entry:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L174)

`rootsearch()` is responsible for:

1. initialize search parameters
2. rebuild current Zobrist key from board state
3. handle simple opening shortcuts
4. run tactical VCF check first
5. build root legal-move mask
6. run iterative deepening loop
7. adapt time budget based on stability
8. return best move

Recommended Python API:

```python
class RootSearcher:
    def search(self, board: Board, limits: SearchLimits) -> SearchResult:
        ...
```

## Search Context

The C code uses global mutable state. Python should replace this with an explicit context object.

Recommended fields:

```python
@dataclass
class SearchContext:
    board: Board
    config: EngineConfig
    tt: TranspositionTable
    evaluator: Evaluator
    movegen: MoveGenerator
    threats: ThreatSearcher
    start_time_ns: int
    soft_time_limit_ms: int
    hard_node_limit: int | None
    node_count: int = 0
    stop: bool = False
    current_depth: int = 0
    max_depth_reached: int = 0
    best_so_far: int | None = None
```

This context should be passed explicitly through root search and alpha-beta.

## Root Search Flow

### 1. Initialize Search Parameters

Reference fields:

- `DEPTH`
- `WIDE`
- `RATIO1`
- `RATIO2`

These should become explicit values inside Python search limits or search config.

Recommended Python structure:

```python
@dataclass(frozen=True)
class SearchLimits:
    max_depth: int
    root_width: int
    child_width_num: int
    child_width_den: int
    time_limit_ms: int | None = None
    node_limit: int | None = None
```

### 2. Rebuild Zobrist

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L279)

The root search reconstructs `CurrentZobrist` from board state.

Python policy:

- `Board` should already maintain the live hash
- root search should trust `board.zobrist_key`
- add tests to guarantee make/unmake stability

### 3. Opening Shortcuts

Reference special cases:

- empty board uses an opening shortcut
- if only one move exists and center is occupied, a nearby response is chosen
  from the two hard-coded replies in `AIx.cpp`

Python policy:

- preserve the empty-board center move shortcut
- preserve the one-move nearby response shortcut present in the reference code
- note that the reference code randomly chooses between the two hard-coded
  replies; if `pyslow` stays deterministic, it should still preserve the same
  two-move candidate set and document the deterministic tie-break

### 4. Run VCF First

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L306)

If tactical search finds a winning VCF, root search returns it immediately.

Python requirement:

- root search must consult threat search before normal alpha-beta

### 5. Root Candidate Filter

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L320)

If the opponent has a VCF threat, root search filters out moves that fail to address it.

This idea should be preserved in Python, including the root-side filtering behavior when the opponent has a tactical forcing line.

### 6. Iterative Deepening

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L390)

Search pattern:

- for depth `1..DEPTH`
- call alpha-beta
- retain last stable best line
- stop on win/loss/time pressure

Python should keep iterative deepening as the only root driver.

Reference default launch path from `main.cpp`:

- `rootsearch(24, 60, 1, 1)`

Unless explicitly overridden, `pyslow` should start from these same root search
defaults.

### 7. Time Adaptation

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L402)

If the score or best move is unstable, the engine allows a larger time budget; otherwise it keeps a smaller target.

Python should preserve the capability that score and PV stability affect root time allocation. The implementation can be cleaner than the C code, but the behavior should not be intentionally downgraded to a fixed-limit-only model.

## Alpha-Beta Entry Conditions

Reference entry:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L519)

At the beginning of each node, the search checks:

- node limit
- external stop flag
- time expiration via propagated stop flag
- TT probe

Recommended Python order:

1. `if should_stop(context): return stopped_result`
2. increment node count
3. probe TT
4. if depth <= 0: evaluate leaf
5. otherwise generate/search moves

## TT Semantics

Reference TT flags:

- `hashfEXACT`
- `hashfALPHA`
- `hashfBETA`

Reference behavior:

- exact hit returns immediately
- alpha entries can either cut or shrink window
- beta entries cut when they exceed `beta`
- lookup returns a `best` move hint, and `alphabeta` gives that move a scoring
  bonus during candidate scoring

Python requirement:

- preserve these semantics
- preserve the practical effect of bounded-entry replacement and TT-guided move reuse

Recommended API:

```python
class TranspositionTable:
    def probe(self, key: int, depth: int, alpha: int, beta: int) -> ProbeResult: ...
    def store(self, key: int, entry: TTEntry) -> None: ...
```

## Leaf Evaluation Flow

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L596)

At leaf:

1. backup local incremental caches
2. recompute `ValueWide`
3. call global `value()`
4. convert terminal wins/losses to `INF - ply` style values
5. restore caches
6. store exact TT

Python policy:

- preserve evaluation semantics
- cache backup/restore can be implemented more cleanly using board/evaluator undo layers, without reducing functionality

Recommended leaf helper:

```python
def evaluate_leaf(ctx: SearchContext, ply: int, side: int) -> int:
    ...
```

## Candidate Generation Flow

### Covered Region

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L674)

The move generator only considers empty cells reached by the fixed
`coverdir[32]` template around existing stones. This is close to a "distance 3"
description, but it is not a generic full-radius scan.

Python requirement:

- reproduce the reference `coverdir` coverage template as the default normal
  move domain

### Candidate Metadata

For each covered point:

- `moveValue1bWide`
- self attack level
- opponent attack level

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L705)

Recommended Python candidate object:

```python
@dataclass
class Candidate:
    move: int
    order_score: int
    self_attack: int
    opp_attack: int
```

### Forcing Classification

Reference flags:

- `sglflag`
- `hsflag`
- `winpri`

Meaning:

- `sglflag`: there exist forcing moves or must-play moves
- `hsflag`: there exists a strong hostile threat region
- `winpri`: current side has immediate winning priority

Python should preserve these concepts as real move-selection mechanisms, not placeholders.

### Special Active-Three Bonus

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L738)

There is an extra branch that boosts continuation points of certain active-three structures by `10000`.

Policy:

- this should be preserved because it materially affects move ordering and tactical quality

### Root Mask Penalty

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L897)

If root filtering determined some moves are irrelevant, they get a penalty or are excluded.

Python should implement this as a root-only allowed move mask.

### Candidate List Outcome

After scoring:

- some moves can trigger immediate return
- forcing conditions can collapse the list to one move
- otherwise list is sorted and trimmed to `wide`

This is the effective normal search branching policy.

## Move Ordering

Reference ordering uses:

- candidate score
- TT best move preference
- `getmi(...)` tie-breaker

Python ordering requirements:

1. preserve the TT best-move bias carried by lookup results
2. descending candidate score
3. deterministic tie-breaker
4. preserve the role served by `getmi()` as an additional deterministic ordering signal

## Width Reduction

Reference recursion uses:

- `min(wide * RATIO1 / RATIO2 + 1, wide)`

Meaning:

- deeper nodes search narrower candidate sets

Python should preserve this exact concept.

Recommended helper:

```python
def next_width(width: int, num: int, den: int) -> int:
    return min((width * num) // den + 1, width)
```

## Depth Reduction

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L1106)

Depth reduction is driven by:

- candidate count
- `EXTENDRATIO`
- accumulated `downf`
- attack bonus terms

The engine computes:

- `depthdown`
- optional extra `net`
- `atdown` from attack level 3/4
- root-only bonus from `rootbonus()`

Python requirement:

- preserve attack bonus and width-dependent depth reduction
- preserve the reference search heuristics that materially affect move choice

## PVS-Style Window Search

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L1133)

Pattern:

- first candidate searched with full window
- later candidates searched with narrow window
- if narrow result improves alpha, re-search full window

This should be preserved. It is a meaningful part of search efficiency.

Recommended Python structure:

```python
if found_pv:
    score = -search(child, -alpha - 1, -alpha)
    if alpha < score < beta:
        score = -search(child, -beta, -alpha)
else:
    score = -search(child, -beta, -alpha)
```

## Terminal Score Normalization

Reference leaf normalization:

- wins become `INF - ply`
- losses become `-INF + ply`

Purpose:

- prefer faster wins
- prefer slower losses

Python should preserve this.

## Root Bonus

Reference:

- [`AIx.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/AI/AIx.cpp#L89)

This is a root-only positional bonus based on:

- proximity to edge/corner
- local stone density

Policy:

- preserve as root-ordering bias
- do not merge it into the board evaluator

## Stop Conditions

The search should stop on:

- external stop
- time limit
- node limit
- root half-end equivalent if implementing progressive time control

Python requirements:

- time limit
- node limit
- explicit stop flag

## Recommended Python Modules

```text
pyslow/search/
  tt.py
  ordering.py
  movegen.py
  alphabeta.py
  root.py
```

Suggested responsibilities:

- `tt.py`: probe/store and flags
- `ordering.py`: candidate sort and tie-break
- `movegen.py`: covered-cell generator and candidate metadata
- `alphabeta.py`: recursive node search
- `root.py`: iterative deepening and root-only policy

## Fidelity Requirement

Except for board size and supported rule set, search behavior should be aligned with the reference engine rather than intentionally simplified.

That means the Python implementation should preserve:

- iterative deepening
- TT exact/alpha/beta semantics
- covered-cell candidate generation
- move ordering based on bucket-derived scores
- attack-level-driven search bonuses
- root-side tactical filtering
- score-stability-aware root control
- tactical VCF hook before normal search
- the extra ordering branches that materially affect candidate priority

## Required Tests

Before calling the searcher usable, add tests for:

1. TT exact hit returns stored result
2. alpha/beta TT bounds shrink or cut correctly
3. candidate generator excludes distant empty cells
4. move ordering prefers immediate wins and must-defend points
5. iterative deepening returns stable best move on curated positions
6. terminal win normalization prefers shorter wins
7. make/unmake plus evaluator state remains consistent across recursive search

## Build Order Suggested By This Spec

1. `tt.py`
2. `movegen.py`
3. `ordering.py`
4. leaf evaluation adapter
5. basic alpha-beta
6. iterative deepening root search
7. root-only filters and bonuses
8. search heuristics parity verification

## Final Design Rule

The normal searcher in `pyslow` should be evaluation-driven and candidate-driven, not board-scan-driven.

That is the key structural lesson from `SlowRenju`.
