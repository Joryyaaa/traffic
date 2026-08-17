# Abha named-site scenarios — Madina / RL package

Every scenario is named by its place or purpose; there are no S/A/B/C labels.
All networks are real OpenStreetMap drive-network crops with 30–100 segments.

| Scenario name | Purpose | Ibex status |
|---|---|---|
| Art Street and Al-Muftaha baseline | fully open comparison case | fast baselines only |
| Central Al-Muftaha Market | candidate vehicle restrictions | fast baselines + 2,048-step model |
| Asir Central Hospital | candidate side-street restrictions | fast baselines; intervention budget is negative |
| School cluster | temporary morning restrictions | geometry only; no mapped residential origins |
| King Abdulaziz Grand Mosque | temporary post-prayer restrictions | fast baselines + 2,048-step model; accessibility warning |
| Abu Kheyal Park | evening pedestrian conversion | geometry only; directed baseline accessibility is zero |

The blocked labels are deliberate. No synthetic origins, destinations, or
reward changes were added to force a scenario to run.

## Optimizations used

- The mentor's batched action mask and eight-worker Linux/Ibex path.
- The mentor's exact one-way drive-network support.
- The mentor's exact indexed directed-graph rebuild, measured at 61× on the
  full Abha belt.
- One Slurm array task per independent site; no `srun`; numerical libraries
  capped at one thread.
- Greedy and `zone_builder_best` are separated from the fast jobs.

## Ibex jobs

```bash
sbatch slurm/abha_hotspot_baselines_array.sbatch
sbatch slurm/abha_hotspot_train_2048_array.sbatch
```

The baseline array runs four data-valid sites concurrently. The model array
runs only Central Market and King Abdulaziz Grand Mosque concurrently. See
`slurm/ABHA_HOTSPOT_IBEX_GUIDE.md` for submission and monitoring commands.

Geometry maps and pre-run MP4 previews are under
`results/abha_hotspot_scenarios/`. Red roads in those previews are proposed
intervention targets, not completed model results.
