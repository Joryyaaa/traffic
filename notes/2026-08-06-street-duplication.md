> **Already fixed upstream.** Jory independently found and fixed both headline
> items in this note before it was filed: the duplicated bidirectional streets and
> the `rel()` blow-up on a near-zero baseline are both fixed in `b138dba`, with a
> regression test in `f827820`, and a third related exploit (unreachable O-D pairs
> vanishing from `mean_trip_distance` instead of counting as a penalty) in
> `de90953`. This note is kept as the measurement record: the numbers below are
> what the bugs cost, measured on real data, which is useful evidence for the
> writeup. Section 6 (parameter re-derivation) and section 8 (environment and
> tooling issues) are the parts still open.
>
> Baselines re-measured on the fixed code, same data, for reference:
> Al Nakheel `zone_builder` +0.2661, Jeddah +0.9435, greedy 0.0000 on both.

# Every street was in the layer twice, and it invalidates the real-city results

**Date:** 2026-08-06
**Status:** pipeline fixed; all real-city numbers need re-measuring; no sweeps run
**Affects:** `configs/city_madina_*.yaml` (real data only). The synthetic-lattice
results (`hard.yaml`, `hard_demand`, `hard_stochastic`, `hard_large`) are **not**
affected -- `StubBackend` builds its own grid and has no duplicates.

This was found while preparing the `[needs Ibex]` seed sweeps. The sweeps were
**not** submitted, because they would have spent ~280 core-hours computing a
precise mean ± std for a setup in which the agent's closures did nothing.

---

## 1. What was wrong

`scripts/fetch_osm_data.py:fetch_streets()` did:

```python
G = ox.graph_from_point(center, dist=radius_m, network_type=NETWORK_TYPE, simplify=True)
_, edges = ox.graph_to_gdfs(G)
edges = edges.reset_index(drop=True)[["geometry"]].copy()
```

`ox.graph_from_point` returns a **directed** graph. For a `walk` network every
street is traversable both ways, so `graph_to_gdfs` emits **two rows per street**
-- same geometry, one reversed. Nothing downstream knew they were the same street.

Verified at 1 cm precision, direction-insensitive, on all four scenarios:

| scenario | rows in `streets.geojson` | distinct centerlines | ratio |
|---|---|---|---|
| Al Nakheel r=250 | 52 | **26** | 2.00 |
| Jeddah r=250 | 116 | **58** | 2.00 |
| Al Nakheel r=700 | 772 | **386** | 2.00 |
| Abha r=250 | 160 | **80** | 2.00 |

Exactly 2×, every geometry, no exceptions. Total row length on Al Nakheel was
3461.9 m against 1731.0 m of actual street.

## 2. Why it matters: a closure of one row does nothing

`closure_mode: penalize` multiplies the *closed row's* perceived cost by 1000.
The twin row keeps its normal cost, so pedestrians route over it as if nothing
happened.

Measured on Al Nakheel. Segment 34 carried 238.69 baseline flow; segment 45 is
its identical twin (`geometry.equals()` is `True`):

| | mean_access | total_flow | mean_trip_distance |
|---|---|---|---|
| baseline | 1.804025 | 949.85 | 181.66 |
| close 34 only | **1.804025** | **949.85** | **181.66** |
| close 34 **and** 45 | 1.230139 | 1006.83 | 178.53 |

Closing one copy is identical to six decimal places. This is the mechanism behind
the anomaly already recorded in the README:

> found accessibility/equity/detour are all exactly 0 for the trained agent's
> episode; the closed corridor doesn't sit on any O-D shortest path, so the zone
> bonus was earned "for free"

The diagnosis of the symptom was right, the attributed cause was not. The terms
were *exactly* zero because the closures were physically inert, not because the
corridor sat off every path.

**`zone_min_flow_fraction` (commit 15d2fa2) does not fix this.** It gates the zone
bonus on baseline flow, and the twin that carries the flow *does* qualify. The
agent could close segment 34 (flow 238.69, qualifying), change nothing about the
network, and collect the full bonus.

Three further consequences:

- `max_closures: 6` meant at most **3** real streets -- and if the agent picked
  six non-twin rows, **zero** physical closures.
- `min_zone_size: 3` did not mean 3 streets. Twins are not adjacent to each other
  (`adjacency[34][45] == False`, because identical lines overlap rather than
  touch) but both touch the same neighbours, so a "3-segment zone" could be 2
  streets.
- `flow_entropy` is computed over `n_segments`. Half the rows carried zero flow,
  which depressed it: Al Nakheel's baseline entropy was 0.548 with duplicates and
  is **0.664** without. `w_flow_concentration` was weighted against the biased value.

