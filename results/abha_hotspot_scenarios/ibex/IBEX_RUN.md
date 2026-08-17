# Ibex run record: Abha named-site scenarios

Executed 2026-08-17 from `codex/abha-hotspot-scenarios` at `eb87e85`, exactly as
`slurm/ABHA_HOTSPOT_IBEX_GUIDE.md` documents. Three arrays, eight tasks, all
COMPLETED.

| job | array | tasks | elapsed |
|---|---|---|---:|
| 50635294 `snrl-abha-hotspots` | 0-3 | four baseline sites | 5-8 s each |
| 50635295 `snrl-abha-2048` | 0-1 | two 2,048-step trainings | 1:33 and 1:50 |
| 50635296 `snrl-abha-eval` | 0-1 | evaluate both saved agents | 16 s and 22 s |

Total compute across all eight tasks was **under four minutes**. The existing
`snrl` environment was reused rather than rebuilt from `environment.yml`: it
already satisfies the guide's import check, and recreating it would have risked
the environment every other result in this repo was produced with.

## Baselines, four data-bearing sites

| Named scenario | segments | random | highest_flow | lowest_flow | zone_builder |
|---|---:|---:|---:|---:|---:|
| Art Street and Al-Muftaha baseline | 57 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Central Al-Muftaha Market | 82 | -0.0500 | -0.4001 | -0.0500 | **+0.8363** |
| Asir Central Hospital | 96 | -0.0500 | -0.4173 | -0.0500 | -0.4173 |
| King Abdulaziz Grand Mosque | 87 | -0.1007 | +0.0503 | -0.0500 | +0.0503 |

Art Street returning 0.0000 across all four policies is the intended behaviour
of a fully-open comparison case, not a failure. Central Market is the only site
where the heuristic finds a large positive zone. The hospital's negative
`zone_builder` matches the "intervention budget is negative" status the package
already declares for it.

## The 2,048-step agents lose to the heuristic on both sites

| Named scenario | trained agent | zone_builder | training ep_rew_mean |
|---|---:|---:|---:|
| Central Al-Muftaha Market | **-0.1188** | +0.8363 | -0.217 |
| King Abdulaziz Grand Mosque | **-0.0500** | +0.0503 | -0.145 |

Read this as a **pipeline test that passed, not a training result**. 2,048
timesteps is roughly 136 episodes of 15 steps. The scale sweep in
`results/scale_sweep/` needed 100k-300k timesteps before returns became
meaningful at 26-386 segments, so a 2,048-step run is two orders of magnitude
short of where learning starts. What it demonstrates is that
train -> save -> `evaluate.py` -> `reward_breakdown.py` runs end to end on a
directed drive network and produces a loadable agent and a reward chart.

The reward breakdown says the same thing from the other direction. The
intervention penalty is **42.1%** of Central Market's cumulative return and
**100.0%** of the mosque's, meaning the agent is paying to close roads and
earning almost nothing back:

| term | Central Market | Grand Mosque |
|---|---:|---:|
| accessibility | -0.0383 (32.3%) | 0.0000 |
| flow_concentration | -0.0205 (17.2%) | 0.0000 |
| equity | -0.0057 (4.8%) | 0.0000 |
| detour | -0.0043 (3.6%) | 0.0000 |
| intervention | -0.0500 (42.1%) | -0.0500 (100.0%) |
| disconnection | 0.0000 | 0.0000 |

At the mosque every term except intervention is exactly 0.0000, so that agent
closed roads and moved no metric at all. Its -0.0500 is the intervention cost
and nothing else, the same structural signature as `lowest_flow` at -0.0500
here and in `results/abha_baselines_ibex/PROVENANCE.md`.

## What this run does and does not establish

It establishes that the RL path works on these networks and that the two
blocked sites stayed blocked. It does **not** establish that RL beats the
heuristic on any Abha site. On the only two sites trained, the heuristic wins
by +0.955 and +0.100.

The obvious next step is the one the package deliberately did not take: train
at 100k-300k timesteps, the range `results/scale_sweep/PROVENANCE.md` measured
as the point where returns stop being noise. At the pace measured here, 2,048
steps in 1:50 on 82 segments, 100k steps projects to roughly **1.5 hours** per
site and 300k to roughly **4.5 hours**, comfortably inside a single batch job.
That is the run worth submitting next, and it is cheap.

Jory's decision to block School cluster (no origins) and Abu Kheyal Park (zero
baseline accessibility) rather than fabricate demand is the right call and is
why the four sites above can be read at face value.
