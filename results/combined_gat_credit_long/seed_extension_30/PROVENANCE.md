# COMBINED: 5 -> 30 seeds — handoff for submission

**Branch:** `combined-gat-credit-long-30seed`, based on `combined-gat-credit-long@8f3e0be`
(the completed 5-seed results). **Status: prepared and verified, seeds 6-30 NOT submitted
from this session** (no direct Ibex/Slurm access here). Do not treat anything below as a
30-seed result — only 5 of 30 seeds exist right now.

## Why this extension

Mentor's ask: verify the COMBINED experiment's outperformance of `zone_builder` (+0.6863)
is statistically robust, not luck across 5 runs. Same experiment, no changes — extend to
30 total seeds (5 already done + 25 new).

## What was verified before preparing anything (VERIFICATION.md has the full detail)

- The 5 completed seeds' setup (config, training script, GAT extractor, env code, Slurm
  harness) is byte-for-byte unchanged since this session's last full validation
  (`d1cb5d7`, 42/42 checks, including a real GAT forward pass on the real 89-segment
  network) — empty diff, confirmed directly, not assumed.
- `slurm/combined_gat_credit_long.sbatch` needs **zero edits** for seeds 6-30: its
  `#SBATCH --array=1-5` is an overridable default (`sbatch --array=6-30 ...` on the command
  line takes precedence, standard Slurm behavior), and `OUTROOT` already defaults to
  `runs/r400_gat_mzs1_167k` with each array task writing its own `task_$SEED` — so
  `--array=6-30` produces `task_6`..`task_30` with no possibility of touching `task_1`..`task_5`.

## Exact submission command

```bash
cd /home/alblueja/traffic        # $SLURM_SUBMIT_DIR — wherever this checkout lives
git fetch origin
git checkout combined-gat-credit-long-30seed   # or combined-gat-credit-long, same files
git pull

sbatch --array=6-30 slurm/combined_gat_credit_long.sbatch
```

25 array tasks submitted together run in parallel across Ibex's scheduler by default (same
as this project's other up-to-100-seed arrays, e.g. `slurm/sweep_array.sbatch`) — no extra
flag needed for that. Resources unchanged from the file's defaults
(`--time=06:00:00 --mem=12G --cpus-per-task=2`): the completed 5-seed run's actual max was
104.0 min, well inside the 6h limit.

## Watching and collecting

```bash
squeue -u $USER
sacct -j 50676009 --format=JobID,JobName,State,Elapsed,MaxRSS,NNodes,NCPUS   # the reference job, if still queryable
sacct -u $USER --starttime=today --format=JobID,JobName,State,Elapsed,MaxRSS
```

## Full 30-seed analysis, once seeds 6-30 finish

```bash
python scripts/analyze_combined_30seed.py \
    --root runs/r400_gat_mzs1_167k --expect 1-30 --benchmark 0.6863 \
    --out results/combined_gat_credit_long/seed_extension_30/combined_30seed_results_all.csv
```

`--expect 1-30` reports any missing seed explicitly rather than silently computing a
smaller-N result under a "30-seed" label — matches "do not cherry-pick or exclude
failures." The script reads `runs/r400_gat_mzs1_167k/task_<seed>/results.csv` for every
seed 1-30 (the 5 completed ones are already sitting there from the original submission,
same directory the 25 new ones land in), so it produces one true 30-seed report, not two
reports concatenated by hand.

## What the script reports (smoke-tested against the real 5 completed seeds, not fabricated)

All individual returns; mean; sample std (ddof=1 — see note below); median; min/max; 95%
CI for the mean (t-distribution); count and % >= benchmark; count and % below benchmark;
mean margin above benchmark; worst-seed margin vs. benchmark; and a one-sample one-sided
t-test (H0: population mean <= benchmark, H1: population mean > benchmark), reporting the
t-statistic, one-sided p-value, effect size, and the accept/reject call at alpha=0.05.

**Smoke-test result on the real 5 completed seeds** (proves the script's logic is correct;
this is NOT a 30-seed result):

```
mean +0.8528, std 0.0235, median +0.8633, min/max +0.8108/+0.8633
95% CI: [+0.8236, +0.8819]
5/5 (100%) >= benchmark, 0/5 below
mean margin +0.1665, worst-seed margin +0.1245 (worst seed still beats benchmark)
t(4) = 15.8478, one-sided p = 4.63e-05 -> reject H0 even at n=5
```

**Note on std:** this script uses sample std (`ddof=1`, dividing by n-1), the statistically
correct choice for a confidence interval or t-test. `completed_5seed/RESULTS.md`'s
previously-reported 0.0210 is population std (`ddof=0`, dividing by n) — both are "correct"
for what they each compute, they are not the same quantity. Flagging this now so the
eventual 30-seed std isn't mistaken for a discrepancy against the 5-seed number already on
record.

## Files created (this branch)

- `results/combined_gat_credit_long/seed_extension_30/VERIFICATION.md` — Stage 1
- `scripts/analyze_combined_30seed.py` — Stage 2
- `results/combined_gat_credit_long/seed_extension_30/PROVENANCE.md` — this file

**Nothing else touched.** `slurm/combined_gat_credit_long.sbatch`,
`configs/city_madina_ablation_r400_gat_mzs1.yaml`, `scripts/seed_sweep_gat.py`,
`src/snrl/gnn.py`, `src/snrl/env.py`, and every file under `completed_5seed/` are
byte-identical to `combined-gat-credit-long@8f3e0be` — confirmed via `git diff`, not
asserted.

## No 30-seed outcome is claimed

The 5-seed smoke-test numbers above exist only to prove `analyze_combined_30seed.py` is
correct. The real answer to "is COMBINED robust across 30 independent seeds" requires the
25 new seeds to actually run on Ibex — not done from this session, per instruction not to
launch RL training here.
