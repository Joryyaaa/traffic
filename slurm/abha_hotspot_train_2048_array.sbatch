#!/bin/bash
# One exact 2,048-step MaskablePPO run per positive-return, data-valid Abha site.
# Uses scripts/train.py unchanged and the mentor's 8-worker action-mask path.
# The baseline has no intervention; the school cluster has no real origins;
# Asir Central Hospital has a negative directed-network budget result; and Abu
# Kheyal Park has zero directed baseline accessibility at every valid crop.
#
# Submit:
#   sbatch slurm/abha_hotspot_train_2048_array.sbatch
#SBATCH --job-name=snrl-abha-2048
#SBATCH --partition=batch
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=12G
#SBATCH --array=0-1
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
TIMESTEPS="${TIMESTEPS:-2048}"

CONFIGS=(
  "configs/city_madina_abha_central_market.yaml"
  "configs/city_madina_abha_king_abdulaziz_grand_mosque.yaml"
)
NAMES=("central_market" "king_abdulaziz_grand_mosque")

IDX="${SLURM_ARRAY_TASK_ID}"
CONFIG="${CONFIGS[$IDX]}"
SCENARIO="${NAMES[$IDX]}"

cd "$PROJECT_DIR"
mkdir -p logs runs/abha_hotspot_2048

unset SLURM_CPU_BIND SLURM_CPU_BIND_LIST SLURM_CPU_BIND_TYPE SLURM_CPU_BIND_VERBOSE
unset SLURM_HINT SLURM_DISTRIBUTION
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export MPLCONFIGDIR="${MPLCONFIGDIR:-$HOME/.cache/matplotlib}"
mkdir -p "$MPLCONFIGDIR"

MASK_CPUS="${SLURM_CPUS_PER_TASK:-1}"
if [ "$MASK_CPUS" -gt 8 ]; then MASK_CPUS=8; fi
export SNRL_MASK_WORKERS="${SNRL_MASK_WORKERS:-$MASK_CPUS}"

source "$(conda info --base)/etc/profile.d/conda.sh"
if [ -z "${CONDA_ENV:-}" ]; then
    for candidate in snrl traffic_env; do
        if conda env list | awk '{print $1}' | grep -qx "$candidate"; then
            CONDA_ENV="$candidate"
            break
        fi
    done
fi
conda activate "${CONDA_ENV:?no traffic_env or snrl conda env found}"
echo "conda env=$CONDA_ENV"

RUN_NAME="${SCENARIO}_seed42_${TIMESTEPS}"
echo "scenario=$SCENARIO config=$CONFIG timesteps=$TIMESTEPS workers=$SNRL_MASK_WORKERS"
echo "started=$(date -Is)"
python scripts/train.py \
  --config "$CONFIG" \
  --timesteps "$TIMESTEPS" \
  --run-name "$RUN_NAME" \
  --out runs/abha_hotspot_2048
echo "finished=$(date -Is)"
