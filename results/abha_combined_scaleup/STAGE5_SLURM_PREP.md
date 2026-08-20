# Stage 5: Slurm screening arrays -- prepared and validated, NOT submitted

One dedicated sbatch per valid scenario, following
`slurm/gat_scaleup_r*.sbatch`'s pattern from the Riyadh scale-up study
exactly: real `$SLURM_SUBMIT_DIR`/`PYTHONPATH`, FATAL (not silent-refetch)
data-presence checks, an isolated output root per scenario, and an explicit
guard so no scenario's output root can collide with any other scenario's or
with any protected branch's existing run directory.

| Scenario | sbatch file | Config | Output root |
|---|---|---|---|
| Art Street / Al-Muftaha baseline | `slurm/abha_combined_art_street.sbatch` | `configs/city_madina_abha_art_street_baseline_combined.yaml` | `runs/abha_combined_art_street_5seed` |
| Central Market | `slurm/abha_combined_central_market.sbatch` | `configs/city_madina_abha_central_market_combined.yaml` | `runs/abha_combined_central_market_5seed` |
| Asir Central Hospital | `slurm/abha_combined_asir_hospital.sbatch` | `configs/city_madina_abha_asir_central_hospital_combined.yaml` | `runs/abha_combined_asir_hospital_5seed` |
| King Abdulaziz Grand Mosque | `slurm/abha_combined_grand_mosque.sbatch` | `configs/city_madina_abha_king_abdulaziz_grand_mosque_combined.yaml` | `runs/abha_combined_grand_mosque_5seed` |

Each sbatch:
- `--array=1-5`, `TIMESTEPS=167000` (defaults baked in, overridable via env vars).
- FATAL exit (not a warning, not a silent refetch) if the config or any of
  `streets.geojson`/`residential.geojson`/`amenities.geojson` under that
  scenario's `data/raw/abha_hotspots/<scenario>/` is missing. Unlike the
  Riyadh study's `riyadh_r445` (gitignored, needed a manual copy step onto
  Ibex), the Abha hotspot data is git-tracked (`.gitignore` already carries
  an `abha_hotspots/**` exception from commit `c149487`), so a normal
  `git checkout abha-combined-scaleup && git pull` already has it -- the
  FATAL check exists as a guard against an incomplete checkout, not as an
  expected failure mode.
- Isolation guard: `OUTROOT` checked against the other 3 new scenario roots,
  all 3 Riyadh scale-up roots, and both r400 COMBINED-lineage roots
  (`runs/r400_gat_167k`, `runs/r400_gat_mzs1_167k`) -- 9 forbidden values per
  file, covering every other scenario named in the task plus the 3 new
  siblings.
- `python -c "from sb3_contrib import MaskablePPO"` and
  `python -c "from snrl.gnn import GATFeaturesExtractor"` FATAL checks before
  training starts.
- Calls `scripts/seed_sweep_gat.py` with the established GAT hyperparameter
  defaults (`--gat-hidden-dim 32 --n-heads 4 --global-embed-dim 16
  --features-dim 64`, baked into `seed_sweep_gat.py` itself, not overridden
  here) -- unchanged from the COMBINED reference, per instruction.

## Exact submission commands (NOT run by this task)

```bash
sbatch --array=1-5 slurm/abha_combined_art_street.sbatch
sbatch --array=1-5 slurm/abha_combined_central_market.sbatch
sbatch --array=1-5 slurm/abha_combined_asir_hospital.sbatch
sbatch --array=1-5 slurm/abha_combined_grand_mosque.sbatch
```

Per the task's explicit instruction: screening arrays are written and
validated (Stage 4), never submitted, in this task. No `sbatch` command was
executed.
