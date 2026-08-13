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
| zone_builder_best | **+0.9518** | **+0.9518** | **+0.9518** | **+0.9518** |
| greedy | not run, see below | not run | not run | not run |

`zone_builder_best` took 4.2 to 4.7 h per scenario (8 mask workers, 64 GB).

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
2. **`zone_builder_best` reaches +0.9518, slightly above that floor.** This was
   predicted as "exactly +0.9500, because +0.95 is the maximum attainable" before
   the runs finished, and that prediction was wrong. 0.95 is a *floor* for any
   planner that spends the whole budget on one contiguous zone, not a ceiling:
   the remaining terms are very small but not identically zero, and the best seed
   clears 0.95 by +0.0018 by picking a zone that also marginally helps
   accessibility, equity, flow-entropy or detour.

   The residual is nevertheless **not** scenario-sensitive. All four scenarios
   return +0.9518, including S2, which is the only one that actually changes the
   network (it adds a road, 4,602 segments) and the only one that moves the flow
   metrics at all (-0.63% flow, -0.72% VKT proxy). A scenario that visibly
   changes the network and still produces a bit-identical return is the strongest
   evidence here that the return is measuring the zone-contiguity arithmetic and
   not the network.

   Treat the +0.0018 as unusable regardless of sign: it is one seed search per
   scenario with no error bars, four decimal places of printed precision, and no
   spread to compare against.

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

## greedy could not be run: simulate() leaks 6.75 MB per call

`abha-s2-greedy` was OOM-killed at 16 GB after 1h13. That is not a too-small
memory request, it is a leak, measured directly and perfectly linear:

| simulate() calls | RSS above baseline |
|---|---|
| 10 | +68 MB |
| 20 | +137 MB |
| 30 | +203 MB |
| 40 | +270 MB |

**6.75 MB per call.** The result cache cannot account for it: `cache_size`
defaults to 4096 and a `SimulationResult` is ~40 KB, so that is ~0.15 GB bounded.
The likely source is the `mp.Manager()` that madina's
`paralell_betweenness_exposure()` creates on **every** `simulate()`, which is
exactly the TODO already recorded in `src/snrl/backends/madina_backend.py`. Note
also that this backend deliberately reports fake `psutil.virtual_memory()` to
stop madina's own throttle from sleeping, which also disables madina's own OOM
guard, so nothing brakes before the kernel does.

Consequences:

- **greedy is infeasible here at any memory.** It needs 15 steps x 4,531
  candidates = 67,965 calls, i.e. ~448 GB. The other three greedy jobs were
  cancelled at 1h16 rather than left to reach the same OOM; S1A and S1B were
  already at 16.5 and 16.8 GB against a 16 GB request.
- **`zone_builder_best` needed 64 GB, not the 24 GB first requested.** It makes
  561 x (1 fresh-env baseline + up to 6 closures) ~= 3,927 calls, projecting to
  26.1 GB, so the first attempt would have died at roughly 90% completion after
  nearly six hours. Cancelled at 53 min and resubmitted at 64 GB, which
  completed.

greedy's answer is however known by construction and by measurement. Sampling 25
of the 554 flow-qualifying first closures gives a best single-closure reward of
**-0.00668** against **0.0** for the no-op, because `min_zone_size: 3` means a
one-segment zone scores zero, so a first closure earns no bonus and only pays
`w_intervention`. greedy therefore takes the no-op at every step and returns
**0.0000**, as it does on Al Nakheel and Jeddah. That also means it never spends
its budget, so `at_budget` never short-circuits the mask and it pays the full
candidate lookahead on all 15 steps rather than 6, which is why it is ~34 h
rather than ~14 h.

Fixing the leak (patch `mp.Manager()` the way `_ImmediateExecutor` already
patches `ProcessPoolExecutor`) would make greedy roughly a day instead of
impossible, and matters well beyond greedy: it caps how long any evaluation or
training run on a large network can go before it dies.

## Caveats

- `greedy` is missing from the table above: five of six policies were measured.
- Budget (`max_closures: 6`, `min_zone_size: 3`, `episode_length: 15`) is Jory's
  and was **not** re-derived by measurement here, unlike the scale-sweep configs.
  Given the ceiling analysis above, that is the parameter most worth revisiting.
- S2 is a **hypothetical** Green Road alignment
  (`scripts/build_abha_s2_env_data.py` prints this too). It is not a real
  proposal and must not be reported as one until ASDA supplies the alignment.
