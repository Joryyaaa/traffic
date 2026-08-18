# NEOM Baseline B0: Sharma / Camp 26 (r = 5 km)

## Identity

| Field | Value |
|---|---|
| Baseline ID | `NEOM_B0_sharma_camp26_r5km` |
| Candidate | A (Sharma / Camp 26) |
| Center | 28.03066 N, 35.24203 E |
| Radius | 5,000 m |
| OSM snapshot | `2026-08-18T22:55:19Z` |
| Frozen date | 2026-08-18 |
| Branch | `neom-baseline-sharma-camp26-r5km` |
| CRS | EPSG:32636 (UTM 36N) |

## Anchors

| Name | Lat | Lon | OSM ID | Type |
|---|---|---|---|---|
| Sharma | 28.0306558 | 35.242029 | 5796927641 | village |
| Camp 26 | 28.0809225 | 35.214663 | 12390325515 | camp |
| Const Camp W1 | 28.019137 | 35.188786 | 849104049 | construction camp |
| Const Camp W2 | 28.006535 | 35.188342 | 849118868 | construction camp |

## Network

| Metric | Full B0 | Sim-ready (largest component) |
|---|---|---|
| Ways | 278 | 274 |
| Segments | 2,424 | 2,398 |
| Nodes | 2,274 | 2,247 |
| Connected components | 5 | 1 |
| Largest component | 2,247 (98.8%) | 2,247 (100%) |

### Highway classes (full B0)

| Class | Ways |
|---|---|
| service | 134 |
| construction | 36 |
| residential | 34 |
| trunk | 27 |
| track | 15 |
| trunk_link | 10 |
| unclassified | 9 |
| tertiary | 5 |
| footway | 4 |
| secondary | 3 |
| rest_area | 1 |

## Features

| Feature | Count |
|---|---|
| Buildings | 303 |
| Residential buildings | 17 (dormitory) |
| Amenities | 83 |
| Construction zones | 12 |
| Landuse areas | 34 |
| Places | 3 |

### Building types

dormitory 17, commercial 5, hospital 5, industrial 6, generic 270

### Amenity types

shelter 61, parking 17, hospital 2, fuel 1, car_rental 1, place_of_worship 1

## Origins and Destinations

| | Count | Composition |
|---|---|---|
| Origins | 21 | 17 residential buildings + 1 village + 1 camp + 2 construction camps |
| Destinations | 111 | 12 construction sites + 83 amenities + 16 workplaces |

## File Layout

```
data/neom_baseline/sharma_camp26_r5km/
  streets.geojson                    # Full frozen street network (278 ways)
  streets_largest_component.geojson  # Simulation-ready subset (274 ways)
  buildings.geojson                  # All 303 buildings
  residential.geojson                # 17 residential buildings
  construction.geojson               # 12 construction landuse areas
  amenities.geojson                  # 83 amenity points
  landuse.geojson                    # 34 landuse polygons
  origins.geojson                    # 21 trip origin points
  destinations.geojson               # 111 trip destination points
  places.geojson                     # 3 OSM place nodes
  qa.json                           # QA validation with all counts
  provenance.json                   # Source provenance and query details

results/neom_baseline/sharma_camp26_r5km/
  baseline_map.html                 # Interactive Leaflet map

configs/neom_baseline/
  city_madina_neom_b0.yaml          # Madina config (uses sim-ready network)

docs/neom_baseline/
  NEOM_BASELINE_B0.md               # This document
```

## Simulation-Ready Network Derivation

The simulation-ready network (`streets_largest_component.geojson`) is derived from the full B0 network by keeping only ways that touch the largest BFS-connected component (2,247 of 2,274 nodes, 98.8%). Four minor disconnected fragments (12, 7, 6, and 2 nodes) are excluded.

The full B0 (`streets.geojson`) preserves all 278 ways and all 5 components for audit and reproducibility.

## Immutability

This B0 baseline is frozen. Future scenarios (S1, S2, ...) operate on localized sub-areas within this fixed 5 km extent. The baseline files must not be modified after the freeze date.

## Next Steps

To build scenarios from this frozen B0:

```bash
python scripts/evaluate.py --config configs/neom_baseline/city_madina_neom_b0.yaml --episodes 3
```

This will load the simulation-ready network into Madina and run a baseline evaluation. Scenario configs (S1, S2, ...) should reference the same frozen data files and modify only the `action` and `reward` sections.

## Important OSM IDs

Sample way IDs (first 10 of 278): 131685204, 131685212, 131685220, 131685223, 131685243, 167516514, 167516516, 167516517, 167516540, 267542668
