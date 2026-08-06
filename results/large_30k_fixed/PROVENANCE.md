# Provenance -- 386-centerline scale scenario

**Scenario:** Al Nakheel, north Riyadh, r=700m (`configs/city_madina_ablation_large.yaml`)
**Data:** `data/raw/riyadh_large`, deduplicated: 772 directed rows -> **386 centerlines**.
163 origins, 37 destinations. Same neighborhood as the 26-centerline scenario, so
this isolates network scale rather than confounding it with a different city.
**Reward:** current (Jory's `b138dba` + `de90953`).
**Run:** 10 seeds x 30,000 steps, **all 10 complete**. 192 min per seed (mean),
303 min max -- seeds 1 and 2 shared a heavily contended node and took ~303 min
against ~165 min for the other eight, which is scheduling noise, not a difference
in the runs.

## Budget was measured, not derived

A "10% of the network" rule was tried first and is wrong at this scale. Measured
`zone_builder` on the fixed reward:

| max_closures / min_zone_size / episode_length | zone_builder |
|---|---|
| **12 / 6 / 30** (used) | **+0.2878** |
| 20 / 10 / 40 | -0.0525 |
| 39 / 20 / 60 | -0.2177 |

At 39 closures the accessibility loss swamps the pedestrian_zone bonus and the
planner scores worse than doing nothing, so the scenario could not test the
greedy-fails/planning-wins claim at all. An array was submitted at 39, caught in
pre-flight, cancelled and resubmitted at 12.

## Result: a negative result about scale

All 10 seeds are negative and tightly clustered. Five of the ten sit at
essentially exactly **-0.05**, which is precisely the `w_intervention` cost of
holding the full 12-closure budget while earning **zero** zone bonus. The agent
closes streets and never assembles a qualifying zone.

The std of 0.0046 is the tell. On the 26- and 58-centerline scenarios seeds spread
widely because different seeds found different plans; here they all converge on the
same non-solution.

| | |
|---|---|
| mean | **-0.0489** |
| std | **0.0046** |
| min / median / max | -0.0571 / -0.0500 / -0.0381 |
| match/beat planner (+0.2878) | **0/10** |

This is **not** a reward problem. `zone_builder` reaches +0.2878 on this exact
network, so the return is there to be had -- PPO cannot find it at this budget.
With a 387-wide action space, 6 contiguous qualifying closures needed out of only
75 qualifying segments, and 30k steps (~1,000 episodes), there is not enough
exploration to stumble onto a contiguous cluster and therefore never a payoff to
learn from.

Read it as: the current MLP-over-flat-observation policy does not scale to a few
hundred segments. That is direct evidence for the GNN-policy question (README open
question 5), and a more interesting finding than the affordability argument this
scenario was originally designed to make.

## Caveat: training budget is a confound

30k steps is short for this action space, and longer training clearly helped on the
26-centerline scenario under the fixed reward (8/11 seeds matched the planner at
100k vs 32% at 30k). A 200k-300k run on 2-3 seeds would separate "does not scale"
from "undertrained". Until that is run, the honest claim is the weaker one.

## For reference: greedy is unaffordable here

Greedy costs `(n_segments + 1) x episode_length` simulations per episode:
387 x 30 x ~0.6s is roughly **2 hours per episode**, against ~18 s for a trained
policy. `scripts/evaluate.py` was therefore not run with greedy on this config;
greedy's 0.0000 is known by construction (it never starts a plaza).
