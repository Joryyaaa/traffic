# Provenance: Abha to Jabal Soudah Viewpoint, Ibex run

Jory's `optimized-abha-jabal-soudah-ibex` package, executed 2026-08-17 exactly
as `ABHA_JABAL_SOUDAH_IBEX.md` documents it: three Madina runs (full-belt city
context, Route 10, Route 2120) plus three cases derived from them.

Jobs 50606320 (city), 50606321 (corridor array), 50606322 (aggregate), all
COMPLETED. Validation run 50606359.

## Result

| Scenario | Method | Access | Access Gini | VKT proxy (km) | Trip distance (m) | Major-road flow | Unreachable |
|---|---|---:|---:|---:|---:|---:|---:|
| route10_reference | simulated | 0.190740 | 0.0000 | 10.554 | 55228.2 | 78.5% | 0.0% |
| route2120_reference | simulated | 0.228092 | 0.0000 | 11.326 | 49266.9 | 96.4% | 0.0% |
| khamis_viewpoint_baseline | derived | 0.209416 | 0.0446 | 21.881 | 52247.5 | 85.8% | 0.0% |
| combined_peak_1_5 | derived | 0.209416 | 0.0446 | 32.821 | 52247.5 | 85.8% | 0.0% |
| combined_peak_2_0 | derived | 0.209416 | 0.0446 | 43.761 | 52247.5 | 85.8% | 0.0% |
| current_full_belt | simulated | 1.080261 | 0.4799 | 143.207 | 795.6 | 1.7% | 9.6% |

Route 2120 is the better approach on every corridor measure: 19.6% higher mean
accessibility, 10.8% shorter mean trip, and it keeps 96.4% of its flow on
major roads against Route 10's 78.5%. Neither approach puts any flow on a
protected local street (0.0% both), which is what the corridor-restricted
network was built to guarantee.

`current_full_belt` is context only and is not comparable to the rows above
it: different origins, different destinations, a 800 m radius against 75 km.

## Runtime

Total compute for the whole package was **under one minute**.

| job | wall | setup | simulate |
|---|---:|---:|---:|
| city context (17,185 segments, 740 origins, 275 destinations) | 13 s | 1.9 s | 5.0 s |
| corridor Route 10 (3,123 segments) | 30 s | | 1.5 s |
| corridor Route 2120 | 9 s | | 0.8 s |
| derive + aggregate | 8 s | | |

Requested limits were 2 h / 30 min / 10 min, so nothing came close. Queue time
was the only meaningful wait, and it was seconds.

## Verification

`scripts/` output was re-derived from source rows before anything here was
believed, 30 checks, all passing.

**Ibex reproduces Jory's local run.** Every metric in the PREFLIGHT smoke table
matches to its printed precision: Route 10 access 0.1907395 vs 0.190740, Route
2120 0.2280921 vs 0.228092, combined 0.2094158 vs 0.209416, and the three VKT
figures to 4 decimal places.

**The derive-instead-of-simulate optimization is exact, and this was tested on
Ibex rather than carried over from the local check.** A real combined Madina
run (job 50606359, `configs/city_madina_abha_khamis_soudah_combined_reference.yaml`)
was executed and compared against the derived baseline:

- all eight aggregate metrics agree to **0 ulp**, not merely to 1e-9;
- per-segment flow agrees on **all 3,123 segments, worst absolute difference
  0.000e+00**;
- `positive_flow_segments` 389 in both.

That is stronger than the `3e-15` the package claimed. The superposition
`baseline == route10 + route2120` is likewise exact to 0.000e+00 per segment.
So the package's central claim holds: three runs really do produce six correct
result sets here, and the saved runs were not an approximation.

## The peak cases are multiplication, not congestion

Worth stating plainly because the table invites the opposite reading. Across
1.0x, 1.5x and 2.0x demand:

- every accessibility quantity is **bit-identical** (access 0.209416, Gini
  0.0446, trip distance 52247.5, unreachable 0.0%);
- every flow quantity is **exactly** the baseline times the multiplier (VKT
  21.881 / 32.821 / 43.761 km, verified to 1e-9);
- the major-road and protected-local shares are unchanged, because both
  numerator and denominator scale together.

There is no capacity, queueing or congestion feedback in this configuration, so
a demand multiplier cannot change route choice. The peak rows carry no
information beyond the arithmetic and must not be reported as a peak-hour
finding. Deriving them rather than simulating them was therefore the right
call: simulating would have burned three more runs to reproduce a multiply.