## 3. The fix

`_drop_reversed_duplicates()` in `scripts/fetch_osm_data.py`, applied inside
`fetch_streets()`. Direction-insensitive key on the rounded coordinate sequence;
the two rows share the same sequence reversed, so it pairs them exactly.

**Deduplicating does not change the open network.** Al Nakheel before and after:

| | segments | mean_access | total_flow | trip_dist | components |
|---|---|---|---|---|---|
| duplicated | 52 | 1.804025 | 949.85 | 181.66 | 1 |
| deduplicated | 26 | 1.804025 | 949.85 | 181.66 | 1 |

Identical. The extra rows were pure artefact. What changes is that closures now
have an effect: closing the busiest street moves mean_access by −0.5739, the
second-busiest by −0.0208.

## 4. What this does to the results

`scripts/evaluate.py --config configs/city_madina_ablation.yaml --episodes 3`:

| policy | before (duplicated) | after (deduplicated) |
|---|---|---|
| random | −0.0692 | −0.8977 |
| **greedy** | 0.0000 | **0.0000** |
| highest_flow | +0.1315 | −0.3565 |
| lowest_flow | −0.0167 | −0.0167 |
| **zone_builder** | **+0.6444** | **−0.4586** |

`zone_builder` flips sign. Its +0.6444 was an artefact of inert closures.

**On corrected Al Nakheel, doing nothing is the best available policy.** Greedy
scores 0.0000 by refusing to act, and that now beats every other baseline
including the hand-coded planner. The "greedy fails / planning wins" claim does
not survive on this scenario once closures are physical.

## 5. Why: the equity term is normalized by a near-zero baseline

`reward_breakdown.py` on `zone_builder`, corrected data, cumulative over the episode:

| term | contribution |
|---|---|
| pedestrian_zone | **+0.6944** |
| equity | **−0.8955** |
| accessibility | −0.1976 |
| intervention | −0.0500 |
| detour | −0.0153 |
| flow_concentration | +0.0053 |
| **total** | **−0.4586** |

The planner *does* build a qualifying zone and earn the full bonus. The equity
term alone more than cancels it.

The cause is in `rewards.py`:

```python
def rel(key):
    scale = abs(b.get(key, 0.0)) or 1.0      # b = BASELINE stats
    return (cur[key] - ref.get(key, 0.0)) / scale
```

Al Nakheel's baseline `access_gini` is **0.0576** -- 17 households on 26 streets
all have similar access, so the network starts almost perfectly equal. Dividing a
Gini *delta* by 0.0576 amplifies it ~17×. Measured: closing 3 qualifying streets
moves Gini 0.0576 → 0.6240, and the equity term for that alone is **−2.95**,
against a maximum possible zone bonus of **+1.00**.

So the equity term can be three times the entire zone bonus. The reward is
structurally incapable of rewarding a pedestrian zone here, whatever the policy.

Two compounding causes, worth separating:

1. **A reward-design hazard, independent of the data bug.** Any term whose
   baseline is near zero gets a near-zero denominator and explodes. Gini and
   entropy are both bounded in [0,1] and can legitimately start near zero. A
   floor on the denominator, or normalizing by a fixed scale rather than the
   baseline level, would fix it.
2. **The scenario is too small.** With 3 destinations, closing 3 streets really
   does strand households, so the raw Gini change is genuinely large too.

## 6. Parameter re-derivation on real street counts

`max_closures` counted rows, so its physical meaning was half what it appeared to
be, and it now varies wildly across scenarios:

| scenario | streets | current `max_closures` | share of network |
|---|---|---|---|
| Al Nakheel r=250 | 26 | 6 | **23.1%** |
| Jeddah r=250 | 58 | 6 | 10.3% |
| Abha r=250 | 80 | 6 | 7.5% |
| Al Nakheel r=700 | 386 | 12 | 3.1% |

Two problems: 23% of a neighbourhood closed to traffic is far beyond any real
scheme (and was *believed* to be 11.5%, i.e. 6 of 52); and the same nominal
budget is a 7× different physical intervention across scenarios, so returns are
not comparable between cities even though the reward normalizes them onto the
same 0–0.95 scale.

Proposal: set the budget as a fixed **fraction of the network** (~10%, which is
in the range real pedestrianization schemes touch and happens to leave Jeddah
exactly as it is), and keep a plaza at half the budget:

| scenario | streets | `max_closures` | `min_zone_size` |
|---|---|---|---|
| Jeddah r=250 | 58 | **6** (unchanged) | **3** (unchanged) |
| Abha r=250 | 80 | 8 | 4 |
| Al Nakheel r=700 | 386 | 39 | 20 |
| Al Nakheel r=250 | 26 | 3 | 2 |

