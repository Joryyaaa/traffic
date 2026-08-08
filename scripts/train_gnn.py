"""Train a PPO agent on the street-network environment using the experimental
GCN feature extractor (src/snrl/gnn.py) instead of the default flatten+MLP one.

    python scripts/train_gnn.py --config configs/hard.yaml --timesteps 30000

This is a copy of train.py with one difference: policy_kwargs wires in
GCNFeaturesExtractor, fed with this scenario's fixed segment-adjacency matrix
(env._adjacency). It is a parallel experiment, not a replacement for
train.py -- see the README's GNN section before treating its numbers as
comparable to the MLP baseline.

Uses MaskablePPO (sb3-contrib) when available so the agent never proposes a
closure that would fragment the network; falls back to plain PPO otherwise.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from snrl import StreetNetworkEnv, load_config  # noqa: E402
from snrl.gnn import GCNFeaturesExtractor  # noqa: E402


def make_env(cfg):
    from stable_baselines3.common.monitor import Monitor

    return Monitor(StreetNetworkEnv(cfg))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--timesteps", type=int, default=20_000)
    ap.add_argument("--run-name", default="ppo_gnn_baseline")
    ap.add_argument("--out", default="runs")
    ap.add_argument("--seed", type=int, default=None, help="Override cfg.seed (training is fully deterministic per-seed, so re-running with the same seed just retraces the same trajectory -- use this to try a different one)")
    ap.add_argument("--gcn-hidden-dim", type=int, default=32)
    ap.add_argument("--global-embed-dim", type=int, default=16)
    ap.add_argument("--features-dim", type=int, default=64)
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.seed is not None:
        cfg.seed = args.seed
    env = make_env(cfg)
    # Fixed per scenario, not part of the per-step observation -- read once
    # from the unwrapped env before it's wrapped further below.
    adjacency = env.unwrapped._adjacency
    out_dir = Path(args.out) / args.run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # tensorboard is optional — training must not die because a logging
    # dependency is missing on someone else's machine.
    try:
        import tensorboard  # noqa: F401

        tb_log = str(out_dir)
    except ImportError:
        print("tensorboard not installed — training without curve logging.")
        tb_log = None

    policy_kwargs = dict(
        features_extractor_class=GCNFeaturesExtractor,
        features_extractor_kwargs=dict(
            adjacency=adjacency,
            gcn_hidden_dim=args.gcn_hidden_dim,
            global_embed_dim=args.global_embed_dim,
            features_dim=args.features_dim,
        ),
    )
    kwargs = dict(verbose=1, seed=cfg.seed, tensorboard_log=tb_log, policy_kwargs=policy_kwargs)
    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker

        env = ActionMasker(env, lambda e: e.unwrapped.action_masks())
        model = MaskablePPO("MlpPolicy", env, **kwargs)
    except ImportError:
        from stable_baselines3 import PPO

        print("sb3-contrib not installed — falling back to unmasked PPO.")
        model = PPO("MlpPolicy", env, **kwargs)

    model.learn(total_timesteps=args.timesteps, progress_bar=True)
    model.save(out_dir / "model")
    print(f"saved -> {out_dir / 'model'}")


if __name__ == "__main__":
    main()
