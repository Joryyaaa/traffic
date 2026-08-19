#!/bin/bash
# GAT scale-up SCREENING run, size 1 of 3: r=445m, 176 segments (~150 target).
# Same Al Nakheel center, same GAT architecture, same min_zone_size=1, same
# 167,000 timesteps, same reward/observation/algorithm as the r400/89-segment
# COMBINED reference (which reached mean +0.8365 over 30 seeds, 29/30 >=
# zone_builder's +0.6863). The ONLY intended difference is network size and
# the budget that scales with it (measured, not guessed -- see
# results/gat_scaleup_riyadh/STAGE2_DATASETS.md: max_closures=10,
# episode_length=25 -> zone_builder=+0.8111 on this exact network).
#
# SCREENING, not the full study: 5 seeds (1-5), not 30. Confirms the setup
# trains cleanly at this size before committing more seeds/Ibex time.
#
# Submit (5 array tasks):
#   cd <your checkout>          # $SLURM_SUBMIT_DIR
#   git checkout gat-scaleup-riyadh
#   git pull
#   sbatch --array=1-5 slurm/gat_scaleup_r445.sbatch
#
# Aggregate after completion:
#   python scripts/aggregate_sweep.py --root runs/gat_scaleup_r445_5seed \
#       --success-threshold 0.8111 --expect 1-5
#
#SBATCH --job-name=snrl-gat-scaleup-r445
#SBATCH --partition=batch
#SBATCH --time=06:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --array=1-5
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
CONFIG="${CONFIG:-configs/city_madina_ablation_r445_gat_mzs1.yaml}"
TIMESTEPS="${TIMESTEPS:-167000}"
OUTROOT="${OUTROOT:-runs/gat_scaleup_r445_5seed}"
EPISODES="${EPISODES:-1}"
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
export MPLCONFIGDIR="${MPLCONFIGDIR:-/home/$USER/.cache/matplotlib}"
mkdir -p "$MPLCONFIGDIR"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

echo "=== GAT scale-up SCREENING: r445 (176 segments, ~150 target), 5 seeds ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "project   : $PROJECT_DIR"
echo "config    : $CONFIG"
echo "timesteps : $TIMESTEPS"
echo "seed      : $SEED"
echo "out       : $OUTROOT/task_$SEED"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

EXPECTED_CONFIG="configs/city_madina_ablation_r445_gat_mzs1.yaml"
if [ "$CONFIG" != "$EXPECTED_CONFIG" ]; then
    echo "WARNING: CONFIG ($CONFIG) differs from the intended r445 scale-up config ($EXPECTED_CONFIG)."
fi

if [ ! -f "$CONFIG" ]; then
    echo "FATAL: $CONFIG not found."
    exit 1
fi

for forbidden in "runs/r400_gat_30k" "runs/r400_gat_mzs1_30k" "runs/r400_gat_167k" \
                 "runs/r400_gat_mzs1_167k" "runs/gat_scaleup_r630_5seed" "runs/gat_scaleup_r850_5seed"; do
    if [ "$OUTROOT" = "$forbidden" ]; then
        echo "FATAL: OUTROOT must not be $forbidden -- that is another experiment's output directory."
        exit 1
    fi
done

for f in streets.geojson residential.geojson amenities.geojson; do
    if [ ! -f "data/raw/riyadh_r445/$f" ]; then
        echo "FATAL: data/raw/riyadh_r445/$f not found. This must be the exact frozen dataset from"
        echo "  Stage 2 (results/gat_scaleup_riyadh/STAGE2_DATASETS.md) -- do NOT refetch or rebuild it."
        echo "  data/raw/ is gitignored, so a fresh checkout/worktree will not have it -- copy or"
        echo "  symlink it from wherever it already exists on this filesystem, then resubmit."
        exit 1
    fi
done

python -c "from sb3_contrib import MaskablePPO" || {
    echo "FATAL: sb3-contrib not installed — MaskablePPO required."
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
    --out "$OUTROOT/task_$SEED"

echo
echo "finished  : $(date -Is)"
