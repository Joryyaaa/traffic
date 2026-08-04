"""Report the "no interventions" baseline for one or more scenarios --
i.e. what accessibility/flow/equity look like on the fully-open network,
before the agent touches anything. This is the reference point every reward
term and every policy comparison is measured against, so it's worth reporting
on its own, per the mentor's "baseline scenarios" request.

Usage (one scenario):
    python scripts/baseline_report.py --config configs/city_madina_ablation.yaml

Usage (compare several scenarios side by side):
    python scripts/baseline_report.py \\
        --config configs/city_madina_ablation.yaml \\
        --config configs/city_madina_alkharj.yaml \\
        --config configs/city_madina_smoketest.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snrl.config import load_config  # noqa: E402
from snrl.env import StreetNetworkEnv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", action="append", required=True, help="Repeatable: one or more config paths")
    args = ap.parse_args()

    rows = []
    for config_path in args.config:
        cfg = load_config(config_path)
        env = StreetNetworkEnv(cfg)
        stats = env._baseline_stats  # already computed in __init__ from an all-open closed_mask
        rows.append((Path(config_path).stem, env.n_segments, stats))

    name_w = max(len(name) for name, _, _ in rows) + 2
    header = (
        f"{'scenario':<{name_w}}{'segments':>10}{'mean_access':>13}{'gini':>8}"
        f"{'flow_entropy':>14}{'total_flow':>12}{'trip_dist_m':>13}"
    )
    print(header)
    print("-" * len(header))
    for name, n_segments, s in rows:
        print(
            f"{name:<{name_w}}{n_segments:>10}{s['mean_access']:>13.3f}{s['access_gini']:>8.3f}"
            f"{s['flow_entropy']:>14.3f}{s['total_flow']:>12.1f}{s['mean_trip_distance']:>13.1f}"
        )


if __name__ == "__main__":
    main()
