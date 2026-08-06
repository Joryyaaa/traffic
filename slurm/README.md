# Running the heavy experiments on Ibex

The README's `[needs APEX]` items are all the same shape: train the same config
across many seeds, then report a mean ± std instead of one lucky run.
`scripts/seed_sweep.py` does that serially in one process. On a cluster the
seeds are independent, so they belong in a Slurm **array** job: one seed per
task, all in flight at once.

`slurm/sweep_array.sbatch` calls `scripts/seed_sweep.py` unmodified, once per
array task, with `--seeds <task_id>` and its own `--out` directory. That last
part matters: `seed_sweep.py` truncates `<out>/results.csv` when it starts, so
two tasks sharing one `--out` would overwrite each other's rows.
`scripts/aggregate_sweep.py` merges the per-task CSVs back into one sweep.

## One-time setup

```bash
# conda env (geopandas + madina + sb3-contrib). ~10 min.
conda env create -f environment.yml            # see note below
conda activate snrl
pip install --no-deps -i https://test.pypi.org/simple/ madina

# real-city data (needs outbound internet; Ibex compute nodes have it)
python scripts/fetch_osm_data.py --radius 250 --out data/raw/riyadh_ablation --lat 24.7412 --lon 46.6335
python scripts/fetch_osm_data.py --radius 250 --out data/raw/jeddah          --lat 21.583186 --lon 39.153762

# sanity: is the pedestrian-zone bonus even reachable on this network?
python scripts/check_zone_feasibility.py --config configs/city_madina_ablation.yaml
python scripts/baseline_report.py --config configs/city_madina_ablation.yaml
```

Two notes on `environment.yml`:

- it does not list `osmnx`, which `scripts/fetch_osm_data.py` imports
  (`requirements.txt` has it, the conda file does not).
- its `pip:` block sets TestPyPI as the *primary* index, so pip may resolve
  `geopandas`/`numpy`/... from TestPyPI, where anyone can upload under those
  names. Installing madina afterwards with
  `pip install --no-deps -i https://test.pypi.org/simple/ madina` avoids that.

## Submitting a sweep

```bash
cd /home/shiekhmf/Student_Projects/Jory/traffic

# Al Nakheel (Riyadh), 100 seeds x 30k steps
sbatch --array=1-100 \
  --export=ALL,CONFIG=configs/city_madina_ablation.yaml,TIMESTEPS=30000,OUTROOT=runs/sweep_ablation_30k \
  slurm/sweep_array.sbatch

# Jeddah (Al Salamah), same protocol -- does greedy-fails/planning-wins repeat?
sbatch --array=1-100 \
  --export=ALL,CONFIG=configs/city_madina_jeddah.yaml,TIMESTEPS=30000,OUTROOT=runs/sweep_jeddah_30k \
  slurm/sweep_array.sbatch

# longer training, on a subset of the same seeds, so 30k vs 100k is a
# within-seed comparison rather than two different seed sets
sbatch --array=1-10,42 \
  --export=ALL,CONFIG=configs/city_madina_ablation.yaml,TIMESTEPS=100000,OUTROOT=runs/sweep_ablation_100k \
  slurm/sweep_array.sbatch
```

The array task ID **is** the seed. `--array=1-100` trains seeds 1..100;
`--array=1-10,42` trains seeds 1..10 and 42.

Overridable via `--export`: `CONFIG`, `TIMESTEPS`, `OUTROOT`, `EPISODES`,
`PROJECT_DIR`, `CONDA_ENV`.

`EPISODES` defaults to **1** on purpose. The madina backend is deterministic
(`FlowBackend.reseed()` returns `False` for it) and the eval policy is
deterministic, so N eval episodes are N identical rollouts and the per-seed
`std_return` is structurally 0. Raise it only for a stochastic-demand stub
config, where each episode really is a different draw.

## Watching and collecting

```bash
squeue -u $USER                      # queue state
sacct -j <jobid> --format=JobID,State,Elapsed,MaxRSS   # after the fact
tail -f logs/snrl-sweep-<jobid>_1.out

python scripts/aggregate_sweep.py --root runs/sweep_ablation_30k --expect 1-100 \
    --success-threshold <zone_builder return from evaluate.py on this config>
```

`--expect` makes a partly-failed array visible: any submitted seed with no
results row is listed as missing, so a sweep that lost 12 tasks cannot be
quoted as a 100-seed mean.

## Picking `--success-threshold`

`seed_sweep.py` defaults to 0.9, which came from pre-fix Al Nakheel numbers.
Re-measure per scenario and use that run's `zone_builder` (or `zone_builder_best`)
return, because the right bar differs a lot by scenario:

    python scripts/evaluate.py --config <config> --episodes 1

Measured on 2026-08-06, on deduplicated data with the corrected `rel()`
(commit b138dba):

| scenario | streets | greedy | zone_builder | suggested threshold |
|---|---|---|---|---|
| Al Nakheel r=250 | 26 | 0.0000 | +0.2661 | 0.2661 (secondary bar: 0.0) |
| Jeddah r=250 | 58 | 0.0000 | +0.9435 | 0.9435 |

Greedy scores exactly 0.0000 on both by refusing to act, so 0.0 is always worth
reporting as "did the agent beat doing nothing".
