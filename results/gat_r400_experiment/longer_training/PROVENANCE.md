# GAT r400 — Longer Training Follow-up (167k steps)

**Branch:** `gat-r400-longer-training`, forked from `34f03c8` (`gat-r400-experiment`,
"add completed 5-seed GAT r400 results").
**Status:** prepared, not run. Real 5-seed Ibex jobs to be submitted by Jory, not this
session (see "Exact submission commands" below).

## Hypothesis

The completed 30k-step GAT experiment (mean -0.0322, std 0.0060, 0/5 seeds beat
`zone_builder`'s +0.6863) improved on both MLP baselines but stayed far below the
planner. Two candidate explanations were raised after review: (A) a credit-assignment
problem in the reward (`min_zone_size=4` delays the first non-zero signal — being
tested separately, branch `credit-assignment-ablation`), and (B) the model is simply
undertrained at 30k steps. **This experiment tests (B) in isolation**, changing nothing
except how long GAT trains.

## Why this is a controlled comparison

| | GAT, 30k (completed, `34f03c8`) | GAT, 167k (this experiment) |
|---|---|---|
| Config file | `configs/city_madina_ablation_r400_gat.yaml` | **same file, unmodified** |
| Network | Al Nakheel r=400m, 89 segments | same |
| Observation | 7 features (`include_adjacency_state: true`) | same |
| Extractor | `GATFeaturesExtractor` | same |
| GAT architecture | 2 layers, 32-dim, 4 heads (head_dim=8), ELU | same (all defaults in `seed_sweep_gat.py`, untouched) |
| Algorithm | MaskablePPO | same |
| `max_closures` / `episode_length` | 9 / 22 | same |
| Reward weights, `min_zone_size`, `zone_exponent`, `zone_min_flow_fraction` | unchanged | same |
| Seeds | 1, 2, 3, 4, 5 | same |
| Eval | 1 deterministic episode | same |
| Training script | `scripts/seed_sweep_gat.py` | **same file, unmodified** |
| **Timesteps** | **30,000** | **167,000** |
| Output dir | `runs/r400_gat_30k` | `runs/r400_gat_167k` (never overwrites the 30k dir — the sbatch script itself refuses to run if `OUTROOT=runs/r400_gat_30k`) |

No code was changed to run this experiment: `--timesteps` and `--out` are pre-existing
CLI flags on `seed_sweep_gat.py` (added when that script was first written for the 30k
run), so the "only intended difference is training budget" claim holds by construction,
not just by care -- there was no config field or code path to accidentally touch.
`scripts/validate_gat_r400_longer_training.py` checks this mechanically (see below).

## Why 167,000 steps, not the suggested default of 100,000

Repository evidence points at 167k specifically, not an arbitrary round number:
the mentor's own completed **network-size sweep** (`origin/mentor/sweep-harness`,
`results/README.md`, "Network-size sweep, 5 sizes x 3 seeds") already trained a
**plain MLP** (5-feature observation, no adjacency state, no graph extractor — the
`flatten+MLP` default SB3 extractor) on this **exact same 89-segment r400 network**
for **167,000 steps**, 3 seeds, and reached:

| segments | steps | mean | max | planner | >= planner |
|---|---|---|---|---|---|
| 89 | 167k | +0.2631 | **+0.8125** | +0.6863 | 1/3 |

That is a qualitatively different regime from anything measured on this network at 30k
steps so far — MLP baseline -0.0733, MLP+adjacency -0.0529, GAT -0.0322, all negative.
167k is not a guess at "how long is long enough" here; it is the exact budget already
shown sufficient to reach (and on one seed, beat) planner-class performance on this
network, using a strictly *weaker* architecture (no adjacency information at all). If
GAT — which has strictly more information available (adjacency-aware observation,
learned attention over neighbours) — still cannot reach that regime at the same step
count, that is a meaningfully stronger negative result than "GAT underperforms at 30k."
If GAT matches or beats the plain-MLP-at-167k result, that is a meaningfully stronger
positive result than closing part of a 30k-step gap.

A round 100k was the suggested default in the absence of contrary evidence; this
evidence is direct, on this exact network, and was already sitting in the repository
(`origin/mentor/sweep-harness`) before this branch was created.

