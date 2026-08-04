"""Visualize a simulation: color every street segment by how much
pedestrian/bike flow (betweenness) it carries. This is the "what does the
simulation actually look like" visual the mentor asked for -- separate from
plot_closures.py (which shows the *agent's decisions*), this shows the raw
Madina output on the fully-open network.

Usage:
    python scripts/plot_flow.py --config configs/city_madina_ablation.yaml

Optionally pass --closed to see the flow pattern *after* a specific set of
closures (comma-separated segment indices), to compare before/after by eye:
    python scripts/plot_flow.py --config configs/city_madina_ablation.yaml --closed 3,4,5,6,7,8
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from snrl.config import load_config  # noqa: E402
from snrl.env import StreetNetworkEnv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--closed", default="", help="Comma-separated segment indices to close before plotting")
    ap.add_argument("--out", default="flow_map.png")
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)

    closed_mask = np.zeros(env.n_segments, dtype=bool)
    if args.closed.strip():
        idx = [int(x) for x in args.closed.split(",")]
        closed_mask[idx] = True

    sim = env.backend.simulate(closed_mask)
    streets = env.backend._base_streets

    fig, ax = plt.subplots(figsize=(10, 10))
    streets.plot(
        ax=ax,
        column=sim.segment_flow,
        cmap="inferno",
        linewidth=2.5,
        legend=True,
        legend_kwds={"label": "pedestrian/bike flow (betweenness)", "shrink": 0.6},
    )
    if closed_mask.any():
        streets[closed_mask].plot(ax=ax, color="#00ff00", linewidth=1.0, linestyle="--")
    title = "Simulated flow -- fully open network" if not closed_mask.any() else \
        f"Simulated flow -- {int(closed_mask.sum())} segments closed (dashed green)"
    ax.set_title(title)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"Saved -> {args.out}")
    print(f"mean_access={np.mean(sim.origin_access):.3f}  total_flow={np.sum(sim.segment_flow):.1f}  "
          f"mean_trip_distance={sim.mean_trip_distance:.1f}")


if __name__ == "__main__":
    main()
