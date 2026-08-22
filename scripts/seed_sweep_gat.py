"""Train + evaluate the GAT feature extractor across several seeds.

Same protocol as seed_sweep.py (MLP baseline) but wires in
GATFeaturesExtractor as the features_extractor_class for MaskablePPO.
Uses the adjacency-aware 7-feature observation (include_adjacency_state).

Checkpointing / resume (added for the NEOM 273-segment / 167k-timestep run,
after the 599-segment Riyadh scale-up run demonstrated that a long
non-checkpointed job is unacceptable -- a timeout/preemption there had
nothing to resume from and had to restart from timestep 0):

  - every --checkpoint-freq timesteps, SB3's own CheckpointCallback saves
    model.zip into <out>/seed_<N>/checkpoints/
  - on start, if a checkpoint already exists for this seed, it is loaded via
    MaskablePPO.load(..., env=env) and training continues with
    reset_num_timesteps=False for only the remaining timesteps -- NOT
    restarted from 0. This is logged explicitly (not silent).
  - if <out>/seed_<N>/model.zip (the final saved model) already exists, this
    seed is treated as already complete: training is skipped entirely and
    only evaluation is (re-)run.
  - progress (timesteps completed, elapsed seconds, last checkpoint path) is
    written to <out>/seed_<N>/progress.json every --checkpoint-freq
    timesteps, so it survives a job requeue/resubmission even if stdout is
    lost -- elapsed time accumulates correctly across resumes by reading the
    previous progress.json's elapsed_seconds back out as an offset.

Usage:
    python scripts/seed_sweep_gat.py --config configs/city_madina_ablation_r400_gat.yaml \
        --timesteps 30000 --seeds 1-5 --out runs/r400_gat_30k
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from snrl import StreetNetworkEnv, load_config  # noqa: E402
from snrl.gnn import GATFeaturesExtractor  # noqa: E402

_CKPT_RE = re.compile(r".*_(\d+)_steps\.zip$")


def find_latest_checkpoint(ckpt_dir: Path) -> tuple[Path, int] | None:
    """Return (path, absolute_timestep) of the highest-timestep checkpoint in
    ckpt_dir, or None if there isn't one. Parses the filename SB3's
    CheckpointCallback itself writes (`{name_prefix}_{num_timesteps}_steps.zip`)
    -- num_timesteps there is the model's absolute step count, not an
    offset relative to this particular learn() call, so this works correctly
    across any number of resumes.
    """
    if not ckpt_dir.exists():
        return None
    candidates = []
    for f in ckpt_dir.glob("*_steps.zip"):
        m = _CKPT_RE.match(f.name)
        if m:
            candidates.append((int(m.group(1)), f))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    steps, path = candidates[-1]
    return path, steps


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


class _ProgressLoggerCallback:
    """Writes <out_dir>/progress.json every log_freq timesteps -- a plain
    dict-based sidecar (not stdout) so a Slurm requeue/resubmission can see
    how far a seed got even if the log stream was lost.
    """

    def __init__(self, progress_path: Path, ckpt_dir: Path, start_time: float,
                 target_timesteps: int, seed: int, log_freq: int):
        from stable_baselines3.common.callbacks import BaseCallback

        self._progress_path = progress_path
        self._ckpt_dir = ckpt_dir
        self._start_time = start_time
        self._target_timesteps = target_timesteps
        self._seed = seed
        self._log_freq = max(int(log_freq), 1)

        outer = self

        class _Inner(BaseCallback):
            def _on_step(self_inner) -> bool:
                if (self_inner.num_timesteps % outer._log_freq == 0
                        or self_inner.num_timesteps >= outer._target_timesteps):
                    outer._write(self_inner.num_timesteps)
                return True

        self.callback = _Inner()

    def _write(self, num_timesteps: int) -> None:
        latest = find_latest_checkpoint(self._ckpt_dir)
        data = {
            "seed": self._seed,
            "timesteps_completed": int(num_timesteps),
            "target_timesteps": self._target_timesteps,
            "elapsed_seconds": round(time.time() - self._start_time, 1),
            "last_checkpoint": str(latest[0]) if latest else None,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        self._progress_path.write_text(json.dumps(data, indent=2))

    def flush_final(self, num_timesteps: int) -> None:
        self._write(num_timesteps)


def train_one_seed(cfg, seed: int, timesteps: int, out_dir: Path,
                   gat_hidden_dim: int, n_heads: int,
                   global_embed_dim: int, features_dim: int,
                   checkpoint_freq: int = 10_000):
    from sb3_contrib import MaskablePPO
    from sb3_contrib.common.wrappers import ActionMasker
    from stable_baselines3.common.callbacks import CheckpointCallback
    from stable_baselines3.common.monitor import Monitor

    out_dir.mkdir(parents=True, exist_ok=True)
    ckpt_dir = out_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    progress_path = out_dir / "progress.json"
    final_model_path = out_dir / "model.zip"

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

    if final_model_path.exists():
        print(f"[resume] seed {seed}: final model already exists at {final_model_path} "
              f"-- skipping training, loading for evaluation only.")
        model = MaskablePPO.load(str(final_model_path), env=env)
        return model

    start_time = time.time()
    latest = find_latest_checkpoint(ckpt_dir)
    if latest is not None:
        ckpt_path, ckpt_steps = latest
        print(f"[resume] seed {seed}: found checkpoint at {ckpt_steps} timesteps -> {ckpt_path}. "
              f"Continuing from there, NOT restarting from 0.")
        model = MaskablePPO.load(str(ckpt_path), env=env)
        if progress_path.exists():
            try:
                prev = json.loads(progress_path.read_text())
                start_time = time.time() - float(prev.get("elapsed_seconds", 0.0))
            except (json.JSONDecodeError, OSError, ValueError):
                pass
    else:
        print(f"seed {seed}: no checkpoint found -- starting fresh from timestep 0.")
        model = MaskablePPO("MlpPolicy", env, verbose=0, seed=seed,
                            policy_kwargs=policy_kwargs)

    already_done = model.num_timesteps
    remaining = max(timesteps - already_done, 0)
    print(f"seed {seed}: {already_done}/{timesteps} timesteps already done, "
          f"{remaining} remaining.")

    progress = _ProgressLoggerCallback(
        progress_path, ckpt_dir, start_time, timesteps, seed, checkpoint_freq,
    )
    checkpoint_cb = CheckpointCallback(
        save_freq=checkpoint_freq,
        save_path=str(ckpt_dir),
        name_prefix=f"seed{seed}",
    )

    if remaining > 0:
        model.learn(
            total_timesteps=remaining,
            reset_num_timesteps=False,
            callback=[checkpoint_cb, progress.callback],
            progress_bar=True,
        )
    progress.flush_final(model.num_timesteps)

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
    ap.add_argument("--checkpoint-freq", type=int, default=10_000,
                     help="save a resumable checkpoint + progress.json every N timesteps")
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

    if not results_path.exists():
        with open(results_path, "w", newline="") as f:
            csv.writer(f).writerow(["seed", "mean_return", "std_return", "n_episodes", "train_seconds"])

    already_recorded = set()
    if results_path.exists():
        with open(results_path, newline="") as f:
            for row in csv.DictReader(f):
                already_recorded.add(int(row["seed"]))

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
            checkpoint_freq=args.checkpoint_freq,
        )
        train_seconds = time.time() - t0

        returns = evaluate_deterministic(cfg, model, args.episodes)
        mean_r, std_r = float(np.mean(returns)), float(np.std(returns))
        all_means.append(mean_r)
        print(f"seed {seed}: mean_return={mean_r:.4f}  std={std_r:.4f}  ({train_seconds/60:.1f} min)")

        if seed not in already_recorded:
            with open(results_path, "a", newline="") as f:
                csv.writer(f).writerow([seed, mean_r, std_r, args.episodes, round(train_seconds, 1)])
            already_recorded.add(seed)

    all_means = np.array(all_means)
    n_success = int(np.sum(all_means >= args.success_threshold))
    print("\n=== summary across all seeds ===")
    print(f"mean: {all_means.mean():.4f}   std: {all_means.std():.4f}")
    print(f"success rate (>= {args.success_threshold}): {n_success}/{len(seeds)}")
    print(f"per-seed results saved -> {results_path}")


if __name__ == "__main__":
    main()
