#!/bin/bash
# Slurm array job: one seed per array task, so a ~100-seed sweep runs in
# parallel across the cluster instead of serially inside one process.
#
# scripts/seed_sweep.py is deliberately used unmodified: each array task calls
# it with a single seed and its own --out directory, so the results.csv it
# truncates on startup belongs to that task alone (two tasks sharing one --out
# would clobber each other's rows). scripts/aggregate_sweep.py then merges the
# per-task CSVs into one sweep-level mean +/- std.
#
# Submit (defaults: Al Nakheel, 30k steps, seeds 1-100):
#   cd /home/shiekhmf/Student_Projects/Jory/traffic
#   sbatch slurm/sweep_array.sbatch
#
# Submit (override anything):
#   sbatch --array=1-100 \
#          --export=ALL,CONFIG=configs/city_madina_jeddah.yaml,TIMESTEPS=30000,OUTROOT=runs/sweep_jeddah_30k \
#          slurm/sweep_array.sbatch
#
# The array task ID *is* the seed, so --array=1-100 trains seeds 1..100 and
# --array=1-10,42 trains seeds 1..10 and 42.
#
#SBATCH --job-name=snrl-sweep
#SBATCH --partition=batch
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --array=1-100
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/shiekhmf/Student_Projects/Jory/traffic}"
CONFIG="${CONFIG:-configs/city_madina_ablation.yaml}"
TIMESTEPS="${TIMESTEPS:-30000}"
OUTROOT="${OUTROOT:-runs/sweep_ablation_30k}"
# The madina backend is deterministic (FlowBackend.reseed() returns False for
# it, see src/snrl/backends/base.py), and the eval policy is deterministic too,
# so N eval episodes are N identical rollouts. 1 is the honest number here;
# raise it only for a stochastic-demand (stub) config.
EPISODES="${EPISODES:-1}"
CONDA_ENV="${CONDA_ENV:-snrl}"

SEED="${SLURM_ARRAY_TASK_ID}"

cd "$PROJECT_DIR"
mkdir -p logs "$OUTROOT"

# `--export=ALL` (needed to pass CONFIG/TIMESTEPS/... through) also drags the
# submitting shell's CPU-binding mask in with it. If you submit from inside
# another Slurm allocation -- e.g. an interactive session -- that stale mask
# describes cores this job was never given, and the step dies with
# "CPU binding outside of job step allocation ... Unable to satisfy cpu bind
# request". Drop the inherited binding and let this job's own allocation stand.
unset SLURM_CPU_BIND SLURM_CPU_BIND_LIST SLURM_CPU_BIND_TYPE SLURM_CPU_BIND_VERBOSE
unset SLURM_HINT SLURM_DISTRIBUTION

# One thread per task: the policy is a small MLP, and 100 concurrent array
# tasks each grabbing every core on their node would thrash.
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
# Keep matplotlib/fontconfig scratch off the shared home fs.
export MPLCONFIGDIR="${MPLCONFIGDIR:-/ibex/user/$USER/mplconfig}"
mkdir -p "$MPLCONFIGDIR"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

echo "=== snrl seed sweep ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "config    : $CONFIG"
echo "timesteps : $TIMESTEPS"
echo "seed      : $SEED"
echo "episodes  : $EPISODES"
echo "out       : $OUTROOT/task_$SEED"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

# No `srun`: this is one serial Python process, so a job step buys nothing and
# only adds a launcher that can fail on inherited CPU-bind state (see above).
python scripts/seed_sweep.py \
    --config "$CONFIG" \
    --timesteps "$TIMESTEPS" \
    --seeds "$SEED" \
    --episodes "$EPISODES" \
    --out "$OUTROOT/task_$SEED"

echo
echo "finished  : $(date -Is)"
