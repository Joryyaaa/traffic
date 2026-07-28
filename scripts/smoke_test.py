"""Minimal end-to-end check: build the env, run a random episode, print stats.

    python scripts/smoke_test.py --config configs/default.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from snrl import StreetNetworkEnv, load_config  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--episodes", type=int, default=2)
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg, render_mode="ansi")

    print(f"segments      : {env.n_segments}")
    print(f"action_space  : {env.action_space}")
    print(f"obs_space     : {env.observation_space.shape}")
    print(f"baseline      : {env._baseline_stats}\n")

    rng = np.random.default_rng(cfg.seed)
    for ep in range(args.episodes):
        obs, info = env.reset(seed=cfg.seed + ep)
        total = 0.0
        while True:
            mask = env.action_masks()
            valid = np.flatnonzero(mask)
            action = int(rng.choice(valid))
            obs, reward, terminated, truncated, info = env.step(action)
            total += reward
            if terminated or truncated:
                break
        print(f"episode {ep}: return={total:+.4f}  {env.render()}")

    env.close()
    print("\nOK — environment runs end to end.")


if __name__ == "__main__":
    main()
