#!/bin/bash
# One-off Slurm job: single-seed GNN-prototype smoke-scale test on the
# 89-segment scenario from the network-size sweep (results/README.md on this
# branch -- 89 segments is the "bimodal" size: 1 of 3 MLP seeds reached
# +0.8125, clearly above zone_builder's +0.6863; the other two sat near zero,
# mean +0.2631, std 0.3886).
#
# This is NOT a seed sweep and does NOT use scripts/seed_sweep.py -- that
# script trains the plain-MLP policy only. src/snrl/gnn.py +
# scripts/train_gnn.py wire in an experimental pure-PyTorch GCN feature
# extractor instead. See results/gnn_prototype_test/PROVENANCE.md for what
# this is and is not (a single-seed smoke-scale signal, not a validated
# comparison -- n=1, no baseline GNN run at any other size yet).
#
# Confirmed locally (Windows, not Ibex) before this was written: the GNN
# prototype trains, saves, and evaluate.py loads the saved model back without
# error, on both configs/hard.yaml and the 26-segment Al Nakheel config
# (configs/city_madina_ablation.yaml). NOT run at 89 segments for 30k+ steps
# locally -- calibrated on this exact config at ~1.35s/step (2026-08-08,
# isolated, no other process competing for CPU), which puts 30k steps at
# roughly 11.3 hours locally. The mentor's own 89-segment MLP run took 2.02h
# for 167k steps (~0.0436s/step) on Ibex -- roughly 30x faster per step than
# this machine, almost certainly the mp.Manager()-per-simulate()-call cost
# documented as a TODO in src/snrl/backends/madina_backend.py. Hence: prepped
# here, not run locally.
#
# Submit (defaults: 89-segment config, 30k steps, seed 1):
#   cd /home/shiekhmf/Student_Projects/Jory/traffic
#   sbatch slurm/gnn_prototype_test.sbatch
#
# Submit (the longer end of the requested 30k-50k range, or a different seed):
#   sbatch --export=ALL,TIMESTEPS=50000 slurm/gnn_prototype_test.sbatch
#   sbatch --export=ALL,SEED=7 slurm/gnn_prototype_test.sbatch
#
#SBATCH --job-name=snrl-gnn-proto
#SBATCH --partition=batch
#SBATCH --time=04:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/shiekhmf/Student_Projects/Jory/traffic}"
CONFIG="${CONFIG:-configs/city_madina_ablation_r400.yaml}"
TIMESTEPS="${TIMESTEPS:-30000}"
SEED="${SEED:-1}"
RUN_NAME="${RUN_NAME:-gnn_r400_seed${SEED}_${TIMESTEPS}}"
CONDA_ENV="${CONDA_ENV:-snrl}"

cd "$PROJECT_DIR"
mkdir -p logs

# See slurm/sweep_array.sbatch for why these two blocks exist -- same
# inherited-allocation and thread-thrash issues apply to any job here, even a
# single non-array one.
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

echo "=== snrl GNN-prototype single-seed test ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_JOB_ID:-local}"
echo "config    : $CONFIG"
echo "timesteps : $TIMESTEPS"
echo "seed      : $SEED"
echo "run_name  : $RUN_NAME"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

python scripts/train_gnn.py \
    --config "$CONFIG" \
    --timesteps "$TIMESTEPS" \
    --seed "$SEED" \
    --run-name "$RUN_NAME"

echo
echo "=== evaluating (deterministic, 1 episode -- madina backend is deterministic, see slurm/sweep_array.sbatch's EPISODES note) ==="
python scripts/evaluate.py \
    --config "$CONFIG" \
    --model "runs/$RUN_NAME/model" \
    --episodes 1

echo
echo "finished  : $(date -Is)"
echo "compare the rl_agent row above against zone_builder=+0.6863 and the MLP seed sweep at this size (mean +0.2631, best +0.8125, 1/3 seeds >= planner -- results/README.md, 'Network-size sweep' section)"
