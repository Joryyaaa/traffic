#!/bin/bash
#SBATCH --job-name=abha_event_madina
#SBATCH --array=0-3
#SBATCH --time=00:10:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/abha_event_%A_%a.out
#SBATCH --error=logs/abha_event_%A_%a.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate snrl
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"

python -c "import madina; print('Madina:', madina.__file__)"
python -c "from snrl.backends.madina_backend import MadinaBackend; print('MadinaBackend OK')"

mkdir -p logs results/abha_event_hotspot_madina

SCENARIOS=(B0 S1 S2 S3)
NAMES=(B0_Baseline S1_Event_Zone_Vehicle_Restriction S2_Main_Parking_Hub S3_Managed_Entry_Exit)
SCENARIO="${SCENARIOS[$SLURM_ARRAY_TASK_ID]}"
SCENARIO_NAME="${NAMES[$SLURM_ARRAY_TASK_ID]}"
echo "Running ${SCENARIO}: ${SCENARIO_NAME}"
timeout 8m python scripts/run_abha_event_hotspot_madina.py --scenario "$SCENARIO"
