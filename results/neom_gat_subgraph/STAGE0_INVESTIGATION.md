# Stage 0: What's actually on `neom-scenarios-existing-methodology`

Per instruction, this experiment sources NEOM data from
`origin/neom-scenarios-existing-methodology` (read via `git show`, never
checked out), not the older frozen B0 dataset on
`neom-baseline-sharma-camp26-r5km` that `NEOM_SUBGRAPH_PLAN.md` (on
`gat-scaleup-riyadh`) was originally written against.

Branch tip at investigation time: `a816369` ("add NEOM scenario
visualizations and overview video").

## What exists there

Real, already-committed NEOM data and scenario definitions (Sharma village /
Camp 26, r=5km, EPSG:32636):

| File | Content |
|---|---|
| `data/neom_baseline/sharma_camp26_r5km/streets_largest_component.geojson` | 274 ways, largest connected component of the raw OSM fetch |
| `data/neom_scenarios/sharma_camp26_r5km/streets_madina_ready.geojson` | **2,398 edge-level segments** -- each of the 274 ways split into 2-point segments so Madina's endpoint-based graph builder sees every intersection (commit `66b368e`, "fix 148-component topology"). Single connected component, 2,247 nodes. |
| `data/neom_scenarios/sharma_camp26_r5km/B0/origins.geojson` | 21 real origins: 17 dormitory buildings + Sharma village + Camp26 + 2 construction-camp anchors |
| `data/neom_scenarios/sharma_camp26_r5km/B0/destinations.geojson` | 12 real construction-zone centroids |
| `configs/neom_scenarios/city_madina_neom_{b0,s1,s2,s3_entry,s3_exit}.yaml` | 4 named scenarios (B0 baseline, S1 vehicle restriction, S2 parking hub, S3 entry/exit gates) |
| `docs/neom_scenarios/NEOM_SCENARIOS_FINAL_REPORT.md` | Full scenario methodology writeup, 58 PASS / 0 FAIL validation |

## Does a 150-300 segment scenario already exist?

**No.** Every named scenario (B0/S1/S2/S3) runs on the same full network:

- B0: 2,398 segments (unmodified)
- S1: 2,389 segments (9 removed -- still 2,389, nowhere near the target)
- S2, S3: 2,398 segments (unmodified, only OD pairs change)

`results/neom_scenarios/sharma_camp26_r5km/qa/madina_ready_topology.json`
confirms this directly: `"output_segments": 2398`.

**Conclusion**: per the task's own contingency ("or whether you need to
derive a new spatial subset yourself from a larger real NEOM network"), a
new spatial subset must be derived. Stage 1 does this by clipping
`streets_madina_ready.geojson` (2,398 segments) -- the Madina-ready
derivative of the real, already-committed B0 network -- the same
"largest-connected-component-of-a-radius-clip" pattern this branch's own
history already used once (`streets.geojson` -> `streets_largest_component.geojson`).
No new OSM fetch. No synthesized geometry or demand.
