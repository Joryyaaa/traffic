# Abha S1A Baseline Results — King Abdulaziz One-Way NE

**Config:** `configs/city_madina_abha_s1a.yaml`
**Network:** 4,570 directed segments (S0 minus 16 SW-bearing King Abdulaziz segments)
**Intervention:** Close all SW-bearing segments of King Abdulaziz Road (bearing ~225°),
keeping only the NE-bearing direction (~45°)

## Data construction

Built by `scripts/build_abha_s1_env_data.py`:
1. Read S0 streets.geojson (4,586 segments)
2. Read `data/abha_baseline/s1a_king_abdulaziz.geojson` (29 King Abdulaziz segments)
3. Remove 16 segments where `road_open=False` (SW-bearing, closed in S1A)
4. Result: 4,570 segments

Closed segment IDs: 21, 59, 88, 1010, 1013, 1141, 1429, 1434, 2409, 2509, 3896, 3899, 3903, 3905, 4244, 4478

## Baseline simulation metrics (no additional closures beyond the scenario)

From `scripts/baseline_report.py`:
- mean_access: 1.303
- total_flow: 22,257.0
- trip_dist_m: 774.9
