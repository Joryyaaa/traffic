# Stage 1: which Abha named-site scenarios are valid for COMBINED training

All numbers measured directly against the actual `.geojson` files and a real
`StreetNetworkEnv` construction in this worktree's `snrl` conda environment
(`C:\ProgramData\Miniconda33\envs\snrl\python.exe`), not taken from the status
report or from `build_summary.json`/`qa.json` without independent
verification.

## Segment counts: reported vs. measured

| Scenario | Reported | `build_summary.json` | Direct feature count (`len(streets.geojson['features'])`) | Match? |
|---|---|---|---|---|
| Art Street / Al-Muftaha baseline | 57 | 57 | **57** | yes |
| Asir Central Hospital | 96 | 96 | **96** | yes |
| Central Market | 82 | 82 | **82** | yes |
| King Abdulaziz Grand Mosque | 87 | 87 | **87** | yes |
| School Cluster | -- (blocked) | 94 | **94** | n/a (blocked regardless of count) |
| Abu Kheyal Park | -- (blocked) | 34 | **34** | n/a (blocked regardless of count) |

All four reported counts (57/82/87/96) are confirmed exactly by direct
feature count. No correction needed.

## The 4 candidate scenarios: connectivity + demand audit

`StreetNetworkEnv` construction + `env.backend.simulate(all-open)` on each
scenario's *existing* config (data/network unaffected by the Stage 2 reward
edits):

| Scenario | n_segments | n_components | unreachable_fraction | origin_access sum | baseline flow sum | env constructs / action_masks has valid closures |
|---|---|---|---|---|---|---|
| Art Street baseline | 57 | 1 | 0.0 | 4.673 | 5.282 | yes |
| Central Market | 82 | 1 | 0.0 | 6.787 | 11.795 | yes (79/82 valid) |
| Asir Central Hospital | 96 | 1 | 0.0 | 0.374 | 3.908 | yes (85/96 valid) |
| King Abdulaziz Grand Mosque | 87 | 1 | 0.0 | 13.894 | 52.257 | yes (79/87 valid) |

All four: single connected component, zero unreachable fraction, nonzero
origin access and flow -- genuinely usable, matching the status report's
"runnable" characterization and confirming it independently rather than
trusting `build_summary.json`'s `"runnable": true` flag at face value.

(Art Street's own config ships with `max_closures=0/episode_length=1` --
that is a deliberate fully-open comparison case from the original package,
not a sign the network itself is unusable; the COMBINED config gives it a
real measured budget instead, see Stage 2/3.)

## The 2 blocked scenarios: re-verified as still genuinely blocked, right now

### School Cluster -- still blocked

`residential.geojson` has **0 features** (confirmed by direct count, matches
`build_summary.json`'s `residential_origins: 0` across every one of the 15
radius attempts logged there, from 150m to 500m -- there is no radius at
this location with a mapped OSM residential node). Constructing
`StreetNetworkEnv` on the existing config raises
`KeyError: 'origin_weight'` -- there are zero origin rows, so the weight
column the env expects to read doesn't exist. This is the same root cause
described in the scenario config's own comment ("every crop that contains
30-100 drive segments has zero OSM residential origins") and in
`ABHA_HOTSPOT_SCENARIOS.md`. Still genuinely blocked; not attempting to
fetch or invent a substitute origin layer, per instruction.

### Abu Kheyal Park -- still blocked

`residential.geojson` (3 features) and `amenities.geojson` (2 features) are
both non-empty, and `StreetNetworkEnv` *does* construct successfully (34
segments, 33/34 valid closure actions) -- so this scenario is blocked for a
different, more subtle reason than School Cluster, and it would have been
wrong to mark it runnable just because construction succeeds. Running
`env.backend.simulate(all-open)` (i.e. the true baseline, zero closures) on
the directed (`respect_oneway: true`) network gives:

```
origin_access = [0., 0., 0.]   (all three origins, zero accessibility each)
segment_flow  = all zeros across all 34 segments
unreachable_fraction = 1.0
```

So even with every segment open, none of the mapped origins can reach any
mapped destination on the directed network -- baseline accessibility is
exactly zero, confirmed independently and reproduced right now (not just
inherited from an old finding). This matches the scenario config's own
comment ("directed baseline accessibility is zero") and
`ABHA_HOTSPOT_SCENARIOS.md`'s status line. Still genuinely blocked; not
attempting to relax `respect_oneway`, widen the radius, or otherwise force a
number here, per instruction -- that would be exactly the kind of shortcut
this task exists to avoid.

## Verdict

4 scenarios proceed to Stage 2 (Art Street baseline, Central Market, Asir
Central Hospital, King Abdulaziz Grand Mosque). 2 scenarios remain excluded
(School Cluster: zero residential origins; Abu Kheyal Park: zero directed
baseline accessibility despite nonzero OD counts) -- both re-confirmed as
still genuinely blocked today, not blocked out of habit.
