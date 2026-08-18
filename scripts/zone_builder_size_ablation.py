"""Restricted zone-size ablation for zone_builder: what return does the
hand-coded planner get when it's only allowed to grow a zone up to N
segments, instead of running to the max_closures budget?

Deterministic, cheap (one episode per size -- ~24s each on the r400 config,
see results/zone_builder_size_ablation/INSPECTION.md), no RL training
involved. Runs zone_builder_policy(env, max_zone_size=N) from
scripts/evaluate.py for each requested size against a given config, plus one
unrestricted run for the reference row.

Usage:
    python scripts/zone_builder_size_ablation.py \
        --config configs/city_madina_ablation_r400_gat.yaml \
        --sizes 1,2,3,4,5,6,7,8,9 \
        --out results/zone_builder_size_ablation/results_mzs4.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from snrl import StreetNetworkEnv, load_config  # noqa: E402
from evaluate import _closed_group_size, run_policy, zone_builder_policy  # noqa: E402


def run_one(cfg, max_zone_size: int | None):
    env = StreetNetworkEnv(cfg)
    t0 = time.time()
    choose = zone_builder_policy(env, max_zone_size=max_zone_size)
    total, _ = run_policy(env, choose, seed=cfg.seed)
    dt = time.time() - t0
    qualifying_mask = env.reward_fn._qualifying_mask
    achieved_size = _closed_group_size(env.closed_mask, env._adjacency, qualifying_mask)
    n_closed = int(env.closed_mask.sum())
    env.close()
    return total, achieved_size, n_closed, dt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--sizes", default="1,2,3,4,5,6,7,8,9",
                     help="comma-separated allowed zone sizes to test")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    sizes = [int(s.strip()) for s in args.sizes.split(",") if s.strip()]
    cfg = load_config(args.config)

    rows = []
    print(f"config: {args.config}  (min_zone_size={cfg.reward.min_zone_size})")
    print(f"{'allowed_size':>12} {'return':>10} {'achieved_size':>14} {'n_closed':>9} {'wall_s':>8}")

    for size in sizes:
        total, achieved, n_closed, dt = run_one(cfg, max_zone_size=size)
        rows.append(("restricted", size, total, achieved, n_closed, round(dt, 1)))
        print(f"{size:>12} {total:>10.4f} {achieved:>14} {n_closed:>9} {dt:>8.1f}")

    total_u, achieved_u, n_closed_u, dt_u = run_one(cfg, max_zone_size=None)
    rows.append(("unrestricted", None, total_u, achieved_u, n_closed_u, round(dt_u, 1)))
    print(f"{'unrestricted':>12} {total_u:>10.4f} {achieved_u:>14} {n_closed_u:>9} {dt_u:>8.1f}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "allowed_zone_size", "return", "achieved_zone_size", "n_segments_closed", "wall_seconds"])
        for row in rows:
            w.writerow(row)
    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
