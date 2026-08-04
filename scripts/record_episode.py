"""Record a trained agent's episode as an animated GIF: streets turn red one
by one as the agent closes them, so a reviewer can watch the *order* and
*shape* of the decisions form, not just see the final map (see
plot_closures.py for the static final-state version).

Usage:
    python scripts/record_episode.py --config configs/city_madina_ablation.yaml \\
        --model runs/ablation_riyadh_seed1/model.zip --out episode.gif

Needs matplotlib + pillow (pillow already comes with matplotlib). No ffmpeg
required -- writes a GIF, not an mp4.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FuncAnimation, PillowWriter  # noqa: E402
from sb3_contrib import MaskablePPO  # noqa: E402

from snrl.config import load_config  # noqa: E402
from snrl.env import StreetNetworkEnv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", default="episode.gif")
    ap.add_argument("--fps", type=float, default=1.5)
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)
    model_path = args.model[:-4] if args.model.endswith(".zip") else args.model
    model = MaskablePPO.load(model_path)

    streets = env.backend._base_streets

    # Snapshot closed_mask BEFORE the first action too, so frame 0 is the
    # fully-open baseline -- makes the "before" state explicit in the video.
    obs, _ = env.reset()
    snapshots = [env.closed_mask.copy()]
    while True:
        action, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
        obs, reward, terminated, truncated, info = env.step(int(action))
        snapshots.append(env.closed_mask.copy())
        if terminated or truncated:
            break

    fig, ax = plt.subplots(figsize=(9, 9))

    def draw(i):
        ax.clear()
        mask = snapshots[i]
        streets[~mask].plot(ax=ax, color="#999999", linewidth=1.5)
        if mask.sum() > 0:
            streets[mask].plot(ax=ax, color="#d62728", linewidth=3.5)
        ax.set_title(f"step {i}/{len(snapshots)-1} -- {int(mask.sum())} closed")
        ax.set_axis_off()

    anim = FuncAnimation(fig, draw, frames=len(snapshots), interval=1000 / args.fps)
    anim.save(args.out, writer=PillowWriter(fps=args.fps))
    print(f"Saved -> {args.out} ({len(snapshots)} frames)")


if __name__ == "__main__":
    main()
