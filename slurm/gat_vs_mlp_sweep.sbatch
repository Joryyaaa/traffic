#!/bin/bash
# Slurm array job for GAT-vs-MLP controlled architecture comparison.
#
# Each array task trains one seed with one architecture on one scale.
# Set ARCH=gat or ARCH=mlp_adj to select the architecture.
# The config file is shared — architecture is determined by the script.
#
# Submit GAT r445 (5 seeds):
#   sbatch --array=1-5 --time=36:00:00 --mem=16G \
#     --export=ALL,ARCH=gat,CONFIG=configs/gat_vs_mlp_r445_mzs1.yaml,TIMESTEPS=200000,OUTROOT=runs/r445_gat_200k,EPISODES=5 \
#     slurm/gat_vs_mlp_sweep.sbatch
#
# Submit MLP+adj r445 (5 seeds):
#   sbatch --array=1-5 --time=36:00:00 --mem=16G \
#     --export=ALL,ARCH=mlp_adj,CONFIG=configs/gat_vs_mlp_r445_mzs1.yaml,TIMESTEPS=200000,OUTROOT=runs/r445_mlp_adj_200k,EPISODES=5 \
#     slurm/gat_vs_mlp_sweep.sbatch
#
# Submit GAT r630 (5 seeds):
#   sbatch --array=1-5 --time=48:00:00 --mem=24G \
#     --export=ALL,ARCH=gat,CONFIG=configs/gat_vs_mlp_r630_mzs1.yaml,TIMESTEPS=200000,OUTROOT=runs/r630_gat_200k,EPISODES=5 \
#     slurm/gat_vs_mlp_sweep.sbatch
#
# Submit MLP+adj r630 (5 seeds):
#   sbatch --array=1-5 --time=48:00:00 --mem=24G \
#     --export=ALL,ARCH=mlp_adj,CONFIG=configs/gat_vs_mlp_r630_mzs1.yaml,TIMESTEPS=200000,OUTROOT=runs/r630_mlp_adj_200k,EPISODES=5 \
#     slurm/gat_vs_mlp_sweep.sbatch
#
#SBATCH --job-name=gat-mlp
#SBATCH --partition=batch
#SBATCH --time=36:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --array=1-5
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/shiekhmf/Student_Projects/Jory/traffic}"
CONFIG="${CONFIG:-configs/gat_vs_mlp_r445_mzs1.yaml}"
TIMESTEPS="${TIMESTEPS:-200000}"
OUTROOT="${OUTROOT:-runs/gat_sweep}"
EPISODES="${EPISODES:-5}"
ARCH="${ARCH:-gat}"
CONDA_ENV="${CONDA_ENV:-snrl}"
CHECKPOINT_FREQ="${CHECKPOINT_FREQ:-50000}"

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
export SNRL_MASK_WORKERS=8
export MPLCONFIGDIR="${MPLCONFIGDIR:-/ibex/user/$USER/mplconfig}"
mkdir -p "$MPLCONFIGDIR"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

echo "=== GAT-vs-MLP controlled comparison ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "arch      : $ARCH"
echo "config    : $CONFIG"
echo "timesteps : $TIMESTEPS"
echo "seed      : $SEED"
echo "episodes  : $EPISODES"
echo "out       : $OUTROOT/task_$SEED"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

if [ "$ARCH" = "gat" ]; then
    SCRIPT="scripts/seed_sweep_gat.py"
elif [ "$ARCH" = "mlp_adj" ]; then
    SCRIPT="scripts/seed_sweep_mlp_adj.py"
else
    echo "ERROR: ARCH must be 'gat' or 'mlp_adj', got '$ARCH'"
    exit 1
fi

python "$SCRIPT" \
    --config "$CONFIG" \
    --timesteps "$TIMESTEPS" \
    --seeds "$SEED" \
    --episodes "$EPISODES" \
    --out "$OUTROOT/task_$SEED" \
    --checkpoint-freq "$CHECKPOINT_FREQ"

echo
echo "finished  : $(date -Is)"
