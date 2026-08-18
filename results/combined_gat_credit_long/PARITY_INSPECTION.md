# Parity inspection: CREDIT (115220e) vs GAT-LONG (25f968a)

Raw inspection notes, done before writing any combined config/harness, per instruction not
to assume either branch's contents. Everything below was checked directly against the two
commits (`git show`, `git diff`), not from memory of the earlier (pre-completion) prep work.

## 1. CREDIT's exact config (`configs/city_madina_ablation_r400_gat_mzs1.yaml` @ 115220e)

Diffed directly against `configs/city_madina_ablation_r400_gat.yaml` (the GAT-LONG control)
at the same commit. **Only `reward.min_zone_size` differs (4 -> 1)**, plus header comments.
Confirmed byte-for-byte via `git diff`, not inferred from commit messages:

- network/data paths: identical (`data/raw/riyadh_r400/...`, same CRS)
- simulation: identical
- action (`max_closures=9`, `episode_length=22`, etc.): identical
- reward weights other than `min_zone_size`: identical
- `include_adjacency_state: true`: identical
- `seed: 42` (base seed, overridden per-array-task): identical

## 2. GAT-LONG's exact implementation (25f968a)

- `configs/city_madina_ablation_r400_gat.yaml`: min_zone_size=4 (the control this whole
  lineage started from)
- `scripts/seed_sweep_gat.py`: GAT defaults `gat_hidden_dim=32, n_heads=4,
  global_embed_dim=16, features_dim=64` — unchanged from the original 30k experiment
- `src/snrl/gnn.py` (`GATFeaturesExtractor`): 2 layers, 32-dim, 4 heads, ELU, mean-pool +
  16-dim global-row MLP -> 64-dim output — same architecture as both prior experiments

## 3-7. Code identity between the two branches

`git diff 115220e 25f968a` on the three files that matter for reproducing training exactly:

| file | diff |
|---|---|
| `scripts/seed_sweep_gat.py` | **empty — byte-identical** |
| `src/snrl/gnn.py` | **empty — byte-identical** |
| `src/snrl/env.py` | **empty — byte-identical** |

No drift between the two independently-completed branches on any code path the combined
run depends on. This means the combined config only needs `min_zone_size=1` (from CREDIT)
+ `--timesteps 167000` (from GAT-LONG's CLI flag) — no code changes at all, and no new
config content beyond what CREDIT already committed as
`configs/city_madina_ablation_r400_gat_mzs1.yaml`.

## 8. Seed handling

Both experiments: `seed_sweep_gat.py`, seeds 1-5, one Slurm array task per seed
(`SEED="${SLURM_ARRAY_TASK_ID}"`), `cfg.seed = seed` inside `train_one_seed()`. Identical
mechanism in both branches (confirmed by the empty diff above).

## 9. Evaluation procedure

Both: `evaluate_deterministic()` in `seed_sweep_gat.py`, 1 episode (`--episodes 1` default),
`model.predict(..., deterministic=True)`. Identical (same file, no diff).

## 10. Output structure

- CREDIT: `runs/r400_gat_mzs1_30k/task_<seed>/{model.zip,...}`, aggregated via
  `scripts/aggregate_sweep.py --root runs/r400_gat_mzs1_30k`
- GAT-LONG: `runs/r400_gat_167k/task_<seed>/{model.zip,...}`, same aggregator
- Combined run must use a **third, new** directory — see the harness for the explicit guard
  (below).

## 11. Slurm resources — real fix discovered on Ibex, not in either original harness commit

Both completed-results commits (115220e, 25f968a) include a 3-line diff to their own
sbatch file, applied **after** the original harness was written and validated locally, and
**before** the jobs that actually completed successfully:

```diff
-PROJECT_DIR="${PROJECT_DIR:-/home/alblueja/traffic}"
+PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
 ...
 cd "$PROJECT_DIR"
+export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
```

Applied identically, independently, on both branches — this is the real, validated fix for
the worktree/project-directory issue referenced in the combined-experiment brief, not a
one-off. The combined harness below starts from this pattern rather than the older
hardcoded-path version that neither completed run actually used.

## 12. Runtime, for resource sizing

GAT-LONG (167k) actual per-seed `train_seconds`, from `gat_167k_results_all.csv`:
8324.3, 7320.2, 8798.5, 6459.4, 8622.4 -> mean 7904.96s = **131.7 min/seed** (range 107.7-146.6
min). Notably faster than the 30k-run's linear extrapolation predicted (227.7 min) -- the
original 167k harness's 6-hour time limit had ~2.7x actual margin, not the ~1.6x it was sized
for. CREDIT (30k, mzs1) actual: 2867.6, 2393.6, 2443.7, 2285.4, 2429.1 -> mean 2483.9s = 41.4
min/seed, in line with the original (non-mzs1) 30k run's 40.9 min/seed -- min_zone_size does
not meaningfully change per-step cost, as expected (it only changes the reward's zone-scoring
arithmetic, not the simulation).

The combined run (mzs1 + 167k) has no direct precedent for runtime, but nothing about
combining the two treatments should change per-step cost -- both observed effects (167k's
step count, mzs1's reward arithmetic) are independent of each other. Sized the harness off
the 167k run's actual numbers as the more relevant (same step count) reference.
