#!/bin/bash
#SBATCH --job-name=makkah_ibrahim_b0
#SBATCH --time=00:20:00
#SBATCH --mem=8G
#SBATCH --cpus-per-task=1
#SBATCH --output=logs/makkah_ibrahim_b0_%j.out
#SBATCH --error=logs/makkah_ibrahim_b0_%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-$PWD}"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate snrl
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
mkdir -p logs data/makkah_ibrahim_osm results/makkah_ibrahim_osm
python -c "import osmnx, geopandas, networkx, folium; print('IMPORTS PASS'); print('OSMnx:',osmnx.__version__)"
python scripts/build_makkah_ibrahim_osm_network.py
python scripts/validate_makkah_ibrahim_osm_network.py
python scripts/render_makkah_ibrahim_baseline.py
