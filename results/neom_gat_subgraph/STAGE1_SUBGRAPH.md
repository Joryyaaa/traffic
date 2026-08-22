# Stage 1: NEOM GAT subgraph construction

Script: `scripts/build_neom_gat_subgraph.py`
Output: `data/neom_gat_subgraph/sharma_dorm_r750/{streets,origins,destinations}.geojson` + `provenance.json`

## Source

- Branch: `origin/neom-scenarios-existing-methodology`
- Commit: `a816369cb1485746c91d39b58da63aba1aca74ed`
- Streets: `data/neom_scenarios/sharma_camp26_r5km/streets_madina_ready.geojson` (2,398 segments, verified by direct feature count)
- Origins: `data/neom_scenarios/sharma_camp26_r5km/B0/origins.geojson` (21 real points)
- Destinations: `data/neom_scenarios/sharma_camp26_r5km/B0/destinations.geojson` (12 real points)

## Method (reproducible, no OSM refetch, no synthesized geometry)

1. **Anchor**: centroid of the 17 real dormitory-building origins (the
   `origin_type == "residential_building"` subset of B0's 21 origins) =
   **28.0037929 N, 35.2039997 E**. This is the densest real residential
   cluster in the B0 extent, immediately adjacent to the western
   construction compound that S1's own closure roads sit in (per
   `NEOM_SCENARIOS_FINAL_REPORT.md`: "western cluster, ~28.01 N 35.19 E").
2. Reproject everything to EPSG:32636 (meters), buffer the anchor point by
   **750 m**, keep every street segment that spatially intersects the
   buffer.
3. Build a graph from segment endpoints (already 2-point segments in the
   Madina-ready source) and keep **only the largest connected component**
   -- a circular clip creates small disconnected fragments/dangling stubs at
   its boundary; dropping them is the exact same step this branch's own
   history already took once (`streets.geojson` -> `streets_largest_component.geojson`).
4. Keep real origins/destinations whose point falls within the same 750m
   buffer. No new demand points invented, no weights changed, no rows
   duplicated.

## Radius sweep (segment counts measured directly, not guessed)

| radius (m) | segments intersecting buffer | components | **largest-component segments** | origins in buffer | destinations in buffer |
|---:|---:|---:|---:|---:|---:|
| 600 | 255 | 8 | 206 | 17 | 7 |
| 650 | 272 | 6 | 206 | 17 | 7 |
| 700 | 290 | 5 | 250 | 17 | 7 |
| **750** | **318** | **5** | **273** | **17** | **7** |
| 800 | 344 | 2 | 304 | 17 | 7 |
| 850 | 348 | 3 | 307 | 17 | 7 |
| 1000 | 353 | 3 | 307 | 17 | 7 |

750 m was selected: comfortably inside the 150-300 target (273), full
destination coverage plateaus by 700m already (7 of the 12 real destinations
-- the other 5 are 4.8-10.2 km away, clearly a different part of the 5km
B0 extent), and the origin/destination count doesn't change between 700m
and 1000m, so 750m isn't a fragile choice sitting on a boundary.

## Real-data sanity check (not just "inside a circle")

Distance from every one of the real 21 origins / 12 destinations to the
**retained** (largest-component-only) street geometry:

- 17 dormitory origins: 11.1m - 58.1m (all immediately adjacent)
- 4 excluded origins (Sharma village, Camp26, 2 construction camps): 799m - 8,279m away -- correctly excluded, they belong to other parts of the 5km B0 extent
- 7 included destinations: 68m - 244m away
- 5 excluded destinations: 4.8km - 10.2km away -- correctly excluded

No origin/destination was included or excluded on an arbitrary circular-buffer technicality; every kept point is genuinely near the retained network, every dropped point is genuinely far from it.

## Verified exact segment count

```
$ python -c "import json; print(len(json.load(open('data/neom_gat_subgraph/sharma_dorm_r750/streets.geojson', encoding='utf-8'))['features']))"
273
```

Cross-checked independently with `geopandas.read_file(...)` -> `len(gdf) == 273`. Also re-verified inside `scripts/validate_neom_gat_subgraph.py` (Stage 4) by reading the raw JSON feature list directly, not trusting the filename/config comment.

**Final subgraph: 273 street segments, 17 origins, 7 destinations, EPSG:32636.**
