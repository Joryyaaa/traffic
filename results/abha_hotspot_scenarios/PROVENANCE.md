# Provenance: Abha named-site scenarios

## Locked pipeline

The reward, measurements, `scripts/evaluate.py`, and `scripts/train.py` are
unchanged from the repository history containing
`origin/mentor/sweep-harness` at `9ea62b3`.

The package also copies the mentor's exact latest drive-network path from
`origin/optimized-abha-jabal-soudah-ibex`:

- one-way direction support and tests from `f0c720e`;
- indexed directed-graph rebuild from `7156224`, measured by the mentor at 61×
  on the 17,185-segment full-belt network.

The existing batched action-mask implementation is unchanged. Ibex jobs set
`SNRL_MASK_WORKERS=8`, the mentor-measured worker sweet spot.

## Data

All networks are deterministic crops of the committed full-belt OSM snapshot.
The drive files preserve `u`, `v`, and `oneway`, and every runnable config sets
`respect_oneway: true`.

| Named scenario | Radius | Segments | Origins | Destinations |
|---|---:|---:|---:|---:|
| Art Street and Al-Muftaha baseline | 300 m | 57 | 2 | 5 |
| Central Al-Muftaha Market | 300 m | 82 | 5 | 6 |
| Asir Central Hospital | 325 m | 96 | 2 | 1 |
| School cluster | 250 m | 94 | 0 | 5 |
| King Abdulaziz Grand Mosque | 250 m | 87 | 16 | 4 |
| Abu Kheyal Park | 375 m | 34 | 3 | 2 |

The hospital radius increases from 250 m to 325 m because the smaller crops
contain no residential origins. The school cluster is blocked because every
valid 30–100-segment crop has zero origins. Abu Kheyal Park is blocked because
all valid directed crops from 375 m through 550 m have zero baseline
accessibility. No demand was fabricated.

## Pre-submit budget measurement

`scripts/measure_abha_hotspot_budgets.py` imports the exact current environment,
reward, and deterministic `zone_builder` from `scripts/evaluate.py`.

| Named scenario | Return | Access baseline → final | Decision |
|---|---:|---:|---|
| Art Street and Al-Muftaha baseline | 0.0000 | 2.337 → 2.337 | no intervention |
| Central Al-Muftaha Market | +0.8363 | 1.357 → 1.233 | model run allowed |
| Asir Central Hospital | −0.4173 | 0.187 → 0.000 | evaluation only |
| School cluster | — | — | blocked: no origins |
| King Abdulaziz Grand Mosque | +0.0503 | 0.868 → 0.297 | model run allowed, accessibility warning |
| Abu Kheyal Park | +0.9500 | 0.000 → 0.000 | blocked: reward bonus on zero-access network |

The park row exposes a reward weakness: a pedestrian-zone bonus can be positive
even when no modelled trip is reachable. It is not accepted as a valid model
case. The mosque's positive total return also does not hide its substantial
accessibility loss; Accessibility Gini and the full metrics remain required in
the final review.

## Ibex runtime design

Local directed budget checks took 5.0–8.5 seconds per site. The four fast
baseline tasks run concurrently and exclude `greedy` and
`zone_builder_best`; expected compute wall time is minutes, not hours, plus
scheduler queue time. The two independent 2,048-step model jobs also run as a
Slurm array with eight mask workers and a 30-minute safety limit.

The exact four-policy Central Market command completed locally in about 28
seconds total (6.6–7.5 seconds per policy). Because Ibex runs the four sites as
independent array tasks, the fast comparison should be governed by the slowest
site rather than the sum of all four.

The exact wall time must be taken from `sacct` after submission. No sub-minute
claim is made for RL training before Ibex measures it.

VKT remains the repository's Madina flow-distance proxy, not observed traffic
VKT. The current simulation has no queueing or capacity-dependent congestion.
