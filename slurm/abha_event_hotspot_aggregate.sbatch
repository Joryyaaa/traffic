#!/bin/bash
#SBATCH --job-name=abha_event_aggregate
#SBATCH --time=00:05:00
#SBATCH --mem=2G
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/abha_event_aggregate_%j.out
#SBATCH --error=logs/abha_event_aggregate_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate snrl
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

python -c "import madina; print('Madina:', madina.__file__)"
python scripts/aggregate_abha_event_hotspot.py
