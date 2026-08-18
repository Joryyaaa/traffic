#!/bin/bash
# GAT r400 — LONGER TRAINING follow-up to the completed 30k-step experiment.
#
# The completed run (branch gat-r400-experiment, commit 34f03c8) trained GAT
# for 30,000 timesteps/seed and got mean -0.0322 (std 0.0060), still far
# below zone_builder (+0.6863) -- see results/gat_r400_experiment/PROVENANCE.md
# on that branch. This is NOT a redesign: same config, same GATFeaturesExtractor
# architecture, same 7-feature adjacency-aware observation, same reward, same
# min_zone_size, same seeds. The ONLY intended change is training budget:
# 30,000 -> 167,000 timesteps.
#
# Why 167,000 and not a round 100,000: the mentor's own completed network-size
# sweep (origin/mentor/sweep-harness, results/README.md) already trained a
# PLAIN MLP (no adjacency observation, no GAT) on this EXACT 89-segment r400
# network for 167,000 steps and reached mean +0.2631 (best seed +0.8125,
# beating zone_builder). That is direct repository evidence that 167k is a
# training budget already PROVEN sufficient to reach planner-class performance
# on this exact network size -- a stronger, non-arbitrary anchor than a round
# 100k guess. See results/gat_r400_experiment/longer_training/PROVENANCE.md
# for the full justification and the parity checks against the 30k run.
#
# Runtime: the completed 30k run measured 40.9 min/seed (mean; range 39.3-42.4
# min across the 5 seeds -- see gat_30k_results_all.csv on gat-r400-experiment).
# Linear extrapolation: 40.9 * (167000/30000) = ~227.7 min/seed = ~3.8h/seed.
# --time below (6h) gives ~58% margin over that estimate.
#
# Submit (5 array tasks):
#   cd /home/alblueja/traffic
#   git checkout gat-r400-longer-training
#   git pull
#   sbatch --array=1-5 slurm/gat_r400_experiment_167k.sbatch
#
# Aggregate after completion:
#   python scripts/aggregate_sweep.py --root runs/r400_gat_167k \
#       --success-threshold 0.6863 --expect 1-5
#
# Comparison targets:
#   GAT, 30k steps (completed):        mean -0.0322, std 0.0060
#   MLP baseline, 30k (5-feature):     mean -0.0733
#   MLP + adjacency, 30k (7-feature):  mean -0.0529
#   Plain MLP, 167k, no adjacency
#     (mentor's scale sweep, same network): mean +0.2631, best +0.8125
#   zone_builder:                       +0.6863
#
#SBATCH --job-name=snrl-gat-r400-167k
#SBATCH --partition=batch
#SBATCH --time=06:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=12G
#SBATCH --array=1-5
#SBATCH --output=logs/%x-%A_%a.out
#SBATCH --error=logs/%x-%A_%a.err

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/alblueja/traffic}"
CONFIG="${CONFIG:-configs/city_madina_ablation_r400_gat.yaml}"
TIMESTEPS="${TIMESTEPS:-167000}"
OUTROOT="${OUTROOT:-runs/r400_gat_167k}"
EPISODES="${EPISODES:-1}"
CONDA_ENV="${CONDA_ENV:-snrl}"

SEED="${SLURM_ARRAY_TASK_ID}"

cd "$PROJECT_DIR"
mkdir -p logs "$OUTROOT"

unset SLURM_CPU_BIND SLURM_CPU_BIND_LIST SLURM_CPU_BIND_TYPE SLURM_CPU_BIND_VERBOSE
unset SLURM_HINT SLURM_DISTRIBUTION

export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export MPLCONFIGDIR="${MPLCONFIGDIR:-/home/$USER/.cache/matplotlib}"
mkdir -p "$MPLCONFIGDIR"

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

echo "=== GAT r400 experiment -- LONGER TRAINING (167k) ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "config    : $CONFIG"
echo "timesteps : $TIMESTEPS"
echo "seed      : $SEED"
echo "episodes  : $EPISODES"
echo "out       : $OUTROOT/task_$SEED"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

# Same config as the completed 30k run -- must resolve to the SAME file, not
# a copy, so a future edit to one can't silently diverge from the other.
EXPECTED_CONFIG="configs/city_madina_ablation_r400_gat.yaml"
if [ "$CONFIG" != "$EXPECTED_CONFIG" ]; then
    echo "WARNING: CONFIG ($CONFIG) differs from the completed 30k run's config ($EXPECTED_CONFIG) -- this is no longer a training-budget-only comparison unless you know what you're doing."
fi

# Guard against ever overwriting the completed 30k results directory.
if [ "$OUTROOT" = "runs/r400_gat_30k" ]; then
    echo "FATAL: OUTROOT must not be runs/r400_gat_30k -- that would overwrite the completed 30k results."
    exit 1
fi

python -c "from sb3_contrib import MaskablePPO" || {
    echo "FATAL: sb3-contrib not installed — MaskablePPO required."
    exit 1
}

python -c "from snrl.gnn import GATFeaturesExtractor" || {
    echo "FATAL: GATFeaturesExtractor not importable."
    exit 1
}

python scripts/seed_sweep_gat.py \
    --config "$CONFIG" \
    --timesteps "$TIMESTEPS" \
    --seeds "$SEED" \
    --episodes "$EPISODES" \
    --out "$OUTROOT/task_$SEED"

echo
echo "finished  : $(date -Is)"
