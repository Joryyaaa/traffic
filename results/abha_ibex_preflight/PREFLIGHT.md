# Abha Ibex preflight — Jabal Soudah Viewpoint

Status: **READY FOR IBEX STATIC MADINA RUN**

Optimized execution: **3 Madina runs + 3 exact derived cases**, instead of
6 Madina runs.

## Corrected destination

- Destination: Jabal Soudah Viewpoint / `مطل السودة١`
- OSM node: `7523059174`
- Coordinates: `18.2704765, 42.3636140`
- The previous endpoint east of the mountain is no longer used.
- One existing 515.3 m unclassified final-access segment is included.
- The road access node is 97.3 m from the mapped viewpoint.
- All other residential, service, living, and unclassified streets remain
  unavailable to external Khamis-to-viewpoint through traffic.

## Geometry and data QA

- Full-belt network: 17,185 segments, one undirected component.
- King Abdulaziz belt: connected, including roundabout `683599895`.
- City demand: 740 residential origins and 275 destinations.
- Corridor-only network: 3,123 segments.
- Route 10 to viewpoint: directionally connected.
- Route 2120 to viewpoint: directionally connected.
- Preferred existing route selected by constrained geometry search:
  Route 2120, 49.657 km, 169 connected segments.
- Resilient existing alternative: Route 10, 57.471 km, 245 connected
  segments, 28.3% overlap with the preferred-route interior.
- Neither route uses residential or service streets.

## Local Madina smoke results

These are technical preflight runs, not the final Ibex comparison. The
both-approaches reference case is the Khamis-to-viewpoint baseline.

| Case | Simulation | Mean accessibility | Accessibility Gini | VKT proxy | Protected-local flow |
|---|---:|---:|---:|---:|---:|
| Route 10 | 5.30 s | 0.190740 | 0.0000 | 10.554 km | 0.0% |
| Route 2120 | 4.13 s | 0.228092 | 0.0000 | 11.326 km | 0.0% |
| Both approaches | 8.70 s | 0.209416 | 0.0446 | 21.881 km | 0.0% |

The full 17,185-segment city baseline previously took 304.69 seconds locally.
The corridor cases therefore complete in seconds; the Ibex array is expected
to finish in minutes after it starts, not days.

## Verification completed

- All six configs passed `--validate-only`.
- Route/demand geometry QA passed.
- Local Madina runs completed without an exception.
- `12` targeted Madina/connectivity/evaluator tests passed.
- Updated HTML, PNG, and MP4 validation outputs were regenerated.
- The analytically derived both-approach baseline matched a real combined
  Madina run for every reported metric (maximum floating-point difference
  below `3e-15`).

## Ibex submission

Follow `slurm/ABHA_KHAMIS_SOUDAH_IBEX_GUIDE.md`. The scenario array and final
aggregation are submitted with:

```bash
CITY_JOB=$(sbatch --parsable slurm/abha_khamis_soudah_city_context.sbatch)
CORRIDOR_JOB=$(sbatch --parsable slurm/abha_khamis_soudah_madina.sbatch)
sbatch --dependency=afterok:${CITY_JOB}:${CORRIDOR_JOB} \
  slurm/abha_khamis_soudah_aggregate.sbatch
```

The eight-worker action-mask optimization is retained for the separate
closure-policy timing job. It is not used by these static Madina scenarios,
which run as two small array tasks plus one separately sized city task. Exact greedy and
other multi-day closure-policy runs are not submitted by this package.
