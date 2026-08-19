# NEOM Scenario Suite — Sharma / Camp 26 (r = 5 km)

**Branch**: `neom-scenarios-existing-methodology`
**Frozen baseline**: `neom-baseline-sharma-camp26-r5km` commit `0ac7a86`
**CRS**: EPSG:32636 (UTM 36N)
**Center**: 28.03066 N, 35.24203 E

---

## Methodology

All four scenarios (B0, S1, S2, S3) are ported from the Abha event-hotspot methodology documented in `ABHA_HOTSPOT_SCENARIOS.md` and the `abha-event-hotspot-ibex` branch. The reconstruction is documented in [EXISTING_METHOD_PARITY.md](EXISTING_METHOD_PARITY.md).

**Key principle**: identical simulation/action/reward parameters across all scenarios; only the network topology and OD pairs change.

### Madina-ready edge-level network

The frozen B0 stores 274 OSM ways as multi-vertex LineStrings. Madina builds graph nodes
from LineString endpoints only (`_build_topology` line 971), so intersections at interior
vertices don't create connections. The derived `streets_madina_ready.geojson` splits each
way into consecutive 2-point segments (2398 total), producing a fully connected graph
(1 component, 2247 nodes). All configs point to this derived file.

The frozen baseline (`streets_largest_component.geojson`) is **not modified**.

### Shared parameters (from Abha event-hotspot configs)

| Parameter | Value |
|---|---|
| search_radius | 3500 |
| detour_ratio | 1.0 |
| beta | 0.0008 |
| closure_mode | rebuild |
| max_closures | 0 |
| episode_length | 1 |
| w_accessibility | 1.0 |
| disconnection_penalty | 5.0 |
| all other reward weights | 0.0 |

---

## Scenarios

### B0 — Baseline (no intervention)

Full network, all worker origins, all construction destinations. Pure evaluation run.

| Metric | Value |
|---|---|
| Streets | 274 ways, 2398 segments (largest component) |
| Origins | 21 dormitory buildings |
| Destinations | 12 construction zone centroids |
| Network modification | None |
| Config | `configs/neom_scenarios/city_madina_neom_b0.yaml` |

### S1 — Construction Zone Vehicle Restriction

Same origins and destinations as B0. Five internal service roads in the construction compound are removed from the network. Workers must use alternative routes.

| Metric | Value |
|---|---|
| Closure way IDs | 849103822, 996697456, 849103837, 849103835, 849103823 |
| Removed ways | 5 |
| Removed segments | 9 |
| Remaining ways | 269 |
| Remaining segments | 2389 |
| Config | `configs/neom_scenarios/city_madina_neom_s1.yaml` |

### S2 — Parking Hub at Camp 26

Same full network as B0, same 21 worker origins. Single destination: Camp 26 (NRC-26, OSM node 12390325515) as a parking/staging hub. Last-mile transport (shuttle/pedestrian) is not modeled.

| Metric | Value |
|---|---|
| Destination | Camp 26 (28.0809 N, 35.2147 E) |
| Origin count | 21 |
| Destination count | 1 |
| Config | `configs/neom_scenarios/city_madina_neom_s2.yaml` |

### S3 — Managed Entry/Exit Gates

Same full network as B0. Two separate Madina runs because the backend is undirected:

**Entry run**: 21 worker origins to trunk junction gate (28.00453 N, 35.22165 E, way 1447890028).
**Exit run**: construction cluster center (28.005 N, 35.203 E) to trunk far south gate (27.97053 N, 35.27476 E, way 849104008).

| Metric | Value |
|---|---|
| Entry origins | 21 (same as B0) |
| Entry destination | 1 (trunk junction gate) |
| Exit origin | 1 (construction center) |
| Exit destination | 1 (trunk south gate) |
| Config (entry) | `configs/neom_scenarios/city_madina_neom_s3_entry.yaml` |
| Config (exit) | `configs/neom_scenarios/city_madina_neom_s3_exit.yaml` |

---

## Mentor "8 Workers" Interpretation

The "8 workers" is **SNRL_MASK_WORKERS**, a performance optimization for parallel action-mask computation. It is NOT a demand/scenario concept.

- `src/snrl/env.py:33-46`: `_mask_workers()` reads `SNRL_MASK_WORKERS` env var
- `src/snrl/backends/madina_backend.py:924-946`: `n_workers` parameter for connectivity mask parallelism
- Set via: `export SNRL_MASK_WORKERS=8` on Ibex before training

---

## File Organization

```
data/neom_scenarios/sharma_camp26_r5km/
  streets_madina_ready.geojson  (2398 edge-level segments, derived from frozen B0)
  B0/
    origins.geojson          (21 worker origins, demand_weight=1.0)
    destinations.geojson     (12 construction centroids, destination_weight=1.0)
    qa.json
  S1/
    streets_restricted.geojson             (269 ways, closure roads removed)
    streets_restricted_madina_ready.geojson (2389 segments, edge-level)
    closure_reference.geojson              (5 removed roads)
    origins.geojson             (same 21)
    destinations.geojson        (same 12)
    qa.json
  S2/
    origins.geojson          (same 21)
    destinations.geojson     (Camp 26 only)
    qa.json
  S3/
    entry_origins.geojson    (21 workers)
    entry_destination.geojson (trunk junction gate)
    exit_origin.geojson      (construction center)
    exit_destination.geojson (trunk south gate)
    qa.json

configs/neom_scenarios/
  city_madina_neom_b0.yaml
  city_madina_neom_s1.yaml
  city_madina_neom_s2.yaml
  city_madina_neom_s3_entry.yaml
  city_madina_neom_s3_exit.yaml

results/neom_scenarios/sharma_camp26_r5km/
  maps/
    scenario_b0.html
    scenario_s1.html
    scenario_s2.html
    scenario_s3.html
    scenarios_combined.html
  qa/
    validation_results.json
```

---

## Running on Ibex

```bash
# Activate environment
module load cuda/12.1 python/3.11
source ~/snrl-env/bin/activate
cd ~/traffic

# Performance optimization (mentor's 8-worker mask)
export SNRL_MASK_WORKERS=8
export PYTHONIOENCODING=utf-8

# B0 baseline evaluation
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_b0.yaml \
  --scenario B0

# S1 restricted network
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_s1.yaml \
  --scenario S1

# S2 parking hub
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_s2.yaml \
  --scenario S2

# S3 entry
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_s3_entry.yaml \
  --scenario S3_entry

# S3 exit
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_s3_exit.yaml \
  --scenario S3_exit
```

---

## Validation

Run:
```bash
python scripts/validate_neom_scenarios.py
```

Last result: **71 PASS, 0 FAIL, 5 SKIP** (skips are snrl import on local machine).
