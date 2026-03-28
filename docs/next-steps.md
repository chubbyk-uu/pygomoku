# Next Steps

## Current State

`pyslow` is no longer a skeleton. The current codebase now has:

- working `15x15` freestyle board, undo, winner detection, zobrist
- parameter mapping aligned to `SlowRenju`
- `ValueWide`-style local caches and global eval
- normal move generation, TT, iterative deepening alpha-beta, root control
- working `VCF` and `ThreatBoardView`
- working Gomocup protocol adapter
- working pygame GUI with local and Gomocup engine modes
- benchmark/profile helpers
- opponent benchmark scripts for `zhou`, `pyslow`, and `SlowRenju`
- Linux-buildable `SlowRenju/slowrenju_linux`

Current verified baseline:

- [`alignment_compare.py`](../benchmarks/alignment_compare.py)
  - `70/70` aligned at `depth=3`, `width=10`
- `pytest -q`
  - `155 passed`
- interactive defaults
  - `depth=5`, `width=15`
- representative fixed search timing
  - `PYTHONPATH=. python benchmarks/profile_search.py --depth 5 --width 15 --top 10`
  - about `0.51s`
- representative short selfplay timing
  - `PYTHONPATH=. python benchmarks/selfplay_smoke.py --depth 5 --width 15 --plies 4`
  - about `1463 ms/ply`

Recent stable wins already landed:

- optional native backends for `line`, `movegen`, `ordering`, `threat_board`
- local-eval native kernel in the stable baseline
- `shape_cache` snapshot/restore changed from whole-cache deep copy to undo-log
- `VCF` attacker duplicate-scan removal
- native `broken_four_reply` / `broken_four_point_for_side` helpers in `threat_board`

Recent conclusions already validated:

- semantic alignment is closed enough for current freestyle `15x15` scope
- `pyslow` and `SlowRenju` remain aligned on the current `70/70` compare set
- the current project phase has moved from branch-level alignment to:
  - performance analysis
  - protocol correctness
  - practical search reach

## External Play Status

Current opponent benchmark results:

- `pyslow` via Gomocup, protocol-correct persistent session
  - 5-openings vs `zhou`, `depth=5 width=15`
    - black: `5-0`
    - white: `2-3`
- `pyslow` via Gomocup, reduced search
  - 5-openings vs `zhou`, `depth=3 width=15`
    - black: `5-0`
    - white: `4-1`
  - 9-openings vs `zhou`, `depth=3 width=15`
    - black: `8-1`
    - white: `8-1`
- `SlowRenju` via Gomocup, default time settings
  - 5-openings vs `zhou`
    - black: `5-0`
    - white: `5-0`
  - 9-openings vs `zhou`
    - black: `9-0`
    - white: `9-0`

Important protocol conclusion:

- fresh-per-move Gomocup replay is not equivalent to a real match
- restarting the engine before every move changes searcher lifecycle and TT reuse
- opponent and GUI validation must use persistent engine sessions across a whole game
- treat the persistent-session `depth=5 width=15` external-play result as the
  protocol-correct baseline for current `pyslow` strength
- do not compare later opponent results against the discarded fresh-per-move
  runner, even if that runner happened to score better in a small sample

## Work Order

### 1. Current Priority: Performance Analysis And Acceleration

Primary source of truth:

- [acceleration-plan.md](./acceleration-plan.md)

Current phase goal:

- this is now a deliberate large-acceleration phase
- the objective is substantial search-throughput gain, not just incremental local speedups
- semantics must stay equivalent to the current validated `pyslow` baseline
- hot subsystems should be moved from Python into Cython/C together with their data paths, not as thin wrapper ports
- the practical target is to push usable search reach toward at least `depth=8 width=20`

Rules:

- do not change semantics
- always keep Python fallback
- every speedup must have both:
  - semantic regression evidence
  - benchmark evidence

Execution order:

1. keep the current stable baseline frozen
2. continue cost-model-driven work on `eval/local`, `movegen`, `ordering`
3. revisit `global_eval` only with a clearly profitable kernel boundary
4. revisit remaining cache work only when measurements justify it
5. revisit `VCF` after eval/cache costs come down further
6. increase practical root depth / width only after post-optimization measurements

Immediate deliverables:

1. measure the next remaining `local / movegen / global_eval` hot path before changing code
2. keep semantic regressions frozen while optimizing
3. prefer small profitable kernels over broad speculative refactors
4. benchmark both fixed search and short selfplay after each speedup
5. use persistent-session opponent matches as practical validation after larger search-reach gains

Likely hotspots:

- `eval/local`
- `search/movegen`
- `eval/global_eval`
- `eval/caches`
- `threats/vcf`

Current recommendation:

- keep Python as the semantic reference path
- keep native optional and narrow
- allow larger subsystem refactors when they are measurement-driven and preserve equivalent semantics
- do not repeat:
  - wrapper-style native experiments around Python object graphs
  - `flat + nested` dual-write cache experiments
  - fresh-per-move Gomocup replay as a proxy for engine strength

### 2. Search Reach Upgrade

The next practical target is no longer “a bit faster”.

Current goal:

1. keep `depth=5 width=15` comfortably practical
2. move the stable Python engine toward at least `depth=8 width=20`
3. compare practical opponent results only under persistent Gomocup sessions

Immediate likely knobs:

- root iterative depth
- root width
- child width ratio
- VCF depth caps

### 3. Add VCT

Only after:

- checklist alignment is sufficiently stable
- VCF semantics are trusted
- current hotspots are understood

### 4. Continue Product-Level Work

After the above:

- improve GUI usability
- extend opponent benchmark suites
- plan the next native boundaries more concretely

## Resume Advice

When resuming work later, do not start by re-analyzing the whole project.

Start here:

1. run [alignment_compare.py](../benchmarks/alignment_compare.py) and confirm `70/70`
2. run `pytest -q` and confirm the current regression baseline
3. read [acceleration-plan.md](./acceleration-plan.md)
4. profile the aligned baseline before changing default search limits
5. read [performance-roadmap.md](./performance-roadmap.md) for the native priority order
6. implement or measure only one hotspot family at a time
7. after each speedup, re-run alignment, regression, fixed search timing, and short selfplay
