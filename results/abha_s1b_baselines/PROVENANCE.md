# Abha S1B Baseline Results — King Abdulaziz One-Way SW

**Config:** `configs/city_madina_abha_s1b.yaml`
**Network:** 4,573 directed segments (S0 minus 13 NE-bearing King Abdulaziz segments)
**Intervention:** Close all NE-bearing segments of King Abdulaziz Road (bearing ~45°),
keeping only the SW-bearing direction (~225°)

## Data construction

Built by `scripts/build_abha_s1_env_data.py`:
1. Read S0 streets.geojson (4,586 segments)
2. Read `data/abha_baseline/s1b_king_abdulaziz.geojson` (29 King Abdulaziz segments)
3. Remove 13 segments where `road_open=False` (NE-bearing, closed in S1B)
4. Result: 4,573 segments

Closed segment IDs: 3, 209, 210, 1009, 1198, 1435, 3629, 3682, 3895, 3901, 4044, 4242, 4246

## Baseline simulation metrics (no additional closures beyond the scenario)

From `scripts/baseline_report.py`:
- mean_access: 1.301
- total_flow: 22,232.5
- trip_dist_m: 774.9
