# Pattern And Bucket Mapping For `pyslow`

## Purpose

This document specifies the pattern labels, directional shape flow, bucket compression, and cache semantics that should be preserved from `SlowRenju` when implementing `pyslow`.

Primary references:

- [`SlowRenju/Headers/game.h`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Headers/game.h#L124)
- [`SlowRenju/Shape/line.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Shape/line.cpp)
- [`SlowRenju/Value/ValueWide.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Value/ValueWide.cpp#L296)

## Shape Label Set

The reference engine defines these labels:

- `L0 = 0`
- `L1S = 1`
- `L1 = 2`
- `L2S = 3`
- `L2BB = 4`
- `L2B = 5`
- `L2 = 6`
- `L3S = 7`
- `L3B = 8`
- `L3 = 9`
- `L4S = 10`
- `L4 = 11`
- `L5 = 12`
- `L6 = 13`

Recommended Python representation:

```python
class ShapeLabel(IntEnum):
    L0 = 0
    L1S = 1
    L1 = 2
    L2S = 3
    L2BB = 4
    L2B = 5
    L2 = 6
    L3S = 7
    L3B = 8
    L3 = 9
    L4S = 10
    L4 = 11
    L5 = 12
    L6 = 13
```

For phase 1 we do not need to rename these into human-friendly names. Keeping the original label set reduces drift from the reference implementation.

## What A Directional Shape Represents

For an empty point `(x, y)`, the engine evaluates each of four directions:

- horizontal
- vertical
- diagonal `\`
- diagonal `/`

For each direction, it asks:

- if black plays here, what is the resulting directional shape?
- if white plays here, what is the resulting directional shape?

This is why caches are indexed as:

- `shapeM[2][x][y][4]`

where:

- first dimension `0` means black move at this empty point
- first dimension `1` means white move at this empty point

## `ComputeShape1b()` Contract

Reference function:

- [`ValueWide.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Value/ValueWide.cpp#L296)

Flow:

1. temporarily place black at `(x, y)`
2. extract the corresponding line for direction `d`
3. compute directional shape
4. store to `shapeM[0][x][y][d]`
5. replace the same point with white
6. recompute directional shape
7. store to `shapeM[1][x][y][d]`
8. restore empty

This means `shapeM` is a hypothetical-move cache, not a cache of already occupied board cells.

## Packed Shape Encoding

`line::shape()` returns a packed integer, not just a simple enum.

Observed usage:

- the category is extracted by `(shape >> 16) & 15`
- for `L4S`, low bits are used as multiplicity information

Required Python design:

- expose a readable internal representation if helpful
- but preserve a stable packed representation for compatibility with bucket construction

Recommended representation:

```python
@dataclass(frozen=True)
class PackedShape:
    raw: int

    @property
    def label(self) -> int:
        return (self.raw >> 16) & 0xF

    @property
    def aux(self) -> int:
        return self.raw & 0xF
```

## Directional Semantics Used By Bucket Construction

In `ComputeValue1b()`, each directional shape contributes to:

- `lines[i]`: normalized line strength for this direction
- `A3l`: count of active three-like threats
- `B4l`: count of broken/branching four-like threats
- `A5l`: count of fives
- `A6l`: count of overlines
- `at`: attack priority level

Relevant logic in:

- [`ValueWide.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Value/ValueWide.cpp#L357)

Meaning by label in this context:

- `L3`, `L3B`:
  - count as strong attack-three forms
  - set attack level to at least `3`
- `L4S`:
  - contributes `aux` value to `B4l`
  - sets attack level to at least `4`
  - if `aux >= 2`, line strength is forced to `8`
- `L4`:
  - contributes one direct four
  - sets attack level to at least `5`
- `L5`:
  - winning line
  - sets attack level to `6`
- `L6`:
  - overline
  - tracked separately

Everything else contributes mainly through the normalized `lines[]` array.

## Normalized Line Strength

The code uses:

```cpp
lines[i] = temp % L6;
```

Since `L6 = 13`, this effectively means:

- all ordinary labels stay as-is
- overline handling is special-cased before bucket aggregation

Special normalization rule:

- if a directional `L4S` has branch count `>= 2`, that line is forced to strength `8`

This rule must be preserved because it affects bucket identity and attack priority.

## Two-Best-Lines Compression

The reference engine does not use all 4 directional values directly as a 4D key.

Instead it:

1. sorts the first pair and second pair internally
2. selects the two strongest effective line strengths among all four directions
3. maps those two strengths into a bucket id via `doubleShape`

Relevant code:

- [`ValueWide.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Value/ValueWide.cpp#L382)

This is the critical compression rule behind `valueM`.

## `doubleShape` Table

Reference table:

- [`ValueWide.cpp`](/home/jerry/python-test/gomoku/slow_temp/SlowRenju/Value/ValueWide.cpp#L327)

The table is triangular and yields bucket ids `1..91`.

This is why `DSHAPESIZE = 92`:

- bucket `0` exists as a sentinel or invalid value
- real buckets cover `1..91`

Python must copy this table exactly.

Recommended representation:

```python
DOUBLE_SHAPE: tuple[tuple[int, ...], ...] = (
    (1,),
    (2, 3),
    ...
    (79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91),
)
```

## Bucket Construction Algorithm

For each empty point and each player view:

1. inspect four directional packed shapes
2. derive:
   - line strengths
   - `A3l`
   - `B4l`
   - `A5l`
   - `A6l`
   - attack level `at`
3. pick the two strongest normalized lines
4. assign:
   - `valueM[player][x][y] = doubleShape[top1][top2]`
   - `attackM[player][x][y] = at`

In Python this should probably live in a helper:

```python
def compute_bucket_and_attack(direction_shapes: Sequence[PackedShape]) -> tuple[int, int]:
    ...
```

## Cache Layout To Preserve

Reference caches:

- `shapeM[2][N][N][4]`
- `valueM[2][N][N]`
- `attackM[2][N][N]`
- `boardM[N][N]`

Recommended Python mapping:

```python
@dataclass
class EvalCaches:
    board_shadow: list[list[int]]
    shape_cache: list[list[list[list[int]]]]
    value_cache: list[list[list[int]]]
    attack_cache: list[list[list[int]]]
```

Storage format may differ from the C implementation, but semantics and update boundaries must match the reference behavior from the start.

## Incremental Recompute Contract

`ValueWideCompute()` does not fully recompute every point. It:

1. compares current board with `boardM`
2. marks nearby points and affected directions
3. recomputes only impacted directional shapes
4. recomputes merged bucket and attack values for impacted empty points

This is a core design feature, not an optimization detail.

Python should implement both:

- full recompute helper for correctness checks
- incremental recompute path for normal runtime

And then add tests:

- incremental result equals full recompute result

## Freestyle-Only Scope Boundary

The reference `ComputeValue1b()` has Renju foul logic behind `fflag`.

For phase 1 freestyle Gomoku:

- `fflag == 0`
- foul-specific branches are out of scope only because Renju itself is out of scope

That means these branches are intentionally unsupported due to the agreed rule scope:

- double-three foul suppression
- overline foul suppression
- foul-based `valueM` invalidation

But the surrounding structure should remain compatible so later extension is not blocked.

## Attack Level Semantics

Observed attack levels in the reference logic:

- `0`: no relevant threat
- `3`: active three level
- `4`: `L4S`-class forcing threat
- `5`: direct four
- `6`: immediate winning five

These attack levels are consumed by the searcher, not only by the evaluator.

Used in:

- candidate prioritization
- forced-move collapse
- attack bonus application via `ATDOWN3` and `ATDOWN4`

Therefore Python should treat attack level as a first-class output of evaluation caches.

## Required Python APIs

To match the reference engine cleanly, `pyslow` should expose at least:

```python
def compute_direction_shape(board: Board, x: int, y: int, direction: int, stone: int) -> int:
    ...


def compute_bucket_and_attack(shape4: Sequence[int]) -> tuple[int, int]:
    ...


def recompute_point_caches(board: Board, caches: EvalCaches, x: int, y: int) -> None:
    ...


def move_value(caches: EvalCaches, x: int, y: int, side: int, config: EngineConfig) -> int:
    ...
```

## Tests Required By This Spec

Before using these structures in search, tests should verify:

1. directional shape extraction is stable under make/unmake
2. packed shape label extraction is correct
3. `doubleShape` produces exactly bucket ids `1..91`
4. bucket/attack values for curated positions are stable
5. incremental cache recompute matches full recompute
6. `move_value` uses `attack_value[self_bucket] + defend_value[opp_bucket]`

## Immediate Implementation Consequences

This document implies the following coding order:

1. copy `doubleShape` exactly
2. define `ShapeLabel`
3. implement directional line extraction
4. implement `line::shape()` equivalent
5. implement bucket-and-attack merge
6. implement caches
7. implement incremental update

Without this layer, neither the reference evaluation numbers nor the reference search ordering can be reproduced faithfully.
