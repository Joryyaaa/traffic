# Stage 2: three frozen datasets + configs

Al Nakheel center (24.7412, 46.6335) throughout -- same as the r400 GAT/COMBINED
reference and every prior size point in this project's lineage. Fetched via
`scripts/fetch_osm_data.py`, unmodified.

## Final radii and actual segment counts

Radius selection needed iteration -- Overpass API had a persistent multi-hour flaky
window during this stage (documented below); final radii landed almost exactly on
target once a working attempt went through:

| target | radius tried | segments | residential | amenities | notes |
|---|---|---|---|---|---|
| ~150 | 430m | 101 | 64 | 13 | too low, tried again |
| ~150 | **445m** | **176** | 65 | 15 | **adopted** |
| ~300 | **630m** | **290** | 117 | 33 | **adopted**, succeeded on 1st attempt after a retry-loop reset |
| ~600 | 950m | 733 | -- | -- | too high, tried a closer radius instead |
| ~600 | **850m** | **599** | 277 | 42 | **adopted**, near-exact match |

Data saved to `data/raw/riyadh_r445/`, `data/raw/riyadh_r630/`, `data/raw/riyadh_r850/`
(gitignored, same as every other scenario's data in this project).

## Budgets: measured against zone_builder, not derived from a ratio

Same methodology as `results/large_30k_fixed/PROVENANCE.md` (where a naive
10%-of-network guess produced a negative return at 386 segments) and
`results/scale_sweep_prep/PROVENANCE.md`. `min_zone_size=1` is fixed for every size
per instruction; only `max_closures`/`episode_length` (the budget) varies, and each
was checked with `scripts/evaluate.py --policies zone_builder` before being accepted:

| segments | first candidate | result | accepted budget | result |
|---|---|---|---|---|
| 176 | max_closures=10, ep_len=25 | **+0.8111** (accepted on 1st try) | 10 / 25 | +0.8111 |
| 290 | max_closures=11, ep_len=28 | **-0.1145** (rejected -- negative) | **8 / 20** | **+0.6115** |
| 599 | max_closures=14, ep_len=35 | **+0.4636** (accepted on 1st try) | 14 / 35 | +0.4636 |

The 290-segment point is the one that actually needed correction -- its first
candidate reproduced the exact failure mode this project already documented once
before (budget too large relative to what the network can support without the
closure cost swamping the zone bonus). Read honestly: budget does not scale
monotonically with segment count in this lineage (89->9, 176->10, 290->**8**,
386->12, 599->14) -- 290 needing a *smaller* budget than both its smaller (176) and
larger (599) neighbors is a real, measured result, not a typo. This reinforces why
every budget in this project is measured per-network rather than assumed from a
formula.

## Comparability to the r400 GAT/COMBINED reference

Every new config is `configs/city_madina_ablation_r400_gat_mzs1.yaml` with ONLY
`network.streets_path/origins_path/destinations_path` and
`action.max_closures/episode_length` changed. `min_zone_size=1`,
`include_adjacency_state: true`, all other reward weights, `simulation` block, and
`crs: EPSG:32638` are byte-identical across all four configs (r400 reference + 3
new sizes) -- confirmed by inspection, not assumed (Stage 3 re-confirms this
programmatically).

## Connectivity, CRS, OD counts

- CRS: `EPSG:32638` (UTM 38N) for all three, same as every other Riyadh scenario --
  correct for this longitude regardless of radius.
- Connectivity: all three networks loaded and simulated successfully via
  `StreetNetworkEnv`/`MadinaBackend` (implicit connectivity check --
  `zone_builder` completed full episodes without a disconnection-triggered
  termination on any of them). Stage 3 re-confirms this explicitly per-network.
- OD counts: see table above (residential = origins, amenities = destinations).
  Both grow with radius as expected, no zero-origin/zero-destination scenario like
  the Al Olaya commercial-core case this project already hit once.

## Environment reliability note (not a data problem, but worth recording)

Overpass API round-tripped through ~9 consecutive connection failures across the
630m and 950m attempts (both the primary `overpass-api.de` endpoint and the
`overpass.kumi.systems` mirror), before a fresh retry succeeded immediately -- same
class of transient backend flakiness documented in
`notes/2026-08-06-street-duplication.md` section 8. A bounded retry loop (3-6
attempts, 180-240s apart) resolved it without manual intervention each time.

Separately, evaluating the r445 config specifically inside the
`gat-scaleup-riyadh` git worktree (`../traffic-gat-scaleup`) crashed silently
(exit 127, no Python traceback) 7 times in a row at/after environment
construction, while the exact same config+data run from the main working tree
(`C:\Users\جوري\traffic`) succeeded immediately and reproducibly. Not a data or
config problem -- isolated to that specific worktree's process environment (cause
undetermined; possibly related to this session's very high count of concurrently-
created git worktrees on this filesystem). Working pattern adopted for the rest of
this task: git operations (commit/push) happen in the isolated worktree, but any
heavy Madina/geopandas computation runs from the main working tree, with inputs/
outputs copied across as needed. Flagging in case it recurs for Stage 3/4 work too.
