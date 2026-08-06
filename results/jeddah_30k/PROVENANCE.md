# Provenance

**Scenario:** Al Salamah, Jeddah, r=250m (`configs/city_madina_jeddah.yaml`)
**Data:** `data/raw/jeddah`, fetched 2026-08-06, deduplicated: 116 directed rows
from osmnx -> **58 real centerlines**. 63 origins, 31 destinations.
**Run:** 100 seeds x 30,000 steps, MaskablePPO, 1 eval episode per seed
(the madina backend is deterministic, so more episodes are identical rollouts).
All 100 tasks COMPLETED; all 100 seeds present.

## Result

| | |
|---|---|
| mean | **+0.2705** |
| std | 0.3162 |
| min / median / max | -0.1411 / +0.1901 / **+0.9459** |
| beat doing nothing (>= 0.0) | 67/100 |
| planner-class (>= 0.90) | 7/100 |
| matched the planner (>= 0.9459) | 1/100 |

Distribution: 33 negative, 22 in [0, 0.25), 19 in [0.25, 0.50), 19 in [0.50, 0.90),
7 at >= 0.90.

Baselines on the same data: `zone_builder` +0.9459, `zone_builder_best` +0.9459,
greedy 0.0000, lowest_flow -0.0167, highest_flow -0.0510, random -0.2327.
Theoretical ceiling is 0.95 (a full 6-segment qualifying zone minus the
intervention cost), so zone_builder is effectively at the ceiling here.

## How to read it

Greedy scores exactly 0.0000 by refusing to ever start a plaza, and the mean
return of +0.2705 beats that clearly, so the agent is learning real structure
from the reward alone. Seven seeds reach planner-class and one matches the
planner exactly, which shows contiguity *is* discoverable on real city data
without being told about it.

But the distribution is close to uniform with a tail, not concentrated: a third
of seeds finish negative, the median is +0.1901, and the std exceeds the mean. So
this does **not** support "MaskablePPO beats the hand-coded planner" on real data
-- at this budget the typical seed lands well short of it and only 1 in 100
matches it. The defensible claim is that PPO reaches planner-class performance on
a minority of seeds and is strongly seed-sensitive.

The 100k-step run on Al Nakheel (`results/ablation_100k`) suggests this is
optimisation fragility rather than undertraining: within-seed, 6 of 11 improved
with 3.3x the budget, 4 sat frozen at exactly +0.1282, and seed 42 collapsed
from -0.0578 to -0.4984.

## CAVEAT: reward version

This sweep ran on the **pre-b138dba** reward, before `rel()` stopped dividing
bounded [0,1] metrics by their baseline. Jeddah is by far the least affected
scenario -- `zone_builder` is +0.9459 under the old reward and +0.9435 under the
fixed one, a difference of 0.0024 -- so these numbers are expected to survive a
re-run largely intact. That is an expectation, not a measurement. Al Nakheel's
numbers, by contrast, definitely do not survive: its `zone_builder` moves from
-0.4586 to +0.2661.

## Reproduce

    sbatch --array=1-100 --time=04:00:00 \
      --export=ALL,CONFIG=configs/city_madina_jeddah.yaml,TIMESTEPS=30000,OUTROOT=runs/sweep_jeddah_30k,EPISODES=1 \
      slurm/sweep_array.sbatch
    python scripts/aggregate_sweep.py --root runs/sweep_jeddah_30k --expect 1-100 --success-threshold 0.9459
