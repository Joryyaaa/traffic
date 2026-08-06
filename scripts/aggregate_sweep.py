"""Merge the per-task results.csv files a Slurm array sweep produces into one
sweep-level summary (mean +/- std, success rate), i.e. the same numbers
scripts/seed_sweep.py prints at the end of a serial run.

Why this exists: seed_sweep.py truncates <out>/results.csv on startup, so a
parallel sweep has to give every seed its own --out directory (see
slurm/sweep_array.sbatch). This walks those directories and reassembles the
sweep.

Usage:
    python scripts/aggregate_sweep.py --root runs/sweep_ablation_30k
    python scripts/aggregate_sweep.py --root runs/sweep_ablation_30k \\
        --success-threshold 0.95 --expect 1-100

`--expect` (optional) is the seed set you *submitted*; any seed in it with no
results row is reported as missing, so a silently-failed or still-queued array
task cannot masquerade as a completed sweep.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np


def parse_seed_spec(spec: str) -> list[int]:
    """Same '1,3,7' / '1-100' / '1-50,777' syntax as seed_sweep.py --seeds."""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="Sweep root, e.g. runs/sweep_ablation_30k")
    ap.add_argument(
        "--success-threshold",
        type=float,
        default=0.9,
        help="A seed counts as a success if mean_return >= this "
        "(set it to the zone_builder return measured on the same config)",
    )
    ap.add_argument(
        "--expect",
        default=None,
        help="Seed set that was submitted (e.g. '1-100'); missing seeds are reported",
    )
    ap.add_argument("--out", default=None, help="Merged CSV path (default: <root>/results_all.csv)")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        raise SystemExit(f"no such sweep root: {root}")

    rows: dict[int, dict[str, str]] = {}
    csv_paths = sorted(root.glob("task_*/results.csv"))
    # Also accept a serial seed_sweep.py run in the same root.
    if (root / "results.csv").exists():
        csv_paths.append(root / "results.csv")

    for path in csv_paths:
        with open(path, newline="") as f:
            for row in csv.DictReader(f):
                if not row.get("seed"):
                    continue
                rows[int(row["seed"])] = row

    if not rows:
        raise SystemExit(
            f"found no results rows under {root} "
            "(expected <root>/task_<seed>/results.csv). Are the array tasks still running?"
        )

    out_path = Path(args.out) if args.out else root / "results_all.csv"
    fieldnames = ["seed", "mean_return", "std_return", "n_episodes", "train_seconds"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for seed in sorted(rows):
            w.writerow({k: rows[seed].get(k, "") for k in fieldnames})

    seeds = np.array(sorted(rows))
    means = np.array([float(rows[s]["mean_return"]) for s in seeds])
    train_s = np.array([float(rows[s].get("train_seconds") or "nan") for s in seeds])
    n_success = int(np.sum(means >= args.success_threshold))

    print(f"=== sweep summary: {root} ===")
    print(f"seeds completed : {len(seeds)}")
    print(f"mean return     : {means.mean():.4f}")
    print(f"std             : {means.std():.4f}")
    print(f"min / median / max : {means.min():.4f} / {np.median(means):.4f} / {means.max():.4f}")
    print(f"success rate (>= {args.success_threshold}) : {n_success}/{len(seeds)}")
    if np.isfinite(train_s).any():
        print(
            f"train time/seed : mean {np.nanmean(train_s)/60:.1f} min, "
            f"max {np.nanmax(train_s)/60:.1f} min"
        )

    print("\nworst 5 seeds:")
    for s in seeds[np.argsort(means)][:5]:
        print(f"  seed {s:>5}: {float(rows[s]['mean_return']):+.4f}")
    print("best 5 seeds:")
    for s in seeds[np.argsort(means)][-5:][::-1]:
        print(f"  seed {s:>5}: {float(rows[s]['mean_return']):+.4f}")

    if args.expect:
        expected = set(parse_seed_spec(args.expect))
        missing = sorted(expected - set(seeds.tolist()))
        if missing:
            print(f"\nMISSING {len(missing)} of {len(expected)} submitted seeds: {missing}")
            print("  -> these array tasks did not finish. Check logs/ before quoting the mean.")
        else:
            print(f"\nall {len(expected)} submitted seeds accounted for.")

    print(f"\nmerged per-seed rows -> {out_path}")


if __name__ == "__main__":
    main()
