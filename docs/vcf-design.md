# VCF Design For `pyslow`

## Purpose

This document specifies how `pyslow` should model VCF search based on the reference `SlowRenju` implementation.

Project rule already agreed:

- tactical search must be separate from normal search
- tactical search only generates threat points and defense points
- tactical search does not use the ordinary neighborhood candidate rules

Primary reference:

- [`SlowRenju/VCF/VCF.cpp`](../SlowRenju/VCF/VCF.cpp)
- [`SlowRenju/Shape/line4v.cpp`](../SlowRenju/Shape/line4v.cpp)

## What VCF Means Here

The reference code uses `VCFd_hash(...)` as a tactical solver for forcing sequences built around four-threat continuations.

The important engineering lesson is not just "search deeper on threats". It is:

- use a different move generator
- use different state transitions
- use a different cache
- return quickly when a forcing line is found

## Phase-1 Goal

For `pyslow` phase 1, the tactical module should support:

- VCF detection from the current root position
- VCF checks from inside normal search when needed
- threat-only candidate generation
- direct extension path toward VCT and compatible integration points

The project target in this repository still includes tactical enhancement up to VCF/VCT, so the module design should not assume that VCT is a non-goal.

## Reference Entry Function

Reference:

- [`VCF.cpp`](../SlowRenju/VCF/VCF.cpp#L55)

Signature:

```cpp
int VCFd_hash(int begin, int c, int depth)
```

Return semantics:

- `< S*S`: found winning move index
- `== S*S`: no winning move at this depth, but search tree was fully explored
- `== S*S + 1`: not found or search stopped / inconclusive

Python should use clearer return types.

Recommended API:

```python
class ThreatSearchResult(NamedTuple):
    move: int | None
    solved: bool
```

Semantics:

- `move is not None`: winning tactical move found
- `move is None and solved is True`: fully searched, no VCF
- `move is None and solved is False`: interrupted or depth-limited inconclusive

## Tactical Search State

The reference VCF module uses:

- `line4v line_4`
- `CurrentLine`
- `finishflag`
- `hm` memo table

This is independent from normal search candidate state.

Python should encapsulate this in a dedicated class:

```python
class VCFSearcher:
    def __init__(self, config: EngineConfig):
        ...
```

Recommended internal state:

- tactical board view or access to board helpers
- memo table
- current sequence stack
- stop flag / search context

## Tactical Board View

The reference code relies heavily on `line4v`, which stores:

- rows
- columns
- both diagonal families

This allows fast tactical checks like:

- `A4`
- `A5`
- `B4p`
- foul checks in Renju mode

For freestyle Gomoku phase 1:

- foul checks are out of scope only because Renju is out of scope
- a dedicated tactical line-view helper is still required

Suggested Python helper:

```python
class ThreatBoardView:
    def has_a4(self, x: int, y: int) -> bool: ...
    def has_a5(self, x: int, y: int) -> bool: ...
    def broken_four_point(self, side: int) -> int | None: ...
    def broken_four_response(self, x: int, y: int) -> int | None: ...
```

## Search Depth Policy

Reference:

- [`VCF.cpp`](../SlowRenju/VCF/VCF.cpp#L70)

It caps tactical depth using `VCFM`.

Meaning:

- requested depth is not always used literally
- the tactical solver applies its own depth policy

Python should preserve the existence of tactical-module-owned depth policy. The public API may pass an explicit request depth, but the tactical solver should remain free to apply its own cap policy just like the reference engine.

## Memoization Strategy

Reference memoization:

- `unordered_map<wstring, int> hm`
- key derived from `CurrentLine`
- key canonicalized by `Reorder(...)`

Interpretation:

- memo is not based on full board hash
- it is based on canonicalized threat sequence state

This exact string encoding is not required in Python.

What matters:

- tactical memo table should treat equivalent continuation states as identical
- it should avoid revisiting the same forcing pattern orderings

Recommended Python direction:

- use a tactical memo key that can represent both board state and forcing-sequence equivalence
- do not assume that a plain board-hash-only cache is sufficient for parity

## Tactical Candidate Ordering In Reference

The reference tactical solver checks in this order.

### 1. Immediate forcing continuation for current side

Reference:

- [`VCF.cpp`](../SlowRenju/VCF/VCF.cpp#L131)

If `B4p(c)` exists, return it immediately.

Meaning:

- if the attacker already has a direct forcing continuation, take it

### 2. Opponent direct forcing point

Reference:

- [`VCF.cpp`](../SlowRenju/VCF/VCF.cpp#L137)

If opponent has a single broken-four response point, attacker may play there and try to turn it into `A4` or a recursive forcing branch.

### 3. Generate nearby tactical points that create `A4`

Reference:

- [`VCF.cpp`](../SlowRenju/VCF/VCF.cpp#L225)

For empty cells near existing attacker stones:

- if move creates `A4`, return it

### 4. Generate nearby tactical points that create `B4p`

Reference:

- [`VCF.cpp`](../SlowRenju/VCF/VCF.cpp#L277)

These are not all normal neighborhood moves. They are tactical continuations only.

### 5. Recurse only through forcing continuation and defense

The solver appends:

- attacker move
- forced defense move

Then recurses.

That is the key tactical branching model to preserve.

## Tactical Candidate Domain

The reference uses a small fixed offset set `vec`:

- only positions within threat-relevant offsets from current stones are considered

Reference:

- [`VCF.cpp`](../SlowRenju/VCF/VCF.cpp#L34)

This is much narrower than normal search coverage.

Python requirement:

- implement a dedicated threat-neighbor generator
- do not reuse the normal move generator's 3-step covered cells

## Tactical Branch Model

The tactical recursion alternates:

1. attacker plays forcing threat
2. defender plays the forced defensive point
3. recurse

This should be made explicit in Python.

Recommended recursive helper:

```python
def _search_attacker(self, board: Board, side: int, depth: int) -> ThreatSearchResult:
    ...
```

Since defenses are forced, the defender branch often does not need a general move list.

## Tactical Sequence Representation

Reference:

- `CurrentLine` stores alternating attacker and defender moves

Python suggestion:

- maintain an explicit list of move indices for debug, validation, and tactical memo support

```python
sequence: list[int]
```

This is useful for:

- debugging
- test output
- canonicalization support

## Interaction With Normal Search

Reference integration points:

- root search checks VCF before normal search
- normal search can also query VCF in some branches

Python integration policy:

- at root, always try VCF first
- inside normal alpha-beta, call VCF only in selected tactical windows
- keep the threat module fully separate from normal move generation

Suggested interface:

```python
class ThreatSearcher:
    def find_vcf(self, board: Board, side: int, depth: int, ctx: SearchContext | None = None) -> ThreatSearchResult:
        ...
```

## Freestyle Simplifications

The reference code contains foul checks because it also supports Renju.

For phase 1 freestyle Gomoku:

- ignore `foulr(...)`
- ignore Renju-only invalid move handling

But keep the module boundaries ready for later extension.

## Required Tactical Predicates

To implement VCF cleanly, Python needs these primitives:

- `is_five_after_move(side, move)`
- `is_open_or_forcing_four_after_move(side, move)`
- `broken_four_point_for_side(side)`
- `forced_defense_after_move(side, move)`
- tactical-neighbor iterator around attacker stones

These helpers should live in `threats/` or in a threat-focused adapter over `patterns/`.

## Proposed Python Module Layout

```text
pyslow/threats/
  __init__.py
  threat_board.py
  vcf.py
  vct.py
  types.py
```

Responsibilities:

- `threat_board.py`: fast tactical line access and predicates
- `vcf.py`: VCF solver
- `vct.py`: later extension
- `types.py`: results, threat node metadata

## Recommended Python API

```python
class VCFSearcher:
    def find(self, board: Board, side: int, max_depth: int) -> ThreatSearchResult:
        ...
```

Additional optional debug API:

```python
class ThreatSearchResult(NamedTuple):
    move: int | None
    solved: bool
    sequence: tuple[int, ...] = ()
```

## Fidelity Requirement

Except for board size and supported rule set, the tactical subsystem should aim for parity with the reference design rather than intentional simplification.

That means the Python implementation should preserve:

- separate tactical move generator
- forced attacker/defender branching model
- root-level VCF query before normal search
- internal tactical checks from normal search where required
- tactical candidates restricted to threats and defenses
- tactical-module-owned depth policy
- memoization that respects forcing-sequence structure
- direct extension path to VCT

## Required Tests

Before trusting the VCF module, add tests for:

1. immediate broken-four continuation is found
2. immediate defensive forcing point is found
3. unrelated neighborhood moves are not generated
4. recursive forcing line with one defense is found
5. solver returns inconclusive when depth is insufficient
6. solver remains deterministic on repeated runs

## Build Order Suggested By This Spec

1. threat predicates over current board
2. tactical neighbor generator
3. immediate `B4p` and `A4` detection
4. recursive attacker/defender VCF search
5. memo table
6. root integration
7. internal integration into normal search

## Final Design Rule

For `pyslow`, VCF is not a special search mode inside the normal move generator.

It is a separate tactical solver that happens to be consulted by the normal engine.
