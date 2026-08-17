# Abha Event Hotspot — Ibex Run Package

Branch-ready Madina package for Baseline 2 (Art Street + Al-Muftaha).

Scenarios: B0 baseline, S1 event-zone vehicle restriction, S2 main parking hub + walk/golf cart, and S3 managed entry + separate exit.

Run the local smoke test before submitting to Ibex:

```bash
conda activate traffic_env
python scripts/run_abha_event_madina_smoketest.py
```

Ibex submission:

```bash
sbatch slurm/abha_event_hotspot_madina.sbatch
```

Do not describe the package as validated until the Madina smoke run passes.