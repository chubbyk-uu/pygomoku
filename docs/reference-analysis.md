# Reference Analysis For `pyslow`

## Scope

This document records the implementation details from `SlowRenju/` that should be preserved when building `pyslow/`.

Confirmed scope for `pyslow` phase 1:

- Only `15x15` freestyle Gomoku
- No Renju support
- No Standard Gomoku support
- Keep room for later native acceleration
- Reuse `SlowRenju`'s evaluation structure and score tables as much as possible
- Keep tactical search separate from normal move generation

The goal is not a literal C-to-Python port. The goal is to preserve the engine's chess strength sources while rebuilding them in a Python-friendly architecture.

## Repository State

Current workspace:

- `SlowRenju/`: reference C/C++ engine
- `pyslow/`: Python port in progress

Important reference files:

- `SlowRenju/Headers/game.h`
- `SlowRenju/Common/global_value.cpp`
- `SlowRenju/Common/main.cpp`
- `SlowRenju/Value/ValueB.cpp`
- `SlowRenju/Value/ValueW.cpp`
- `SlowRenju/Value/ValueWide.cpp`
- `SlowRenju/Shape/line.cpp`
- `SlowRenju/Shape/line4v.cpp`
- `SlowRenju/AI/AIx.cpp`
- `SlowRenju/AI/Hash.cpp`
- `SlowRenju/VCF/VCF.cpp`

## High-Level Understanding

`SlowRenju` is a Gomocup-compatible engine using:

- Iterative deepening alpha-beta
- Transposition table with Zobrist hash
- Pattern-based local evaluation
- Incremental local cache recomputation
- Tactical VCF search before and during normal search

Additional runtime behavior that matters for parity:

- root search is launched with hard-coded defaults `depth=24`, `wide=60`,
  `ratio1=1`, `ratio2=1` from `main.cpp`
- optional dynamic-board mode crops the active move list to a square window with
  4-cell margin before searching
- config reload can happen before each move if `READCONFIG` is enabled
- fallback move selection uses `AIs()` and contains randomness among tied local
  best moves

For `pyslow`, the parts that matter most are:

1. Parameter grouping and default values
2. Pattern classification and value bucketing
3. Incremental local evaluation flow
4. Candidate generation and move ordering
5. Alpha-beta structure and TT semantics
6. Tactical threat search as an independent subsystem

## What Must Be Preserved

### 1. Parameter System

`SlowRenju` centralizes evaluation and search parameters in a single `para[]` array.

Definitions in `game.h`:

- `LASTEVAL`
- `NEXTEVAL`
- `ATTACKVALUE`
- `DEFENDVALUE`
- `DRIFT`
- `DGN`
- `ATDOWN3`
- `ATDOWN4`
- `LASTWEIGHT`
- `READCONFIG`
- `EXTENDRATIO`

There are `DSHAPESIZE = 92` bucket entries per major table. The layout is:

1. `LASTEVAL[92]`
2. `NEXTEVAL[92]`
3. `ATTACKVALUE[92]`
4. `DEFENDVALUE[92]`
5. Scalar tail values:
   - `DRIFT`
   - `DGN`
   - `ATDOWN3`
   - `ATDOWN4`
   - `LASTWEIGHT`
   - `READCONFIG`
   - `EXTENDRATIO`

This exact grouping should be preserved in Python, but not the raw-array API.

One runtime detail from `main.cpp` also matters:

- if config is loaded from `srconfig.txt`, the reference code adds `65536` to
  `para[156]` and `para[157]` after parsing

Recommended Python mapping:

- `config.py`
- `EvalBuckets`
- `SearchTuning`
- `RuntimeOptions`

Suggested structure:

```python
@dataclass(frozen=True)
class EvalBuckets:
    last_eval: tuple[float, ...]
    next_eval: tuple[float, ...]
    attack_value: tuple[int, ...]
    defend_value: tuple[int, ...]


@dataclass(frozen=True)
class SearchTuning:
    drift: float
    dgn: float
    atdown3: int
    atdown4: int
    last_weight: float
    extend_ratio: float


@dataclass(frozen=True)
class RuntimeOptions:
    read_config_each_move: bool = False
```

Important rule: the default numeric values should initially come directly from `SlowRenju/Common/global_value.cpp`, not from fresh hand-tuning.

### 2. Pattern-Based Evaluation Model

