# Independent reproduction of the named-site Ibex run

Jory had already run this package (jobs `50634291` / `50634292` / `50634633`,
recorded in `IBEX_RESULTS.md`). I submitted it again from `eb87e85` without
having seen her results, on different jobs and different nodes. **Read
`IBEX_RESULTS.md` for the findings; this file only records that they reproduce
and adds the sizing for the next run.**

| | Jory | mine |
|---|---|---|
| baselines | `50634291`, 14-17 s | `50635294`, 5-8 s |
| 2,048-step training | `50634292`, 1:51 / 1:30 | `50635295`, 1:50 / 1:33 |
| trained evaluation | `50634633`, 22-26 s | `50635296`, 16 s / 22 s |

## Every number reproduced exactly

All 20 policy returns across the four data-bearing sites, both trained-agent
returns, and all seven reward-breakdown terms match to the printed four decimal
places:

| Scenario | random | highest_flow | lowest_flow | zone_builder | RL (2,048) |
|---|---:|---:|---:|---:|---:|
| Art Street and Al-Muftaha baseline | 0.0000 | 0.0000 | 0.0000 | 0.0000 | not trained |
| Asir Central Hospital | -0.0500 | -0.4173 | -0.0500 | -0.4173 | not trained |
| Central Al-Muftaha Market | -0.0500 | -0.4001 | -0.0500 | **+0.8363** | **-0.1188** |
| King Abdulaziz Grand Mosque | -0.1007 | +0.0503 | -0.0500 | +0.0503 | **-0.0500** |

The fully-open network measurements match too (Art Street accessibility 2.337 /
Gini 0.070, hospital 0.187 / 0.043, market 1.357 / 0.211, mosque 0.868 / 0.130).
Training `ep_rew_mean` landed at -0.217 and -0.145.

This matters more than a duplicate run usually would: it shows the directed
Madina path is deterministic across separate Ibex jobs and nodes, which nothing
else in this repo had tested. 47 checks trace every figure here to a job log or
to `sacct`.

## Sizing the run that would actually test the RL claim

Jory's reading is right and worth stating in the strongest form: on the only two
sites trained, the heuristic beats the agent by **+0.955** and **+0.100**. The
2,048-step runs establish that train -> save -> `evaluate.py` ->
`reward_breakdown.py` works end to end on a directed drive network. They
establish nothing about whether RL beats the heuristic here.

2,048 timesteps is about 136 episodes of 15 steps.
`results/scale_sweep/PROVENANCE.md` measured 100k-300k timesteps as where
returns stop being noise at 26-386 segments, so these runs are two orders of
magnitude short of where learning starts.

From the pace measured here, 2,048 steps in 1:50 on 82 segments:

| timesteps | projected per site | fits in one batch job |
|---:|---:|---|
| 100,000 | ~1.5 h | yes |
| 300,000 | ~4.5 h | yes |

Both sites could run as a two-task array. That is the next submission worth
making, and it is cheap. The projection assumes per-step cost stays flat as the
policy starts closing more roads; `at_budget` short-circuits the mask once the
closure budget is spent, so if anything it should get cheaper per step, not
dearer.

## One caveat on the reward breakdown

At the mosque every reward term except intervention is exactly 0.0000, so that
agent closed roads and moved no metric at all; its -0.0500 is the intervention
cost and nothing else. That is the same structural signature as `lowest_flow` at
-0.0500 here, in `results/scale_sweep/` at 186 and 386 segments, and in
`results/abha_baselines_ibex/PROVENANCE.md`. It is worth checking whether the
mosque crop has enough reachable structure for any closure to register before
spending 4.5 h training on it.
