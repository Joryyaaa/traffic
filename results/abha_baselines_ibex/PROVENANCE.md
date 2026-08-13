# Provenance: Abha baselines on Ibex, all four scenarios

The runs `results/abha_s0_baselines/PROVENANCE.md` deferred to Ibex, executed
2026-08-13. Cross-scenario rather than per-scenario because the main finding is
only visible by comparing the four.

**Data.** `data/raw/abha_{s0,s1a,s1b,s2}` was never committed, so it was
regenerated with `scripts/build_abha_s0_env_data.py` (then
`build_abha_s1_env_data.py`, `build_abha_s2_env_data.py`, which derive from S0).
All five of that script's drift checks matched exactly: 1,729 nodes / 4,586
segments / 315 origins / 56 destinations / King Abdulaziz 29. So OSM has not
drifted since the original run and these numbers are comparable to
`data/abha_baseline/run_output.txt`.

The fetch needed the Overpass workarounds from `configs/city_madina_ablation_r460.yaml`:
`overpass-api.de` still round-robins onto `65.109.112.52`, which refuses
connections, and osmnx re-pins the host itself over DNS-over-HTTPS. Pin the
healthy IP and disable DoH. This is the same failure that made the r=460 point
look unfetchable, not a new one.

**Run.** `slurm/abha_s0_baselines.sbatch`, one job per (scenario, policy subset).
`--episodes 1` for the deterministic policies: `MadinaBackend` inherits
`FlowBackend.reseed()` returning `False`, so demand never redraws and N episodes
of a deterministic policy are N identical rollouts with a structurally zero std.
Only `random` uses 5 episodes.

## Result: the four scenarios are indistinguishable by policy return

| policy | S0 (4586) | S1A (4570) | S1B (4573) | S2 (4602) |
|---|---|---|---|---|
| random (5 ep) | -0.0500 | -0.0500 | -0.0500 | -0.0498 |
| highest_flow | +0.0660 | +0.0662 | +0.0660 | +0.0651 |
| lowest_flow | -0.0500 | -0.0500 | -0.0500 | -0.0500 |
| zone_builder | **+0.9500** | **+0.9500** | **+0.9500** | **+0.9500** |
| greedy | pending | pending | pending | pending |
| zone_builder_best | pending | pending | pending | pending |

`zone_builder = 0.9500` on all four is **the reward's structural ceiling, not a
measurement**. With `max_closures: 6` and `zone_exponent: 2.0`,
`_zone_scale = 6^2 = 36`, so a single contiguous zone spending the whole budget
scores `36/36 = 1.0`, against `intervention = -w_intervention x n_closed_frac
= -0.05 x 1.0`:

    1.0 - 0.05 = 0.9500  exactly

The value being identical to four decimals across four different networks is the
tell: the accessibility, equity, flow-entropy and detour terms are all
contributing exactly 0.0000. Closing 6 of ~4,586 segments is invisible to them.
`results/abha_scenario_maps/comparison_table.txt` says the same thing from the
other direction, the scenarios differ by 0.10% on access (S1A) and 0.00% on flow
(S1B).

Two consequences:

1. **Do not read the policy-return table as a scenario comparison.** It cannot
   separate S0 from S1A/S1B/S2, because the return is set by the zone-contiguity
   arithmetic and not by the network. The discriminating comparison is the flow
   metrics in `results/abha_scenario_maps/`, where S2 is the only scenario that
   moves anything (access -0.71%, VKT proxy -0.72%).
2. **`zone_builder_best` is expected to be exactly +0.9500 too.** It maximizes
   over candidate seeds, and +0.95 is the maximum attainable. It is still being
   run as a check on that reasoning rather than because the number is in doubt.

`lowest_flow` at exactly -0.0500 is the same signature seen at 186 and 386
segments in `results/scale_sweep/`: the full intervention cost paid for a zone
that never reaches `min_zone_size`, so it earns no bonus at all.

## What would make this experiment discriminate

The intervention has to be large enough to move the accessibility terms, or the
network small enough that 6 closures matter. Options, none yet run:

- raise `max_closures` by one to two orders of magnitude, which changes what
  "budget" means and needs the measurement discipline in
  `configs/city_madina_ablation_large.yaml`;
- restrict the network to the study corridor rather than the full r=1500m disc,
  so the closures are a meaningful fraction of it;
- or accept that the RL formulation is not the right instrument for comparing
  one-way schemes, and compare on the flow metrics directly.

## action_masks() was the bottleneck, and was fixed

Measured on S0, per `env.step()`: `action_masks()` 34.45s, `simulate()` 1.82s.
The mask was **95%** of the cost of a step. It called
`backend.is_connected()` once per segment, and each of those did a full
`_topology.copy()`, so one mask made 4,586 copies of a 1,729-node graph.

Two changes, both in this commit:

| | S0 mask |
|---|---|
| before | 34.33s |
| one copy per batch instead of per candidate | 16.40s (2.1x) |
| plus 8 forked workers (`SNRL_MASK_WORKERS=8`) | **4.72s (7.3x)** |

It stops improving past 8 workers. `SNRL_MASK_WORKERS` defaults to 1, so
training loops are unaffected unless they opt in; the sbatch derives it from
`--cpus-per-task`.

**Equivalence was tested, not assumed.** The pre-change algorithm was
reimplemented as a reference and compared bit-for-bit against the new path,
serial and forked, walking real episodes on 26 / 58 / 89 / 226-segment networks
and on Abha S0 itself. Every mask identical. This matters because `_topology` is
a plain `nx.Graph`, so several segments can collapse onto one `(u, v)` edge, and
a mask that changed which actions are legal would silently change every result.

That same shared-edge collapse is why single-pass bridge detection was **not**
attempted, despite being the larger prize (~250x): a bridge in `_topology` need
not correspond to a unique segment, and an earlier prototype disagreed with the
current implementation on 5 to 6 of ~715 segments. Left as follow-up work, along
with `scipy.sparse.csgraph.connected_components` (already an env dependency) in
place of `nx.is_connected`.

The fix takes `zone_builder_best` from ~34h to ~6.5h per scenario. It barely
helps `greedy` (~13.8h either way), which is bound by 4,531 `simulate()` calls
per step, not by masking; parallelizing those is the next lever there.

## Caveats

- `greedy` and `zone_builder_best` are still running; the table above is four of
  six policies.
- Budget (`max_closures: 6`, `min_zone_size: 3`, `episode_length: 15`) is Jory's
  and was **not** re-derived by measurement here, unlike the scale-sweep configs.
  Given the ceiling analysis above, that is the parameter most worth revisiting.
- S2 is a **hypothetical** Green Road alignment
  (`scripts/build_abha_s2_env_data.py` prints this too). It is not a real
  proposal and must not be reported as one until ASDA supplies the alignment.