`SlowRenju` does not score directly from raw board shapes every time. It follows a layered pipeline:

1. For each empty point, compute four directional pattern descriptors
2. Compress those descriptors into a discrete bucket id
3. Use bucket ids to look up attack and evaluation values
4. Aggregate local values into a global evaluation

This model must be preserved because the search logic depends on these derived values, not just on a final board score.

### 3. Incremental Cache Model

The reference engine maintains several caches in `ValueWide.cpp`:

- `shapeM[2][N][N][4]`
- `valueM[2][N][N]`
- `attackM[2][N][N]`
- `boardM[N][N]`

Meaning:

- index `0` is black-as-player
- index `1` is white-as-player
- per empty point, store directional shapes and merged bucket id
- separately store an attack priority level

The engine does not fully recompute all local structures from scratch after every move. It detects changed areas and only recomputes affected points and directions.

This is essential for Python too. Even if the first implementation is not maximally optimized, the API should be built around incremental recomputation.

### 4. Normal Search Candidate Logic

The normal search in `AIx.cpp` does not enumerate all empty cells.

It first creates a covered region using the fixed `coverdir[32]` offset table in
`AIx.cpp`, not a generic radius parameter:

- offsets at distance `1`
- a selected set of offsets at distance `2`
- only the eight `3`-step corner/cardinal offsets at distance `3`
- all other empty points are ignored

Then for each covered point:

- compute `moveValue1bWide`
- compute `attack1bWide` for self
- compute `attack1bWide` for opponent
- classify forcing status such as immediate threats or defensive urgency

Then the candidate list is filtered and reordered again using:

- root filtering
- active threat bonuses
- special handling for single-forcing lines
- top-`wide` truncation

This means `pyslow` should not start with a naive "all neighbor points within radius 2" generator and call it done. It should replicate the reference engine's multi-stage candidate pipeline.

### 5. Tactical Search Is Separate

`VCF.cpp` uses its own move generation. It does not use the normal covered-point logic.

It explicitly searches:

- direct forcing moves
- threat continuation points
- specific defenses

This is aligned with the project requirement: tactical search must only generate threat points and defense points, not general neighborhood moves.

### 6. Search Control Depends On Evaluation Metadata

`AIx.cpp` uses not only the static score but also:

- attack level
- candidate count
- root bonus
- extension ratio
- threat penalties and bonuses

That means the evaluation subsystem in Python must expose more than `evaluate(board) -> int`.

It should expose at least:

- bucket id for a point
- attack level for a point
- move ordering score for a point
- static eval contribution for a point

## Detailed Reference Notes

### A. Global Constants And State

Defined in `game.h` and `global_value.cpp`:

- `WIN = 15000`
- `INF = 20000`
- `hashfEMPTY`, `hashfEXACT`, `hashfALPHA`, `hashfBETA`
- board array and move count
- time controls and node limit

For Python:

- keep these as named constants
- do not reproduce C-style global mutable state
- store runtime state in `Board`, `SearchContext`, and `Engine` objects

### B. Shape Labels

The directional shape labels are defined in `game.h`:

- `L0`
- `L1S`
- `L1`
- `L2S`
- `L2BB`
- `L2B`
- `L2`
- `L3S`
- `L3B`
- `L3`
- `L4S`
- `L4`
- `L5`
- `L6`

The exact semantic names are not documented in comments, but the usage reveals the role:

- `L5` is a five
- `L6` is overline
- `L4` is a direct four
- `L4S` is a split/blocked-four type that additionally stores branch count in low bits
- `L3`, `L3B`, `L3S` are strong and semi-strong three patterns
- `L2*`, `L1*` are lower-level shape classes

Python should preserve the same labels as an enum or integer constants. Do not invent a new label system yet.

### C. `line::shape()` Output Contract

`line::shape()` in `Shape/line.cpp` returns a packed integer encoding:

- high 4 bits of the returned shape code store category information
- low 4 bits can carry a branch count or subtype information

Later, `ComputeValue1b()` extracts:

- `temp = (shapeM[player][x][y][i] >> 16) & 15`
- low bits of `L4S` are interpreted as a multiplicity count

This means the Python port should preserve the packed output contract, at least internally.

Recommendation:

- represent the directional shape as a small dataclass for readability
- add a conversion helper to the packed integer form if needed for table compatibility

### D. `doubleShape` Mapping

