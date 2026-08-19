"""Plot the zone_builder size-ablation curves (min_zone_size=4 vs 1).

Usage:
    python scripts/plot_zone_builder_size_ablation.py \
        --mzs4 results/zone_builder_size_ablation/results_mzs4.csv \
        --mzs1 results/zone_builder_size_ablation/results_mzs1.csv \
        --out results/zone_builder_size_ablation/size_vs_return.png
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


def load(path):
    sizes, returns = [], []
    with open(path) as f:
        for row in csv.DictReader(f):
            if row["mode"] != "restricted":
                continue
            sizes.append(int(row["allowed_zone_size"]))
            returns.append(float(row["return"]))
    return sizes, returns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mzs4", required=True)
    ap.add_argument("--mzs1", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sizes4, ret4 = load(args.mzs4)
    sizes1, ret1 = load(args.mzs1)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(sizes4, ret4, marker="o", label="min_zone_size=4 (original control / GAT-LONG)")
    ax.plot(sizes1, ret1, marker="s", label="min_zone_size=1 (CREDIT / COMBINED)")
    ax.axhline(0.0, color="grey", linewidth=0.8, linestyle=":")
    ax.axvline(4, color="grey", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.annotate("min_zone_size=4\nthreshold", xy=(4, 0), xytext=(4.2, -0.09),
                fontsize=8, color="grey")
    ax.set_xlabel("Allowed zone size (segments)")
    ax.set_ylabel("zone_builder return")
    ax.set_title("zone_builder return vs. restricted allowed zone size\n(r400 / 89 segments)")
    ax.legend()
    ax.set_xticks(sizes4)
    fig.tight_layout()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