Note what that last row shows: at 26 streets a 10% budget is 3 closures with a
minimum zone of 2, which leaves essentially one possible plan and no planning
problem at all.

**Recommendation on scenarios:**

- **Jeddah becomes the primary real-city scenario.** 58 streets, 63 origins, 31
  genuine destinations (shops, restaurants, a hospital), and its current
  `max_closures: 6` / `min_zone_size: 3` are already the right values.
- **Al Nakheel r=250 is retired as a headline scenario** and kept as a fast
  smoke-test config. 26 streets and 3 destinations (a mosque, a fast-food outlet
  and a car park) cannot carry a case study.
- **Al Nakheel r=700 (386 streets) becomes the scale scenario**, with
  `max_closures: 39` / `min_zone_size: 20` rather than the 12/3 first drafted.
  Note 39 raises the zone normalizer to 39² = 1521 and makes greedy far more
  expensive; re-check the cost before running.

## 7. Blocking issue before any sweep

**The reward weights were tuned against a broken simulation.** While closures
were inert, four of the six terms were structurally ~0, so only
`pedestrian_zone` and `intervention` were live. Now that accessibility, equity,
detour and flow_concentration all respond, the balance is wrong -- most visibly
`w_equity: 0.3` combined with the near-zero-baseline normalizer.

Re-tuning has to come before the seed sweeps, otherwise the sweeps measure the
variance of a reward that prefers inaction.

## 8. Also found while preparing (unrelated to the above)

- **`environment.yml` omits `osmnx`**, which `fetch_osm_data.py` imports; only
  `requirements.txt` lists it. Its `pip:` block also makes **TestPyPI the primary
  index**, so pip can resolve `geopandas`/`numpy`/... from a registry where anyone
  may upload under those names. Safer:
  `pip install --no-deps -i https://test.pypi.org/simple/ madina` after conda has
  installed the real dependencies.
- **The OSM fetch is unreliable for a findable reason.** `overpass-api.de`
  round-robins over two backends and `65.109.112.52` refuses connections from
  Ibex. osmnx also resolves the host itself over DNS-over-HTTPS
  (`settings.doh_url_template`) and re-pins via `socket.gethostbyname`, so
  ordinary DNS overrides are ignored. Worth an `--overpass-ip` option plus retry.
- **`action_masks()` is the scaling bottleneck, not the flow model.** At 772 rows
  it cost 1.12 s/step against 0.93 s for the Madina simulation, because it copies
  the topology graph once per candidate segment. A single `nx.bridges()` pass does
  the same job in 4.5 ms (~250×). A first attempt disagreed with the current mask
  on 5–6 of ~715 segments, so it needs care -- partly *because* of the duplicate
  rows, since `_build_topology` uses a simple `nx.Graph` and collapsed parallel
  rows onto one edge.
- **A GPU would not help.** Measured: the policy network is 1.2% of runtime on Al
  Nakheel and 0.18% on the 772-row network, so the ceiling from infinitely fast
  inference is 1.012× / 1.002×. Everything expensive is single-threaded CPU Python
  (Madina, networkx). Per-step single-observation inference on a GPU would likely
  be slower than the 342 µs the CPU already takes.
- **`--episodes > 1` is wasted on the madina backend.** `FlowBackend.reseed()`
  returns `False` for it and the eval policy is deterministic, so N eval episodes
  are N identical rollouts and the per-seed `std_return` is structurally 0.

## 9. State of the working tree

Ready but deliberately unused:

- `slurm/sweep_array.sbatch`, `slurm/README.md`, `scripts/aggregate_sweep.py` --
  one seed per array task, `seed_sweep.py` unmodified, aggregator reports missing
  seeds so a part-failed array cannot be quoted as a 100-seed mean. Validated
  end-to-end on the real queue.
- `configs/city_madina_ablation_large.yaml` -- needs the `max_closures`/
  `min_zone_size` revision in §6.
- `scripts/fetch_osm_data.py` -- dedup fix, plus `--include-generic-buildings`
  for cities where OSM has no building classification (around Abha, 534 of 558
  buildings within 2 km are `building=yes` and exactly one says `residential`, so
  the default filter returns zero origins).

Data: only `data/raw/riyadh_ablation` is currently present, deduplicated. The
Jeddah, Al Nakheel r=700 and Abha layers were deleted during the re-fetch and
Overpass then rate-limited us; they are fully reproducible from the coordinates
and radii recorded in the configs once the API is reachable again.