`ValueWide.cpp` contains a triangular `doubleShape[13][13]` table producing values from `1` to `91`.

This is a key compression step:

- take the two strongest directional line categories among four directions
- map them to a bucket id
- use bucket id to index score tables

This mapping is central and should be copied exactly.

Consequences:

- bucket ids are a stable interface between pattern recognition and scoring
- the bucket ids drive both move ordering and static evaluation

### E. `ComputeShape1b()` Flow

For an empty point `(x, y)`:

1. temporarily place black stone
2. compute 4 directional shapes, store in `shapeM[0][x][y][d]`
3. temporarily place white stone
4. compute 4 directional shapes, store in `shapeM[1][x][y][d]`
5. restore empty

This exact flow is important. `shapeM` is storing "if black plays here" and "if white plays here", not only current-board information.

### F. `ComputeValue1b()` Flow

For each player view separately:

1. inspect the 4 directional shapes
2. derive:
   - count of active threes
   - count of blocked/split fours
   - count of fives
   - count of overlines
   - highest attack level
3. normalize the 4 directional categories into two strongest lines
4. use `doubleShape` to obtain the bucket id
5. store bucket id in `valueM`
6. store attack priority in `attackM`

For freestyle Gomoku, only the non-foul branch matters for phase 1, but the same structure still matters.

### G. `moveValue1bWide`, `evalValue1bWide0`, `evalValue1bWide1`

These are simple but critical adapters:

- `moveValue1bWide(x, y, c)`:
  - returns `ATTACKVALUE[bucket_self] + DEFENDVALUE[bucket_opp]`
  - used for search candidate ordering
- `evalValue1bWide0(x, y, c)`:
  - returns `NEXTEVAL[bucket]`
  - used in defensive/global evaluation
- `evalValue1bWide1(x, y, c)`:
  - returns `LASTEVAL[bucket]`
  - used in offensive/global evaluation

This separation should be preserved exactly in `pyslow`. Search ordering and board evaluation should not share a single ad hoc score.

### H. Global `value()` Function

`ValueW.cpp::value(c, opo)` computes the board score for side `c`.

It does:

1. scan every point
2. for stones already on board, compute a crowding / isolation term contributing to `dgn`
3. for empty points:
   - add offensive contribution via `evalValue1bWide1`
   - add defensive contribution via `evalValue1bWide0`
4. final score is:
   - `affensive - defensive - DRIFT + dgn * DGN`
5. then handle tactical score normalization for very large values:
   - direct win
   - direct loss
   - forced responses

Two important observations:

- This is not a plain linear static evaluator. It has embedded tactical correction for winning patterns.
- The `dgn` term punishes isolated / over-concentrated stone placement and affects strategic bias.

Python should reproduce both parts before trying to retune anything.

### I. `value1b()`

`ValueB.cpp::value1b()` is a simpler local point evaluator used as a local scoring component alongside the wider incremental evaluator.

It manually combines counts of:

- `A1`
- `B2`
- `A2`
- `B3`
- `A3`
- `B4`
- `A4`
- `A5`

and returns a weighted local score.

This is less central than the wide incremental evaluator, but still useful:

- as a baseline check
- as a local scoring cross-check
- as a test oracle for local tactical intuition

`pyslow` should include an equivalent local evaluator as part of faithfully reproducing the reference scoring stack.

## Search Architecture

### Root Search

`rootsearch()` in `AIx.cpp` does the following:

1. initialize timing and counters
2. rebuild current Zobrist from the board
3. special-case opening behavior
4. immediately try `VCFd_hash(...)`
5. if side to move is under tactical pressure, adjust root candidate logic
6. iterative deepening loop:
   - call `alphabeta(...)`
   - adapt time target based on score stability
   - stop on win/loss/time pressure

Important preserved ideas:

- tactical win lookup before normal search
- iterative deepening as the only root driver
- score stability affects time allocation

### Alpha-Beta Core

`alphabeta()` performs:

1. node/time/stop checks
2. TT probe
3. if depth exhausted:
   - recompute local caches
   - call `value()`
   - normalize terminal wins/losses
   - store exact TT result
4. else:
   - recompute local caches
   - build candidate set from covered cells
   - prioritize by `moveValue1bWide` and attack levels
   - sometimes collapse to a single forcing move
   - sort top `wide` candidates
   - recurse with reduced width and adjusted depth
   - use null-window style search after PV found
   - store TT result

