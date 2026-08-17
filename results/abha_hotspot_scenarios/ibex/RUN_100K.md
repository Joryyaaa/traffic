# 100,000-step training on both Abha sites

Jobs 50635988 (training array 0-1) and 50635989 (evaluation array 0-1), all
COMPLETED 2026-08-18. Submitted from `codex/abha-hotspot-scenarios` with
`TIMESTEPS=100000`, so output landed in `runs/abha_hotspot_2048/<site>_seed42_100000/`
and the earlier 2,048-step models and results are untouched and still comparable.

**Result: 49x more training did not beat the heuristic on either site. Both
agents converged on doing nothing.** That is a real finding rather than a failed
run, and it points at one specific cause.

## Returns

| Site | 2,048 steps | 100,000 steps | `zone_builder` | still short by |
|---|---:|---:|---:|---:|
| Central Al-Muftaha Market | -0.1188 | **-0.0250** | +0.8363 | 0.8613 |
| King Abdulaziz Grand Mosque | -0.0500 | **0.0000** | +0.0503 | 0.0503 |

Training improved both substantially, monotonically, and then flattened:

| steps | Central Market | Grand Mosque |
|---:|---:|---:|
| 2,048 | -0.217 | -0.145 |
| 24,576 | -0.059 | -0.0557 |
| 49,152 | -0.0501 | -0.0500 |
| 73,728 | -0.0500 | -0.0475 |
| 100,352 | -0.0486 | -0.0450 |

The curve is flat from roughly 50k onward on both sites. More steps is not the
missing ingredient, which is the same conclusion `results/scale_sweep/` reached
from the other direction when the 386-segment run at 300k steps ruled out
undertraining.

## What the agents actually learned: to stop intervening

The reward breakdowns are the informative part, and they are stark.

**Grand Mosque, every single term exactly 0.0000, intervention included.** An
intervention cost of zero means the agent closed **nothing at all**. It learned
the pure no-op policy and scored 0.0000. Doing nothing is genuinely better than
anything else it could find, and it is still worse than `zone_builder`.

**Central Market closed exactly 2 segments** (steps 0 and 1, -0.0125 each) and
no-opped for the remaining 13 steps. Every non-intervention term is 0.0000, so
those two closures earned nothing whatsoever:

| term | Central Market | Grand Mosque |
|---|---:|---:|
| accessibility | 0.0000 | 0.0000 |
| flow_concentration | 0.0000 | 0.0000 |
| equity | 0.0000 | 0.0000 |
| detour | 0.0000 | 0.0000 |
| pedestrian_zone | 0.0000 | 0.0000 |
| **intervention** | **-0.0250** | **0.0000** |
| disconnection | 0.0000 | 0.0000 |

## Why: it stalled one closure short of where reward begins

`min_zone_size: 3`. A zone of 1 or 2 segments scores zero, so the first two
closures earn no bonus and pay full `w_intervention`. Central Market closed 2 and
stopped, which is exactly one segment short of the threshold where any reward
would have appeared. The mosque never took the first step at all.

This is the credit-assignment cliff in its purest observable form: the agent
must pay for three closures before the reward function pays anything back, and
nothing in the observation tells it that a third adjacent closure is where the
cliff ends.

**And it cannot see which closure would be adjacent.** The observation is
`(n_segments+1, 5)` per `src/snrl/env.py:220`: `closed`, `flow`, `length`,
`flow_delta`, `degree`. Adjacency is not among them. `env._adjacency` exists and
`zone_builder` reads it directly (`scripts/evaluate.py:98`) to pick segments
touching the closed set. So the reward pays for a contiguous zone while the agent
is blind to what "adjacent" means, and `zone_builder` is handed the array that
makes contiguity computable. The two agents converging on no-op is the rational
response to that: if you cannot reliably assemble three touching segments, every
closure is pure cost.

## Cost model: I was wrong three times, here is the measured curve

Worth recording because the next run has to be sized from it.

| estimate | Central Market | Grand Mosque | actual |
|---|---:|---:|---|
| flat cost from the 2,048-step rate | 1.17 h | 1.32 h | too low |
| growth extrapolated linearly, never plateauing | 9.09 h | 3.67 h | too high |
| re-projected once growth plateaued | ~2.2 h | ~1.3 h | closest |
| **measured** | **02:42:22** | **01:38:54** | |

The per-step cost does rise, contradicting my prediction that `at_budget` would
short-circuit the mask and make it cheaper, but it **plateaus** rather than
growing without bound:

| steps | Central Market ms/step | Grand Mosque ms/step |
|---:|---:|---:|
| 2,048 | 40.0 | 35.2 |
| 24,576 | 94.4 | 45.9 |
| 49,152 | 97.7 | 46.8 |
| 100,352 | **96.9** | **58.9** |

Central Market plateaus near 97 ms/step from about 25k onward. The first 8h
submission would have been killed at roughly 90% on the linear projection, which
is why it was cancelled at 12:51 and resubmitted with a 2-day limit. Memory was
never the constraint: 576 MB at rest, 2.2 GB at 50k, against the 64 GB requested.

For sizing future runs: **~97 ms/step at 82 segments, ~59 ms/step at 87
segments**, so 300k steps is roughly 8 h and 5 h respectively.

## What to do next, and what not to

Do **not** run 300k on this architecture. The curve is flat from 50k and the
failure is representational, not a budget problem.

The two experiments that would actually move this, in order of information per
hour:

1. **Add adjacency to the observation.** Two lines in `_observation()`:
   `_adjacency @ closed_mask` (how many of my neighbours are closed) and a
   `touches_closed` flag. This is the cheapest possible test of the diagnosis,
   and if an MLP with it closes most of the gap then the finding is "the
   observation was impoverished", which is a cleaner claim than needing a new
   architecture. It changes the observation space, so it invalidates saved models
   and needs its own seed sweep.
2. **Run the GCN that already exists.** `src/snrl/gnn.py`,
   `scripts/train_gnn.py`, and `slurm/gnn_prototype_test.sbatch` were written on
   2026-08-10 and have never been run at scale. It is permutation-equivariant
   over the adjacency matrix, which is the property the flattened MLP lacks. The
   11 h local estimate that shelved it was Windows `mp.Manager()` overhead, and
   `results/gnn_prototype_test/PROVENANCE.md` records the ~30x Ibex speedup
   itself, so it is 15 to 25 min per seed here. Use 89 segments and 5 seeds: at
   that size the MLP is bimodal (1 of 3 seeds reaches +0.8125 against the
   +0.6863 planner bar), so a single number cannot be read either way.

Also worth considering, given the cliff above: potential-based shaping on zone
growth would smooth the `min_zone_size` threshold without moving the optimum.

## Caveats

- **n = 1 seed per site.** Both sites used seed 42. The scale sweep found seed
  variance large enough to flip conclusions at 89 segments, so these two numbers
  are single draws, not distributions. The flat 50k-to-100k plateau is the more
  robust part of this result; the exact endpoints are not.
- `zone_builder` is a deliberate cheat baseline, handed the adjacency array. Its
  winning is the intended control, not a bug, and not a reason to tune the
  reward.
- Central Market's `zone_builder` bar of +0.8363 comes from the same 2,048-step
  round and is unchanged here; only the RL rows are new.
- The two blocked sites (School cluster, no origins; Abu Kheyal Park, zero
  directed baseline accessibility) remain blocked and were not trained.
