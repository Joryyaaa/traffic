#!/bin/bash
# Abha COMBINED GAT SCREENING run: King Abdulaziz Grand Mosque, 87 segments.
# Same GAT architecture, same min_zone_size=1, same 167,000 timesteps, same
# reward/observation/algorithm as the r400/89-segment COMBINED reference.
# The ONLY intended difference is network (this scenario's own real Abha
# geometry) and the budget measured for it -- see
# results/abha_combined_scaleup/STAGE2_STAGE3.md: max_closures=2,
# episode_length=5 -> zone_builder=+0.0503 on this exact network under
# mzs=1 (independently re-measured, not reused from the old mzs=2 config
# even though the value coincides). Return is positive but accessibility
# fell substantially in the original directed evaluation -- keep
# accessibility Gini/change visible when reviewing trained results, don't
# read the scalar return alone.
#
# SCREENING, not the full study: 5 seeds (1-5), not 30. Confirms the setup
# trains cleanly on this scenario's real geometry before committing more
# seeds/Ibex time. NOT SUBMITTED by this task -- prep and validation only.
#
# Submit (5 array tasks):
#   cd <your checkout>          # $SLURM_SUBMIT_DIR
#   git checkout abha-combined-scaleup
#   git pull
#   sbatch --array=1-5 slurm/abha_combined_grand_mosque.sbatch
#
# Aggregate after completion:
#   python scripts/aggregate_sweep.py --root runs/abha_combined_grand_mosque_5seed \
#       --success-threshold 0.0503 --expect 1-5
#
#SBATCH --job-name=snrl-abha-combined-grand-mosque
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
CONFIG="${CONFIG:-configs/city_madina_abha_king_abdulaziz_grand_mosque_combined.yaml}"
TIMESTEPS="${TIMESTEPS:-167000}"
OUTROOT="${OUTROOT:-runs/abha_combined_grand_mosque_5seed}"
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

echo "=== Abha COMBINED GAT SCREENING: King Abdulaziz Grand Mosque (87 segments), 5 seeds ==="
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

EXPECTED_CONFIG="configs/city_madina_abha_king_abdulaziz_grand_mosque_combined.yaml"
if [ "$CONFIG" != "$EXPECTED_CONFIG" ]; then
    echo "WARNING: CONFIG ($CONFIG) differs from the intended King Abdulaziz Grand Mosque COMBINED config ($EXPECTED_CONFIG)."
fi

if [ ! -f "$CONFIG" ]; then
    echo "FATAL: $CONFIG not found."
    exit 1
fi

# Isolation guard: this output root must not collide with any other Abha
# COMBINED scenario's output root, any Riyadh scale-up output root, or any
# protected experiment's existing run directory.
for forbidden in "runs/r400_gat_30k" "runs/r400_gat_mzs1_30k" "runs/r400_gat_167k" \
                 "runs/r400_gat_mzs1_167k" "runs/gat_scaleup_r445_5seed" \
                 "runs/gat_scaleup_r630_5seed" "runs/gat_scaleup_r850_5seed" \
                 "runs/abha_combined_art_street_5seed" \
                 "runs/abha_combined_central_market_5seed" \
                 "runs/abha_combined_asir_hospital_5seed"; do
    if [ "$OUTROOT" = "$forbidden" ]; then
        echo "FATAL: OUTROOT must not be $forbidden -- that is another experiment's output directory."
        exit 1
    fi
done

for f in streets.geojson residential.geojson amenities.geojson; do
    if [ ! -f "data/raw/abha_hotspots/king_abdulaziz_grand_mosque/$f" ]; then
        echo "FATAL: data/raw/abha_hotspots/king_abdulaziz_grand_mosque/$f not found. This scenario's"
        echo "  data is git-tracked (see .gitignore's abha_hotspots exception) -- a normal"
        echo "  'git checkout abha-combined-scaleup && git pull' should already have it. Do NOT"
        echo "  refetch or rebuild it from OSM; if it's missing, the checkout itself is incomplete."
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
