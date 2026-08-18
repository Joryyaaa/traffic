# Combined GAT Experiment: min_zone_size=1 + 167,000 timesteps

**Branch:** `combined-gat-credit-long`, merging `credit-assignment-ablation@115220e` (CREDIT)
and `gat-r400-longer-training@25f968a` (GAT-LONG), both descendants of the original completed
GAT control at `34f03c8`.
**Status:** prepared and validated (42/42 checks pass, 0 FAIL, 0 SKIP — see
`scripts/validate_combined_gat_credit_long.py`). **Not run.** No 5-seed jobs submitted from
this session.

## Why this experiment: the mentor asked to combine two independently-successful fixes

The original GAT control (30k steps, min_zone_size=4) scored mean -0.0322 — better than both
MLP baselines, but far below `zone_builder` (+0.6863). Two follow-ups each addressed a
different candidate explanation, in parallel, on separate branches:

**A) CREDIT — credit-assignment-ablation (`115220e`).** Hypothesis: `min_zone_size=4` delays
reward until the 4th contiguous closure, which may be too hard to discover by chance. Fix:
`min_zone_size=1` (every closure scores immediately), still 30k steps.

> Mean **+0.3816**, std 0.1834, min/median/max +0.2046 / +0.3210 / +0.7341. **All 5 seeds
> positive.** Large, consistent improvement — supports the credit-assignment hypothesis.

**B) GAT-LONG — gat-r400-longer-training (`25f968a`).** Hypothesis: 30k steps undertrains a
graph model on this action space. Fix: 167,000 steps (a budget the mentor's own scale-sweep
had already shown sufficient for a plain MLP on this exact network), still `min_zone_size=4`.

> Mean **+0.1618**, std 0.3511, min/median/max -0.0262 / -0.0204 / **+0.8633**. Only **1/5**
> beat `zone_builder`. Higher ceiling (best seed nearly matches CREDIT's best) but much less
> consistent — 3 of 5 seeds landed near zero or negative.

**The mentor's question:** does combining both fixes give BOTH CREDIT's consistency AND
GAT-LONG's occasional high ceiling — or does the combination just inherit one experiment's
weakness? Neither result alone answers this: CREDIT never tested whether its consistency
holds up with more training; GAT-LONG never tested whether more training's inconsistency was
itself downstream of the same credit-assignment problem CREDIT fixed.

## Controlled variables (everything held fixed relative to BOTH parents)

- Network: Al Nakheel r=400m, 89 segments, `data/raw/riyadh_r400/` (the exact same dataset
  both CREDIT and GAT-LONG used — not refetched, not rebuilt; the combined Slurm harness
  fails loudly rather than silently regenerating it if it's missing from a checkout)
- Observation: 7 features, `include_adjacency_state: true`
- Extractor: `GATFeaturesExtractor` — 2 layers, 32-dim, 4 heads (head_dim=8), ELU, mean-pool +
  16-dim global-row MLP → 64-dim output (all `seed_sweep_gat.py` defaults, unmodified)
- Algorithm: MaskablePPO
- `max_closures=9`, `episode_length=22`
- All reward weights except `min_zone_size`: unchanged (`w_accessibility=1.0`,
  `w_flow_concentration=0.5`, `w_equity=0.3`, `w_detour=0.2`, `w_intervention=0.05`,
  `disconnection_penalty=5.0`, `w_pedestrian_zone=1.0`, `zone_exponent=2.0`,
  `zone_min_flow_fraction=0.1`)
- Seeds: 1, 2, 3, 4, 5
- Evaluation: 1 deterministic episode (madina backend is deterministic — N episodes would be
  N identical rollouts, same reasoning as every other experiment in this lineage)

Confirmed by `scripts/validate_combined_gat_credit_long.py`, not just asserted: config
network/simulation/action blocks and all reward fields except `min_zone_size` are compared
field-by-field against the mzs=4 control and shown identical; `seed_sweep_gat.py`,
`src/snrl/gnn.py`, and `src/snrl/env.py` are byte-identical to both CREDIT's and GAT-LONG's
versions (no drift, no edits).

## Treatment variables (the two intended differences, one from each parent)

| | CREDIT (30k, mzs=1) | GAT-LONG (167k, mzs=4) | **Combined (this experiment)** |
|---|---|---|---|
| `min_zone_size` | **1** | 4 | **1** (from CREDIT) |
| Timesteps | 30,000 | **167,000** | **167,000** (from GAT-LONG) |

Relative to CREDIT, the only change is 30,000 → 167,000 timesteps. Relative to GAT-LONG, the
only change is `min_zone_size` 4 → 1. Both are pre-existing CLI/config toggles
(`seed_sweep_gat.py --timesteps`, and `min_zone_size` already baked into
`configs/city_madina_ablation_r400_gat_mzs1.yaml` by CREDIT) — no code was written or edited
to construct this experiment.

## Branch / commit lineage

```
34f03c8 (original GAT control, 30k, mzs=4 -- both parents' common ancestor)
   ├── gat-r400-longer-training @ 25f968a (167k, mzs=4)
   └── credit-assignment-ablation @ 115220e (30k, mzs=1)
              │
              ▼
   combined-gat-credit-long, branched from 25f968a, then merged 115220e
   (real git ancestry to all three, not just file-content parity --
    the validation script's ancestry check requires this, and originally
    caught it missing when this branch only cherry-picked CREDIT's config
    file rather than merging)
```

Pushed commits on `combined-gat-credit-long`, in order:
1. `66fff1b` — branch setup (checkout mzs1 config from CREDIT) + parity inspection notes
2. `a919bd4` — combined Slurm harness (`slurm/combined_gat_credit_long.sbatch`)
3. `7226338` — merge `115220e` for real ancestry to CREDIT
4. `d1cb5d7` — validation script (42/42 pass)
5. this commit — PROVENANCE.md

## Expected Ibex commands

```bash
cd <your checkout>            # $SLURM_SUBMIT_DIR — the harness no longer hardcodes a path
git fetch origin
git checkout combined-gat-credit-long
git pull

# if data/raw/riyadh_r400 isn't already in this checkout (it's gitignored):
ln -s /path/to/existing/data/raw/riyadh_r400 data/raw/riyadh_r400

sbatch --array=1-5 slurm/combined_gat_credit_long.sbatch
```

## Expected output directory

`runs/r400_gat_mzs1_167k/task_<seed>/` for seed 1..5 — new, not overlapping any of
`runs/r400_gat_30k`, `runs/r400_gat_mzs1_30k`, or `runs/r400_gat_167k` (the harness refuses
to run if `OUTROOT` is pointed at any of those three).

## Aggregation command

```bash
python scripts/aggregate_sweep.py --root runs/r400_gat_mzs1_167k \
    --success-threshold 0.6863 --expect 1-5
```

Note: `+0.6863` is `zone_builder`'s return measured at `min_zone_size=4` (the only measurement
that exists). CREDIT's own `RESULTS.md` already flagged this: `min_zone_size=1` likely changes
what a fair planner ceiling looks like, since `zone_builder` itself was never re-run under
`min_zone_size=1`. Treat `>= 0.6863` as a useful but not perfectly calibrated bar for this
combined run, same caveat CREDIT already carries forward.

## No outcome is claimed before results exist

Nothing above predicts what the combined run will find. The two parent results are reported
because they motivate the experiment and set comparison targets, not because either forecasts
the combination's outcome — CREDIT's consistency and GAT-LONG's ceiling were never tested
together before.
