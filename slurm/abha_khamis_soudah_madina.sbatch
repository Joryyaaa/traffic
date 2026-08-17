#!/bin/bash
# Approved static Madina scenario suite to Jabal Soudah Viewpoint.
# No road closures and no RL training.
# Run the two small corridor cases concurrently. The larger city-context run
# has its own resource-sized job. Combined and peak cases are derived exactly.

#SBATCH --job-name=abha-ks-corridor
#SBATCH --partition=batch
#SBATCH --time=00:30:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --array=0-1
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
OUTROOT="${OUTROOT:-results/abha_khamis_soudah_ibex}"

SCENARIOS=(
  "route10_reference"
  "route2120_reference"
)
CONFIGS=(
  "configs/city_madina_abha_khamis_soudah_route10.yaml"
  "configs/city_madina_abha_khamis_soudah_route2120.yaml"
)

INDEX="${SLURM_ARRAY_TASK_ID}"
SCENARIO="${SCENARIOS[$INDEX]}"
CONFIG="${CONFIGS[$INDEX]}"

cd "$PROJECT_DIR"
mkdir -p logs "$OUTROOT/$SCENARIO"

# Madina betweenness is currently forced to one process by the backend. The
# two corridor simulations are parallelized at the Slurm-array level.
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
  --config "$CONFIG" \
  --scenario "$SCENARIO" \
  --out "$OUTROOT/$SCENARIO"

echo "saved -> $OUTROOT/$SCENARIO"
