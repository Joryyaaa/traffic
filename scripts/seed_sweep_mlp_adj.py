"""Train + evaluate MLP with adjacency-enhanced observation across several seeds.

Counterpart to seed_sweep_gat.py for the controlled architecture comparison:
same 7-feature observation (include_adjacency_state=True), same config, same
seeds — but uses the default MlpPolicy (flatten+MLP) instead of GAT.

Supports checkpointing/resume: if a checkpoint exists for a seed, training
resumes from it. Checkpoints are saved every --checkpoint-freq timesteps.

Usage:
    python scripts/seed_sweep_mlp_adj.py --config configs/mlp_adj_r445_mzs1.yaml \
        --timesteps 200000 --seeds 1-5 --out runs/r445_mlp_adj_200k
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from snrl import StreetNetworkEnv, load_config  # noqa: E402


def evaluate_deterministic(cfg, model, episodes: int) -> list[float]:
    env = StreetNetworkEnv(cfg)
    returns = []
    for ep in range(episodes):
        obs, _ = env.reset(seed=ep)
        total = 0.0
        while True:
            action, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
            obs, reward, terminated, truncated, _ = env.step(int(action))
            total += reward
            if terminated or truncated:
                break
        returns.append(total)
    return returns


def train_one_seed(cfg, seed: int, timesteps: int, out_dir: Path,
                   checkpoint_freq: int):
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.monitor import Monitor

    cfg.seed = seed
    env = ActionMasker(Monitor(StreetNetworkEnv(cfg)), lambda e: e.unwrapped.action_masks())
    out_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = out_dir / "checkpoint.zip"
    if checkpoint_path.exists():
        print(f"  Resuming from checkpoint: {checkpoint_path}")
        model = MaskablePPO.load(checkpoint_path, env=env)
        remaining = max(0, timesteps - model.num_timesteps)
    else:
        model = MaskablePPO("MlpPolicy", env, verbose=0, seed=seed)
        remaining = timesteps

    if remaining > 0:
        cb = CheckpointCallback(
            save_freq=checkpoint_freq,
            save_path=str(out_dir),
            name_prefix="checkpoint",
        )
        model.learn(total_timesteps=remaining, callback=cb, progress_bar=True,
                    reset_num_timesteps=False)

    model.save(out_dir / "model")
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--timesteps", type=int, default=200_000)
    ap.add_argument("--seeds", default="1-5")
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--out", default="runs/mlp_adj_sweep")
    ap.add_argument("--success-threshold", type=float, default=None)
    ap.add_argument("--checkpoint-freq", type=int, default=50_000)
    args = ap.parse_args()

    seeds = []
    for part in args.seeds.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-")
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.csv"

    with open(results_path, "w", newline="") as f:
        csv.writer(f).writerow(["seed", "mean_return", "std_return", "n_episodes", "train_seconds"])

    all_means = []
    for seed in seeds:
        print(f"\n=== seed {seed} ===")
        cfg = load_config(args.config)
        t0 = time.time()
        model = train_one_seed(cfg, seed, args.timesteps, out_dir / f"seed_{seed}",
                               checkpoint_freq=args.checkpoint_freq)
        train_seconds = time.time() - t0

        returns = evaluate_deterministic(cfg, model, args.episodes)
        mean_r, std_r = float(np.mean(returns)), float(np.std(returns))
        all_means.append(mean_r)
        print(f"seed {seed}: mean_return={mean_r:.4f}  std={std_r:.4f}  ({train_seconds/60:.1f} min)")

        with open(results_path, "a", newline="") as f:
            csv.writer(f).writerow([seed, mean_r, std_r, args.episodes, round(train_seconds, 1)])

    all_means = np.array(all_means)
    print("\n=== summary across all seeds ===")
    print(f"mean: {all_means.mean():.4f}   std: {all_means.std():.4f}")
    if args.success_threshold is not None:
        n_success = int(np.sum(all_means >= args.success_threshold))
        print(f"success rate (>= {args.success_threshold}): {n_success}/{len(seeds)}")
    print(f"per-seed results saved -> {results_path}")


if __name__ == "__main__":
    main()
