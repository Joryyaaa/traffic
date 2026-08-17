# Abha named-site Ibex guide

## Submit

From the Ibex shell, update the repository and enter the published branch:

```bash
cd ~/traffic
git fetch origin
git switch codex/abha-hotspot-scenarios
git pull --ff-only
```

Then submit from the repository root:

```bash
conda activate traffic_env
python -m pip install -i https://pypi.org/simple/ pydeck Rtree psutil ipython ipykernel
python -m pip install --no-deps -i https://test.pypi.org/simple/ madina==0.0.15
python -c "import pydeck, rtree, psutil, IPython, ipykernel; from madina.una.tools import betweenness; print('Madina OK')"
mkdir -p logs

BASELINES_JOB=$(sbatch --parsable slurm/abha_hotspot_baselines_array.sbatch)
MODELS_JOB=$(sbatch --parsable slurm/abha_hotspot_train_2048_array.sbatch)
echo "baselines=$BASELINES_JOB models=$MODELS_JOB"
```

The `--no-deps` flag is intentional: the environment already supplies the
geospatial stack, and it prevents pip from resolving unrelated packages from
TestPyPI.

The four baseline tasks run concurrently:

- Art Street and Al-Muftaha baseline;
- Central Al-Muftaha Market;
- Asir Central Hospital;
- King Abdulaziz Grand Mosque.

The two 2,048-step model tasks run concurrently:

- Central Al-Muftaha Market;
- King Abdulaziz Grand Mosque.

School cluster and Abu Kheyal Park are data-blocked and are not silently run.

## Monitor

```bash
squeue -u "$USER"
sacct -j "$BASELINES_JOB,$MODELS_JOB" \
  --format=JobID,JobName,State,Elapsed,MaxRSS,ExitCode
```

## Outputs

```text
results/abha_hotspot_scenarios/ibex/<scenario-name>/
runs/abha_hotspot_2048/<scenario-name>_seed42_2048/
logs/snrl-abha-hotspots-<job>_<task>.out
logs/snrl-abha-2048-<job>_<task>.out
```

`greedy` and `zone_builder_best` remain optional and separate:

```bash
sbatch --export=ALL,POLICIES=zone_builder_best \
  slurm/abha_hotspot_heavy_optional.sbatch
```
