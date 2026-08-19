# Stage 1: existing network-generation infrastructure, and radius selection

## Infrastructure (already exists, reused unchanged)

- **`scripts/fetch_osm_data.py`** — pulls a street network + residential/amenity layers
  from OSM for a given `--lat/--lon/--radius`, dedupes bidirectional edges (fix `b138dba`),
  writes `data/raw/<out>/{streets,residential,amenities}.geojson`. This is the exact tool
  that produced every scenario in this project's lineage (Al Nakheel at every radius,
  Jeddah, Abha). No changes needed or made.
- **Existing Al Nakheel radius points** (same center throughout: 24.7412, 46.6335), from
  this project's own prior work, real not assumed — `results/scale_sweep/PROVENANCE.md`
  and `results/scale_sweep_prep/PROVENANCE.md`:

| radius | segments |
|---|---|
| 250m | 26 |
| 400m | 89 (the COMBINED experiment's own network) |
| 460m | 186 |
| 500m | 226 |
| 600m | 269 |
| 700m | 386 |

Street density grows faster than linearly with radius in this area (89->186 is +97
segments over +60m, 500->700 is +160 over +200m) -- not uniform, so new radii for ~150,
~300, ~600 segments need their own empirical check, not a formula. Chosen starting points,
interpolating/extrapolating from the table above:

- **~150 segments**: between 400m (89) and 460m (186) -> try **430m**
- **~300 segments**: between 500m (226) and 700m (386) -> try **630m**
- **~600 segments**: beyond 700m (386); the 500->700 growth rate (+160/+200m) extrapolated
  forward suggests **~950-1000m**, tried as **950m** first

All three use the *same* Al Nakheel center as every prior size point and the COMBINED
89-segment experiment itself, so size is isolated from city/demand/street-morphology --
same principle `results/scale_sweep_prep/PROVENANCE.md` already established, carried
forward unchanged.

## Comparability across the three new configs and the r400 GAT reference

Every new config will be built from `configs/city_madina_ablation_r400_gat_mzs1.yaml`
(the exact COMBINED config) changing ONLY: `network.streets_path/origins_path/
destinations_path` (new data dir) and `action.max_closures`/`reward.min_zone_size`... no --
`min_zone_size` stays 1 (fixed, per instruction), only `max_closures`/`episode_length` (the
budget) is size-dependent and must be MEASURED per size via `zone_builder`, not derived
from a fixed ratio -- same methodology as `results/scale_sweep_prep/PROVENANCE.md` and
`results/large_30k_fixed/PROVENANCE.md` (where a naive 10%-of-network guess was shown to
break down at 386 segments). `include_adjacency_state: true` stays on, all reward weights
other than the budget-dependent pair stay identical to the r400 control. This keeps every
new config comparable to the 89-segment reference on everything *except* what's
intentionally varying (size, and the budget that must scale with it).

## What Stage 1 does NOT yet know (measured in Stage 2)

- Exact achieved segment counts at 430m/630m/950m (radius targets are starting guesses,
  to be corrected empirically, same as every prior radius pick in this lineage)
- Measured `max_closures`/`min_zone_size`-appropriate-episode_length per size (Stage 2)
- Independently-measured `zone_builder` benchmark per size (Stage 5, per instruction not
  to reuse 0.6863 on larger networks blindly)

## Connectivity / CRS / OD counts

Not assumed constant -- reported per config once fetched (Stage 2/3), same as every prior
scenario in this project (`fetch_osm_data.py` reports residential/amenity counts on fetch;
`StreetNetworkEnv` construction reports `n_components`/connectivity via
`backend.is_connected()`, exercised directly in Stage 3's validation). CRS is fixed at
`EPSG:32638` (UTM 38N) for all Al Nakheel scenarios regardless of radius -- same zone
already used by every other Riyadh config in this project, correct for this longitude
(~46.7E), not radius-dependent.
