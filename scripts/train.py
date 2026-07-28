"""Train a PPO agent on the street-network environment.

    python scripts/train.py --config configs/default.yaml --timesteps 50000

Uses MaskablePPO (sb3-contrib) when available so the agent never proposes a
closure that would fragment the network; falls back to plain PPO otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snrl import StreetNetworkEnv, load_config  # noqa: E402


def make_env(cfg):
    from stable_baselines3.common.monitor import Monitor

    return Monitor(StreetNetworkEnv(cfg))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--timesteps", type=int, default=20_000)
    ap.add_argument("--run-name", default="ppo_baseline")
    ap.add_argument("--out", default="runs")
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = make_env(cfg)
    out_dir = Path(args.out) / args.run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker

        env = ActionMasker(env, lambda e: e.unwrapped.action_masks())
        model = MaskablePPO(
            "MlpPolicy", env, verbose=1, seed=cfg.seed, tensorboard_log=str(out_dir)
        )
    except ImportError:
        from stable_baselines3 import PPO

        print("sb3-contrib not installed — falling back to unmasked PPO.")
        model = PPO("MlpPolicy", env, verbose=1, seed=cfg.seed, tensorboard_log=str(out_dir))

    model.learn(total_timesteps=args.timesteps, progress_bar=True)
    model.save(out_dir / "model")
    print(f"saved -> {out_dir / 'model'}")

    # TODO: log the best-found closure set as GeoJSON for mapping in Madina
    # (zonal.create_map) so results can be reviewed visually.


if __name__ == "__main__":
    main()
