# NEOM Scenarios — Final Report

**Date**: 2026-08-19
**Branch**: `neom-scenarios-existing-methodology`
**Base**: frozen B0 at `0ac7a86` on `neom-baseline-sharma-camp26-r5km`

---

## Commit History

| Commit | Description |
|---|---|
| `413b707` | freeze NEOM B0 baseline data: Sharma/Camp26 r=5km |
| `0ac7a86` | add NEOM B0 baseline map, config, and documentation |
| `a055c7f` | add existing scenario methodology inspection report |
| `68c9665` | add NEOM B0/S1/S2/S3 scenario data and configs |
| `2fe6b66` | add validation, scenario maps, documentation, and final report |

---

## Source Files Used for Reconstruction

| Source | Purpose |
|---|---|
| `configs/city_madina_abha_event_b0.yaml` | Reference B0 config (simulation/action/reward params) |
| `configs/city_madina_abha_event_s1.yaml` | Reference S1 config (restricted streets path) |
| `configs/city_madina_abha_event_s2.yaml` | Reference S2 config (parking hub destination) |
| `configs/city_madina_abha_event_s3_entry.yaml` | Reference S3 entry config |
| `configs/city_madina_abha_event_s3_exit.yaml` | Reference S3 exit config |
| `scripts/build_abha_event_hotspot_data.py` | Scenario data builder (HTML-based origins) |
| `scripts/build_abha_event_osm_network.py` | OSM network builder with closure/entry/exit way IDs |
| `scripts/run_abha_event_hotspot_madina.py` | Scenario runner with CONFIG_MAP |
| `src/snrl/env.py:33-46` | `_mask_workers()` function |
| `src/snrl/backends/madina_backend.py:924-946` | `n_workers` mask parallelism |
| `ABHA_HOTSPOT_SCENARIOS.md` | Scenario documentation reference |
| `results/abha_event_hotspot_madina/PROVENANCE.md` | Provenance and known issues |

---

## Scenario Definitions

### B0 — Baseline

- **Network**: full B0 streets (274 ways, 2398 segments, largest component)
- **Origins**: 21 worker dormitories (demand_weight=1.0)
- **Destinations**: 12 construction zone centroids (destination_weight=1.0)
- **Closures**: none (max_closures=0)
- **Meaning**: baseline accessibility measurement before any traffic intervention

### S1 — Construction Zone Vehicle Restriction

- **Network**: B0 streets minus 5 internal service roads (9 segments removed)
- **Closure OSM IDs**: 849103822, 996697456, 849103837, 849103835, 849103823
- **Remaining**: 269 ways, 2389 segments
- **Origins/Destinations**: identical to B0
- **Meaning**: how does restricting internal compound access affect worker route accessibility?

### S2 — Parking Hub at Camp 26

- **Network**: full B0 streets (unmodified)
- **Origins**: same 21 worker dormitories
- **Destination**: Camp 26 (NRC-26, OSM node 12390325515, 28.0809 N 35.2147 E) as single parking hub
- **Meaning**: what if all workers park at Camp 26 and take last-mile transport?

### S3 — Managed Entry/Exit Gates

- **Network**: full B0 streets (unmodified)
- **Two Madina runs** (backend is undirected):
  - **Entry**: 21 worker origins -> trunk junction gate (28.00453 N, 35.22165 E, way 1447890028)
  - **Exit**: construction center (28.005 N, 35.203 E) -> trunk south gate (27.97053 N, 35.27476 E, way 849104008)
- **Meaning**: what traffic patterns emerge when workers enter through a managed trunk junction and exit through a southern gate?

---

## 8-Worker Interpretation

The mentor's "8 workers" = `SNRL_MASK_WORKERS=8`. It is a CPU parallelism setting for action-mask computation, NOT a demand or scenario concept.

- Defined in `src/snrl/env.py:33-46` (`_mask_workers()`)
- Used in `src/snrl/backends/madina_backend.py:924-946` (`n_workers`)
- Set before training: `export SNRL_MASK_WORKERS=8`
- Relevant only on Ibex (multi-core Linux), not on local Windows

---

## NEOM Feature Selection

### Worker Origins (21 dormitories)
Selected from `data/neom_baseline/sharma_camp26_r5km/residential.geojson` — all 17 buildings tagged `building=dormitory`, plus 4 additional large residential buildings near Camp 26 with name matches.

### Construction Destinations (12 zones)
Centroids of all 12 polygons in `data/neom_baseline/sharma_camp26_r5km/construction.geojson` (landuse=construction).

### S1 Closure Roads
5 service roads internal to the largest construction compound (western cluster, ~28.01 N 35.19 E). Selected because they are:
- Tagged `highway=service`
- Inside a construction landuse polygon
- Internal (removing them does not disconnect the main network)

### S2 Parking Hub
Camp 26 (NRC-26), OSM node 12390325515, is the only named settlement/camp in the study area with sufficient infrastructure for a staging hub.

### S3 Entry/Exit Ways
- Entry way 1447890028: trunk road connecting Sharma to the construction junction
- Exit way 849104008: trunk road heading south from the junction toward the coast

---

## Maps

| Map | Path |
|---|---|
| B0 Baseline | `results/neom_scenarios/sharma_camp26_r5km/maps/scenario_b0.html` |
| S1 Restriction | `results/neom_scenarios/sharma_camp26_r5km/maps/scenario_s1.html` |
| S2 Parking Hub | `results/neom_scenarios/sharma_camp26_r5km/maps/scenario_s2.html` |
| S3 Entry/Exit | `results/neom_scenarios/sharma_camp26_r5km/maps/scenario_s3.html` |
| Combined | `results/neom_scenarios/sharma_camp26_r5km/maps/scenarios_combined.html` |

---

## Validation

Script: `scripts/validate_neom_scenarios.py`
Result: **58 PASS, 0 FAIL, 5 SKIP** (skips = snrl not importable locally)
Output: `results/neom_scenarios/sharma_camp26_r5km/qa/validation_results.json`

Checks include: branch ancestry, B0 integrity, config existence and loading, scenario-specific metrics, cross-scenario origin consistency, Abha config parameter parity, and no-unrelated-output verification.

---

## Mismatches and Notes

1. **No mismatch found** — all four scenarios translate cleanly from Abha event-hotspot methodology.
2. **CRS difference**: Abha uses EPSG:32638 (UTM 38N); NEOM uses EPSG:32636 (UTM 36N). This is expected for different longitudes and is handled in the configs.
3. **S3 undirected limitation**: same as Abha — the Madina backend treats edges as undirected, so S3 requires two separate runs (entry/exit) rather than one directional run.
4. **Demand weights**: set to uniform 1.0 as in Abha. Real demand data is not yet available.

---

## Ibex Commands

```bash
# Setup
module load cuda/12.1 python/3.11
source ~/snrl-env/bin/activate
cd ~/traffic
git checkout neom-scenarios-existing-methodology
export SNRL_MASK_WORKERS=8
export PYTHONIOENCODING=utf-8

# Validate scenarios
python scripts/validate_neom_scenarios.py

# Run B0
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_b0.yaml \
  --scenario B0

# Run S1
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_s1.yaml \
  --scenario S1

# Run S2
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_s2.yaml \
  --scenario S2

# Run S3 (two runs)
python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_s3_entry.yaml \
  --scenario S3_entry

python scripts/run_abha_event_hotspot_madina.py \
  --config configs/neom_scenarios/city_madina_neom_s3_exit.yaml \
  --scenario S3_exit
```
