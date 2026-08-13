#!/bin/bash
# Full evaluate.py baseline suite (random, greedy, highest_flow, lowest_flow,
# zone_builder, zone_builder_best) on Abha S0 -- the full 4,586-segment drive
# network, r=1500m around (18.2264426, 42.5053914), same data the mentor's
# S0/S1A/S1B King Abdulaziz one-way scenarios use (data/abha_baseline/,
# results/abha_scenario_maps/).
#
# Why this needs Ibex and not a laptop: measured locally
# (scripts/_probe_abha_s0_timing.py, this exact config) at ~7.8s per Madina
# simulate() call, 4,531 valid actions, 561 zone_builder_best-qualifying
# seeds:
#   greedy              ~590 min/step x 15 steps x 5 episodes  ~= 30 days
#   zone_builder_best    561 seeds x one 15-step episode        ~= 18 hours
# results/gnn_prototype_test/PROVENANCE.md measured Ibex at ~30x faster per
# step than this Windows machine for the identical simulate() call (the
# mp.Manager()-per-call spawn cost documented as a TODO in
# src/snrl/backends/madina_backend.py is Windows-spawn-specific) -- so expect
# roughly ~1 day for greedy and ~35 min for zone_builder_best here instead.
# Only S0 random completed locally before the Windows run was stopped. This
# job runs all six policies and records one complete table per scenario.
#
# One-time setup (see slurm/README.md on origin/mentor/sweep-harness for the
# rest of the env): this config's data/raw/abha_s0/*.geojson isn't fetched by
# the usual scripts/fetch_osm_data.py --radius flow. Either commit those 3
# files (~1.9MB total, already generated and cross-checked locally against
# data/abha_baseline/run_output.txt) or regenerate on Ibex:
#   python scripts/build_abha_s0_env_data.py
#
# Submit (default: configs/city_madina_abha_s0.yaml, 5 episodes):
#   cd /home/shiekhmf/Student_Projects/Jory/traffic
#   sbatch slurm/abha_s0_baselines.sbatch
#
# Submit S1A (King Abdulaziz one-way NE, 4,570 segments):
#   sbatch --export=ALL,CONFIG=configs/city_madina_abha_s1a.yaml slurm/abha_s0_baselines.sbatch
#
# Submit S1B (King Abdulaziz one-way SW, 4,573 segments):
#   sbatch --export=ALL,CONFIG=configs/city_madina_abha_s1b.yaml slurm/abha_s0_baselines.sbatch
#
# Submit S2 (hypothetical Green Road alignment, 4,602 segments):
#   sbatch --export=ALL,CONFIG=configs/city_madina_abha_s2.yaml slurm/abha_s0_baselines.sbatch
#
# Submit all four at once:
#   for cfg in configs/city_madina_abha_s0.yaml configs/city_madina_abha_s1a.yaml configs/city_madina_abha_s1b.yaml configs/city_madina_abha_s2.yaml; do
#     sbatch --export=ALL,CONFIG="$cfg" slurm/abha_s0_baselines.sbatch
#   done
#
#SBATCH --job-name=snrl-abha-s0-baselines
#SBATCH --partition=batch
#SBATCH --time=30:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/shiekhmf/Student_Projects/Jory/traffic}"
CONFIG="${CONFIG:-configs/city_madina_abha_s0.yaml}"
EPISODES="${EPISODES:-5}"
CONDA_ENV="${CONDA_ENV:-snrl}"

cd "$PROJECT_DIR"
mkdir -p logs

# See slurm/sweep_array.sbatch for why these two blocks exist.
unset SLURM_CPU_BIND SLURM_CPU_BIND_LIST SLURM_CPU_BIND_TYPE SLURM_CPU_BIND_VERBOSE
unset SLURM_HINT SLURM_DISTRIBUTION

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export MPLCONFIGDIR="${MPLCONFIGDIR:-/ibex/user/$USER/mplconfig}"
mkdir -p "$MPLCONFIGDIR"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

if [ ! -f data/raw/abha_s0/streets.geojson ]; then
    echo "data/raw/abha_s0/streets.geojson missing -- regenerating from OSM"
    python scripts/build_abha_s0_env_data.py
fi

# S1A/S1B data: generated from S0 by scripts/build_abha_s1_env_data.py
# (removes closed segments per data/abha_baseline/s1{a,b}_king_abdulaziz.geojson)
if echo "$CONFIG" | grep -q "s1[ab]" && [ ! -f "$(python -c "from snrl import load_config; print(load_config('$CONFIG').network.streets_path)")" ]; then
    echo "S1A/S1B streets missing -- regenerating from S0"
    python scripts/build_abha_s1_env_data.py
fi

if echo "$CONFIG" | grep -q "s2" && [ ! -f data/raw/abha_s2/streets.geojson ]; then
    echo "S2 streets missing -- building the clearly-labelled hypothetical alignment"
    python scripts/build_abha_s2_env_data.py
fi

SCENARIO="$(basename "$CONFIG" .yaml | sed 's/city_madina_abha_//')"
RESULT_DIR="results/abha_${SCENARIO}_baselines"
mkdir -p "$RESULT_DIR"
RESULT_FILE="$RESULT_DIR/ibex_full_baselines_${SLURM_JOB_ID:-local}.txt"

echo "=== Abha full baseline suite (evaluate.py, all 6 policies) ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_JOB_ID:-local}"
echo "config    : $CONFIG"
echo "episodes  : $EPISODES"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

python scripts/evaluate.py --config "$CONFIG" --episodes "$EPISODES" | tee "$RESULT_FILE"

echo
echo "finished  : $(date -Is)"
echo "results   : $RESULT_FILE"
