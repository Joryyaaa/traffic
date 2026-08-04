"""Visual sanity-check for a trained policy: run it once (deterministic), see
which real street segments it decides to close, and plot them on the actual
map. Answers the question "did the agent build a real, contiguous pedestrian
zone, or just find scattered closures that happen to score well?"

Run:
    python scripts/plot_closures.py --config configs/city_madina_ablation.yaml --model runs/ablation_riyadh_seed1/model.zip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt  # noqa: E402
from sb3_contrib import MaskablePPO  # noqa: E402

from snrl.config import load_config  # noqa: E402
from snrl.env import StreetNetworkEnv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", default="closures_map.png")
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)
    model_path = args.model[:-4] if args.model.endswith(".zip") else args.model
    model = MaskablePPO.load(model_path)

    obs, _ = env.reset()
    while True:
        action, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
        obs, reward, terminated, truncated, info = env.step(int(action))
        if terminated or truncated:
            break

    closed_mask = env.closed_mask
    streets = env.backend._base_streets  # real geometry, same order as segment_id
    n_closed = int(closed_mask.sum())

    print(f"Closed {n_closed} of {env.n_segments} segments.")

    fig, ax = plt.subplots(figsize=(10, 10))
    streets[~closed_mask].plot(ax=ax, color="#999999", linewidth=1.5, label="open")
    if n_closed > 0:
        streets[closed_mask].plot(ax=ax, color="#d62728", linewidth=3.5, label="closed by agent")
    ax.set_title(f"Al Nakheel -- streets closed by the trained agent ({n_closed}/{env.n_segments})")
    ax.set_axis_off()
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"Saved -> {args.out}")


if __name__ == "__main__":
    main()
