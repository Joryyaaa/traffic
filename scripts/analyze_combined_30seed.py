"""Full statistical analysis of the COMBINED (GAT, min_zone_size=1, 167k) experiment
across all 30 seeds (1-30), against the zone_builder benchmark.

Reads per-task results.csv files the same way scripts/aggregate_sweep.py does
(so it can run directly against runs/r400_gat_mzs1_167k/task_*/results.csv
once seeds 6-30 land there), OR a single already-merged CSV (e.g. the
completed_5seed/combined_mzs1_167k_results_all.csv committed at 8f3e0be) via
--csv, so the same script can be smoke-tested against the 5 completed seeds
before the other 25 exist.

Reports everything the analysis asks for: all individual returns, mean, std,
median, min/max, 95% CI for the mean, count/% >= benchmark, count/% below,
mean margin above benchmark, worst-seed margin, and a one-sample one-sided
t-test (H0: population mean <= benchmark, H1: population mean > benchmark).

Usage (once seeds 6-30 have run on Ibex):
    python scripts/analyze_combined_30seed.py \
        --root runs/r400_gat_mzs1_167k --expect 1-30 \
        --benchmark 0.6863

Usage (smoke-test against an already-merged CSV, e.g. the 5 completed seeds):
    python scripts/analyze_combined_30seed.py \
        --csv results/combined_gat_credit_long/completed_5seed/combined_mzs1_167k_results_all.csv \
        --benchmark 0.6863
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
from scipy import stats


def parse_seed_spec(spec: str) -> list[int]:
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def load_from_root(root: Path) -> dict[int, float]:
    rows: dict[int, float] = {}
    csv_paths = sorted(root.glob("task_*/results.csv"))
    if (root / "results.csv").exists():
        csv_paths.append(root / "results.csv")
    for path in csv_paths:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("seed"):
                    rows[int(row["seed"])] = float(row["mean_return"])
    return rows


def load_from_csv(path: Path) -> dict[int, float]:
    rows: dict[int, float] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("seed"):
                rows[int(row["seed"])] = float(row["mean_return"])
    return rows


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--root", help="Sweep root with task_<seed>/results.csv subdirs")
    src.add_argument("--csv", help="A single already-merged CSV with seed,mean_return columns")
    ap.add_argument("--expect", default=None, help="Seed set expected, e.g. '1-30' -- reports any missing")
    ap.add_argument("--benchmark", type=float, default=0.6863, help="zone_builder reference to compare against")
    ap.add_argument("--out", default=None, help="Write the merged per-seed CSV here too (only with --root)")
    args = ap.parse_args()

    if args.root:
        root = Path(args.root)
        if not root.is_dir():
            raise SystemExit(f"no such sweep root: {root}")
        rows = load_from_root(root)
        if not rows:
            raise SystemExit(f"found no results rows under {root}")
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["seed", "mean_return"])
                for s in sorted(rows):
                    w.writerow([s, rows[s]])
            print(f"merged per-seed rows -> {out_path}\n")
    else:
        rows = load_from_csv(Path(args.csv))
        if not rows:
            raise SystemExit(f"found no results rows in {args.csv}")

    if args.expect:
        expected = set(parse_seed_spec(args.expect))
        missing = sorted(expected - set(rows))
        if missing:
            print(f"WARNING: {len(missing)} of {len(expected)} expected seeds missing: {missing}")
            print("These are NOT included below. Do not quote this as the full N-seed result.\n")

    seeds = np.array(sorted(rows))
    returns = np.array([rows[s] for s in seeds])
    n = len(returns)
    benchmark = args.benchmark

    mean = returns.mean()
    std = returns.std(ddof=1) if n > 1 else 0.0  # sample std (N-1), for CI/t-test consistency
    median = np.median(returns)
    lo, hi = returns.min(), returns.max()

    # 95% CI for the mean, using the t-distribution (small-sample-correct;
    # reduces to the usual z-based interval as n grows).
    if n > 1:
        sem = std / np.sqrt(n)
        t_crit = stats.t.ppf(0.975, df=n - 1)
        ci_lo, ci_hi = mean - t_crit * sem, mean + t_crit * sem
    else:
        sem = float("nan")
        ci_lo = ci_hi = mean

    n_at_or_above = int(np.sum(returns >= benchmark))
    n_below = n - n_at_or_above
    mean_margin = mean - benchmark
    worst_margin = lo - benchmark

    # One-sided one-sample t-test: H0: population mean <= benchmark,
    # H1: population mean > benchmark. scipy's ttest_1samp gives the
    # two-sided p-value for H0: mean == benchmark; for a one-sided test in
    # the direction the statistic actually points, halve it (standard
    # construction) -- only valid when t > 0, i.e. the sample mean is on the
    # H1 side; report that explicitly.
    if n > 1:
        t_stat, p_two_sided = stats.ttest_1samp(returns, benchmark)
        if t_stat > 0:
            p_one_sided = p_two_sided / 2
        else:
            # sample mean below benchmark: no evidence for H1 at all,
            # one-sided p-value is >= 0.5, not derived from the two-sided
            # value the same way.
            p_one_sided = 1 - (p_two_sided / 2)
    else:
        t_stat, p_one_sided = float("nan"), float("nan")

    print(f"=== COMBINED (GAT, min_zone_size=1, 167k) vs. zone_builder benchmark ({benchmark}) ===")
    print(f"n seeds: {n}\n")

    print("Per-seed returns:")
    for s in seeds:
        flag = "OK " if rows[s] >= benchmark else "BELOW"
        print(f"  seed {int(s):>3}: {rows[s]:+.4f}  [{flag}]")

    print(f"\nmean            : {mean:+.4f}")
    print(f"std (sample)    : {std:.4f}")
    print(f"median          : {median:+.4f}")
    print(f"min / max       : {lo:+.4f} / {hi:+.4f}")
    print(f"95% CI for mean : [{ci_lo:+.4f}, {ci_hi:+.4f}]" + ("" if n > 1 else "  (n=1, undefined -- CI collapses to the point estimate)"))
    print(f"\n>= benchmark    : {n_at_or_above}/{n}  ({100*n_at_or_above/n:.1f}%)")
    print(f"< benchmark     : {n_below}/{n}  ({100*n_below/n:.1f}%)")
    print(f"mean margin above benchmark  : {mean_margin:+.4f}")
    print(f"worst-seed margin vs benchmark: {worst_margin:+.4f}" + (" (worst seed is BELOW benchmark)" if worst_margin < 0 else " (worst seed still beats benchmark)"))

    print("\n--- Hypothesis test ---")
    print("Test: one-sample, one-sided t-test")
    print(f"H0: population mean <= {benchmark}   (COMBINED does not exceed zone_builder)")
    print(f"H1: population mean >  {benchmark}   (COMBINED exceeds zone_builder)")
    if n > 1:
        print(f"t-statistic (df={n-1}): {t_stat:.4f}")
        print(f"one-sided p-value      : {p_one_sided:.6g}")
        print(f"effect size (mean - benchmark): {mean_margin:+.4f}")
        alpha = 0.05
        if t_stat > 0 and p_one_sided < alpha:
            print(f"=> reject H0 at alpha={alpha}: evidence COMBINED's expected return exceeds {benchmark}.")
        else:
            print(f"=> fail to reject H0 at alpha={alpha}.")
    else:
        print("n=1: t-test undefined (needs n>=2). Not evaluated.")


if __name__ == "__main__":
    main()