Preserved search concepts:

- iterative deepening + alpha-beta
- TT lookup and store
- PVS-like null window after first PV
- width reduction on deeper plies
- depth reduction based on candidate count
- attack-based search bonus/penalty

### Depth And Width Heuristics

Important search tuning variables:

- `WIDE`
- `DEPTH`
- `RATIO1`, `RATIO2`
- `EXTENDRATIO`
- `ATDOWN3`
- `ATDOWN4`

Observed roles:

- `wide` is the candidate cap
- deeper nodes reduce width using `wide * RATIO1 / RATIO2`
- effective depth reduction depends on candidate count and `EXTENDRATIO`
- high-attack moves get additional search bonus via `ATDOWN3` and `ATDOWN4`

These should remain explicit tuning fields in Python.

### Root Bonus

`rootbonus()` adds a positional bonus related to edge and corner structure when choosing among root moves.

This is not part of the static evaluator. It is a root-level ordering / search bias.

Python should keep this separated from board evaluation.

## Candidate Generation Details

The normal search candidate generator in `AIx.cpp` has these steps.

### Step 1: Covered Region

Mark empty points within 3 cells of any existing stone using `coverdir`.

This immediately cuts search width without using tactical knowledge.

### Step 2: Point Metadata

For each covered empty point:

- `vbw = moveValue1bWide(...)`
- `att1 = attack1bWide(point, self)`
- `att2 = attack1bWide(point, opp)`

Derived flags:

- `sglflag`: forcing or near-forcing move exists
- `hsflag`: opponent has strong counter-threat region
- `winpri`: current side has direct winning priority

### Step 3: Special Threat Bonuses

In one branch, the code further detects certain active-three continuation points and adds `10000` to related move values.

Meaning:

- the move generator is already mixing structural and tactical ordering
- the ordering logic is not a pure static sort by point bucket

### Step 4: Final Candidate List

Only positive-value or relevant points survive.

Then:

- if there is a forced winning class, return immediately
- if there is a single forcing move class, collapse to one candidate
- otherwise sort and keep top `wide`

This exact logic should be reproduced in Python. Apart from the agreed scope reduction to `15x15` freestyle Gomoku, the engine design should not intentionally weaken or simplify these candidate-selection branches.

## Transposition Table

`Hash.cpp` defines:

- Zobrist table `zobrist[2][N*N+1]`
- 2-slot bucket table `hash_table[1<<23][2]`

Stored fields:

- `key`
- `value`
- `hashf`
- `depth`
- `priority`
- `best`

Probe behavior:

- exact hit can return immediately
- alpha entries can either return or shrink the window
- beta entries cut when they exceed `beta`
- TT best move is returned from lookup and then used as a move-ordering bias in
  `alphabeta`, not as a separate full ordering pass

Python phase-1 implementation should preserve semantics, not exact memory layout.

Recommended first version:

- keyed by Python int Zobrist
- entry fields mirror C struct
- explicit replacement policy

Recommended interface:

```python
class TTEntry(NamedTuple):
    key: int
    value: int
    flag: int
    depth: int
    priority: int
    best_move: int
```

Future native acceleration target:

- TT backend can be replaced without changing search API

## Tactical Search: VCF

### What The Reference Code Does

`VCFd_hash(begin, c, depth)` in `VCF.cpp` performs a threat-only search.

Important behavior:

- respects `computevcf` switch
- stops on engine stop flag
- uses a reduced tactical depth cap
- uses its own hash-like memoization via `unordered_map<wstring, int>`
- tracks move sequence in `CurrentLine`
- canonicalizes the sequence by `Reorder(...)`

### Tactical Candidate Classes

The code searches in this order:

1. current side has a direct `B4p(c)` forcing continuation
2. opponent has `B4p(-c)` and may need immediate answer
3. empty points near existing threat stones that create `A4`
4. empty points near existing threat stones that create `B4p`
5. recursive continuation with only tactical responses

This is exactly the tactical-only branching policy the Python project wants.

### Why It Matters

The key design lesson is not the exact `wstring` cache key. It is:

- tactical search has its own state model
- tactical search has its own candidate generator
- tactical search uses only threat continuation and defense moves
- tactical search can be called both before root search and inside normal search

### Python Design Recommendation

Create a separate package:

- `pyslow/threats/`

Suggested modules:

