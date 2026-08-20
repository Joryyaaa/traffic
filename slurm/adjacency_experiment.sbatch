#!/bin/bash
# Adjacency-observation experiment: MLP baseline vs MLP+adjacency on r400.
#
# Two conditions, five seeds each (1-5), 30,000 timesteps per seed.
# Uses scripts/seed_sweep.py with one seed per array task (same pattern as
# slurm/sweep_array.sbatch). Each condition is submitted as a separate job.
#
# Hypothesis: the MLP underperforms because its observation lacks local
# topology information, not because MLP is inherently insufficient.
# See results/adjacency_experiment/PROVENANCE.md for full protocol.
#
# Submit BOTH conditions (5 array tasks each, 10 total):
#   cd /home/alblueja/traffic
#
#   sbatch --array=1-5 \
#          --export=ALL,CONFIG=configs/city_madina_ablation_r400_mlp_baseline.yaml,OUTROOT=runs/r400_mlp_baseline_30k \
#          slurm/adjacency_experiment.sbatch
#
#   sbatch --array=1-5 \
#          --export=ALL,CONFIG=configs/city_madina_ablation_r400_mlp_adjacency.yaml,OUTROOT=runs/r400_mlp_adjacency_30k \
#          slurm/adjacency_experiment.sbatch
#
# Aggregate after both complete:
#   python scripts/aggregate_sweep.py --root runs/r400_mlp_baseline_30k \
#       --success-threshold 0.6863 --expect 1-5
#   python scripts/aggregate_sweep.py --root runs/r400_mlp_adjacency_30k \
#       --success-threshold 0.6863 --expect 1-5
#
# zone_builder reference on this config: +0.6863
# Seeds 1-3 overlap historical MLP results for direct comparison.
#
#SBATCH --job-name=snrl-adj-exp
#SBATCH --partition=batch
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --array=1-5
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/alblueja/traffic}"
CONFIG="${CONFIG:-configs/city_madina_ablation_r400_mlp_baseline.yaml}"
TIMESTEPS="${TIMESTEPS:-30000}"
OUTROOT="${OUTROOT:-runs/r400_mlp_baseline_30k}"
EPISODES="${EPISODES:-1}"
CONDA_ENV="${CONDA_ENV:-snrl}"

SEED="${SLURM_ARRAY_TASK_ID}"

cd "$PROJECT_DIR"
mkdir -p logs "$OUTROOT"

unset SLURM_CPU_BIND SLURM_CPU_BIND_LIST SLURM_CPU_BIND_TYPE SLURM_CPU_BIND_VERBOSE
unset SLURM_HINT SLURM_DISTRIBUTION

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export MPLCONFIGDIR="${MPLCONFIGDIR:-/home/$USER/.cache/matplotlib}"
mkdir -p "$MPLCONFIGDIR"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

echo "=== adjacency-observation experiment ==="
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

# Verify MaskablePPO is available — fail fast rather than silently falling
# back to unmasked PPO and producing incomparable results.
python -c "from sb3_contrib import MaskablePPO" || {
    echo "FATAL: sb3-contrib not installed — MaskablePPO required for this experiment."
    exit 1
}

python scripts/seed_sweep.py \
    --config "$CONFIG" \
    --timesteps "$TIMESTEPS" \
    --seeds "$SEED" \
    --episodes "$EPISODES" \
    --out "$OUTROOT/task_$SEED"

echo
echo "finished  : $(date -Is)"
