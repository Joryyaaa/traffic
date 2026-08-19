# Verification before submitting seeds 6-30

**Goal:** extend COMBINED from 5 to 30 total seeds, same experiment, no changes. This
document is the verification step done *before* preparing the submission command, per
instruction not to submit anything until byte-for-byte/effective identity is confirmed.

## Completed 5-seed results (branch `combined-gat-credit-long`, commit `8f3e0be`)

Read directly from the committed files, not from memory:

```
Mean return: +0.8528, Std: 0.0210, Min: +0.8108, Median: +0.8633, Max: +0.8633
5/5 seeds >= +0.6863
Mean training time: 95.9 min/seed, Max: 104.0 min

seed 1: +0.8633  (5979.1s)
seed 2: +0.8633  (5762.8s)
seed 3: +0.8108  (6237.3s)
seed 4: +0.8633  (5526.5s)
seed 5: +0.8633  (5271.9s)
```

Matches exactly what was reported to this session — confirmed, not assumed.

## Identity check: nothing has changed since the validated setup that produced these 5 seeds

`d1cb5d7` (this session's own prior commit, "pre-flight validation for the combined
experiment -- all 42 checks pass") is the last point this exact setup was verified
end-to-end, including a real GAT forward pass on the real 89-segment network. Diffed every
file the training run depends on, `d1cb5d7` vs `8f3e0be` (the tip that added the completed
results):

```
git diff d1cb5d7 8f3e0be -- \
    configs/city_madina_ablation_r400_gat_mzs1.yaml \
    scripts/seed_sweep_gat.py \
    src/snrl/gnn.py \
    src/snrl/env.py \
    slurm/combined_gat_credit_long.sbatch
```

**Empty diff on every one of those files.** The config, training script, GAT extractor,
environment code, and Slurm harness that produced the completed seeds 1-5 are exactly what
this worktree has right now, unmodified — nothing to re-verify or reconcile, and nothing
in this task changes any of them.

## Submission for seeds 6-30 requires zero file changes

`slurm/combined_gat_credit_long.sbatch`'s `#SBATCH --array=1-5` is a *default*, not a fixed
value — Slurm's `sbatch --array=<range>` on the command line overrides an in-file
`#SBATCH --array` directive (standard Slurm behavior, same mechanism already used
throughout this project's other sweeps, e.g. `slurm/sweep_array.sbatch`'s own
`--array=1-100` submit example vs. `--array=1-10,42` override example). `OUTROOT` already
defaults to `runs/r400_gat_mzs1_167k`, and each array task writes to
`$OUTROOT/task_$SLURM_ARRAY_TASK_ID` — so `--array=6-30` produces `task_6` through `task_30`
without touching `task_1` through `task_5` at all, by construction, with **no new guard
needed and no file edit**. This is the strictest possible "byte-for-byte identical except
seed/task IDs" — literally the same file, unedited, invoked with a different array range.

**Conclusion: submit seeds 6-30 exactly as follows, no code/config/harness changes.**

```bash
cd /home/alblueja/traffic          # or wherever this checkout lives ($SLURM_SUBMIT_DIR)
git fetch origin
git checkout combined-gat-credit-long
git pull

sbatch --array=6-30 slurm/combined_gat_credit_long.sbatch
```

Everything else (`CONFIG`, `TIMESTEPS=167000`, `CONDA_ENV`, resource requests) stays at the
file's defaults, matching the run that already produced seeds 1-5.

## On job `50676009`

Referenced as "the successful job" to match. This session has no direct Slurm/Ibex access
(no `squeue`/`sacct` from here), so its logs weren't independently inspected — but the
committed results (`8f3e0be`'s `RESULTS.md`/CSV) are consistent with exactly this harness:
same config path, same `TIMESTEPS=167000`, same `OUTROOT=runs/r400_gat_mzs1_167k` naming
convention, same per-seed train_seconds order of magnitude as GAT-LONG's own 167k run. The
verification above (empty diff since the last full local validation) is what this session
can independently confirm; matching the *exact* job further is the part only Ibex-side
`sacct -j 50676009 --format=...` can add, which is left as the exact command below rather
than assumed.

```bash
sacct -j 50676009 --format=JobID,JobName,State,Elapsed,MaxRSS,NNodes,NCPUS
```

## Resources: unchanged, and already generously sized

`--time=06:00:00 --mem=12G --cpus-per-task=2` in the file, unedited. The completed 5-seed
run's actual max was 104.0 min (1.73h) — well inside the existing 6h limit (using only 29%
of it). No reason to change resources for seeds 6-30 running the identical workload; 25
tasks submitted as one array will each land on their own node/allocation per Ibex's
scheduler, same as any other array job in this project (see `slurm/sweep_array.sbatch`'s
own up-to-100-seed arrays), so "in parallel" falls out of `sbatch --array=6-30` by itself —
no extra flag needed for that either.
