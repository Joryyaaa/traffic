# Stage 4: Slurm screening arrays (5 seeds/size, not 30 yet)

Three dedicated sbatch files, one per size, following the exact pattern already
validated by `slurm/combined_gat_credit_long.sbatch` (real `$SLURM_SUBMIT_DIR` +
`PYTHONPATH` export, output-dir overwrite guards, data-presence checks that fail
loudly instead of silently refetching/rebuilding):

| file | config | segments | budget | seeds | output root |
|---|---|---|---|---|---|
| `slurm/gat_scaleup_r445.sbatch` | `city_madina_ablation_r445_gat_mzs1.yaml` | 176 | 10/25 | 1-5 | `runs/gat_scaleup_r445_5seed` |
| `slurm/gat_scaleup_r630.sbatch` | `city_madina_ablation_r630_gat_mzs1.yaml` | 290 | 8/20 | 1-5 | `runs/gat_scaleup_r630_5seed` |
| `slurm/gat_scaleup_r850.sbatch` | `city_madina_ablation_r850_gat_mzs1.yaml` | 599 | 14/35 | 1-5 | `runs/gat_scaleup_r850_5seed` |

Screening only, per instruction: 5 seeds each, not the 30-seed full study. Each
guards its own output root against every other experiment's completed/in-progress
output directory in this lineage (`runs/r400_gat_30k`, `runs/r400_gat_mzs1_30k`,
`runs/r400_gat_167k`, `runs/r400_gat_mzs1_167k`, and each other's screening root)
-- none of them can overwrite anything.

## Resource sizing

r445 and r630: `--time=06:00:00 --mem=12G`, matching the COMBINED (r400,
167k) precedent that actually completed on Ibex (max observed 104.0 min --
these two networks are 2-3.3x the reference size, not an order of magnitude, so
the same envelope with its existing ~3.5x margin should hold, though this is
extrapolation, not a measurement -- flag if either job runs close to the limit).

r850: `--time=10:00:00 --mem=16G` -- deliberately more generous. This network
(599 segments) is ~6.7x the r400 reference, larger than any GAT run this project
has timed, so there's no measured precedent to extrapolate from with confidence.
Sized up rather than risk a mid-run timeout on the most expensive of the three
screening arrays.

## To run (not run from this session)

```bash
cd <your checkout>          # $SLURM_SUBMIT_DIR
git checkout gat-scaleup-riyadh
git pull

sbatch --array=1-5 slurm/gat_scaleup_r445.sbatch
sbatch --array=1-5 slurm/gat_scaleup_r630.sbatch
sbatch --array=1-5 slurm/gat_scaleup_r850.sbatch
```

All three can be submitted together and will run in parallel across Ibex's
scheduler, same as any other array job in this project.

## Watching

```bash
squeue -u $USER
sacct -u $USER --starttime=today --format=JobID,JobName,State,Elapsed,MaxRSS
```
