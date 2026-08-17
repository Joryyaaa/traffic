#!/bin/bash
#SBATCH --job-name=abha_event_osm_build
#SBATCH --time=00:15:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/abha_event_osm_build_%j.out
#SBATCH --error=logs/abha_event_osm_build_%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate snrl
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
mkdir -p logs data/abha_event_hotspot_osm
python -c "import osmnx; print('OSMnx:', osmnx.__version__)"
python scripts/build_abha_event_osm_network.py
python scripts/validate_abha_event_osm_network.py
