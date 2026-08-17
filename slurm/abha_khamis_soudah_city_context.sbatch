#!/bin/bash
# One full-belt city-accessibility context run, sized separately so the two
# small corridor tasks do not wait for or reserve this job's memory.

#SBATCH --job-name=abha-city-context
#SBATCH --partition=batch
#SBATCH --time=02:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=24G
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
OUTROOT="${OUTROOT:-results/abha_khamis_soudah_ibex}"

cd "$PROJECT_DIR"
mkdir -p logs "$OUTROOT/current_full_belt"

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

source "$(conda info --base)/etc/profile.d/conda.sh"
# Jory's local env is traffic_env, the Ibex env is snrl. Take whichever exists
# so one script runs in both places, and fail loudly rather than half-activate.
if [ -z "${CONDA_ENV:-}" ]; then
    for candidate in traffic_env snrl; do
        if conda env list | awk '{print $1}' | grep -qx "$candidate"; then
            CONDA_ENV="$candidate"
            break
        fi
    done
fi
conda activate "${CONDA_ENV:?no traffic_env or snrl conda env found}"
echo "conda env : $CONDA_ENV"

python scripts/run_abha_khamis_soudah_scenario.py \
  --config configs/city_madina_abha_current_full_belt.yaml \
  --scenario current_full_belt \
  --out "$OUTROOT/current_full_belt"

echo "saved -> $OUTROOT/current_full_belt"
