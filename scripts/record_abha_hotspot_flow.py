"""Record a Madina flow/closure sequence as an MP4.

The simulation, action mask, reward, and policy are imported from the existing
pipeline.  This file only records their states; it does not reimplement them.
The intervention sequence uses evaluate.py's deterministic zone_builder
baseline so the video can be reproduced before an RL model is trained.

VKT is the repository's established simulation proxy:
    sum(segment betweenness * segment length_m) / 1000
It is not observed vehicle-kilometres travelled.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import imageio_ffmpeg  # noqa: E402
import matplotlib as mpl  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402

from evaluate import zone_builder_policy  # noqa: E402
from snrl import StreetNetworkEnv, load_config  # noqa: E402


TITLES = {
    "art_street_baseline": "Fully open Art Street and Al-Muftaha baseline",
    "central_market": "Abha central marketplace",
    "asir_central_hospital": "Asir Central Hospital",
    "king_abdulaziz_grand_mosque": "King Abdulaziz Grand Mosque",
    "abu_kheyal_park": "Abu Kheyal Park",
}


def _vkt_proxy_km(env: StreetNetworkEnv) -> float:
    return float(np.sum(env._last_sim.segment_flow * env.backend.segment_lengths) / 1000.0)


def _snapshot(env: StreetNetworkEnv, reward: float = 0.0) -> dict:
    return {
        "step": int(env._step_count),
        "closed_mask": env.closed_mask.copy(),
        "segment_flow": env._last_sim.segment_flow.copy(),
        "mean_access": float(env._prev_stats["mean_access"]),
        "access_gini": float(env._prev_stats["access_gini"]),
        "total_flow": float(env._prev_stats["total_flow"]),
        "mean_trip_distance_m": float(env._prev_stats["mean_trip_distance"]),
        "vkt_proxy_km": _vkt_proxy_km(env),
        "reward": float(reward),
    }


def _collect_states(env: StreetNetworkEnv) -> list[dict]:
    obs, _ = env.reset(seed=env.cfg.seed)
    states = [_snapshot(env)]
    if env.cfg.action.max_closures == 0:
        return states

    choose = zone_builder_policy(env)
    while True:
        before = env.closed_mask.copy()
        action = int(choose(env, obs))
        obs, reward, terminated, truncated, _ = env.step(action)
        if not np.array_equal(before, env.closed_mask):
            state = _snapshot(env, reward)
            state["action"] = action
            states.append(state)
        if terminated or truncated or np.array_equal(before, env.closed_mask):
            break
    return states


def _serializable(state: dict) -> dict:
    return {
        key: (np.flatnonzero(value).astype(int).tolist() if key == "closed_mask" else value)
        for key, value in state.items()
        if key != "segment_flow"
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--scenario", required=True, choices=sorted(TITLES))
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--seconds-per-state", type=float, default=1.5)
    ap.add_argument("--dpi", type=int, default=160)
    args = ap.parse_args()

    mpl.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)
    states = _collect_states(env)
    streets = env.backend._base_streets

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta_path = out.with_suffix(".json")
    meta_path.write_text(
        json.dumps(
            {
                "config": args.config,
                "scenario": args.scenario,
                "policy": "zone_builder (scripts/evaluate.py)",
                "vkt_definition": "sum(Madina segment betweenness * segment length_m) / 1000; simulation proxy, not observed VKT",
                "states": [_serializable(state) for state in states],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    max_flow = max(float(np.max(state["segment_flow"])) for state in states) or 1.0
    norm = mpl.colors.Normalize(vmin=0.0, vmax=max_flow)
    cmap = mpl.colormaps["inferno"]
    repeat = max(1, int(round(args.fps * args.seconds_per_state)))

    fig, ax = plt.subplots(figsize=(9, 9))
    writer = FFMpegWriter(
        fps=args.fps,
        codec="libx264",
        bitrate=3200,
        metadata={"title": TITLES[args.scenario], "artist": "SNRL / Madina"},
        extra_args=["-pix_fmt", "yuv420p"],
    )
    scalar = mpl.cm.ScalarMappable(norm=norm, cmap=cmap)

    with writer.saving(fig, str(out), dpi=args.dpi):
        for state in states:
            ax.clear()
            streets.plot(
                ax=ax,
                color=[cmap(norm(value)) for value in state["segment_flow"]],
                linewidth=2.8,
                alpha=0.95,
            )
            closed = state["closed_mask"]
            if closed.any():
                streets[closed].plot(ax=ax, color="#e31a1c", linewidth=5.0, alpha=1.0)
            ax.set_title(
                f"{TITLES[args.scenario]}\n"
                f"Step {state['step']} | closed {int(closed.sum())}/{cfg.action.max_closures} | "
                f"accessibility {state['mean_access']:.3f} | "
                f"VKT proxy {state['vkt_proxy_km']:.2f} km",
                fontsize=13,
            )
            ax.set_axis_off()
            ax.text(
                0.01,
                0.01,
                "Madina betweenness flow (black/purple = low, yellow = high)\n"
                "red = intervention closure | VKT is a simulation proxy",
                transform=ax.transAxes,
                fontsize=9,
                color="#222222",
                bbox={"facecolor": "white", "edgecolor": "#bbbbbb", "alpha": 0.9},
            )
            cbar = fig.colorbar(scalar, ax=ax, fraction=0.035, pad=0.02)
            cbar.set_label("Madina segment flow (betweenness)")
            fig.tight_layout()
            for _ in range(repeat):
                writer.grab_frame()
            cbar.remove()

    plt.close(fig)
    env.close()
    print(f"saved -> {out} ({len(states)} states, {len(states) * repeat} frames)")
    print(f"metadata -> {meta_path}")


if __name__ == "__main__":
    main()
