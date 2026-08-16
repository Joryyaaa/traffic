#!/bin/bash
# One full-belt city-accessibility context run, sized separately so the two
# small corridor tasks do not wait for or reserve this job's memory.

#SBATCH --job-name=abha-city-context
#SBATCH --partition=batch
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=24G
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
CONDA_ENV="${CONDA_ENV:-traffic_env}"
OUTROOT="${OUTROOT:-results/abha_khamis_soudah_ibex}"

cd "$PROJECT_DIR"
mkdir -p logs "$OUTROOT/current_full_belt"

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

python scripts/run_abha_khamis_soudah_scenario.py \
  --config configs/city_madina_abha_current_full_belt.yaml \
  --scenario current_full_belt \
  --out "$OUTROOT/current_full_belt"

echo "saved -> $OUTROOT/current_full_belt"
