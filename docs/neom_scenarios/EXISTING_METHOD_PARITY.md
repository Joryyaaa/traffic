# Existing Scenario Methodology: Inspection Report

**Date**: 2026-08-19
**Purpose**: Reconstruct the exact B0/S1/S2/S3 scenario logic from the repository before porting to NEOM.

---

## Source Files Inspected

| File/Branch | Role |
|---|---|
| `configs/city_madina_abha_event_b0.yaml` | B0 config |
| `configs/city_madina_abha_event_s1.yaml` | S1 config |
| `configs/city_madina_abha_event_s2.yaml` | S2 config |
| `configs/city_madina_abha_event_s3_entry.yaml` | S3 entry config |
| `configs/city_madina_abha_event_s3_exit.yaml` | S3 exit config |
| `scripts/build_abha_event_hotspot_data.py` | Scenario data builder (HTML-based) |
| `scripts/build_abha_event_osm_network.py` | OSM-based network builder |
| `scripts/run_abha_event_hotspot_madina.py` | Scenario runner |
| `results/abha_event_hotspot_madina/*.json` | Scenario results |
| `data/abha_event_hotspot_osm/qa_report.json` | OSM build QA |
| `src/snrl/env.py` | RL environment (mask workers) |
| `src/snrl/backends/madina_backend.py` | Madina backend (mask workers) |
| `ABHA_HOTSPOT_SCENARIOS.md` | Scenario documentation |
| Branch `abha-event-hotspot-ibex` | Latest event hotspot work |
| Branch `codex/abha-hotspot-scenarios` | Named-site hotspot work |
| Branch `origin/mentor/sweep-harness` | Mentor's changes |

---

## 1. Exact B0 Definition

**B0 = Baseline (no intervention)**

- **Network**: full street network, all roads open (`event_baseline_streets.geojson`)
- **Origins**: reference demand points (`event_reference_origins.geojson`)
- **Destinations**: event zone centroid (`event_zone_destinations.geojson`)
- **Closures**: `max_closures: 0` -- pure evaluation, no road closures
- **Closure mode**: `rebuild` (not `penalize`)
- **Purpose**: measure baseline accessibility and flow distribution before any intervention

Config differences from other scenarios: none except the data paths.

## 2. Exact S1 Definition

**S1 = Event Zone Vehicle Restriction**

- **Network**: MODIFIED -- roads belonging to the closure way (OSM way ID 95507294) are REMOVED from the street GeoJSON (`event_s1_restricted_streets.geojson`)
- **Origins**: SAME as B0
- **Destinations**: SAME as B0 (event zone)
- **Effect**: vehicles can no longer traverse the restricted zone; they must detour around it
- **Implementation**: the builder filters out features whose `properties.id` matches the closure way ID

In the OSM builder: `edges[~mask]` where mask identifies rows whose `osmid` contains the closure way ID.

Result: B0 had 90 segments (HTML) / 7114 segments (OSM); S1 had 89 segments (HTML) / 7104 segments (OSM). The difference is the closure road's segments.

## 3. Exact S2 Definition

**S2 = Main Parking Hub**

- **Network**: SAME as B0 (all roads open)
- **Origins**: SAME as B0
- **Destinations**: CHANGED -- parking hub point P (`event_parking_destination.geojson`) instead of event zone
- **Effect**: vehicles drive to the parking facility, not the event zone. The "last mile" from parking to event is pedestrian (not modeled by Madina)
- **Implementation**: only the `destinations_path` config line changes

## 4. Exact S3 Definition

**S3 = Managed Entry/Exit**

- **Network**: SAME as B0
- **Two separate Madina runs** (because backend is undirected):
  - **Entry run**: origins = B0 reference origins, destination = managed entry point (nearest endpoint of entry way to event zone)
  - **Exit run**: origin = event zone centroid, destination = managed exit point (farthest endpoint of exit way from event zone)
- **Key OSM way IDs**: entry way 787786457, exit way 135229579
- **Implementation**: `outer_endpoint()` function finds the point on the entry/exit way that is farthest from the event zone centroid (in projected coordinates)

## 5. What the Mentor Changed

From `ABHA_HOTSPOT_SCENARIOS.md` and the code:

1. **Batched action mask with 8-worker parallelism** (`SNRL_MASK_WORKERS`)
2. **Exact one-way drive-network support** (directed Madina backend)
3. **Exact indexed directed-graph rebuild** (61x speedup on full Abha belt)
4. **Sweep harness** (branch `mentor/sweep-harness`)

These are ALL infrastructure/performance optimizations. None modify scenario semantics, demand design, or origins/destinations.

## 6. What "8 Workers" Means

**"8 workers" = `SNRL_MASK_WORKERS=8`**

This is an environment variable that controls the number of parallel processes used to compute the action mask (connectivity check) during RL training.

From `src/snrl/env.py` lines 33-46:
```python
def _mask_workers() -> int:
    """Processes to fan the action-mask connectivity batch across.
    Defaults to 1. Measured on Abha S0:
    1 worker 16.5s, 8 workers 4.8s, stops improving past 8."""
    n = int(os.environ.get("SNRL_MASK_WORKERS", "1") or 1)
    return max(1, n)
```

