# Network-size sweep -- config prep (no training run locally)

**Date:** 2026-08-08
**Status:** 4 configs ready, budgets measured, timesteps assigned. **No training was run** --
local per-step cost makes this infeasible on a single machine (see below). Meant to be
picked up and run on Ibex/Slurm, same protocol as `origin/mentor/sweep-harness`'s
`slurm/sweep_array.sbatch`.

## Why 4 sizes, not 5

The original ask was 5 sizes (26 / ~new / ~new / ~new / 386) spanning the two existing
endpoints. A 3rd intermediate size (targeted at r=460m, ~186 segments, chosen to fill a gap
between the r400 and r500 attempts) could not be fetched: `fetch_osm_data.py`'s amenities
query to `overpass-api.de` timed out on every attempt (4 tries, including a trivial 50m-radius
sanity query and an alternate mirror), while streets/residential fetched fine every time. This
looks like the round-robin backend flakiness already documented in
`notes/2026-08-06-street-duplication.md` section 8, not a problem with this specific query or
radius. Per instruction, proceeding with the 4 sizes that did fetch cleanly rather than keep
retrying against a currently-unreliable endpoint.

## The 4 sizes

Same Al Nakheel center (24.7412, 46.6335) throughout, so scale is isolated from city/demand
(matches `city_madina_ablation_large.yaml`'s existing rationale).

| radius | config | segments | residential | amenities |
|---|---|---|---|---|
| 250m | `configs/city_madina_ablation.yaml` | 26 | 17 | 3 |
| 400m | `configs/city_madina_ablation_r400.yaml` | 89 | 59 | 9 |
| 500m | `configs/city_madina_ablation_r500.yaml` | 226 | 74 | 23 |
| 700m | `configs/city_madina_ablation_large.yaml` | 386 | 163 | 37 |

## Budget: measured per size, not a flat 10% rule

Same methodology as `results/large_30k_fixed/PROVENANCE.md` on `origin/mentor/sweep-harness`:
run `zone_builder` (deterministic, one episode, no training) at a candidate budget and check the
return is clearly positive before committing to it. The 26- and 386-segment budgets were already
established (6/3/15 and 12/6/30, respectively -- the latter specifically *because* the naive 10%
guess, 39 closures, made `zone_builder` negative there). For the two new sizes, the first
candidate tried already worked cleanly -- no need to search further:

| segments | max_closures | min_zone_size | episode_length | zone_builder | naive 10% would've been |
|---|---|---|---|---|---|
| 26 | 6 | 3 | 15 | +0.2661 | 3 (already known to be too tight -- see notes/) |
| 89 | 9 | 4 | 22 | **+0.6863** | 9 (same -- happened to match) |
| 226 | 23 | 11 | 58 | **+0.3297** | 23 (same -- happened to match) |
| 386 | 12 | 6 | 30 | +0.2878 | 39 (measured negative, -0.2177 -- see mentor's PROVENANCE.md) |

Read honestly: the naive 10% rule happened to coincide with the measured-good budget at 89 and
226 segments. That's not evidence the rule is fine in general -- it visibly broke at 386
segments in the mentor's own measurement, and wasn't re-checked here beyond the first try. Worth
a second candidate budget at each size if this needs to be airtight rather than just workable.

## Timesteps: 100k (smallest) to 300k (largest), interpolated by rank

| segments | config | timesteps |
|---|---|---|
| 26 | `city_madina_ablation.yaml` | 100,000 |
| 89 | `city_madina_ablation_r400.yaml` | 167,000 |
| 226 | `city_madina_ablation_r500.yaml` | 233,000 |
| 386 | `city_madina_ablation_large.yaml` | 300,000 |

Linear interpolation by rank (not by segment count) across the 4 sizes: `100k + i * (300k-100k)/3`
for i=0..3, rounded to the nearest 1,000. Flag if proportional-to-segment-count spacing was
intended instead -- it would give a very different middle two values (segment counts aren't
evenly spaced: 26, 89, 226, 386).

## Why this can't run locally

Measured directly (2026-08-08, this machine, not Ibex) on the 386-segment scenario: **~1.68s per
`env.step()`**, using a properly `if __name__ == "__main__":`-guarded probe. That number is a
genuine blend of ~2-4s per *new* closed-segment combination (a real Madina `betweenness()` call)
and near-0s for steps after a episode's budget is exhausted (repeats the same `closed_mask`,
hits `MadinaBackend`'s internal result cache) -- not an artifact of a bad measurement.

Extrapolated, per seed, on this one machine:

| steps | wall-clock |
|---|---|
| 100,000 | ~46.8 hours (~2 days) |
| 200,000 | ~93.5 hours (~3.9 days) |
| 300,000 | ~140.3 hours (~5.8 days) |

That's for the *largest* config alone, one seed, one machine. The original ask (2-3 seeds per
size, 4-5 sizes) would run into weeks of sequential wall-clock time locally. The mentor's own
`large_30k_fixed` run (10 seeds x 30k steps in 192min mean / 303min max) only looks fast because
it used a Slurm **array** -- 10 seeds in parallel on separate nodes, not one machine running them
one after another. Same order of per-step cost, entirely different wall-clock outcome from
parallelism. This is why nothing here was trained locally -- see also the `mp.Manager()` TODO in
`src/snrl/backends/madina_backend.py` for the specific likely cause (a real OS process spawned by
Madina's `betweenness()` on every single `simulate()` call, regardless of `num_cores`, uncovered
by the existing `_force_single_process_betweenness()` patch).

## To run

Same protocol as `slurm/README.md` on `origin/mentor/sweep-harness`:

```bash
sbatch --array=1-3 \
  --export=ALL,CONFIG=configs/city_madina_ablation_r400.yaml,TIMESTEPS=167000,OUTROOT=runs/scale_r400 \
  slurm/sweep_array.sbatch

sbatch --array=1-3 \
  --export=ALL,CONFIG=configs/city_madina_ablation_r500.yaml,TIMESTEPS=233000,OUTROOT=runs/scale_r500 \
  slurm/sweep_array.sbatch

sbatch --array=1-3 \
  --export=ALL,CONFIG=configs/city_madina_ablation.yaml,TIMESTEPS=100000,OUTROOT=runs/scale_r250 \
  slurm/sweep_array.sbatch

sbatch --array=1-3 \
  --export=ALL,CONFIG=configs/city_madina_ablation_large.yaml,TIMESTEPS=300000,OUTROOT=runs/scale_r700 \
  slurm/sweep_array.sbatch
```

`--array=1-3` trains seeds 1, 2, 3 -- matches "2-3 seeds" from the original ask; bump to whatever
Ibex allocation allows. `slurm/sweep_array.sbatch` and `scripts/aggregate_sweep.py` are unmodified
from `origin/mentor/sweep-harness`.
