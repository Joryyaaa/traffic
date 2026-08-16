# Abha S0 Baseline Results

**Config:** `configs/city_madina_abha_s0.yaml`
**Network:** 4,586 directed segments, 1,729 nodes, 315 origins, 56 destinations
**Center:** (18.2264426, 42.5053914), r=1500m, drive network
**CRS:** EPSG:32638 (UTM 38N)

## Cheap baselines (local — partial, stopped early)

Run locally via `scripts/run_abha_s0_baselines_cheap.py`. Stopped after random policy
completed — simulate() measured at ~61s/call locally (vs ~2s on Ibex), making a full
local run infeasible (~11h for all 3 scenarios). All policies deferred to Ibex.

- **Completed:** random (mean_return=-0.05, std=0.0, 5 episodes, 4565s wall)
- **Skipped:** highest_flow, lowest_flow, zone_builder (deferred to Ibex)
- **Output:** `cheap_baselines_partial.json`

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
