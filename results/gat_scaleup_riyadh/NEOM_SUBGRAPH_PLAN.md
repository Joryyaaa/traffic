# Plan: NEOM subgraph experiment (~150-300 segments), same COMBINED setup, trained from scratch

Written as a plan, per instruction -- nothing below has been executed or committed as
runnable code/config yet.

## What's already frozen and usable (found by inspection, not assumed)

Branch `neom-baseline-sharma-camp26-r5km`, commit `413b707` ("freeze NEOM B0 baseline
data") + `0ac7a86` (config/docs). Real, already-fetched, already-documented:

- **`data/neom_baseline/sharma_camp26_r5km/streets_largest_component.geojson`** --
  2,398 segments (274 of 278 ways touch the largest connected component, 98.8% of
  nodes), single connected component by construction (4 disconnected fragments of
  12/7/6/2 nodes already excluded).
- **Center:** Sharma village, 28.0306558N / 35.242029E. Also anchored: Camp 26,
  2 construction camps. **CRS: EPSG:32636 (UTM 36N)** -- correct for this longitude,
  already verified (NEOM spans multiple UTM zones; this is NOT Riyadh's 32638).
- **Origins/destinations (full 5km extent):** 21 origins (17 residential/dormitory
  buildings + village + camp + 2 construction camps), 111 destinations (12
  construction sites + 83 amenities + 16 workplaces) -- already thin at 5km radius,
  worth flagging before scoping down further (see Step 1 below).
- **Existing config:** `configs/neom_baseline/city_madina_neom_b0.yaml` -- uses the
  frozen sim-ready network directly, but with `min_zone_size=3` (not 1) and
  `max_closures=6`/`episode_length=15` (not measured against `zone_builder` on this
  network, and not the COMBINED setup at all -- no `include_adjacency_state`, plain
  5-feature MLP config, not GAT). Not reusable as-is for this experiment; a new
  config is needed, built the same way `city_madina_ablation_r445/r630/r850_gat_mzs1.yaml`
  were built from the r400 GAT/COMBINED reference in this task.
- **Immutability policy** (`docs/neom_baseline/NEOM_BASELINE_B0.md`): "This B0
  baseline is frozen... must not be modified after the freeze date." **This plan
  does not modify any frozen file** -- see Step 1.

2,398 segments is ~27x the r400/89-segment reference and above even this task's
largest Riyadh point (599). The mentor's ask is ~150-300 segments -- a spatial
subgraph of the frozen network, not the full B0 extent.

## Step 1: derive a ~150-300 segment subgraph WITHOUT touching the frozen files

Same relationship `streets_largest_component.geojson` already has to `streets.geojson`
(a derived, spatially/topologically filtered subset, source untouched) -- apply a
smaller radius clip around one of B0's own anchor points to the *already-frozen*
`streets_largest_component.geojson`, entirely offline (geopandas spatial filter, no
new OSM query, no live network fetch). Candidate anchors, in order of promise:

- **Sharma village center** (28.0306558, 35.242029) -- the B0 baseline's primary
  anchor; likely the densest residential area, best origin count at a smaller radius.
- **Camp 26** (28.0809225, 35.214663) -- second anchor, worth checking as an
  alternative if Sharma's smaller-radius subgraph turns out too origin-poor.

Radius needs the same empirical approach as this task's Riyadh points (Stage 1/2):
try a candidate (e.g. 800-1000m, extrapolating from Riyadh's own ~150-segment radius
being 445m in a denser urban grid -- NEOM's road network here is sparser/more
service-road-heavy per B0's highway-class breakdown, so likely needs a larger radius
for the same segment count), measure actual segment/origin/destination counts, adjust.

**Critical pre-check before building any config:** run
`scripts/check_zone_feasibility.py` (already exists in this project, built exactly
for this) against the candidate subgraph immediately after clipping it -- B0's full
5km extent already has only 21 origins/111 destinations; a ~150-300 segment slice of
it could plausibly have too few qualifying destinations to make a pedestrian-zone
bonus reachable at all (the same failure mode `configs/city_madina.yaml`'s Al Olaya
0-residential-buildings case and this project's Abha scenario both hit). If the best
available anchor/radius combination fails this check, that is itself the answer
worth reporting back before writing any Slurm harness -- not a reason to lower the
bar or substitute synthetic demand.

## Step 2: config, built the same way as this task's 3 Riyadh configs

Derive from `configs/city_madina_ablation_r400_gat_mzs1.yaml` (the COMBINED
reference), changing:
- `network.streets_path/origins_path/destinations_path` -> the new NEOM subgraph
  files from Step 1
- `network.crs` -> `EPSG:32636` (NOT 32638 -- this is the one field that must differ
  from every Riyadh config, per B0's own documented CRS warning)
- `action.max_closures`/`episode_length` -> MEASURED against `zone_builder` on the
  actual NEOM subgraph (same methodology as every budget in this task -- the r630
  case already showed a naive guess can score negative; no reason to assume NEOM's
  different demand/street-morphology pattern is safer to guess on)

Everything else identical to every config in this lineage: `min_zone_size: 1`,
`include_adjacency_state: true`, same reward weights, same GAT architecture
(unmodified `seed_sweep_gat.py` defaults).

## Step 3: independently measure zone_builder on the NEOM subgraph

Same reason as every size in this task: NEOM's demand pattern (construction camps
and worker housing, not a residential neighborhood) is different enough from Riyadh
that reusing any Riyadh benchmark -- 0.6863, 0.8111, 0.6115, or 0.4636 -- would repeat
exactly the mistake this task was told not to make for the Riyadh sizes, just against
the wrong city instead of the wrong size.

## Step 4: validate, same Stage 3 pattern

Reuse `scripts/validate_gat_scaleup_datasets.py`'s structure (or extend its
`CONFIGS` list) to confirm action_space.n == n_segments+1, observation shape,
connectivity, and a real GAT forward pass on the NEOM subgraph's actual adjacency,
before any Slurm harness is written.

## Step 5: Slurm screening (5 seeds), same Stage 4 pattern, trained from scratch

Per the architecture-audit conclusion from earlier in this session: zero-shot
transfer of an r400-trained (or any Riyadh-trained) checkpoint to NEOM is not
possible (the SB3 categorical action head is fixed to that network's own
`n_segments+1` at construction time) -- this was never going to be transfer
learning, and isn't proposed as such here. A dedicated `slurm/gat_neom_<radius>.sbatch`,
same PROJECT_DIR/PYTHONPATH/output-guard/data-presence-check pattern as the three
Riyadh scripts, `--array=1-5`, its own output root (e.g. `runs/gat_neom_<radius>_5seed`),
guarded against every Riyadh experiment's output directory too.

## Step 6: extend the aggregation table

Add the NEOM point to `scripts/aggregate_gat_scaleup.py`'s `ZONE_BUILDER_BY_SEGMENTS`
once Step 3's benchmark is measured, so the same comparison script covers Riyadh
(4 points) and NEOM (1 point) side by side without a second parallel tool.

## Open question worth flagging now, not after building the harness

B0's own highway-class breakdown (134 service, 36 construction, 34 residential, 27
trunk, 15 track roads out of 278 total ways) suggests this network's *character* is
closer to an industrial/construction-logistics network than a residential
neighborhood -- `w_pedestrian_zone` and the whole pedestrian-zone reward mechanism
was designed and validated on residential street grids (Al Nakheel, Jeddah, Abha).
Whether a "walkable plaza" bonus is even the right objective for a still-under-
construction industrial corridor is a modeling question worth the mentor's input
before Step 5's Slurm time is spent, separate from whether the technical pipeline
works.
