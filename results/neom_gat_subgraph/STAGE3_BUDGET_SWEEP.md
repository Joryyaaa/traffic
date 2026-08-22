# Stage 3: independent zone_builder budget sweep on the NEOM subgraph

Config under test: `configs/city_madina_neom_gat_subgraph_r750_mzs1.yaml`
(273 segments, 17 origins, 7 destinations; simulation/reward/GAT blocks
byte-identical to the r400 COMBINED reference -- only `action.max_closures`
and `action.episode_length` varied per candidate below).

Method: `scripts/evaluate.py::zone_builder_policy` run directly (not through
`evaluate.py`'s CLI for the sweep itself, to allow overriding
max_closures/episode_length per candidate in one script), 3 episodes/seeds
per candidate (zone_builder is deterministic given the network -- std was
0.0 on every candidate, confirmed), final confirmation re-run through
`scripts/evaluate.py --policies zone_builder --episodes 5` on the selected
budget.

No candidate below reuses a Riyadh config's budget or benchmark value.

## All 14 candidates tested

| max_closures | episode_length | mean return |
|---:|---:|---:|
| 1 | 2 | 0.9370 |
| 1 | 3 | 0.9370 |
| 2 | 4 | 0.9370 |
| 2 | 5 | 0.9370 |
| 3 | 8 | 0.9370 |
| 5 | 12 | 0.9271 |
| 4 | 10 | 0.9271 |
| 6 | 15 | 0.8961 |
| 8 | 20 | 0.8961 |
| 9 | 22 | 0.8961 |
| 10 | 25 | 0.8961 |
| 12 | 30 | 0.5905 |
| 14 | 35 | 0.4063 |
| 16 | 40 | 0.2867 |

**No candidate scored negative or otherwise clearly failed** -- unlike the
Riyadh r630 case (first guess -0.1145), every budget from 1 to 16
simultaneous closures produced a positive return on this network. This is
itself a real, honestly-reported finding, not something to force into a
failure narrative just because the Riyadh precedent had one.

## What the shape of this sweep says about the network

Returns are flat at their maximum (0.9370) for max_closures 1-3, drop
slightly to 0.9271 at 4-5, plateau again at 0.8961 for 6-10, then decline
monotonically from 12 onward. This means the real demand pattern here (17
dormitories -> a handful of nearby construction destinations, all within a
750m cluster) is saturated by a **single well-chosen closure** -- adding
budget beyond that adds accessibility/detour/intervention cost without a
matching zone-bonus gain, hence the decline past 10.

## Budget selection: max_closures=6, episode_length=15 (0.8961)

This is a deliberate choice, not the literal argmax, for a stated reason:
mc=1-3 numerically score marginally higher (0.9370) but reduce the episode
to a near-trivial single-segment pick (episode_length 2-8), which conflicts
with the actual research question this COMBINED setup (min_zone_size=1 +
adjacency-aware GAT) exists to test -- whether an RL agent can learn
**multi-segment** pedestrian-zone construction under credit assignment, not
whether it can find one segment. mc=6/episode_length=15 is:

- the smallest budget in the 0.8961 plateau (identical score through
  mc=10, so no return is being left on the table by not going higher),
- comfortably positive and clear of the declining tail beyond mc=10,
- large enough to require a genuine sequence of closure decisions.

**This judgment call is worth the mentor's review** before Stage 5's Slurm
time is spent -- same spirit as the Riyadh study's own flagged open question
about whether a pedestrian-zone bonus is the right objective for an
industrial/construction-logistics network at all (NEOM's demand pattern
here, worker dormitories to construction sites, is exactly that kind of
network, not a residential neighborhood).

## Final confirmation (selected config, 5 episodes)

```
$ python scripts/evaluate.py --config configs/city_madina_neom_gat_subgraph_r750_mzs1.yaml --policies zone_builder --episodes 5
policy              mean return      std     wall_s
zone_builder             0.8961   0.0000       23.5
```

**Selected zone_builder benchmark for this network: 0.8961** (max_closures=6, episode_length=15).