## 7. How 8 Workers Are Represented

- **NOT** origins, agents, demand points, weights, or repeated workers
- **It is**: a `multiprocessing.Pool` of 8 fork workers that each evaluate connectivity for a chunk of candidate actions
- **Where the number 8 enters**: `SNRL_MASK_WORKERS=8` in Slurm sbatch scripts
- **All scenarios use the same worker count**: yes, it's an environment-level setting
- **Worker origins**: N/A -- these are CPU processes, not simulation agents
- **Destinations**: N/A
- **Weights/multipliers**: N/A

## 8. How Origins and Destinations Are Selected

### Event Hotspot (B0/S1/S2/S3):

**Origins** (`build_abha_event_hotspot_data.py` lines 92-106):
- 3 provisional points placed at bounding-box extremes (north, south, east/west) of the street network endpoints
- `demand_weight: 1.0` each
- Labeled `demand_type: "provisional_reference"`
- NOT measured traffic counts

**Destinations**:
- B0/S1: event zone centroid point Z, `destination_weight: 1.0`
- S2: parking hub point P, `destination_weight: 1.0`
- S3 entry: nearest endpoint of entry way to event zone
- S3 exit: farthest endpoint of exit way from event zone

### Named-site hotspots (build_abha_hotspot_data.py):

**Origins**: residential buildings from OSM within the crop radius, weight = `residents` proxy
**Destinations**: amenities from OSM within the crop radius, weight = `floor_area` proxy
**Intervention targets**: nearest non-major road segments to the POI center

## 9. Parking/Hub Logic

S2 replaces the event zone destination with a parking hub point P. The street network stays the same -- only the destination changes. The parking hub is defined by coordinates (Abha: 42.49902, 18.21418). Vehicles are routed to the parking facility; the pedestrian segment is outside the model.

## 10. Entry/Exit Management

S3 splits the traffic flow into two separate directional assignments:
- **Entry**: residential areas → managed entry gate (on the approach road)
- **Exit**: event zone → managed exit gate (on the departure road)

The split is necessary because Madina's current backend is undirected. Each assignment is a separate Madina run. The entry gate point is the endpoint of the entry way nearest to the event zone; the exit gate is the endpoint of the exit way farthest from the event zone.

## 11. What Files Each Scenario Changes Relative to B0

| Scenario | Streets | Origins | Destinations |
|---|---|---|---|
| B0 | baseline | reference | event zone |
| S1 | **MODIFIED** (closure roads removed) | reference | event zone |
| S2 | baseline | reference | **CHANGED** (parking hub) |
| S3 entry | baseline | reference | **CHANGED** (entry gate) |
| S3 exit | baseline | **CHANGED** (event zone origin) | **CHANGED** (exit gate) |

## 12. What Must Remain Identical Between Scenarios

- Simulation parameters: `search_radius`, `detour_ratio`, `decay`, `beta`, `num_cores`
- Action parameters: `action_type`, `closure_mode`, `max_closures`, `episode_length`
- Reward weights (all identical in the event hotspot configs)
- CRS projection
- `node_snapping_tolerance`
- Seed
- The baseline street network is shared by B0, S2, S3; only S1 modifies it

---

## NEOM Translation Plan

### Geographic equivalents in frozen B0:

| Abha concept | NEOM equivalent | Frozen B0 feature |
|---|---|---|
| Event zone | Construction/work site area | `construction.geojson` (12 zones) |
| Residential origins | Worker camps + residential buildings | `origins.geojson` (21 points) |
| Event zone destination | Worksite destination | Largest construction zone centroid |
| Parking hub P | Camp 26 / staging area | Camp 26 anchor coordinates |
| Entry way | Main approach road from camps to site | Trunk road serving construction area |
| Exit way | Main departure road from site outward | Trunk road leading away from construction |
| Closure road | Road through construction zone to restrict | Service/residential roads in construction area |

### NEOM-specific adaptation notes:

1. **Origins**: Use the 21 frozen origin points (17 residential buildings + 4 anchors) instead of provisional bounding-box extremes. This is BETTER data than the Abha event hotspot's provisional origins.
2. **Destinations**: Use construction zone centroids from `construction.geojson` instead of a single event zone point.
3. **Closure roads (S1)**: Select service/residential roads within or adjacent to a major construction zone in the frozen B0.
4. **Parking hub (S2)**: Camp 26 (NRC-26) at 28.0809, 35.2146 is the natural parking/staging hub.
5. **Entry/exit (S3)**: Trunk roads (27 trunk ways in the B0) serve as managed entry/exit corridors.

### Potential mismatches:

- Abha event hotspot had 3 provisional origin points; NEOM has 21. This is a data improvement, not a semantic mismatch.
- Abha had a single event zone centroid destination; NEOM has 12 construction zones. We should pick the primary one for parity.
- The `origin_weight` and `destination_weight` attribute names may need adjustment based on what the frozen GeoJSON contains. The Abha event configs use `demand_weight`/`destination_weight`; the NEOM B0 config uses `residents`/`floor_area`. The scenario configs must use attribute names that exist in the actual GeoJSON files.
