# Abha Event Hotspot — Ibex Run Guide

This package is built directly from:
`data/abha_baseline/abha_event_hotspot_baseline2_scenarios.html`

## Scenario contract
- **B0 — B0_Baseline** — Baseline existing 2 km road network; destination is the Event Zone.
- **S1 — S1_Event_Zone_Vehicle_Restriction** — Event Zone Vehicle Restriction; same provisional OD basis as B0, with the mapped restricted road removed.
- **S2 — S2_Main_Parking_Hub** — Main Parking Hub; Madina models the **vehicle leg to Parking P only**. Walking / golf-cart last mile remains a visualization/operations concept, not a Madina vehicle result.
- **S3 — S3_Managed_Entry_Exit** — Managed Entry + Separate Exit; represented as **two Madina assignments** (inbound and outbound) because the current backend is undirected.

## Important demand note
The HTML map does not contain observed traffic counts or a measured OD matrix.
Therefore this package uses a deterministic **provisional reference demand** derived from the map's road-network boundary endpoints.
Use these outputs for structural/scenario comparison, not as calibrated traffic-volume predictions.

## Environment
Use the repository's existing Conda environment:

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate snrl
python -c "import madina; print(madina.__file__)"
```

If `snrl` does not exist yet:

```bash
conda env create -f environment.yml
conda activate snrl
```

## Pre-run validation

```bash
python scripts/build_abha_event_hotspot_data.py
python scripts/validate_abha_event_package.py
python scripts/run_abha_event_madina_smoketest.py
```

## Full Ibex run

```bash
mkdir -p logs results/abha_event_hotspot_madina

SCENARIO_JOB=$(sbatch --parsable slurm/abha_event_hotspot_madina.sbatch)
echo "Scenario job: ${SCENARIO_JOB}"

AGG_JOB=$(sbatch --parsable --dependency=afterok:${SCENARIO_JOB} slurm/abha_event_hotspot_aggregate.sbatch)
echo "Aggregation job: ${AGG_JOB}"
```

## Monitor

```bash
squeue -u "$USER"
sacct -j "${SCENARIO_JOB},${AGG_JOB}" --format=JobID,JobName%30,State,ExitCode,Elapsed
```

## Expected outputs

`results/abha_event_hotspot_madina/`

- `B0_Baseline.json`
- `S1_Event_Zone_Vehicle_Restriction.json`
- `S2_Main_Parking_Hub.json`
- `S3_Managed_Entry_Exit.json`
- `scenario_comparison.json`
- `scenario_comparison.csv`
- `scenario_comparison.md`

No ZIP is required for execution.
