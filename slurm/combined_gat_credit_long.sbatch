#!/bin/bash
# GAT r400 — COMBINED experiment: min_zone_size=1 (from the credit-assignment
# ablation) + 167,000 timesteps (from the longer-training follow-up).
#
# Two prior experiments each fixed one weakness of the original 30k GAT
# control (mean -0.0322, std 0.0060, min_zone_size=4):
#
#   CREDIT   (credit-assignment-ablation@115220e): min_zone_size 4->1, still
#            30k steps.  Result: mean +0.3816, std 0.1834, ALL 5 seeds positive.
#   GAT-LONG (gat-r400-longer-training@25f968a):   167k steps, still
#            min_zone_size=4. Result: mean +0.1618, std 0.3511, 1/5 beat
#            zone_builder (+0.6863), highly inconsistent (-0.026 to +0.863).
#
# The mentor asked to combine both. This is NOT a redesign: same r400
# network, same GATFeaturesExtractor architecture, same 7-feature
# adjacency-aware observation, same reward weights, same seeds. The two
# intended changes, each already independently validated, are:
#   relative to CREDIT:   30,000  -> 167,000 timesteps
#   relative to GAT-LONG: min_zone_size 4 -> 1
#
# Config: configs/city_madina_ablation_r400_gat_mzs1.yaml, unmodified,
# checked out as-is from credit-assignment-ablation@115220e (min_zone_size=1
# is already baked into that file -- diffed directly against the mzs=4
# control and confirmed to differ ONLY in min_zone_size, see
# results/combined_gat_credit_long/PARITY_INSPECTION.md). --timesteps 167000
# is a pre-existing CLI flag on seed_sweep_gat.py, same script, unmodified
# (byte-identical between both source branches -- also in
# PARITY_INSPECTION.md). No code was touched to prepare this experiment.
#
# Question this answers: does immediate zone reward (mzs=1) fix GAT-LONG's
# seed-to-seed inconsistency (std 0.3511) while keeping CREDIT's high mean
# (+0.3816), i.e. does the combination give BOTH high performance AND
# consistency, or does it just inherit one experiment's problem?
#
# PROJECT_DIR/PYTHONPATH: this is the pattern both CREDIT and GAT-LONG
# actually used to complete successfully on Ibex (confirmed by diffing their
# completed-results commits -- see PARITY_INSPECTION.md section 11), not the
# hardcoded /home/alblueja/traffic that shipped in the original, never-
# actually-run harness commits. Runs from wherever it's submitted from
# ($SLURM_SUBMIT_DIR), not a hardcoded path -- robust to being submitted from
# a different worktree/checkout.
#
# Runtime: GAT-LONG's actual 167k runtime (same step count as this combined
# run) was 131.7 min/seed mean, 146.6 min max (gat_167k_results_all.csv) --
# notably faster than the original linear estimate. CREDIT's mzs=1 30k
# runtime (41.4 min/seed) was in line with the mzs=4 30k control (40.9
# min/seed), confirming min_zone_size doesn't change per-step cost -- only
# step count does. Nothing about combining the two treatments should change
# per-step cost, so this harness is sized off GAT-LONG's actual 167k numbers.
# --time=06:00:00 below matches the already-validated GAT-LONG harness
# (~2.7x actual margin there). --mem=12G matches BOTH completed harnesses'
# actual committed #SBATCH default; if 16G was used at submission, that was
# a `sbatch --mem=16G ...` command-line override, not a file default --
# Slurm directives are overridable that way, so the file default stays at
# the value both completed runs actually shipped with, and this stays
# override-able the same way (`sbatch --mem=16G slurm/combined_gat_credit_long.sbatch`).
#
# Submit (5 array tasks):
#   cd <your checkout of this repo>
#   git checkout combined-gat-credit-long
#   git pull
#   sbatch --array=1-5 slurm/combined_gat_credit_long.sbatch
#
# Aggregate after completion:
#   python scripts/aggregate_sweep.py --root runs/r400_gat_mzs1_167k \
#       --success-threshold 0.6863 --expect 1-5
#
# Comparison targets:
#   GAT control, mzs=4, 30k (completed):   mean -0.0322, std 0.0060
#   CREDIT, mzs=1, 30k (completed):        mean +0.3816, std 0.1834, 5/5 positive
#   GAT-LONG, mzs=4, 167k (completed):     mean +0.1618, std 0.3511, 1/5 >= planner
#   zone_builder (measured at mzs=4):      +0.6863
#
#SBATCH --job-name=snrl-gat-mzs1-167k
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
CONFIG="${CONFIG:-configs/city_madina_ablation_r400_gat_mzs1.yaml}"
TIMESTEPS="${TIMESTEPS:-167000}"
OUTROOT="${OUTROOT:-runs/r400_gat_mzs1_167k}"
EPISODES="${EPISODES:-1}"
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

echo "=== GAT r400 experiment -- COMBINED (min_zone_size=1 + 167k) ==="
echo "host      : $(hostname)"
echo "job       : ${SLURM_ARRAY_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
echo "project   : $PROJECT_DIR"
echo "config    : $CONFIG"
echo "timesteps : $TIMESTEPS"
echo "seed      : $SEED"
echo "episodes  : $EPISODES"
echo "out       : $OUTROOT/task_$SEED"
echo "python    : $(which python)"
echo "started   : $(date -Is)"
echo

EXPECTED_CONFIG="configs/city_madina_ablation_r400_gat_mzs1.yaml"
if [ "$CONFIG" != "$EXPECTED_CONFIG" ]; then
    echo "WARNING: CONFIG ($CONFIG) differs from the intended combined config ($EXPECTED_CONFIG) -- this is no longer a controlled comparison unless you know what you're doing."
fi

if [ ! -f "$CONFIG" ]; then
    echo "FATAL: $CONFIG not found. This experiment reuses the exact r400 dataset/config already"
    echo "committed by credit-assignment-ablation -- it must already be in this checkout via git,"
    echo "not redownloaded or rebuilt. If missing, 'git pull' first; do not regenerate it."
    exit 1
fi

# Never allow this run to land in (or be pointed at) any prior experiment's
# completed output directory.
for forbidden in "runs/r400_gat_30k" "runs/r400_gat_mzs1_30k" "runs/r400_gat_167k"; do
    if [ "$OUTROOT" = "$forbidden" ]; then
        echo "FATAL: OUTROOT must not be $forbidden -- that is a completed prior experiment's output directory."
        exit 1
    fi
done

# The r400 dataset (data/raw/riyadh_r400/*.geojson) is gitignored (see
# data/raw/ in .gitignore) -- it does not travel with a fresh checkout or a
# new worktree. Fail loudly and specifically rather than silently
# regenerating a possibly-different network, which earlier notes flagged
# happens to be reachable from a currently-flaky Overpass endpoint anyway.
for f in streets.geojson residential.geojson amenities.geojson; do
    if [ ! -f "data/raw/riyadh_r400/$f" ]; then
        echo "FATAL: data/raw/riyadh_r400/$f not found."
        echo "  This experiment must reuse the exact same r400 data the completed CREDIT and"
        echo "  GAT-LONG runs used -- do NOT refetch OSM or rebuild the network here."
        echo "  data/raw/ is gitignored, so it will not exist in a brand-new checkout or worktree."
        echo "  Copy or symlink it from wherever CREDIT/GAT-LONG's data lives on this filesystem, e.g.:"
        echo "    ln -s /path/to/existing/data/raw/riyadh_r400 data/raw/riyadh_r400"
        echo "  then resubmit."
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
    --out "$OUTROOT/task_$SEED"

echo
echo "finished  : $(date -Is)"
