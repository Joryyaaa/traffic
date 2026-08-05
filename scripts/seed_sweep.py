"""Train + evaluate the same config across several seeds, and summarize.

Training is fully deterministic given a seed (see train.py's --seed flag), so
a single run tells you nothing about how *reliable* the result is -- it could
be a lucky (or unlucky) random start. This script automates what we were
doing by hand today (train.py --seed N, evaluate.py, repeat) across as many
seeds as you have time/compute for, and reports mean +/- std plus a
"success rate" (fraction of seeds that got within `success_threshold` of the
hand-coded zone_builder baseline).

Usage:
    python scripts/seed_sweep.py --config configs/city_madina_ablation.yaml \\
        --timesteps 30000 --seeds 1,3,7,42,99,123,7000 --out runs/sweep_ablation

Each seed trains a fresh model (saved under <out>/seed_<N>/model.zip) and is
evaluated for `--episodes` episodes with a deterministic policy. Results are
written incrementally to <out>/results.csv, so if this gets interrupted
partway through (or you're running it on a shared/remote machine and want to
check progress), you don't lose completed seeds -- just re-run with the seeds
that are missing.

This is the expensive, "run this on your bigger machine" script the mentor
asked for: N seeds x --timesteps steps, one after another, no shortcuts.
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
    """Same evaluation protocol as evaluate.py's rl_agent row: deterministic
    action_masks-aware rollouts, one total-return number per episode."""
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


def train_one_seed(cfg, seed: int, timesteps: int, out_dir: Path):
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
    from stable_baselines3.common.monitor import Monitor

    cfg.seed = seed
    env = ActionMasker(Monitor(StreetNetworkEnv(cfg)), lambda e: e.unwrapped.action_masks())
    model = MaskablePPO("MlpPolicy", env, verbose=0, seed=seed)
    model.learn(total_timesteps=timesteps, progress_bar=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save(out_dir / "model")
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--timesteps", type=int, default=30_000)
    ap.add_argument(
        "--seeds",
        default="1,3,7,42",
        help="Comma-separated list (1,3,7,42) and/or ranges (1-100) -- mix freely, e.g. '1-50,777,1000-1010'",
    )
    ap.add_argument("--episodes", type=int, default=5, help="Eval episodes per seed")
    ap.add_argument("--out", default="runs/sweep")
    ap.add_argument(
        "--success-threshold",
        type=float,
        default=0.9,
        help="A seed counts as a 'success' if mean return >= this value "
        "(default 0.9 -- tune to whatever your zone_builder baseline is)",
    )
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

    # Fresh file with a header, so partial re-runs don't silently mix with
    # a previous sweep's numbers.
    with open(results_path, "w", newline="") as f:
        csv.writer(f).writerow(["seed", "mean_return", "std_return", "n_episodes", "train_seconds"])

    all_means = []
    for seed in seeds:
        print(f"\n=== seed {seed} ===")
        cfg = load_config(args.config)
        t0 = time.time()
        model = train_one_seed(cfg, seed, args.timesteps, out_dir / f"seed_{seed}")
        train_seconds = time.time() - t0

        returns = evaluate_deterministic(cfg, model, args.episodes)
        mean_r, std_r = float(np.mean(returns)), float(np.std(returns))
        all_means.append(mean_r)
        print(f"seed {seed}: mean_return={mean_r:.4f}  std={std_r:.4f}  ({train_seconds/60:.1f} min)")

        with open(results_path, "a", newline="") as f:
            csv.writer(f).writerow([seed, mean_r, std_r, args.episodes, round(train_seconds, 1)])

    all_means = np.array(all_means)
    n_success = int(np.sum(all_means >= args.success_threshold))
    print("\n=== summary across all seeds ===")
    print(f"mean: {all_means.mean():.4f}   std: {all_means.std():.4f}")
    print(f"success rate (>= {args.success_threshold}): {n_success}/{len(seeds)}")
    print(f"per-seed results saved -> {results_path}")


if __name__ == "__main__":
    main()
