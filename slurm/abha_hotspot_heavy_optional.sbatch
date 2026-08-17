#!/bin/bash
# Optional expensive baselines, intentionally separate from the fast array.
# Default is zone_builder_best. Run greedy only when explicitly requested:
#   sbatch --array=1 --export=ALL,POLICIES=greedy slurm/abha_hotspot_heavy_optional.sbatch
# Array indices follow the CONFIGS/NAMES lists below.
#SBATCH --job-name=snrl-abha-heavy
#SBATCH --partition=batch
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=12G
#SBATCH --array=0-3
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
POLICIES="${POLICIES:-zone_builder_best}"
CONFIGS=(
  "configs/city_madina_abha_art_street_baseline.yaml"
  "configs/city_madina_abha_central_market.yaml"
  "configs/city_madina_abha_asir_central_hospital.yaml"
  "configs/city_madina_abha_king_abdulaziz_grand_mosque.yaml"
)
NAMES=("art_street_baseline" "central_market" "asir_central_hospital" "king_abdulaziz_grand_mosque")

IDX="${SLURM_ARRAY_TASK_ID}"
CONFIG="${CONFIGS[$IDX]}"
SCENARIO="${NAMES[$IDX]}"
cd "$PROJECT_DIR"
mkdir -p logs "results/abha_hotspot_scenarios/ibex/$SCENARIO"

unset SLURM_CPU_BIND SLURM_CPU_BIND_LIST SLURM_CPU_BIND_TYPE SLURM_CPU_BIND_VERBOSE
unset SLURM_HINT SLURM_DISTRIBUTION
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export MPLCONFIGDIR="${MPLCONFIGDIR:-$HOME/.cache/matplotlib}"
mkdir -p "$MPLCONFIGDIR"
MASK_CPUS="${SLURM_CPUS_PER_TASK:-1}"
if [ "$MASK_CPUS" -gt 8 ]; then MASK_CPUS=8; fi
export SNRL_MASK_WORKERS="${SNRL_MASK_WORKERS:-$MASK_CPUS}"

source "$(conda info --base)/etc/profile.d/conda.sh"
if [ -z "${CONDA_ENV:-}" ]; then
    for candidate in traffic_env snrl; do
        if conda env list | awk '{print $1}' | grep -qx "$candidate"; then
            CONDA_ENV="$candidate"
            break
        fi
    done
fi
conda activate "${CONDA_ENV:?no traffic_env or snrl conda env found}"
echo "conda env=$CONDA_ENV"

RESULT="results/abha_hotspot_scenarios/ibex/$SCENARIO/${POLICIES//,/+}_${SLURM_ARRAY_JOB_ID}_${IDX}.txt"
echo "scenario=$SCENARIO config=$CONFIG policies=$POLICIES workers=$SNRL_MASK_WORKERS"
echo "started=$(date -Is)"
python scripts/evaluate.py --config "$CONFIG" --episodes 1 --policies "$POLICIES" | tee "$RESULT"
echo "finished=$(date -Is)"
