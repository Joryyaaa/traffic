# Abha S2 baseline status

**Scenario:** hypothetical Green Road alignment (not authoritative ASDA geometry)  
**Network:** 4,602 directed segments (S0 + 16 directed Green Road edges)  
**Config:** `configs/city_madina_abha_s2.yaml`

The no-intervention Madina simulation completed locally and is included in
`results/abha_scenario_maps/scenario_metrics.json`. Policy baselines remain
pending because the Windows run measured about 61 seconds per uncached
simulation call.

Run all policies on Ibex:

```bash
sbatch --export=ALL,CONFIG=configs/city_madina_abha_s2.yaml \
  slurm/abha_s0_baselines.sbatch
```

The Slurm job regenerates `data/raw/abha_s2/` when missing and writes its output
to `results/abha_s2_baselines/ibex_full_baselines_<job-id>.txt`.

Do not interpret S2 as an evaluation of ASDA's actual proposal until the
placeholder waypoints are replaced with the authoritative alignment.
