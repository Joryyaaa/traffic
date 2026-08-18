# Stage 1: Inspecting the existing zone_builder implementation (before writing any code)

Answers to all 11 questions, from direct code reading, not memory or assumption.

## 1-3. Where it lives, how it's called, how it selects a zone

`scripts/evaluate.py`:

- `zone_builder_policy(env)` (lines 65-104) — the baseline the +0.6863 reference is. A
  closure: **step 1** (nothing closed yet) picks the highest-degree *qualifying* segment
  (qualifying = passes `zone_min_flow_fraction`, via `env.reward_fn._qualifying_mask`;
  falls back to highest-degree among all valid segments if nothing qualifies). **Every
  subsequent step**, picks the *first* valid segment (by index) that is adjacent to any
  already-closed segment, preferring one that also qualifies. It always extends the SAME
  growing cluster — there is no branching, no lookahead, no backtracking.
- `zone_builder_best_policy(cfg)` (lines 107-163) — tries every qualifying segment as the
  seed, runs the same greedy-extend policy from each seed for a *full episode*, keeps
  whichever full sequence scored highest total reward. Not a true combinatorial optimum,
  just a stronger single-cluster ceiling.
- Called via `run_policy(env, choose, seed)` (lines 31-39): resets the env, calls
  `choose(env, obs)` every step, accumulates `reward`, stops at `terminated` (network
  disconnected) or `truncated` (`step_count >= episode_length`).

## 4. Stopping rule — no zone-specific one exists

Neither `zone_builder_policy` nor `zone_builder_best_policy` has ANY notion of a target
zone size or a "stop once the zone reaches N" rule. The only things that stop it are:

- `env.action_masks()` returning all-`False` for further closures once
  `env.closed_mask.sum() >= cfg.action.max_closures` (a **global** per-episode closure
  budget, shared with every other policy and the RL agent — not zone_builder-specific)
- `episode_length` running out (`truncated`)

On `configs/city_madina_ablation_r400_gat.yaml`: `max_closures=9`, `episode_length=22`.
Since zone_builder always has *something* to extend to until the budget is hit (verified
empirically below), it closes exactly `max_closures=9` segments in practice — this is a
budget cap, not a size restriction the algorithm is aware of or reasons about.

## 5. Zone-size definition — read directly from `src/snrl/metrics.py::zone_score`

```python
# for each connected component of the closed-segment adjacency graph
# (DFS/flood-fill over `adjacency`, the same segment-touches-segment matrix
# used everywhere else):
effective_size = sum(1 for seg in group if qualifying_mask[seg])
if effective_size >= min_size:
    total += float(effective_size) ** exponent
```

**Zone size = count of *qualifying* segments in a connected component of closed segments**
(qualifying = passes `zone_min_flow_fraction`; a non-qualifying segment can sit inside the
group without counting toward its size). This is what `min_zone_size` gates and what
`zone_exponent` is applied to. It is **not** "number of closures" in general — those
coincide only when every closed segment is both connected to the rest and qualifying, which
is the case for zone_builder's own output (it only ever extends into qualifying, adjacent
segments) but is not guaranteed for an arbitrary policy (e.g. an RL agent scattering
closures).

## 0. Empirical reproduction (done before anything else — see "critical validation")

Ran `scripts/evaluate.py --config configs/city_madina_ablation_r400_gat.yaml --policies
zone_builder,zone_builder_best --episodes 1` fresh, in this isolated worktree, from a byte-
identical copy of the r400 data (checksums match the source checkout — see git log for this
worktree's setup).

```
policy              mean return      std     wall_s
zone_builder             0.6863   0.0000       24.0
zone_builder_best        0.8633   0.0000      728.3
```

**+0.6863 reproduced exactly** (difference: 0.0000). `zone_builder_best` = **+0.8633** —
notably, this exactly matches GAT-LONG's best RL seed (+0.8633, seed 4); not something this
task asked to explain, just worth flagging as a sanity signal that the RL agent's best run
found the same return as the strongest hand-coded ceiling.

Exact build (segment IDs, in the order closed): `[11, 10, 13, 16, 29, 31, 46, 48, 51]` — 9
segments, all 9 qualifying, `zone_score = 81.0` (= 9^2, matches `zone_exponent=2.0`).
**Confirms the max_closures=9 budget is exactly what caps the unrestricted zone at size 9**
— it never runs out of adjacent qualifying neighbors before then, so the "unrestricted"
zone size for this network/config is exactly 9, not something smaller. This directly
justifies the tested-size range in DESIGN.md: 1 through 9 is the *complete* range —
anything above 9 is unreachable under this config regardless of any explicit restriction,
so testing e.g. size 10 (as in the prompt's illustrative example) would be indistinguishable
from unrestricted here and add no information.

## 6-9. The +0.6863 reference: exact source

- Function: `zone_builder_policy`, called via `scripts/evaluate.py --policies zone_builder`
- Config: `configs/city_madina_ablation_r400_gat.yaml` — network `data/raw/riyadh_r400/`
  (89 segments), `max_closures=9`, `episode_length=22`, reward weights
  `w_accessibility=1.0, w_flow_concentration=0.5, w_equity=0.3, w_detour=0.2,
  w_intervention=0.05, disconnection_penalty=5.0, w_pedestrian_zone=1.0, min_zone_size=4,
  zone_exponent=2.0, zone_min_flow_fraction=0.1`, `reward_mode=delta`
- 1 episode, `seed=cfg.seed=42` (`run_policy(env, choose, cfg.seed + i)` for `i=0`)

## 10. Determinism

Fully deterministic: `zone_builder_policy` uses only `argmax`/first-match selection, no
`rng` anywhere in it. The Madina backend itself is deterministic
(`FlowBackend.reseed()` returns `False` for it, confirmed in `src/snrl/backends/base.py`
and every prior experiment in this lineage) — so re-running with the same config/seed
reproduces the same number exactly, not just approximately.

## 11. Restricting zone size: existing parameter, or implementation change needed?

**No existing parameter does this.** Checked both candidates explicitly, per instruction
not to confuse them:

- `min_zone_size` (reward config) — gates the **minimum** size a connected group must reach
  before it earns *any* pedestrian-zone bonus. It does not limit how large zone_builder is
  *allowed* to grow; it only changes when the reward turns on. This is what CREDIT changed
  (4 → 1).
- `max_closures` (action config) — a **global episode-wide** closure budget shared by every
  policy/config, not a zone-specific cap. Changing it in the *config* would also change the
  environment for the RL agent and every other baseline, and would not be a clean
  "zone_builder-only" ablation.

**A small implementation change is required**: an optional restriction added directly to
the `zone_builder_policy` choice function — stop extending (return no-op) once the
*current* connected group's size reaches an allowed maximum, independent of
`max_closures`/`env`/config. Default behavior (no restriction passed) must stay byte-for-byte
identical to today's `zone_builder_policy`, so every existing use of it (including the
+0.6863 reference itself) is unaffected. See `DESIGN.md` for the exact function signature.
