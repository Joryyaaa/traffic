# Stage 2: new COMBINED configs + Stage 3: fresh zone_builder benchmarks

## Stage 2: config derivation

Each new config is the scenario's EXISTING config
(`configs/city_madina_abha_<scenario>.yaml`) with exactly these changes,
verified by inspection to be the only diff:

1. `reward.min_zone_size`: 2 (or the config's original value) -> **1**.
2. `include_adjacency_state: true` added at the top level (was absent).
3. `action.max_closures` / `action.episode_length`: re-measured fresh under
   the new `min_zone_size=1` setting (see Stage 3 below) -- never reused
   from the old `min_zone_size=2/3` config or guessed from a ratio.

Everything else -- `network.*` (streets/origins/destinations paths,
`origin_weight` column name, `respect_oneway`, `crs`, `node_snapping_tolerance`),
`simulation.*`, and every `action`/`reward` field other than the three above
-- is byte-identical to the original scenario config and to
`configs/city_madina_ablation_r400_gat_mzs1.yaml` (the COMBINED reference),
confirmed programmatically in Stage 4.

New config files (all in `configs/`):

| Scenario | New config | Segments |
|---|---|---|
| Art Street / Al-Muftaha baseline | `city_madina_abha_art_street_baseline_combined.yaml` | 57 |
| Central Market | `city_madina_abha_central_market_combined.yaml` | 82 |
| Asir Central Hospital | `city_madina_abha_asir_central_hospital_combined.yaml` | 96 |
| King Abdulaziz Grand Mosque | `city_madina_abha_king_abdulaziz_grand_mosque_combined.yaml` | 87 |

## Stage 3: fresh zone_builder benchmarks under min_zone_size=1

Measured with `scripts/evaluate.py`'s `zone_builder_policy` run to
completion via `run_policy` (same hand-coded planner used as the benchmark
throughout this project's lineage, e.g. the Riyadh scale-up study), NOT
reused from the old `min_zone_size=2/3` numbers even where the final value
happens to coincide -- every number below was computed from scratch against
the new config.

### Art Street / Al-Muftaha baseline (57 segments)

No prior real budget exists for this scenario -- its original config
deliberately used `max_closures=0/episode_length=1` (a fully-open
no-intervention comparison case, not a training budget). Budget search from
scratch:

| max_closures | episode_length | zone_builder return |
|---|---|---|
| 6 | 15 | **+0.4657** |
| 5 | 12 | +0.4657 (identical) |
| 8 | 20 | +0.2313 (worse -- extra closures start hurting) |

**Accepted: max_closures=6, episode_length=15 -> +0.4657**

### Central Market (82 segments)

| max_closures | episode_length | zone_builder return |
|---|---|---|
| 4 | 10 | **+0.8363** |

First candidate (identical to the original mzs=2 budget) already positive
and matches the network's known headroom -- accepted on the first try, no
further search needed. Coincidentally equal to the original mzs=2 value;
independently re-computed, not copied.

**Accepted: max_closures=4, episode_length=10 -> +0.8363**

### Asir Central Hospital (96 segments)

The original mzs=2 budget (3/8) reproduces a negative return under mzs=1 too
-- this scenario's intervention budget is genuinely constrained, not an
artifact of the old reward setting:

| max_closures | episode_length | zone_builder return |
|---|---|---|
| 3 | 8 (original budget) | -0.4173 (rejected) |
| 1 | 3 | +0.1383 |
| 2 | 5 | +0.1383 (identical) |
| 3 | 6 | -0.4173 (rejected -- same failure point as the original) |

**Accepted: max_closures=2, episode_length=5 -> +0.1383** (2 chosen over 1 to
give the training agent one extra legal move without losing return).

### King Abdulaziz Grand Mosque (87 segments)

| max_closures | episode_length | zone_builder return |
|---|---|---|
| 2 | 5 (original budget) | +0.0503 |
| 3 | 8 | +0.0503 (identical) |

**Accepted: max_closures=2, episode_length=5 -> +0.0503** (smallest budget
reaching the plateau; matches the original mzs=2 value, independently
re-confirmed under mzs=1, not reused).

## Summary table (Stage 3 deliverable)

| Scenario | Segments | max_closures | episode_length | zone_builder (mzs=1) |
|---|---|---|---|---|
| Art Street / Al-Muftaha baseline | 57 | 6 | 15 | +0.4657 |
| Central Market | 82 | 4 | 10 | +0.8363 |
| Asir Central Hospital | 96 | 2 | 5 | +0.1383 |
| King Abdulaziz Grand Mosque | 87 | 2 | 5 | +0.0503 |

All four positive -- all four proceed to Stage 4/5.
