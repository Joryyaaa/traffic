#!/bin/bash
# Riyadh scale-up near 340 segments: r=660m, exactly 338 segments.
# Same Al Nakheel center and COMBINED recipe as the established scale-up:
# GAT + MaskablePPO, min_zone_size=1, adjacency state, 167k timesteps.
# The action budget was measured on this exact frozen network:
# max_closures=8, episode_length=20, zone_builder=+0.3586685709.
#
# Checkpoint/resume follows the validated NEOM pattern. Resubmitting with the
# same OUTROOT resumes each incomplete seed from its latest 10k checkpoint;
# complete seeds skip training. This file is prepared only -- do not submit
# without explicit approval.
#
# Ready command (5 seeds in parallel):
#   sbatch --array=1-5 slurm/gat_scaleup_r660.sbatch
#
# Aggregate after all seeds complete:
#   python scripts/aggregate_sweep.py --root runs/gat_scaleup_r660_5seed \
#     --success-threshold 0.3586685709 --expect 1-5

#SBATCH --job-name=snrl-gat-scaleup-r660
#SBATCH --partition=batch
#SBATCH --time=20:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --array=1-5
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
CONFIG="${CONFIG:-configs/city_madina_ablation_r660_gat_mzs1.yaml}"
TIMESTEPS="${TIMESTEPS:-167000}"
OUTROOT="${OUTROOT:-runs/gat_scaleup_r660_5seed}"
EPISODES="${EPISODES:-1}"
CHECKPOINT_FREQ="${CHECKPOINT_FREQ:-10000}"
CONDA_ENV="${CONDA_ENV:-snrl}"

SEED="${SLURM_ARRAY_TASK_ID}"

cd "$PROJECT_DIR"
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
mkdir -p logs "$OUTROOT"

unset SLURM_CPU_BIND SLURM_CPU_BIND_LIST SLURM_CPU_BIND_TYPE SLURM_CPU_BIND_VERBOSE
unset SLURM_HINT SLURM_DISTRIBUTION

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export MPLCONFIGDIR="${MPLCONFIGDIR:-$HOME/.cache/matplotlib}"
mkdir -p "$MPLCONFIGDIR"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

echo "=== Riyadh GAT scale-up r660: 338 segments, COMBINED, 5 seeds ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "project   : $PROJECT_DIR"
echo "config    : $CONFIG"
echo "timesteps : $TIMESTEPS"
echo "seed      : $SEED"
echo "episodes  : $EPISODES"
echo "ckpt_freq : $CHECKPOINT_FREQ"
echo "out       : $OUTROOT/task_$SEED"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

EXPECTED_CONFIG="configs/city_madina_ablation_r660_gat_mzs1.yaml"
if [ "$CONFIG" != "$EXPECTED_CONFIG" ]; then
    echo "WARNING: CONFIG ($CONFIG) differs from the intended r660 config ($EXPECTED_CONFIG)."
fi

if [ ! -f "$CONFIG" ]; then
    echo "FATAL: $CONFIG not found. Pull the prepared branch; do not guess this config."
    exit 1
fi

for forbidden in \
    "runs/r400_gat_167k" "runs/r400_gat_mzs1_167k" \
    "runs/gat_scaleup_r445_5seed" "runs/gat_scaleup_r630_5seed" \
    "runs/gat_scaleup_r850_5seed" "runs/neom_gat_subgraph_r750_167k"; do
    if [ "$OUTROOT" = "$forbidden" ]; then
        echo "FATAL: OUTROOT $OUTROOT belongs to another experiment."
        exit 1
    fi
done

for file in streets.geojson residential.geojson amenities.geojson; do
    if [ ! -f "data/raw/riyadh_r660/$file" ]; then
        echo "FATAL: data/raw/riyadh_r660/$file is missing."
        echo "  Use the exact frozen r660 dataset committed with this experiment;"
        echo "  do not refetch or substitute another Riyadh network."
        exit 1
    fi
done

python -c "from sb3_contrib import MaskablePPO" || {
    echo "FATAL: sb3-contrib not installed -- MaskablePPO is required."
    exit 1
}

python -c "from snrl.gnn import GATFeaturesExtractor" || {
    echo "FATAL: GATFeaturesExtractor not importable."
    exit 1
}

python scripts/seed_sweep_gat.py \
    --config "$CONFIG" \
    --timesteps "$TIMESTEPS" \
    --seeds "$SEED" \
    --episodes "$EPISODES" \
    --checkpoint-freq "$CHECKPOINT_FREQ" \
    --success-threshold 0.3586685709 \
    --out "$OUTROOT/task_$SEED"

echo
echo "finished  : $(date -Is)"
