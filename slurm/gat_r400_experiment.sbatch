#!/bin/bash
# GAT experiment on Al Nakheel r=400m: graph attention vs MLP baselines.
#
# Five seeds (1-5), 30,000 timesteps per seed.
# Uses scripts/seed_sweep_gat.py with one seed per array task.
# GATFeaturesExtractor replaces the default flatten+MLP extractor;
# the RL algorithm (MaskablePPO) and all env/reward settings are unchanged.
#
# See results/gat_r400_experiment/PROVENANCE.md for full protocol.
#
# Submit (5 array tasks):
#   cd /home/alblueja/traffic
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
#   sbatch --array=1-5 slurm/gat_r400_experiment.sbatch
#
# Aggregate after completion:
#   python scripts/aggregate_sweep.py --root runs/r400_gat_30k \
#       --success-threshold 0.6863 --expect 1-5
#
# Comparison targets:
#   MLP baseline (5-feature):      mean -0.0733
#   MLP + adjacency (7-feature):   mean -0.0529
#   zone_builder:                  +0.6863
#
#SBATCH --job-name=snrl-gat-r400
#SBATCH --partition=batch
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --array=1-5
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/alblueja/traffic}"
CONFIG="${CONFIG:-configs/city_madina_ablation_r400_gat.yaml}"
TIMESTEPS="${TIMESTEPS:-30000}"
OUTROOT="${OUTROOT:-runs/r400_gat_30k}"
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

echo "=== GAT r400 experiment ==="
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

# Verify MaskablePPO is available
python -c "from sb3_contrib import MaskablePPO" || {
    echo "FATAL: sb3-contrib not installed — MaskablePPO required."
    exit 1
}

# Verify GAT extractor imports
python -c "from snrl.gnn import GATFeaturesExtractor" || {
    echo "FATAL: GATFeaturesExtractor not importable."
    exit 1
}

python scripts/seed_sweep_gat.py \
    --config "$CONFIG" \
    --timesteps "$TIMESTEPS" \
    --seeds "$SEED" \
    --episodes "$EPISODES" \
    --out "$OUTROOT/task_$SEED"

echo
echo "finished  : $(date -Is)"
