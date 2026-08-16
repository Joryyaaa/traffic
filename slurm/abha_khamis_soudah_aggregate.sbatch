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
CONDA_ENV="${CONDA_ENV:-traffic_env}"
OUTROOT="${OUTROOT:-results/abha_khamis_soudah_ibex}"

cd "$PROJECT_DIR"
mkdir -p logs
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

python scripts/derive_abha_khamis_soudah_scenarios.py --root "$OUTROOT"
python scripts/aggregate_abha_khamis_soudah_results.py --root "$OUTROOT"
