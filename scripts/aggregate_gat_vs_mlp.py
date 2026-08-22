"""Aggregate GAT-vs-MLP controlled comparison results.

Reads results.csv from each run directory and produces a summary table
comparing GAT and MLP+adj at each network scale.

Reports: mean, std, min, max per-seed returns, and (if --benchmark is given)
the number of seeds beating the zone_builder benchmark.

Usage:
    python scripts/aggregate_gat_vs_mlp.py \
        --gat-r445 runs/r445_gat_200k \
        --mlp-r445 runs/r445_mlp_adj_200k \
        --gat-r630 runs/r630_gat_200k \
        --mlp-r630 runs/r630_mlp_adj_200k \
        --benchmark-r445 0.5 \
        --benchmark-r630 0.3
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def load_results(results_dir: str | Path) -> list[dict]:
    p = Path(results_dir) / "results.csv"
    if not p.exists():
        print(f"  WARNING: {p} not found — skipping")
        return []
    rows = []
    with open(p) as f:
        for row in csv.DictReader(f):
            rows.append({
                "seed": int(row["seed"]),
                "mean_return": float(row["mean_return"]),
                "std_return": float(row["std_return"]),
                "train_seconds": float(row["train_seconds"]),
            })
    return rows


def summarize(rows: list[dict], label: str, benchmark: float | None = None):
    if not rows:
        print(f"\n  {label}: no results")
        return

    means = [r["mean_return"] for r in rows]
    import numpy as np
    arr = np.array(means)

    print(f"\n  {label} ({len(rows)} seeds)")
    print(f"    mean:  {arr.mean():.4f}")
    print(f"    std:   {arr.std():.4f}")
    print(f"    min:   {arr.min():.4f}")
    print(f"    max:   {arr.max():.4f}")

    total_train = sum(r["train_seconds"] for r in rows)
    print(f"    total train time: {total_train/3600:.1f} hours")

    print(f"    per-seed:")
    for r in sorted(rows, key=lambda x: x["seed"]):
        marker = ""
        if benchmark is not None:
            marker = " *" if r["mean_return"] >= benchmark else ""
        print(f"      seed {r['seed']:>3}: {r['mean_return']:+.4f}{marker}")

    if benchmark is not None:
        n_beat = int(np.sum(arr >= benchmark))
        print(f"    seeds >= benchmark ({benchmark:.4f}): {n_beat}/{len(rows)}")

    return arr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gat-r445", default=None)
    ap.add_argument("--mlp-r445", default=None)
    ap.add_argument("--gat-r630", default=None)
    ap.add_argument("--mlp-r630", default=None)
    ap.add_argument("--benchmark-r445", type=float, default=None)
    ap.add_argument("--benchmark-r630", type=float, default=None)
    args = ap.parse_args()

    import numpy as np

    results = {}

    for scale in ["r445", "r630"]:
        gat_dir = getattr(args, f"gat_{scale}")
        mlp_dir = getattr(args, f"mlp_{scale}")
        benchmark = getattr(args, f"benchmark_{scale}")

        if gat_dir is None and mlp_dir is None:
            continue

        print(f"\n{'='*60}")
        print(f"  Scale: {scale}")
        print(f"{'='*60}")

        gat_arr = None
        mlp_arr = None

        if gat_dir:
            gat_rows = load_results(gat_dir)
            gat_arr = summarize(gat_rows, f"GAT+adj ({scale})", benchmark)

        if mlp_dir:
            mlp_rows = load_results(mlp_dir)
            mlp_arr = summarize(mlp_rows, f"MLP+adj ({scale})", benchmark)

        if gat_arr is not None and mlp_arr is not None and len(gat_arr) > 0 and len(mlp_arr) > 0:
            diff = gat_arr.mean() - mlp_arr.mean()
            print(f"\n  GAT advantage: {diff:+.4f} ({diff/abs(mlp_arr.mean())*100:+.1f}%)")

            results[scale] = {
                "gat_mean": gat_arr.mean(),
                "mlp_mean": mlp_arr.mean(),
                "diff": diff,
                "gat_std": gat_arr.std(),
                "mlp_std": mlp_arr.std(),
            }

    if len(results) >= 2:
        print(f"\n{'='*60}")
        print(f"  Cross-scale comparison")
        print(f"{'='*60}")
        for scale, r in sorted(results.items()):
            print(f"  {scale}: GAT {r['gat_mean']:.4f} vs MLP {r['mlp_mean']:.4f} "
                  f"(delta={r['diff']:+.4f})")

        scales = sorted(results.keys())
        trend = results[scales[1]]["diff"] - results[scales[0]]["diff"]
        print(f"\n  GAT advantage trend ({scales[0]} -> {scales[1]}): {trend:+.4f}")
        if trend > 0:
            print("  -> GAT advantage INCREASES with scale")
        elif trend < 0:
            print("  -> GAT advantage DECREASES with scale")
        else:
            print("  -> GAT advantage UNCHANGED with scale")


if __name__ == "__main__":
    main()
