# Abha S0 Baseline Results

**Config:** `configs/city_madina_abha_s0.yaml`
**Network:** 4,586 directed segments, 1,729 nodes, 315 origins, 56 destinations
**Center:** (18.2264426, 42.5053914), r=1500m, drive network
**CRS:** EPSG:32638 (UTM 38N)

## Cheap baselines (local, this directory)

Run locally via `scripts/run_abha_s0_baselines_cheap.py` — same policy functions as
`scripts/evaluate.py` but skips greedy and zone_builder_best (infeasible locally at
this network scale).

- **Policies:** random, highest_flow, lowest_flow, zone_builder
- **Episodes:** 5 per policy
- **Output:** `cheap_baselines.json`

## Heavy baselines (Ibex)

Prepared in `slurm/abha_s0_baselines.sbatch` — runs all 6 policies including greedy
(~1 day on Ibex) and zone_builder_best (~35 min on Ibex).

Timing estimates from `scripts/_probe_abha_s0_timing.py`:
- simulate() cost: ~7.8s locally, ~0.26s on Ibex (~30x faster)
- greedy: ~30 days locally → ~1 day on Ibex
- zone_builder_best: ~18 hours locally → ~35 min on Ibex

## Baseline simulation metrics (no closures)

From `scripts/baseline_report.py`:
- mean_access: 1.301
- gini: 0.352
- flow_entropy: 0.621
- total_flow: 22,232.5
- trip_dist_m: 774.9
