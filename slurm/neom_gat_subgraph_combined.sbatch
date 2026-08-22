#!/bin/bash
# NEOM GAT subgraph experiment -- COMBINED setup (min_zone_size=1 +
# include_adjacency_state=true), 167,000 timesteps, trained FROM SCRATCH on
# a real, spatially-clipped NEOM subgraph (273 segments, Sharma/Camp26
# dormitory cluster). Same COMBINED recipe as
# slurm/combined_gat_credit_long.sbatch (the validated r400/89-segment
# Riyadh COMBINED run) -- same architecture, same reward weights, same
# min_zone_size=1, same 167k timesteps. The ONLY intended differences are
# network identity/size and the action budget, which is measured
# independently on THIS network (see results/neom_gat_subgraph/
# STAGE3_BUDGET_SWEEP.md) -- never reused from any Riyadh config.
#
# This is NOT zero-shot transfer: the SB3 categorical action head is fixed
# to this network's own n_segments+1 (274) at construction time, so this is
# a from-scratch training run on this network, same as every other size in
# this project's scale-up lineage.
#
# Data: data/neom_gat_subgraph/sharma_dorm_r750/{streets,origins,destinations}.geojson
# (273 segments, 17 dormitory origins, 7 construction destinations -- built
# by scripts/build_neom_gat_subgraph.py from
# neom-scenarios-existing-methodology's real, already-committed B0 network;
# see data/neom_gat_subgraph/sharma_dorm_r750/provenance.json). This data is
# git-tracked (NOT under data/raw/, so NOT gitignored) -- a fresh checkout of
# this branch already has it; no symlink/copy step is needed before
# submitting.
#
# Checkpointing / resume: scripts/seed_sweep_gat.py now saves a resumable
# checkpoint + progress.json every --checkpoint-freq timesteps (default
# 10,000) into runs/.../seed_<N>/checkpoints/ and runs/.../seed_<N>/progress.json.
# If this job is preempted/times out and resubmitted with the SAME OUTROOT,
# it will detect the latest checkpoint on start and continue from there
# instead of restarting at timestep 0 -- this was the explicit gap the
# 599-segment Riyadh scale-up run left (a long non-checkpointed job that had
# nothing to resume from). Progress survives in progress.json even if stdout
# is lost.
#
# Submit (5 array tasks) -- DO NOT RUN until the mentor/PI has reviewed the
# validation + budget-sweep results:
#   cd <your checkout of this repo>
#   git checkout neom-gat-subgraph-combined
#   git pull
#   sbatch --array=1-5 slurm/neom_gat_subgraph_combined.sbatch
#
# Aggregate after completion:
#   python scripts/aggregate_gat_scaleup.py --root runs/neom_gat_subgraph_r750_167k \
#       --success-threshold <measured zone_builder value -- see STAGE3_BUDGET_SWEEP.md>
#
#SBATCH --job-name=snrl-neom-gat-mzs1-167k
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

PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"
CONFIG="${CONFIG:-configs/city_madina_neom_gat_subgraph_r750_mzs1.yaml}"
TIMESTEPS="${TIMESTEPS:-167000}"
OUTROOT="${OUTROOT:-runs/neom_gat_subgraph_r750_167k}"
EPISODES="${EPISODES:-1}"
CHECKPOINT_FREQ="${CHECKPOINT_FREQ:-10000}"
CONDA_ENV="${CONDA_ENV:-snrl}"

SEED="${SLURM_ARRAY_TASK_ID}"

cd "$PROJECT_DIR"
export PYTHONPATH="$PWD/src:${PYTHONPATH:-}"
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

echo "=== NEOM GAT subgraph experiment -- COMBINED (min_zone_size=1 + 167k) ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "project   : $PROJECT_DIR"
echo "config    : $CONFIG"
echo "timesteps : $TIMESTEPS"
echo "seed      : $SEED"
echo "episodes  : $EPISODES"
echo "ckpt_freq : $CHECKPOINT_FREQ"
echo "out       : $OUTROOT/task_$SEED"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

EXPECTED_CONFIG="configs/city_madina_neom_gat_subgraph_r750_mzs1.yaml"
if [ "$CONFIG" != "$EXPECTED_CONFIG" ]; then
    echo "WARNING: CONFIG ($CONFIG) differs from the intended NEOM subgraph config ($EXPECTED_CONFIG)."
fi

if [ ! -f "$CONFIG" ]; then
    echo "FATAL: $CONFIG not found. 'git pull' first; do not regenerate or guess this config."
    exit 1
fi

# Never allow this run to land in (or be pointed at) any prior experiment's
# completed/in-flight output directory in this project.
for forbidden in \
    "runs/r400_gat_167k" "runs/r400_gat_mzs1_167k" \
    "runs/gat_scaleup_r445_5seed" "runs/gat_scaleup_r630_5seed" "runs/gat_scaleup_r850_5seed" \
    "runs/abha_combined_"*; do
    if [ "$OUTROOT" = "$forbidden" ]; then
        echo "FATAL: OUTROOT must not be $forbidden -- that belongs to a different, already-in-flight/completed experiment."
        exit 1
    fi
done

# The NEOM subgraph data is git-tracked (not under data/raw/, not
# gitignored) -- a fresh checkout/worktree of this branch already has it.
# Fail loudly and specifically if it's somehow missing rather than falling
# back to a different network or refetching/resynthesizing anything.
for f in streets.geojson origins.geojson destinations.geojson; do
    if [ ! -f "data/neom_gat_subgraph/sharma_dorm_r750/$f" ]; then
        echo "FATAL: data/neom_gat_subgraph/sharma_dorm_r750/$f not found."
        echo "  This experiment must reuse the exact NEOM subgraph built by"
        echo "  scripts/build_neom_gat_subgraph.py from the real"
        echo "  neom-scenarios-existing-methodology data -- do NOT refetch OSM,"
        echo "  rebuild the subgraph with different parameters, or substitute a"
        echo "  different network here. If this file is genuinely missing,"
        echo "  'git pull' first (it is git-tracked, not gitignored)."
        exit 1
    fi
done

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
    --checkpoint-freq "$CHECKPOINT_FREQ" \
    --out "$OUTROOT/task_$SEED"

echo
echo "finished  : $(date -Is)"