- `threat_types.py`
- `vcf.py`
- `vct.py`
- `threat_board.py` or reuse board with a threat API

Suggested interface:

```python
class ThreatSearcher:
    def find_vcf(self, board: Board, side: int, depth: int) -> int | None:
        ...
```

Return:

- move index if found
- `None` if not found

Do not let normal `movegen.py` handle this.

## Gomocup Protocol Layer

`Common/main.cpp` is thin. Its responsibilities:

- parse commands
- maintain move history
- rebuild board from move list
- call search
- print move

The protocol layer is not the core engine.

For Python phase 1:

- keep protocol code thin
- search and board logic must live outside protocol

Supported commands worth implementing:

- `START`
- `TURN`
- `BEGIN`
- `BOARD`
- `INFO`
- `TAKEBACK`
- `RESTART`
- `ABOUT`
- `END`

## Architecture Recommendation For `pyslow`

Recommended module layout:

```text
pyslow/
  __init__.py
  config.py
  constants.py
  types.py
  board.py
  zobrist.py
  patterns/
    __init__.py
    line.py
    shapes.py
    buckets.py
  eval/
    __init__.py
    caches.py
    local.py
    global_eval.py
  search/
    __init__.py
    movegen.py
    ordering.py
    tt.py
    alphabeta.py
    root.py
  threats/
    __init__.py
    vcf.py
    vct.py
  protocol/
    __init__.py
    gomocup.py
  tests/
```

Key separation principles:

- `board.py`: authoritative state and undo
- `patterns/`: shape recognition only
- `eval/`: local caches and board evaluation
- `search/`: normal move generation, TT, alpha-beta
- `threats/`: tactical-only generation and search
- `protocol/`: I/O only

## Native Acceleration Boundaries

Likely hotspots:

- directional pattern scan
- local cache recomputation
- candidate generation
- TT probing
- VCF recursion

Therefore the Python API should make these replaceable later:

- `patterns.line`
- `eval.caches`
- `search.movegen`
- `search.tt`
- `threats.vcf`

Do not optimize immediately. Just keep clean boundaries.

## Testing Plan Needed By This Design

Before strong search, tests should cover:

- board legality
- make/unmake stability
- Zobrist stability
- direct five detection
- local shape bucket correctness
- local cache incremental update equals full recompute
- move ordering sanity on known tactical positions
- VCF solver on curated positions
- alpha-beta regression on small test positions

Important testing strategy:

- use curated fixed positions
- keep engine deterministic
- compare cached incremental recompute with slower reference recompute

## Recommended Implementation Order

### Phase 0: Reference Extraction

Produce explicit Python-side artifacts before engine code:

- parameter mapping table
- shape label table
- bucket mapping table
- search flow notes
- VCF threat type notes

### Phase 1: Board Core

- `Board`
- move stack
- undo
- win detection
- Zobrist
- tests

### Phase 2: Pattern And Cache Core

- line extraction
- shape encoding
- bucket mapping
- `shape_cache`
- `value_cache`
- `attack_cache`
- tests

### Phase 3: Evaluation

- exact score tables from `SlowRenju`
- local move value helpers
- global board evaluator
- incremental/full recompute equivalence tests

### Phase 4: Normal Search

- covered-point movegen
- ordering values
- TT
- iterative deepening alpha-beta

### Phase 5: Tactical Search

- VCF module
- hook into root search
- hook into normal search

### Phase 6: Protocol

- Gomocup-compatible CLI engine

### Phase 7: Benchmark And Native Decisions

- profile first
- move only real hotspots to native code

## Immediate Next Deliverables

Before implementing `pyslow`, the next useful documents to create are:

1. `docs/parameter-mapping.md`
2. `docs/pattern-bucket-mapping.md`
3. `docs/search-flow.md`
4. `docs/vcf-design.md`

These should be derived from this document and serve as build specs for the Python code.

## Final Judgment

The core lesson from `SlowRenju` is not "port this C code line by line".

The real lesson is:

- preserve the parameterized bucket-based evaluator
- preserve the incremental local cache model
- preserve the search ordering logic driven by attack metadata
- preserve tactical search as a separate move generator and solver

If those four parts are kept, `pyslow` has a realistic path to inherit useful chess strength from the reference engine. If they are replaced by a generic Python Gomoku engine structure, the project will lose the main value of using `SlowRenju` as a reference.
