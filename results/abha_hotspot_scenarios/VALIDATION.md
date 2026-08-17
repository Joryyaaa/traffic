# Validation checklist

- All six configs use clear place names and load through `snrl.load_config`.
- All street files preserve `u`, `v`, and `oneway`; configs enable
  `respect_oneway`.
- The mentor's action-mask path remains unchanged and the Slurm jobs cap it at
  eight workers.
- The mentor's exact directed Madina optimization and its direction tests are
  included from the latest optimized Abha branch.
- Central Market directed preflight completed: 82 segments, accessibility
  1.357, Gini 0.211, mean trip distance 554.4 m.
- Budget preflight completed for every data-bearing scenario in 5.0–8.5 s.
- School cluster is excluded from simulation because its origin layer is empty.
- Abu Kheyal Park is excluded because every valid directed crop has zero
  baseline accessibility.
- MP4 geometry previews are pre-run visual checks only; no simulated flow is
  claimed in them.
- Full test suite: **16 passed**; remaining warnings are deprecations inside the
  installed Madina/pandas stack.
- Seven new scripts compile; all six configs load successfully.
- All three Slurm files pass `bash -n`.
- All six geometry MP4s decode end-to-end; all six target maps report 300 dpi.
- Exact Central Market cheap suite completed locally in about 28 seconds total:
  random 7.4 s, highest-flow 6.7 s, lowest-flow 6.6 s, and zone-builder 7.5 s.
