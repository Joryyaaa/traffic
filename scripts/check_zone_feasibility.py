"""Check whether a zone_min_flow_fraction-qualifying pedestrian zone is even
*possible* on a given scenario -- i.e. do enough adjacent, sufficiently-used
segments exist to ever reach min_zone_size? If the largest contiguous group
of qualifying segments is smaller than min_zone_size, the pedestrian_zone
bonus is literally unreachable on this network no matter how well an agent
(or hand-coded policy) plays, and that's worth knowing before training.

Usage:
    python scripts/check_zone_feasibility.py --config configs/city_madina_ablation.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from snrl.config import load_config  # noqa: E402
from snrl.env import StreetNetworkEnv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)
    q = env.reward_fn._qualifying_mask
    adj = env._adjacency

    if q is None:
        print("zone_min_flow_fraction is 0 (disabled) -- every segment qualifies, no constraint to check.")
        return

    qualifying = np.flatnonzero(q)
    print(f"{len(qualifying)} of {env.n_segments} segments qualify "
          f"(>= {cfg.reward.zone_min_flow_fraction:.0%} of mean baseline flow)")

    seen: set[int] = set()
    groups = []
    for start in qualifying:
        start = int(start)
        if start in seen:
            continue
        seen.add(start)
        stack, group = [start], [start]
        while stack:
            u = stack.pop()
            for v in np.flatnonzero(adj[u]):
                v = int(v)
                if v in seen or not q[v]:
                    continue
                seen.add(v)
                stack.append(v)
                group.append(v)
        groups.append(group)

    groups.sort(key=len, reverse=True)
    print("\nconnected groups among qualifying segments:")
    for g in groups:
        print(f"  size {len(g):>3}: segments {g}")

    largest = len(groups[0]) if groups else 0
    needed = cfg.reward.min_zone_size
    print(f"\nlargest contiguous qualifying group: {largest}")
    print(f"min_zone_size required: {needed}")
    if largest >= needed:
        print(f"OK -- a qualifying zone of size >= {needed} is reachable on this network.")
    else:
        print(
            f"WARNING -- no qualifying zone of size >= {needed} exists on this network. "
            "The pedestrian_zone bonus is unreachable here regardless of policy quality. "
            "Consider a bigger radius (more segments = more chances of a contiguous "
            "used cluster), a lower zone_min_flow_fraction, or a lower min_zone_size."
        )


if __name__ == "__main__":
    main()
