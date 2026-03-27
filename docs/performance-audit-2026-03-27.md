**Performance Audit**

Date: `2026-03-27`

Current semantic baseline:
- `python benchmarks/alignment_compare.py` -> `70/70`
- `pytest -q tests/test_eval.py tests/test_search.py tests/test_vcf.py tests/test_movegen.py` -> `88 passed`

Current stable native wins already landed:
- `line` backend
- `local` point-shape helpers
- `movegen` backend
- `ordering` backend

Current measured timings:
- `hotspot_report.py`
  - `depth=2 width=8` -> `42.14 ms/ply`
  - `depth=3 width=10` -> `139.49 ms/ply`
  - `depth=6 width=10` -> `3249.88 ms/ply`

Representative search profiles:
- `depth=5 width=15`
  - total about `1.85s`
  - top hotspots:
    - `eval/local.py::value_wide_compute`
    - `eval/global_eval.py::evaluate_board`
    - `threats/vcf.py::*`
    - `eval/caches.py::{snapshot,restore,_copy_shape_cache_any}`
    - `search/movegen.py::generate_candidates`
- `depth=6 width=20`
  - total about `3.34s`
  - top hotspots:
    - `value_wide_compute`
    - `evaluate_board`
    - `compute_bucket_and_attack`
    - `cache snapshot/restore`
    - `generate_candidates`
- `depth=8 width=20`
  - total about `2.08s` on the benchmark position
  - same hotspot ordering; local eval and cache copy still dominate

Gap to target:
- User target direction: around `depth=10 width=30`, average move time near `5s`
- Current codebase is materially faster than the earlier Python baseline, but still far from that target under broad workloads
- The remaining gap will not be closed by micro-optimizations alone

What recent experiments proved:
- Small local Python tweaks now have low and unstable ROI
- `movegen` and `ordering` were good native candidates because their inputs/outputs are flat and their control flow is simple
- Several attempted optimizations were reverted because they did not show stable net wins:
  - `value_wide_compute` full-function Cython wrapper
  - `ThreatBoardView` lightweight play/undo
  - cache owned-restore shortcut
  - several partial `VCF` flow tweaks

Main conclusion:
- The remaining performance wall is now mostly structural
- The biggest stable bottleneck is still `value_wide_compute`, but it is not amenable to shallow wrapper-style Cythonization
- To move materially closer to the target, the project needs bigger steps:
  - data-layout-aware native work for local eval
  - tighter cache strategy
  - possibly a dedicated native tactical/threat backend

Priority tiers:

Tier 1:
- `eval/local.py::value_wide_compute`
- `eval/local.py::{compute_direction_shape, compute_bucket_and_attack}`
- `eval/caches.py::{snapshot, restore_snapshot, _copy_shape_cache_any}`

Tier 2:
- `eval/global_eval.py::{evaluate_board, _evaluate_last5_branch, _evaluate_next43_branch}`
- `threats/vcf.py`
- `threats/threat_board.py`

Tier 3:
- `search/movegen.py` remaining Python-side candidate assembly
- `search/root.py` / `search/alphabeta.py` only after lower layers stop dominating

Recommended next-stage strategy:

1. Stop doing isolated micro-optimizations in Python unless the profile shows an obvious cheap win.

2. Treat local eval as a subsystem, not a single function.
   The next real acceleration step should not be a thin Cython wrapper around `value_wide_compute`.
   It should redesign the hot path around a flatter native-friendly representation for:
   - board shadow
   - shape cache
   - value cache
   - attack cache

3. Keep Python orchestration, but move hot kernels together.
   The likely profitable grouping is:
   - shape extraction
   - bucket/attack computation
   - incremental cache writes

4. Revisit VCF only after the eval/cache layer is cheaper.
   Right now VCF is hot, but a large part of the total cost is still upstream eval/cache work.

Execution order for the next phase:
- Phase A: design a flatter native cache/eval representation
- Phase B: implement a dedicated native local-eval update path
- Phase C: benchmark again at `depth=6 width=20` and `depth=8 width=20`
- Phase D: only then decide whether the next module is `vcf` or broader cache storage

Decision:
- Do not keep spending cycles on small Python tweaks
- Increase scope and attack the local-eval/cache subsystem more aggressively