## Runtime and resource sizing

Completed 30k run, from `gat_30k_results_all.csv` on `gat-r400-experiment`:

| seed | train_seconds | minutes |
|---|---|---|
| 1 | 2481.1 | 41.4 |
| 2 | 2461.8 | 41.0 |
| 3 | 2416.0 | 40.3 |
| 4 | 2360.8 | 39.3 |
| 5 | 2543.7 | 42.4 |
| **mean** | **2452.7** | **40.9** |

Linear extrapolation to 167k steps: 40.9 * (167000/30000) = **~227.7 min/seed = ~3.8h/seed**.
`slurm/gat_r400_experiment_167k.sbatch` sets `--time=06:00:00` (~58% margin over the
estimate) and `--mem=12G`, `--cpus-per-task=2` (matching the completed 30k job's *actual*
resource request, confirmed by reading `slurm/gat_r400_experiment.sbatch` directly —
**not** the 16G quoted to this session, which doesn't match either committed GAT sbatch
file, `gat_r400_experiment.sbatch` or `credit_assignment_ablation.sbatch`; both use 12G.
Flagging this rather than silently picking one number). Memory footprint shouldn't scale
with timestep count (same network, same batch size, same model — more steps means more
PPO updates, not more memory per update), so 12G carried forward is a reasoned choice,
not just the default.

## Files changed

- `slurm/gat_r400_experiment_167k.sbatch` (new) — dedicated harness, not a copy edited
  in place, so the completed 30k harness stays exactly as it was for the record.
- `results/gat_r400_experiment/longer_training/PROVENANCE.md` (this file)
- `scripts/validate_gat_r400_longer_training.py` (new) — pre-flight checks
- **Not touched:** `configs/city_madina_ablation_r400_gat.yaml`, `scripts/seed_sweep_gat.py`,
  `src/snrl/gnn.py`, `runs/r400_gat_30k/`, anything under `results/gat_r400_experiment/completed_5seed/`.

## Validation results

See `scripts/validate_gat_r400_longer_training.py` output, run locally (Windows, this
session) since torch/gymnasium/sb3-contrib are available here too — not an Ibex-only
check. Confirms: config file is byte-identical (hash-compared) to the one referenced by
the completed 30k run's sbatch; `seed_sweep_gat.py` is unmodified (hash-compared);
GAT architecture defaults (`gat_hidden_dim=32, n_heads=4, global_embed_dim=16,
features_dim=64`) match the completed run; GATFeaturesExtractor constructs and runs a
forward pass on the real 89-segment adjacency; the new sbatch references the unmodified
config, the new output dir, 167000 default timesteps, and guards against overwriting
`runs/r400_gat_30k`. Full pass/fail output is reported in the chat, not duplicated here
to avoid the log going stale if the script is re-run.

## Exact submission commands (Jory / Ibex — not run by this session)

```bash
cd /home/alblueja/traffic
git fetch origin
git checkout gat-r400-longer-training
git pull

sbatch --array=1-5 slurm/gat_r400_experiment_167k.sbatch
```

## Exact aggregation command (after the array completes)

```bash
python scripts/aggregate_sweep.py --root runs/r400_gat_167k \
    --success-threshold 0.6863 --expect 1-5
```

## Expected output directory

`runs/r400_gat_167k/task_<seed>/` for seed in 1..5, each containing `model.zip` and
`results.csv` (same layout `seed_sweep_gat.py` already produces for the 30k run, just
under a different root). `runs/r400_gat_167k/results.csv` is NOT produced by
`seed_sweep_gat.py` itself in array mode (each array task's `--out` is its own
`task_$SEED` subdirectory, matching the existing 30k harness's convention exactly) —
`aggregate_sweep.py --root runs/r400_gat_167k --expect 1-5` is what merges the five
per-task CSVs into one sweep-level summary, same as the 30k run.

## No outcome is claimed before results exist

This document reports what was prepared and validated, not what the longer-training
run found — no jobs have been submitted from this session. Do not read the "why 167k"
section's cited plain-MLP result (+0.2631 mean, +0.8125 best) as a prediction for what
GAT will do; it is the justification for the chosen budget, not a forecast.
