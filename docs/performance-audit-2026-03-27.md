**Performance Audit**

Date: `2026-03-27`

Current semantic baseline:
- `python benchmarks/alignment_compare.py` -> `70/70`
- current broad regression pass -> `155 passed`

Current stable native wins already landed:
- `line` backend
- `local` point-shape helpers and local update kernel
- `movegen` backend
- `ordering` backend
- `threat_board` hot helpers

Current stable Python-side structural win:

- `shape_cache` snapshot/restore now uses undo-log instead of whole-cache deep copy

Current measured timings:
- `PYTHONPATH=. python benchmarks/profile_search.py --depth 5 --width 15 --top 10`
  - current stable search time about `0.51s`
- `python benchmarks/selfplay_smoke.py --depth 5 --width 15 --plies 4`
  - current average about `1463 ms/ply`

Representative search profiles:
- `depth=5 width=15`
  - total about `0.51s`
  - top hotspots:
    - `eval/local.py::value_wide_compute`
    - `search/movegen.py::generate_candidates`
    - `eval/global_eval.py::evaluate_board`
    - remaining `eval/caches.py::{snapshot,restore}`
    - `threats/vcf.py::*`

Gap to target:
- target direction remains significantly stronger than the current practical
  baseline
- current codebase is much faster than the earlier Python-only baseline, but
  still not close enough to stop optimization
- the remaining gap will not be closed by micro-optimizations alone

What recent experiments proved:
- small local Python tweaks now have lower ROI than before
- `movegen` and `ordering` were good native candidates because their
  inputs/outputs are flat and their control flow is simple
- local-eval work only paid off once the kernel boundary was made narrower and
  the cost model was clearer
- the best recent practical win came from `VCF` / `threat_board`:
  - attacker duplicate-scan removal
  - native `broken_four_reply` / `broken_four_point_for_side`
- several attempted optimizations were reverted because they did not show
  stable net wins:
  - thin wrapper `value_wide_compute` Cythonization
  - `flat + nested` cache dual-write experiments
  - cache owned-restore shortcut
  - lightweight `ThreatBoardView` play/undo experiments
  - several partial `VCF` flow tweaks
  - nested-list based `global_eval` Cython helper experiments
  - fresh-per-move Gomocup replay used as a proxy for real game strength

Main conclusion:
- the remaining performance wall is still mostly structural
- the biggest stable bottleneck remains local eval, followed by movegen,
  global eval, remaining cache work, and then the now-smaller `VCF` layer
- the next meaningful gains should come from cost-model-driven native work, not
  broad speculative refactors

Priority tiers:

Tier 1:
- `eval/local.py::value_wide_compute`
- `eval/local.py::{compute_direction_shape, compute_bucket_and_attack}`
- `search/movegen.py::generate_candidates`
- `eval/global_eval.py::{evaluate_board, _evaluate_last5_branch, _evaluate_next43_branch}`
- `eval/caches.py::{snapshot, restore_snapshot}`

Tier 2:
- `threats/vcf.py`
- `threats/threat_board.py`
- remaining cache-copy helpers if profiling keeps them visible

Tier 3:
- `search/movegen.py` remaining Python-side candidate assembly
- `search/root.py` / `search/alphabeta.py` only after lower layers stop dominating

Recommended next-stage strategy:

1. Stop doing broad speculative refactors without a local cost model.

2. Treat local eval, movegen, and global eval as a measured subsystem.
   Prefer smaller kernels with verified wins over another large cache-layout
   experiment, and do not repeat nested-list Cython experiments that already
   regressed total search time.

3. Keep Python orchestration, but continue to move hot kernels together.
   The currently profitable grouping remains:
   - shape extraction
   - bucket/attack computation
   - incremental cache writes

4. Revisit `VCF` only after the eval/cache layer is cheaper enough that
   tactical recursion again becomes the clear primary wall. Recent `VCF` /
   `threat_board` work already removed the worst duplicate scans.

Execution order for the next phase:
- Phase A: measure the next local/movegen/global-eval sub-cost before each change
- Phase B: keep iterating on profitable local-eval kernels
- Phase C: benchmark again at `depth=5 width=15` and stronger fixed searches
- Phase D: only then decide whether the next module is `vcf` or broader cache work

Decision:
- do not go back to wrapper-style native experiments that already failed
- keep semantics frozen
- keep Gomocup / GUI / external-match validation on persistent engine sessions
- push the next acceleration work where measured cost still remains largest
