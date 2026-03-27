# Parameter Mapping For `pyslow`

## Purpose

This document defines how `SlowRenju`'s `para[]` should be mapped into Python configuration objects for `pyslow`.

Project constraint:

- `pyslow` phase 1 only targets `15x15` freestyle Gomoku
- We still preserve the reference engine's parameter grouping and default values
- We do not preserve the C-style raw array API

Reference definitions:

- [`SlowRenju/Headers/game.h`](../SlowRenju/Headers/game.h#L99)
- [`SlowRenju/Common/global_value.cpp`](../SlowRenju/Common/global_value.cpp#L45)

## Source Layout

In `game.h`, `DSHAPESIZE = 92`, and the `para[]` layout is:

1. `LASTEVAL = para[0:92]`
2. `NEXTEVAL = para[92:184]`
3. `ATTACKVALUE = para[184:276]`
4. `DEFENDVALUE = para[276:368]`
5. scalar tail:
   - `DRIFT = para[368]`
   - `DGN = para[369]`
   - `ATDOWN3 = para[370]`
   - `ATDOWN4 = para[371]`
   - `LASTWEIGHT = para[372]`
   - `READCONFIG = para[373]`
   - `EXTENDRATIO = para[374]`

Total parameter count: `375`

## Python Config Target

Recommended Python representation:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalBucketTables:
    last_eval: tuple[float, ...]
    next_eval: tuple[float, ...]
    attack_value: tuple[int, ...]
    defend_value: tuple[int, ...]


@dataclass(frozen=True)
class SearchParameters:
    drift: float
    dgn: float
    atdown3: float
    atdown4: float
    last_weight: float
    read_config_each_move: bool
    extend_ratio: float


@dataclass(frozen=True)
class EngineConfig:
    eval_tables: EvalBucketTables
    search: SearchParameters
```

Important:

- phase 1 defaults should be loaded from a hardcoded Python constant copied from `SlowRenju`
- later, this can be overridden by file or CLI

## Semantic Meaning By Group

### `LASTEVAL`

Used in:

- [`ValueWide.cpp`](../SlowRenju/Value/ValueWide.cpp#L283)
- [`ValueW.cpp`](../SlowRenju/Value/ValueW.cpp#L120)

Meaning:

- offensive static contribution of an empty point for the side to move
- consumed by `evalValue1bWide1()`
- later aggregated into the board evaluator's `affensive` term

Python field:

- `EvalBucketTables.last_eval`

### `NEXTEVAL`

Used in:

- [`ValueWide.cpp`](../SlowRenju/Value/ValueWide.cpp#L277)
- [`ValueW.cpp`](../SlowRenju/Value/ValueW.cpp#L121)

Meaning:

- defensive or opponent-response static contribution of an empty point
- consumed by `evalValue1bWide0()`
- later aggregated into the board evaluator's `defensive` term

Python field:

- `EvalBucketTables.next_eval`

### `ATTACKVALUE`

Used in:

- [`ValueWide.cpp`](../SlowRenju/Value/ValueWide.cpp#L271)
- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L705)

Meaning:

- search ordering value for the side's own bucket at a candidate point

Python field:

- `EvalBucketTables.attack_value`

### `DEFENDVALUE`

Used in:

- [`ValueWide.cpp`](../SlowRenju/Value/ValueWide.cpp#L271)
- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L705)

Meaning:

- search ordering value for the opponent's bucket at a candidate point

Python field:

- `EvalBucketTables.defend_value`

### `DRIFT`

Used in:

- [`ValueW.cpp`](../SlowRenju/Value/ValueW.cpp#L128)
- [`ValueW.cpp`](../SlowRenju/Value/ValueW.cpp#L278)

Meaning:

- constant offset subtracted from the board evaluation
- part of the calibrated global evaluator, not move ordering

Python field:

- `SearchParameters.drift`

### `DGN`

Used in:

- [`ValueW.cpp`](../SlowRenju/Value/ValueW.cpp#L128)
- [`ValueW.cpp`](../SlowRenju/Value/ValueW.cpp#L278)

Meaning:

- multiplier for the `dgn` strategic shape term
- `dgn` penalizes isolated or overly crowded stone structures

Python field:

- `SearchParameters.dgn`

### `ATDOWN3`

Used in:

- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L1121)

Meaning:

- attack-related search bonus/offset applied when a move has attack level 3

Python field:

- `SearchParameters.atdown3`

### `ATDOWN4`

Used in:

- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L1117)

Meaning:

- attack-related search bonus/offset applied when a move has attack level 4

Python field:

- `SearchParameters.atdown4`

### `LASTWEIGHT`

Current observation:

- defined in [`game.h`](../SlowRenju/Headers/game.h#L108)
- not obviously used in the current checked files

Meaning:

- keep it in config for compatibility
- do not delete it even if phase 1 does not use it yet

Python field:

- `SearchParameters.last_weight`

### `READCONFIG`

Used in:

- [`main.cpp`](../SlowRenju/Common/main.cpp#L394)

Meaning:

- whether to reload config before each move
- after loading `srconfig.txt`, the reference code also adds `65536` to
  `para[156]` and `para[157]`

For `pyslow`:

- keep this as a compatibility option
- if file-based reload support is implemented, preserve the post-load
  adjustment to bucket entries `156` and `157`

Python field:

- `SearchParameters.read_config_each_move`

### `EXTENDRATIO`

Used in:

- [`AIx.cpp`](../SlowRenju/AI/AIx.cpp#L1106)

Meaning:

- controls effective depth reduction as candidate count changes

Python field:

- `SearchParameters.extend_ratio`

## Default Values

The default values must come directly from:

- [`SlowRenju/Common/global_value.cpp`](../SlowRenju/Common/global_value.cpp#L45)

Implementation rule:

- copy these values exactly into a Python constant module
- do not retype by hand in multiple places
- expose a single source of truth, for example `pyslow/config.py`

Recommended layout:

```python
SLOWREnju_PARA: tuple[float, ...] = (...)
```

Then parse once:

```python
def load_default_config() -> EngineConfig:
    para = SLOWRENJU_PARA
    return EngineConfig(
        eval_tables=EvalBucketTables(
            last_eval=tuple(para[0:92]),
            next_eval=tuple(para[92:184]),
            attack_value=tuple(int(v) for v in para[184:276]),
            defend_value=tuple(int(v) for v in para[276:368]),
        ),
        search=SearchParameters(
            drift=para[368],
            dgn=para[369],
            atdown3=para[370],
            atdown4=para[371],
            last_weight=para[372],
            read_config_each_move=bool(para[373]),
            extend_ratio=para[374],
        ),
    )
```

## Bucket Table Contract

These four 92-entry tables are indexed by `valueM[player][x][y]`.

That implies:

- bucket ids are part of the engine ABI between patterns and scoring
- changing bucket numbering later would invalidate both evaluation and move ordering

For `pyslow`, bucket ids must initially match the reference implementation exactly.

## Numeric Type Policy

Recommended Python typing:

- `last_eval`: `float`
- `next_eval`: `float`
- `attack_value`: `int`
- `defend_value`: `int`
- scalar tail:
  - `drift`: `float`
  - `dgn`: `float`
  - `atdown3`: `float`
  - `atdown4`: `float`
  - `last_weight`: `float`
  - `read_config_each_move`: `bool`
  - `extend_ratio`: `float`

Even though some reference values are written as floating point and later used like integers, Python should preserve values faithfully and convert at call sites only if needed.

## Phase-1 Policy Decisions

For `pyslow` phase 1:

- keep all reference defaults
- ignore Renju-only foul semantics in evaluation logic unless a shared helper makes it unavoidable
- do not prune config fields simply because freestyle does not use every branch today

Rationale:

- preserving config structure now reduces drift from the reference engine
- it also makes later tuning and A/B comparison much easier

## Follow-Up Implementation Tasks

After this mapping document, the code work should be:

1. create `pyslow/config.py`
2. add a single raw tuple containing the 375 default values
3. add a parser converting that tuple into dataclasses
4. add tests verifying:
   - length is exactly `375`
   - slices are exactly `92/92/92/92/7`
   - parsed values match expected boundary indices

## Non-Goals

This document does not yet define:

- file format for external config override
- CLI override syntax
- tuning workflow

Those are separate topics from the mapping work here. The immediate goal is a faithful, explicit Python mapping of the reference engine's parameter system.
