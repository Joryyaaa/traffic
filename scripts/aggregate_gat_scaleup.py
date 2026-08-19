"""Cross-size comparison for the GAT scale-up study (Riyadh, ~150/300/600
segments). Merges each size's per-seed results (same task_<seed>/results.csv
layout scripts/aggregate_sweep.py already reads) into one table:

    segments | mean return | std | success rate (vs THAT network's own
    zone_builder) | train time/seed

CRITICAL, per instruction: does NOT reuse the r400 network's 0.6863
zone_builder benchmark for the larger networks. Each size's benchmark was
independently measured with the same methodology (see
results/gat_scaleup_riyadh/STAGE2_DATASETS.md) and is hardcoded below,
labelled by size, specifically so a future edit can't silently apply the
wrong network's number to a different network's returns.

Usage (once the Slurm arrays have produced results):
    python scripts/aggregate_gat_scaleup.py \
        --roots runs/gat_scaleup_r445_5seed:176 \
                runs/gat_scaleup_r630_5seed:290 \
                runs/gat_scaleup_r850_5seed:599 \
        --expect 1-5
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

# segments -> (zone_builder return, source) -- measured independently per
# network, Stage 2. NOT the r400 network's 0.6863 -- do not substitute it in.
ZONE_BUILDER_BY_SEGMENTS = {
    89: (0.6863, "r400 reference, results/combined_gat_credit_long/ lineage"),
    176: (0.8111, "r445, Stage 2 (max_closures=10, episode_length=25)"),
    290: (0.6115, "r630, Stage 2 (max_closures=8, episode_length=20, corrected from a negative first candidate)"),
    599: (0.4636, "r850, Stage 2 (max_closures=14, episode_length=35)"),
}


def parse_seed_spec(spec: str) -> list[int]:
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def load_root(root: Path) -> dict[int, dict[str, str]]:
    rows: dict[int, dict[str, str]] = {}
    for path in sorted(root.glob("task_*/results.csv")):
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("seed"):
                    rows[int(row["seed"])] = row
    if (root / "results.csv").exists():
        with open(root / "results.csv", newline="") as f:
            for row in csv.DictReader(f):
                if row.get("seed"):
                    rows[int(row["seed"])] = row
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--roots", nargs="+", required=True,
        help="One or more <sweep_root>:<segments> pairs, e.g. runs/gat_scaleup_r445_5seed:176",
    )
    ap.add_argument("--expect", default=None, help="Seed set expected per root, e.g. '1-5'")
    args = ap.parse_args()

    print(f"{'segments':>9} {'n':>3} {'mean':>9} {'std':>8} {'min':>9} {'max':>9} "
          f"{'benchmark':>10} {'>=bench':>9} {'train_min':>10}")
    print("-" * 82)

    summary_rows = []
    for spec in args.roots:
        root_str, seg_str = spec.rsplit(":", 1)
        root = Path(root_str)
        segments = int(seg_str)

        if segments not in ZONE_BUILDER_BY_SEGMENTS:
            raise SystemExit(
                f"No independently-measured zone_builder benchmark on record for "
                f"{segments} segments. Refusing to guess or reuse another network's "
                f"number -- measure it first (scripts/evaluate.py --policies "
                f"zone_builder) and add it to ZONE_BUILDER_BY_SEGMENTS in this script."
            )
        benchmark, source = ZONE_BUILDER_BY_SEGMENTS[segments]

        if not root.is_dir():
            print(f"{segments:>9}   -- sweep root not found: {root} (not run yet?)")
            continue

        rows = load_root(root)
        if args.expect:
            expected = set(parse_seed_spec(args.expect))
            missing = sorted(expected - set(rows))
            if missing:
                print(f"{segments:>9}   -- MISSING {len(missing)}/{len(expected)} seeds: {missing}")
                continue

        if not rows:
            print(f"{segments:>9}   -- no completed seeds found under {root}")
            continue

        seeds = sorted(rows)
        returns = np.array([float(rows[s]["mean_return"]) for s in seeds])
        train_s = np.array([float(rows[s].get("train_seconds") or "nan") for s in seeds])
        n_success = int(np.sum(returns >= benchmark))

        print(f"{segments:>9} {len(seeds):>3} {returns.mean():>9.4f} {returns.std():>8.4f} "
              f"{returns.min():>9.4f} {returns.max():>9.4f} {benchmark:>10.4f} "
              f"{n_success}/{len(seeds):>6} {np.nanmean(train_s)/60:>10.1f}")
        summary_rows.append({
            "segments": segments, "n": len(seeds), "mean": returns.mean(),
            "std": returns.std(), "min": returns.min(), "max": returns.max(),
            "benchmark": benchmark, "benchmark_source": source,
            "success": n_success, "train_min_mean": np.nanmean(train_s) / 60,
        })

    if summary_rows:
        out_path = Path("results/gat_scaleup_riyadh/scaleup_comparison.csv")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
            w.writeheader()
            w.writerows(summary_rows)
        print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
