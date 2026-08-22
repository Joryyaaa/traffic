"""Functional smoke test for GAT checkpoint, resume, progress, and skip logic.

This uses a tiny synthetic network and short PPO rollouts only to exercise the
serialization path. It does not alter the production experiment's defaults or
hyperparameters.
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from sb3_contrib import MaskablePPO  # noqa: E402
from sb3_contrib.common.wrappers import ActionMasker  # noqa: E402
from stable_baselines3.common.callbacks import CheckpointCallback  # noqa: E402
from stable_baselines3.common.monitor import Monitor  # noqa: E402

from seed_sweep_gat import (  # noqa: E402
    _ProgressLoggerCallback,
    find_latest_checkpoint,
    train_one_seed,
)
from snrl import StreetNetworkEnv, load_config  # noqa: E402
from snrl.gnn import GATFeaturesExtractor  # noqa: E402


def wrapped_env(cfg):
    env = StreetNetworkEnv(cfg)
    adjacency = env._adjacency
    wrapped = ActionMasker(Monitor(env), lambda item: item.unwrapped.action_masks())
    return wrapped, adjacency


def main() -> int:
    cfg = load_config(ROOT / "configs/default.yaml")
    cfg.include_adjacency_state = True
    cfg.action.allow_reopen = False
    cfg.action.episode_length = 8
    cfg.reward.w_pedestrian_zone = 1.0
    cfg.reward.min_zone_size = 1
    policy_kwargs = {
        "features_extractor_class": GATFeaturesExtractor,
        "features_extractor_kwargs": {
            "gat_hidden_dim": 32,
            "n_heads": 4,
            "global_embed_dim": 16,
            "features_dim": 64,
        },
    }

    with tempfile.TemporaryDirectory(prefix="snrl_resume_smoke_") as temp:
        seed_dir = Path(temp) / "seed_1"
        checkpoint_dir = seed_dir / "checkpoints"
        checkpoint_dir.mkdir(parents=True)
        progress_path = seed_dir / "progress.json"

        env1, adjacency = wrapped_env(cfg)
        policy_kwargs["features_extractor_kwargs"]["adjacency"] = adjacency
        model1 = MaskablePPO(
            "MlpPolicy",
            env1,
            seed=1,
            verbose=0,
            n_steps=8,
            batch_size=8,
            policy_kwargs=policy_kwargs,
        )
        started = time.time()
        progress1 = _ProgressLoggerCallback(
            progress_path, checkpoint_dir, started, 24, 1, 8
        )
        model1.learn(
            total_timesteps=16,
            reset_num_timesteps=False,
            callback=[
                CheckpointCallback(
                    save_freq=8, save_path=str(checkpoint_dir), name_prefix="seed1"
                ),
                progress1.callback,
            ],
        )
        progress1.flush_final(model1.num_timesteps)
        first = find_latest_checkpoint(checkpoint_dir)
        assert first is not None and first[1] == 16, first
        first_progress = json.loads(progress_path.read_text(encoding="utf-8"))
        assert first_progress["timesteps_completed"] == 16

        env2, _ = wrapped_env(cfg)
        model2 = MaskablePPO.load(str(first[0]), env=env2)
        assert model2.num_timesteps == 16, model2.num_timesteps
        resumed_start = time.time() - float(first_progress["elapsed_seconds"])
        progress2 = _ProgressLoggerCallback(
            progress_path, checkpoint_dir, resumed_start, 24, 1, 8
        )
        model2.learn(
            total_timesteps=8,
            reset_num_timesteps=False,
            callback=[
                CheckpointCallback(
                    save_freq=8, save_path=str(checkpoint_dir), name_prefix="seed1"
                ),
                progress2.callback,
            ],
        )
        progress2.flush_final(model2.num_timesteps)
        second = find_latest_checkpoint(checkpoint_dir)
        assert second is not None and second[1] == 24, second
        final_progress = json.loads(progress_path.read_text(encoding="utf-8"))
        assert final_progress["timesteps_completed"] == 24
        assert final_progress["last_checkpoint"].endswith("seed1_24_steps.zip")
        assert final_progress["elapsed_seconds"] >= first_progress["elapsed_seconds"]

        model2.save(seed_dir / "model")
        assert (seed_dir / "model.zip").exists()
        skipped = train_one_seed(
            cfg,
            seed=1,
            timesteps=24,
            out_dir=seed_dir,
            gat_hidden_dim=32,
            n_heads=4,
            global_embed_dim=16,
            features_dim=64,
            checkpoint_freq=8,
        )
        assert skipped.num_timesteps == 24

    print("[PASS] checkpoint saved at timestep 16")
    print("[PASS] fresh model loaded at timestep 16 (not 0)")
    print("[PASS] resume trained only the remaining 8 steps to timestep 24")
    print("[PASS] progress.json accumulated elapsed time and latest checkpoint")
    print("[PASS] final model triggered skip-if-complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
