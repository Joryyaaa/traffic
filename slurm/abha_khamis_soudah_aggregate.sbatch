#!/bin/bash
# Run after the scenario array succeeds to produce one comparison table.

#SBATCH --job-name=abha-ks-summary
#SBATCH --partition=batch
#SBATCH --time=00:10:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
OUTROOT="${OUTROOT:-results/abha_khamis_soudah_ibex}"

cd "$PROJECT_DIR"
mkdir -p logs
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

python scripts/derive_abha_khamis_soudah_scenarios.py --root "$OUTROOT"
python scripts/aggregate_abha_khamis_soudah_results.py --root "$OUTROOT"
