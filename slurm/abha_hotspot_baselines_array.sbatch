#!/bin/bash
# Optimized one-task-per-scenario evaluation for the runnable Abha hotspots.
# Uses scripts/evaluate.py unchanged. The school cluster and Abu Kheyal Park
# are absent because the former has no residential origins and the latter has
# zero directed baseline accessibility at every valid 30--100-segment crop.
#
# Submit:
#   cd /home/shiekhmf/Student_Projects/Jory/traffic
#   sbatch slurm/abha_hotspot_baselines_array.sbatch
#
# Each array task runs independently, so the four scenarios run concurrently.
# Greedy and zone_builder_best are excluded here and live in the optional job.
#SBATCH --job-name=snrl-abha-hotspots
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=12G
#SBATCH --array=0-3
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
EPISODES="${EPISODES:-1}"
POLICIES="${POLICIES:-random,highest_flow,lowest_flow,zone_builder}"

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

# Same CPU-binding protection and single-thread controls as the mentor's
# slurm/sweep_array.sbatch.
unset SLURM_CPU_BIND SLURM_CPU_BIND_LIST SLURM_CPU_BIND_TYPE SLURM_CPU_BIND_VERBOSE
unset SLURM_HINT SLURM_DISTRIBUTION
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export MPLCONFIGDIR="${MPLCONFIGDIR:-$HOME/.cache/matplotlib}"
mkdir -p "$MPLCONFIGDIR"

# Mentor-measured optimum: fan the batched action mask over at most 8 workers.
MASK_CPUS="${SLURM_CPUS_PER_TASK:-1}"
if [ "$MASK_CPUS" -gt 8 ]; then MASK_CPUS=8; fi
export SNRL_MASK_WORKERS="${SNRL_MASK_WORKERS:-$MASK_CPUS}"

source "$(conda info --base)/etc/profile.d/conda.sh"
# Same local/Ibex environment detection as the mentor's latest Abha jobs.
if [ -z "${CONDA_ENV:-}" ]; then
    for candidate in traffic_env snrl; do
        if conda env list | awk '{print $1}' | grep -qx "$candidate"; then
            CONDA_ENV="$candidate"
            break
        fi
    done
fi
conda activate "${CONDA_ENV:?no traffic_env or snrl conda env found}"
echo "conda env    : $CONDA_ENV"

RESULT_DIR="results/abha_hotspot_scenarios/ibex/$SCENARIO"
RESULT_FILE="$RESULT_DIR/cheap_baselines_${SLURM_ARRAY_JOB_ID}_${IDX}.txt"

echo "=== Abha hotspot evaluate.py suite ==="
echo "host         : $(hostname)"
echo "job          : ${SLURM_ARRAY_JOB_ID}_${IDX}"
echo "scenario     : $SCENARIO"
echo "config       : $CONFIG"
echo "episodes     : $EPISODES"
echo "policies     : $POLICIES"
echo "cpus/workers : ${SLURM_CPUS_PER_TASK:-?}/$SNRL_MASK_WORKERS"
echo "python       : $(which python)"
echo "started      : $(date -Is)"
echo

# No srun: identical to the mentor's single-process Slurm launch pattern.
python scripts/baseline_report.py --config "$CONFIG" | tee "$RESULT_DIR/baseline_${SLURM_ARRAY_JOB_ID}_${IDX}.txt"
python scripts/evaluate.py \
  --config "$CONFIG" \
  --episodes "$EPISODES" \
  --policies "$POLICIES" | tee "$RESULT_FILE"

echo
echo "finished : $(date -Is)"
echo "results  : $RESULT_FILE"
