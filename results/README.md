# Seed-sweep results

Two generations of results are kept here on purpose.

`*_fixed` directories were run on the **current** reward (Jory's `b138dba`, which
stopped `rel()` dividing bounded [0,1] metrics by their own baseline, plus
`de90953`, which made unreachable O-D pairs count as a detour penalty instead of
silently vanishing). **These are the numbers to quote.**

The directories without the suffix were run earlier the same day on the reward as
it stood before those commits. They are retained only as a before-measurement, to
show what the two reward bugs were worth. Do not quote them as results.

## Al Nakheel, Riyadh -- 26 centerlines, r=250m

| | old reward | **fixed reward** |
|---|---|---|
| 30k, 100 seeds: mean | -0.0158 | **+0.1478** |
| 30k: max | +0.1366 | **+0.3323** |
| 30k: beat inaction (>= 0.0) | 41/100 | **80/100** |
| 30k: match/beat planner | n/a | **32/100** (vs zone_builder +0.2661) |
| 100k, 11 seeds: mean | +0.0118 | **+0.2375** |
| 100k: match/beat planner | n/a | **8/11** |

The fixed reward turns this scenario into one where RL genuinely outperforms the
hand-coded planner: the best seed (+0.3323) exceeds zone_builder (+0.2661), and a
third of seeds match or beat it. It also reverses an earlier conclusion drawn from
the old-reward run -- more training does help here (32% of seeds reach
planner-class at 30k vs 8 of 11 at 100k), whereas on the broken reward extra
training was actively harmful because the ~17x-amplified equity term punished any
closure.

## Jeddah, Al Salamah -- 58 centerlines, r=250m

| | old reward | **fixed reward** |
|---|---|---|
| mean | +0.2705 | **+0.2881** |
| std | 0.3162 | 0.3317 |
| median | +0.1901 | +0.1909 |
| max | +0.9459 | +0.9435 |
| beat inaction | 67/100 | **69/100** |
| >= 0.90 | 7/100 | **11/100** |
| matched planner | 1/100 | **1/100** |

Essentially unchanged, as expected: Jeddah's `zone_builder` differs by only 0.0024
between the two rewards, because its baseline access_gini (0.119) was never small
enough for the normalizer bug to bite hard.

Read honestly: 11 of 100 seeds reach >= 0.90 and one matches the planner, but 31
finish negative, the median is +0.19, and the std exceeds the mean. So PPO reaches
planner-class on a minority of seeds and is strongly seed-sensitive. It does
**not** beat the planner here -- zone_builder sits at the 0.95 ceiling.

## The contrast is the interesting result

On the small network (26 streets, 3 destinations) RL beats the planner. On the
larger, better-served network (58 streets, 31 destinations) the planner reaches the
reward ceiling and RL only occasionally matches it. Neither scenario alone tells
that story.

## Network-size sweep, 5 sizes x 3 seeds

`scale_sweep/` holds the completed version of the experiment prepared in
`scale_sweep_prep/`: one neighborhood (Al Nakheel) at five radii, so size varies
and city and demand do not. All 15 tasks completed.

| segments | steps | mean | std | max | planner | >= planner | > 0 |
|---|---|---|---|---|---|---|---|
| 26 | 100k | **+0.2595** | 0.0636 | +0.3323 | +0.2661 | **2/3** | 3/3 |
| 89 | 167k | **+0.2631** | 0.3886 | **+0.8125** | +0.6863 | **1/3** | 2/3 |
| 186 | 214k | -0.0470 | 0.0025 | -0.0437 | +0.6190 | 0/3 | 0/3 |
| 226 | 233k | +0.0044 | 0.0245 | +0.0238 | +0.3297 | 0/3 | 2/3 |
| 386 | 300k | -0.0280 | 0.0213 | +0.0018 | +0.2878 | 0/3 | 1/3 |

Three regimes rather than a smooth decay: reliable at 26, bimodal at 89 (one seed
beats the planner, two sit at zero), collapsed from 186 up. The 26- and
89-segment means are nearly equal while the std grows 6x, so quoting means alone
would hide the change.

This also closes the open caveat in `large_30k_fixed/`: at 386 segments, 10x the
training (300k vs 30k) still leaves every seed at or below zero, so the failure is
not undertraining. See `scale_sweep/PROVENANCE.md` for the confounds, which are
significant: n=3, and budget and timesteps both vary with size.

## Baselines, both measured on the fixed reward

| scenario | greedy | zone_builder | zone_builder_best |
|---|---|---|---|
| Al Nakheel 26 | 0.0000 | +0.2661 | +0.2661 |
| Jeddah 58 | 0.0000 | +0.9435 | +0.9435 |
| Al Nakheel 386 (budget 12) | 0.0000 (by construction) | +0.2878 | not run (cost) |

Greedy scores exactly 0.0000 on every scenario by refusing to ever start a plaza,
which is the greedy-fails half of the claim holding on real data throughout.
