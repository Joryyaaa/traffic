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
# Optional subset, e.g. POLICIES=greedy. Left empty this runs the whole suite,
# which is the original behaviour.
#
# Worth splitting on this network. greedy is the *second* entry in evaluate.py's
# policy dict, so a single whole-suite job prints `random` and then blocks every
# remaining policy behind greedy's ~19h+, and the cheap numbers that take five
# minutes arrive a day late. Three jobs per scenario instead:
#
#   POLICIES=random,highest_flow,lowest_flow,zone_builder  EPISODES=5   (minutes)
#   POLICIES=zone_builder_best                             EPISODES=1   (hours)
#   POLICIES=greedy                                        EPISODES=1   (~a day)
#
# EPISODES=1 for the deterministic policies is not a shortcut: MadinaBackend
# inherits FlowBackend.reseed() returning False (src/snrl/backends/base.py), so
# demand never redraws and N episodes of a deterministic policy are N identical
# rollouts with a structurally-zero std. Only `random` gets anything from N>1.
# See slurm/README.md, which sets EPISODES=1 for the seed sweeps for this reason.
POLICIES="${POLICIES:-}"

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

# Fan action_masks()'s per-candidate connectivity checks across the CPUs this
# job was actually given. They are independent, and on Abha S0 the mask was 95%
# of per-step cost (34s of 36s), so this is where the wall-clock is.
#
# Measured on S0: 1 worker 16.5s, 8 workers 4.8s, and it stops improving beyond
# 8 (fork setup starts to outweigh the work), hence the cap. The mask is
# bit-identical at every worker count -- verified against the pre-batching
# implementation on 26/58/89/226-segment networks and on S0 itself -- so this
# only trades cores for latency and never changes a result.
#
# Ask for the cores too, or this does nothing: sbatch --cpus-per-task=8 ...
MASK_CPUS="${SLURM_CPUS_PER_TASK:-1}"
if [ "$MASK_CPUS" -gt 8 ]; then MASK_CPUS=8; fi
export SNRL_MASK_WORKERS="${SNRL_MASK_WORKERS:-$MASK_CPUS}"
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
# Tag the filename with the subset so the three jobs per scenario do not read as
# interchangeable when they land side by side.
if [ -n "$POLICIES" ]; then
    TAG="$(echo "$POLICIES" | tr ',' '+' | cut -c1-40)"
else
    TAG="all"
fi
RESULT_FILE="$RESULT_DIR/ibex_baselines_${TAG}_${SLURM_JOB_ID:-local}.txt"

echo "=== Abha baseline suite (evaluate.py) ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_JOB_ID:-local}"
echo "config    : $CONFIG"
echo "episodes  : $EPISODES"
echo "policies  : ${POLICIES:-all 6}"
echo "cpus      : ${SLURM_CPUS_PER_TASK:-?}  mask_workers: $SNRL_MASK_WORKERS"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

if [ -n "$POLICIES" ]; then
    python scripts/evaluate.py --config "$CONFIG" --episodes "$EPISODES" \
        --policies "$POLICIES" | tee "$RESULT_FILE"
else
    python scripts/evaluate.py --config "$CONFIG" --episodes "$EPISODES" | tee "$RESULT_FILE"
fi

echo
echo "finished  : $(date -Is)"
echo "results   : $RESULT_FILE"
