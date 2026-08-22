# Stage 5: Slurm harness (NOT submitted)

Harness: `slurm/neom_gat_subgraph_combined.sbatch`
Training script: `scripts/seed_sweep_gat.py` (checkpoint/resume support added)

## What's in the harness (same pattern as `slurm/gat_scaleup_r*.sbatch` / `slurm/combined_gat_credit_long.sbatch`)

- Real `$SLURM_SUBMIT_DIR` + `PYTHONPATH` export (not a hardcoded path).
- FATAL (not silent-refetch) checks: config file present, NEOM subgraph
  data files present (all three of streets/origins/destinations.geojson),
  `sb3-contrib`/`GATFeaturesExtractor` importable.
- Output-root collision guard against every existing run directory in this
  project (`runs/r400_gat_167k`, `runs/r400_gat_mzs1_167k`,
  `runs/gat_scaleup_r445_5seed`, `runs/gat_scaleup_r630_5seed`,
  `runs/gat_scaleup_r850_5seed`, `runs/abha_combined_*`).
- `--array=1-5`, config `configs/city_madina_neom_gat_subgraph_r750_mzs1.yaml`,
  167,000 timesteps, own output root `runs/neom_gat_subgraph_r750_167k`.

## Required addition beyond the Riyadh template: checkpointing + resume

The mentor flagged that the 599-segment Riyadh scale-up run showed a long
non-checkpointed job is unacceptable. `scripts/seed_sweep_gat.py` now has:

1. **Checkpointing**: SB3's own `CheckpointCallback` (no custom
   checkpoint-serialization code -- SB3 already provides this) saves
   `model.zip` into `<out>/seed_<N>/checkpoints/` every
   `--checkpoint-freq` timesteps (default 10,000; the sbatch exposes this
   as `$CHECKPOINT_FREQ`).
2. **Resume**: on start, `find_latest_checkpoint()` looks for the
   highest-timestep checkpoint in that seed's `checkpoints/` dir. If found,
   `MaskablePPO.load(ckpt_path, env=env)` restores the model (SB3 preserves
   `model.num_timesteps`), and `model.learn(total_timesteps=remaining,
   reset_num_timesteps=False, ...)` continues training for only the
   remaining steps -- never restarted from 0. This is logged explicitly:
   `[resume] seed N: found checkpoint at K timesteps -> path. Continuing
   from there, NOT restarting from 0.` If the seed's final `model.zip`
   already exists (fully completed before), training is skipped entirely
   and only evaluation re-runs.
3. **Progress logging that survives a lost log stream**: a
   `_ProgressLoggerCallback` writes `<out>/seed_<N>/progress.json` every
   `--checkpoint-freq` timesteps: `{seed, timesteps_completed,
   target_timesteps, elapsed_seconds, last_checkpoint, updated}`.
   `elapsed_seconds` accumulates correctly across resumes (the previous
   progress.json's value is read back as a time offset on resume, so it
   isn't reset to 0 just because the process restarted).

No third-party checkpoint library was added -- this uses
`stable_baselines3.common.callbacks.CheckpointCallback`, which SB3 already
ships, per the instruction to check what SB3/sb3-contrib offers before
writing custom logic.

## Functional verification (not just code review)

`tmp_ckpt_test/test_resume.py` (scratch, not committed -- exercises the
exact same `find_latest_checkpoint`/`_ProgressLoggerCallback` functions
imported directly from `scripts/seed_sweep_gat.py`, with a small
`n_steps=16`/`batch_size=8` purely so the test finishes in seconds instead
of requiring a full 2048-step PPO rollout):

1. Phase 1: fresh `MaskablePPO` trained to 32 timesteps with
   `save_freq=16` -> asserts a checkpoint file exists, its filename encodes
   a nonzero absolute timestep, and `progress.json`'s
   `timesteps_completed` matches `model.num_timesteps`.
2. Phase 2: a **separate** model/env instance loads that checkpoint (
   simulating a fresh process after preemption) -> asserts
   `model2.num_timesteps == ckpt_steps` immediately after load (not 0),
   trains for the remaining timesteps only, asserts the final
   `model2.num_timesteps` hits the target exactly (not overshooting by a
   full fresh rollout), and asserts `progress.json`'s `elapsed_seconds`
   accumulated across the simulated resume rather than resetting.

Result: **ALL CHECKPOINT/RESUME CHECKS PASSED.**

## Exact (unexecuted) future command

```bash
cd <your checkout of this repo>
git checkout neom-gat-subgraph-combined
git pull
sbatch --array=1-5 slurm/neom_gat_subgraph_combined.sbatch
```

**This was not run.** Per instruction, Stage 5 produces the harness only.
