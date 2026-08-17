# Optimized Abha to Jabal Soudah Viewpoint — Ibex Run

This branch contains the self-contained Madina run package for the validated Abha full-belt network and the two Khamis Mushait approaches to Jabal Soudah Viewpoint.

## What runs

Only three irreducible Madina simulations are submitted:

1. Full-belt city-accessibility context.
2. Route 10 approach to Jabal Soudah Viewpoint.
3. Route 2120 approach to Jabal Soudah Viewpoint.

The both-approach baseline and the 1.5x and 2.0x demand cases are then derived exactly from the two approach runs. This avoids repeating equivalent Madina work.

The submitted jobs request 24 GB for the full-city context and 4 GB for the corridor runs. Their scheduler limits are 30 minutes and 10 minutes respectively; expected runtime is minutes, not days.

## Submit on Ibex

From the repository root:

```bash
conda activate traffic_env
mkdir -p logs

CITY_JOB=$(sbatch --parsable slurm/abha_khamis_soudah_city_context.sbatch)
CORRIDOR_JOB=$(sbatch --parsable slurm/abha_khamis_soudah_madina.sbatch)

sbatch --dependency=afterok:${CITY_JOB}:${CORRIDOR_JOB} \
  slurm/abha_khamis_soudah_aggregate.sbatch
```

The final comparison will be written to:

- `results/abha_khamis_soudah_ibex/scenario_comparison.csv`
- `results/abha_khamis_soudah_ibex/scenario_comparison.md`

## Validation notes

- Destination: Jabal Soudah Viewpoint (`مطل السودة١`), OSM node `7523059174`.
- The final existing access segment to the viewpoint is included.
- Both Khamis Mushait approaches are directionally connected to the destination.
- The belt roundabout connection is included in the validated full-belt network.
- The mentor's eight-worker connectivity optimization remains unchanged. These jobs are static Madina assignments and do not modify or depend on the closure-policy code.
- Exact greedy and `zone_builder_best` searches are intentionally excluded from this package because they are separate long-running closure-policy experiments.

For detailed inputs, checks, and expected outputs, see `slurm/ABHA_KHAMIS_SOUDAH_IBEX_GUIDE.md`.
