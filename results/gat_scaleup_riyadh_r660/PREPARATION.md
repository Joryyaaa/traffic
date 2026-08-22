# Riyadh r660 GAT scale-up preparation (not submitted)

## Frozen network

- Center: Al Nakheel, Riyadh `(24.7412, 46.6335)`
- Radius: `660 m`
- Build method: `scripts/fetch_osm_data.py`, identical to the existing Riyadh
  scale-up points
- Street segments: **338**
- Residential origins: **135**
- Amenity destinations: **36**

The three GeoJSON layers are committed with the experiment so an Ibex checkout
does not refetch a different OSM snapshot.

## Fresh budget measurement

`scripts/measure_gat_scaleup_budget.py` ran one deterministic `zone_builder`
episode per candidate on this exact 338-segment network. Reward, observation,
simulation, and all non-budget action fields stayed fixed.

| max closures | episode length | zone_builder return |
|---:|---:|---:|
| **8** | **20** | **+0.3586685709** |
| 9 | 22 | -0.0896613987 |
| 10 | 25 | -0.0896613987 |
| 11 | 28 | -0.1327407563 |
| 12 | 30 | -0.1387382073 |
| 14 | 35 | -0.1545178327 |

Selected: **max_closures=8, episode_length=20**. It is the only positive
candidate in the measured set. The machine-readable record, including wall
times and measurement timestamp, is `budget_measurements.json`.

## Training and walltime

The experiment keeps the validated COMBINED recipe unchanged: GAT feature
extractor, MaskablePPO, adjacency-aware observation, `min_zone_size=1`, and
`167000` timesteps, with five independent seeds in parallel.

Using the completed Riyadh timings (176 segments / 255 min and 290 segments /
689 min), the observed scaling exponent is approximately quadratic. Extrapolating
to 338 segments gives about **15.6 hours per seed**. The Slurm file requests
**20 hours**, leaving roughly 28% headroom; 18 hours is plausible but has only
about 15% headroom. Checkpoints and `progress.json` are written every 10,000
timesteps, so an incomplete seed resumes from its latest checkpoint when the
same output root is resubmitted. Complete seeds skip training.

If a seed resumes, `train_seconds` in its final CSV is read from the cumulative
elapsed time in `progress.json`, rather than reporting only the final Slurm
attempt.

Prepared command, intentionally not run:

```bash
sbatch --array=1-5 slurm/gat_scaleup_r660.sbatch
```

## Validation commands

```bash
python scripts/validate_gat_scaleup_r660.py
python scripts/validate_checkpoint_resume.py
```

The first validates frozen feature counts, exact COMBINED comparability,
machine-recorded budget selection, real environment construction, adjacency,
action/observation spaces, a real GAT forward pass, and the Slurm portability
contract. The second functionally verifies checkpoint, resume, `progress.json`,
and skip-if-complete on a small disposable stub run.