This is the same shape as the `max_closures: 6` ceiling in
`results/abha_baselines_ibex/PROVENANCE.md`: a number that looks like a result
but is set by the arithmetic.

## Two fixes were needed to run it

**`conda activate traffic_env` would have failed immediately.** `traffic_env`
is Jory's local environment; the Ibex environment is `snrl`. All three sbatch
scripts hit this on their first line under `set -e`. They now take whichever of
the two exists and fail loudly rather than half-activating.

**The directed-graph build was O(E^2).** `_rebuild_directed_edge` dropped a
chain's edges by scanning every edge in the graph, once per chain, and madina's
betweenness loop pays that scan twice more per origin. Indexing
`edge_id -> [(u, v)]` per graph, plus dict snapshots of the three
`network.nodes`/`edges` columns the hot path reads:

| | before | after | |
|---|---:|---:|---|
| full belt `_build_zonal` | 165.6 s | 2.7 s | 61x |
| 25 origin insert/remove cycles | 1.9 s | 0.4 s | |
| corridor `_build_zonal` | 2.2 s | 0.4 s | |

Equivalence was tested, not assumed: the pre-change function was reimplemented
verbatim as a reference and the two graphs compared on node set, edge set, and
every edge's weight and id, on both networks, after construction and after each
of 25 origin insert/remove cycles. Every graph identical. The 16 tests in
`tests/` pass.

To be accurate about what this fix did and did not do: the city job would have
finished inside its original 30-minute limit either way, at roughly 3 minutes.
Only the `conda activate` line was actually blocking. The 61x matters for what
comes next, not for this run, since every closure-policy or RL job on a
directed network pays this build once per `simulate()` call.

## Caveats and what would change the conclusion

- **S2-style hypotheticals are absent here, but the Route 10 / Route 2120
  comparison is still a comparison of two *existing* roads under *assumed*
  demand.** The origin weights are 1.0 and 1.0, chosen, not measured. Any real
  split between the two approaches changes the combined row directly, and the
  baseline is the only row that a demand survey would move.
- **`access_gini = 0.0000` on the single-route rows is structural**, not a
  finding: one origin cannot be unequal with itself. Only the combined rows
  have a meaningful Gini, and it is computed over two points.
- **`mean_trip_distance` for derived cases is the plain mean of the two runs'
  own means.** That reproduces a real combined run only while both sources
  contribute the same number of origins, which today is one each. Every other
  derived metric is exact for any origin count, so an unequal split would have
  left this one field quietly wrong in an otherwise-correct file.
  `derive_abha_khamis_soudah_scenarios.py` now refuses rather than deriving it.
  The guard changes nothing today: re-deriving with it in place produced a
  byte-identical `metrics.json`.
- **78.5% of the city-context flow is on protected local streets.** That is
  expected for a city-accessibility run whose origins are 740 residences, but
  it means the protected-local share is only interpretable on the corridor
  rows, where it is the number the corridor restriction was built to hold at
  zero.
- **The viewpoint access segment is a 515 m unclassified road ending 97 m from
  the OSM node.** Every corridor result depends on that one segment being
  passable. If it is gated, seasonal, or misclassified in OSM, both approaches
  change together and the comparison between them survives, but the absolute
  accessibility numbers do not.
- **`data/raw/abha_full_belt_s0/streets.geojson` is 12.5 MB in git.** The
  branch un-ignores it deliberately so the checked-in configs resolve on the
  cluster. It works, and it is worth knowing before the next large network
  lands the same way.

## What is committed here

`metrics.json`, `origin_accessibility.csv`, `segment_flows.csv` and the two
comparison files, for all six scenarios. Every number above lives in one of
them.

`segment_flows.geojson` is **not** committed. It is the input streets layer
plus two computed columns, 19.5 MB against a 23 MB repo, no
`results/**/*.geojson` has ever been tracked here, and the whole package
regenerates in 13 seconds:

    CITY_JOB=$(sbatch --parsable slurm/abha_khamis_soudah_city_context.sbatch)
    CORRIDOR_JOB=$(sbatch --parsable slurm/abha_khamis_soudah_madina.sbatch)
    sbatch --dependency=afterok:${CITY_JOB}:${CORRIDOR_JOB} \
      slurm/abha_khamis_soudah_aggregate.sbatch
