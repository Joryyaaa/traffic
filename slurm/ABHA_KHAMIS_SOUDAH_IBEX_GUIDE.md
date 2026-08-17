# Abha Khamis–Jabal Soudah Viewpoint: Ibex run guide

This package runs the approved full-belt geometry without changing road
directions, closing streets, or adding a hypothetical bridge. It uses explicit
Khamis-to-Jabal Soudah Viewpoint demand that is kept separate from the city-accessibility
demand, preventing unintended origin–destination pairs.

City accessibility uses the complete 17,185-segment network. External
Khamis-to-Jabal Soudah Viewpoint through traffic uses the connected motorway/trunk/primary/
secondary/tertiary network (including link roads), so Madina cannot invent a
shortcut through residential, service, living, or unclassified streets.
Pre-run topology validation finds both Route 10 and Route 2120 directionally
connected to the viewpoint. Their start points are snapped to the reachable
side of each divided carriageway. One existing 515 m unclassified final-access
segment is permitted near the viewpoint; it ends 97 m from the OSM viewpoint.
No other residential, service, living, or unclassified street is available to
external through traffic.

The destination is OSM viewpoint node `7523059174` at
`18.2704765, 42.3636140`, not the previous Route 214 point east of the
mountain. Geometry QA, three local Madina smoke runs, and the relevant unit
tests pass before submission.

## What runs

Only three irreducible Madina tasks run concurrently, split by resource size:

1. Current full-belt city accessibility (740 residential origins and 275 amenities).
2. Route 10 Khamis approach to Jabal Soudah Viewpoint, reference load.
3. Route 2120 Khamis approach to Jabal Soudah Viewpoint, reference load.

The aggregation job then derives three additional complete result folders
without another Madina call:

4. Khamis-to-viewpoint baseline: sum of both approach flows.
5. Both approaches at 1.5x: exact scaling of the baseline assignment.
6. Both approaches at 2.0x: exact scaling of the baseline assignment.

This is exact for the configured static Madina assignment because origin flows
are additive and no capacity-dependent congestion or queue feedback is enabled.
The derived baseline was compared with a real combined Madina run: accessibility,
Accessibility Gini, total flow, flow entropy, trip distance, VKT, protected-road
flow, and positive-flow segment count all matched (floating-point error below
`3e-15`).

Local smoke simulations for the 3,123-segment corridor cases took about
4–12 seconds each. The 17,185-segment city baseline previously took about
305 seconds locally and was projected at roughly 71 seconds on Ibex. The two
small corridor tasks request only 4 GB and have 10-minute limits; the city task
alone requests 24 GB with a 30-minute limit. This avoids making the small jobs
wait for or reserve city-scale memory. Expected compute wall time is minutes,
not days, plus scheduler queue time. The derivation/summary limit is 10 minutes.

The outputs include mean accessibility, Accessibility Gini, mean trip distance,
unreachable share, flow-weighted VKT proxy, major-road flow share, protected
local-street flow share, per-origin accessibility, and per-segment Madina flow.

The 1.5x and 2.0x inputs are unitless sensitivity weights, not observed vehicle
counts. They scale assigned load but do not simulate queues or capacity-dependent
congestion. The VKT value is also a Madina flow-distance proxy, not observed VKT.

The current full-belt city-accessibility task has a different origin/destination
scope and is reported as context only. Numerical scenario comparisons use the
five Khamis-to-viewpoint rows, with the combined reference case as their
baseline.

The bypass/bridge is excluded because terrain, drainage, right-of-way, and cost
inputs are not complete. Residents-versus-visitors is excluded because the
current backend has no traveler-knowledge or signage route-choice model. Neither
scenario should be faked with arbitrary closures.

## Submit

From the repository root on Ibex:

```bash
conda activate traffic_env
mkdir -p logs

CITY_JOB=$(sbatch --parsable slurm/abha_khamis_soudah_city_context.sbatch)
CORRIDOR_JOB=$(sbatch --parsable slurm/abha_khamis_soudah_madina.sbatch)
sbatch --dependency=afterok:${CITY_JOB}:${CORRIDOR_JOB} \
  slurm/abha_khamis_soudah_aggregate.sbatch
```

Watch progress:

```bash
squeue -u "$USER"
sacct -j "$CITY_JOB,$CORRIDOR_JOB" --format=JobID,State,Elapsed,MaxRSS
```

Final summaries:

```text
results/abha_khamis_soudah_ibex/scenario_comparison.csv
results/abha_khamis_soudah_ibex/scenario_comparison.md
```

Each simulated or derived scenario folder also contains `metrics.json`,
`segment_flows.csv`, `segment_flows.geojson`, and `origin_accessibility.csv`.

## Heavy closure policies

Exact greedy and other multi-hour or multi-day closure-policy jobs are excluded
from this submission. The mentor's eight-worker connectivity-mask optimization
remains untouched for separate future policy work; it is not needed by this
static scenario package.
