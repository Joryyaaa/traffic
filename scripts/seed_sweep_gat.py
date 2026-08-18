"""Train + evaluate the GAT feature extractor across several seeds.

Same protocol as seed_sweep.py (MLP baseline) but wires in
GATFeaturesExtractor as the features_extractor_class for MaskablePPO.
Uses the adjacency-aware 7-feature observation (include_adjacency_state).

Usage:
    python scripts/seed_sweep_gat.py --config configs/city_madina_ablation_r400_gat.yaml \
        --timesteps 30000 --seeds 1-5 --out runs/r400_gat_30k
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
from snrl.gnn import GATFeaturesExtractor  # noqa: E402


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
                   gat_hidden_dim: int, n_heads: int,
                   global_embed_dim: int, features_dim: int):
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
    from stable_baselines3.common.monitor import Monitor

    cfg.seed = seed
    env = StreetNetworkEnv(cfg)
    adjacency = env._adjacency

    policy_kwargs = dict(
        features_extractor_class=GATFeaturesExtractor,
        features_extractor_kwargs=dict(
            adjacency=adjacency,
            gat_hidden_dim=gat_hidden_dim,
            n_heads=n_heads,
            global_embed_dim=global_embed_dim,
            features_dim=features_dim,
        ),
    )

    env = ActionMasker(Monitor(env), lambda e: e.unwrapped.action_masks())
    model = MaskablePPO("MlpPolicy", env, verbose=0, seed=seed,
                        policy_kwargs=policy_kwargs)
    model.learn(total_timesteps=timesteps, progress_bar=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    model.save(out_dir / "model")
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--timesteps", type=int, default=30_000)
    ap.add_argument("--seeds", default="1-5")
    ap.add_argument("--episodes", type=int, default=1)
    ap.add_argument("--out", default="runs/r400_gat_30k")
    ap.add_argument("--success-threshold", type=float, default=0.6863)
    ap.add_argument("--gat-hidden-dim", type=int, default=32)
    ap.add_argument("--n-heads", type=int, default=4)
    ap.add_argument("--global-embed-dim", type=int, default=16)
    ap.add_argument("--features-dim", type=int, default=64)
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
        model = train_one_seed(
            cfg, seed, args.timesteps, out_dir / f"seed_{seed}",
            gat_hidden_dim=args.gat_hidden_dim,
            n_heads=args.n_heads,
            global_embed_dim=args.global_embed_dim,
            features_dim=args.features_dim,
        )
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
