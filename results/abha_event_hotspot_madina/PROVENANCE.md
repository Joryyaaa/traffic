# Provenance: Abha Event Hotspot on Ibex

Ran 2026-08-17 from `abha-event-hotspot-ibex`. Jobs 50635245 (array 0-3) and
50635246 (aggregate), all COMPLETED, 9-11 s per task.

**The package now runs. It does not yet produce a usable result, and that is a
data question rather than a code one.**

## Result: all four scenarios are identically empty

| Scenario | Mean accessibility | Mean trip distance | Unreachable | Components | Total flow |
|---|---:|---:|---:|---:|---:|
| B0_Baseline | 0 | 3500.000 | 1 | 26 | 0 |
| S1_Event_Zone_Vehicle_Restriction | 0 | 3500.000 | 1 | 25 | 0 |
| S2_Main_Parking_Hub | 0 | 3500.000 | 1 | 26 | 0 |
| S3_Managed_Entry_Exit | 0 | 3500.000 | 1 | 26 | 0 |

Every origin is unreachable, every flow is zero, and `mean_trip_distance` is
exactly `search_radius` because that is the unreachable fallback. The four
scenarios cannot be compared, because none of them connects anything.

## Why: the network is 26 disconnected fragments

The inputs are scraped from `data/abha_baseline/abha_event_hotspot_baseline2_scenarios.html`,
which is a **visualization** of selected roads, not a topological network. The
90 segments fall into 26 components, and the 3 origins sit in different
components from the event zone.

This is not a snapping-tolerance problem, which was the obvious first guess.
Measured on the built network, 180 endpoints:

| nearest cross-segment endpoint gap | endpoints |
|---|---:|
| exactly 0.00 m | 117 of 180 |
| under 5 m | 117 |
| under 15 m | 134 |
| under 50 m | 151 |

117 endpoints already coincide *exactly* and the network is still in 26 pieces.
Raising `node_snapping_tolerance` does not rescue it:

| tolerance | resulting components |
|---|---:|
| 0.5 m (current) | 26 |
| 5 m | 26 |
| 15 m | 17 |
| 50 m | 10 |

Even at 50 m, which would fuse genuinely distinct junctions and invent
connections, it never reaches one component. The map simply does not contain a
connected 2 km network.

**The fix is to source the network from OSM rather than from the HTML**, the way
`scripts/build_abha_s0_env_data.py` already does for the full belt: fetch the
drive network for a 2 km radius around 18.214, 42.4944 and keep the mapped
closure/entry/exit way IDs (95507294, 787786457, 135229579) as attributes on it.
That is a data-sourcing decision for whoever owns the scenario, so it was not
made here. `node_snapping_tolerance` was deliberately left at 0.5 m: tuning it
upward would have produced non-zero numbers that looked like results.

## One code bug was found and fixed

The local Madina smoke run the package asks for had never been executed. It
failed outright: madina's `create_graph()` raised `KeyError: 27`.

One of the 88 map segments is a closed way, an unnamed `highway=trunk` ring of
29 points at (42.488569, 18.220095) whose first coordinate equals its last.
Madina builds `light_graph` purely from edge start/end pairs, so a closed way is
a self-loop; its `Network` drops the edge, and the endpoint left behind becomes a
street node belonging to no edge. `create_graph()` then indexes
`nodes[27]['type']` and raises. 88 input segments produced 87 edges and 1 orphan.

Fixed in `scripts/build_abha_event_hotspot_data.py` by splitting closed ways into
three arcs. Three rather than two because two arcs share both endpoints and
`light_graph` is a plain `nx.Graph`, so the second would overwrite the first and
one arc's weight would vanish. Coordinates are re-emitted unchanged and
`properties.id` is preserved, so the geometry is identical and the S1 closure
filter still treats the ring as one road. Baseline goes 88 -> 90 segments.

This is worth knowing beyond this package: **any** OSM crop containing a
roundabout or other closed way will hit the same crash on the undirected path.

## Caveats

- The demand is 3 provisional origins placed at the network's bounding-box
  extremes by the builder, not measured counts, and the package says so.
- S3 is represented as two separate assignments because this branch's backend is
  undirected. Note that exact one-way support now exists on both
  `optimized-abha-jabal-soudah-ibex` and `codex/abha-hotspot-scenarios`, so S3
  could be modelled directly rather than approximated once this branch picks up
  that backend.
- The all-zero table above is committed on purpose. It is the evidence for the
  connectivity problem, and it must not be read as a scenario comparison.
