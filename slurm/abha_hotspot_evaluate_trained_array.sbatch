#!/bin/bash
# Evaluate the two completed 2,048-step Abha agents with the repository's
# unchanged evaluate.py and reward_breakdown.py pipeline.
#SBATCH --job-name=snrl-abha-eval
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=12G
#SBATCH --array=0-1
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
CONFIGS=(
  "configs/city_madina_abha_central_market.yaml"
  "configs/city_madina_abha_king_abdulaziz_grand_mosque.yaml"
)
NAMES=("central_market" "king_abdulaziz_grand_mosque")

IDX="${SLURM_ARRAY_TASK_ID}"
CONFIG="${CONFIGS[$IDX]}"
SCENARIO="${NAMES[$IDX]}"
# Same TIMESTEPS override the training array already takes, so a longer run can
# be evaluated without editing this file: the training script names its output
# ${SCENARIO}_seed42_${TIMESTEPS}, and the default keeps the 2,048-step
# behaviour exactly as before.
TIMESTEPS="${TIMESTEPS:-2048}"
MODEL="runs/abha_hotspot_2048/${SCENARIO}_seed42_${TIMESTEPS}/model.zip"

cd "$PROJECT_DIR"
RESULT_DIR="results/abha_hotspot_scenarios/ibex/$SCENARIO"
mkdir -p logs "$RESULT_DIR"

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
conda activate "${CONDA_ENV:-snrl}"

test -f "$MODEL"
echo "scenario=$SCENARIO model=$MODEL workers=$SNRL_MASK_WORKERS"
python scripts/evaluate.py \
  --config "$CONFIG" \
  --model "$MODEL" \
  --episodes 1 \
  --policies rl_agent,zone_builder \
  | tee "$RESULT_DIR/trained_evaluation_${SLURM_ARRAY_JOB_ID}_${IDX}.txt"

python scripts/reward_breakdown.py \
  --config "$CONFIG" \
  --model "$MODEL" \
  --out "$RESULT_DIR/trained_reward_breakdown_${SLURM_ARRAY_JOB_ID}_${IDX}.png" \
  | tee "$RESULT_DIR/trained_reward_breakdown_${SLURM_ARRAY_JOB_ID}_${IDX}.txt"

