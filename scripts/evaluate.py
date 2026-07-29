"""Evaluate a trained policy against baselines.

Baselines to beat (all implemented here so comparisons are apples-to-apples):
    random        - random valid closures
    greedy        - one-step lookahead, close the segment with the best reward
    highest_flow  - close the segments carrying the most baseline flow
    lowest_flow   - close the least-used segments

    python scripts/evaluate.py --config configs/default.yaml --model runs/ppo_baseline/model.zip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from snrl import StreetNetworkEnv, load_config  # noqa: E402


def run_policy(env, choose, seed: int) -> tuple[float, dict]:
    obs, info = env.reset(seed=seed)
    total = 0.0
    while True:
        action = choose(env, obs)
        obs, reward, terminated, truncated, info = env.step(action)
        total += reward
        if terminated or truncated:
            return total, info


def random_policy(rng):
    def choose(env, obs):
        return int(rng.choice(np.flatnonzero(env.action_masks())))
    return choose


def greedy_policy(env_unused=None):
    """One-step lookahead over all valid actions. Expensive but a strong baseline."""
    def choose(env, obs):
        best_a, best_r = None, -np.inf
        prev_stats = dict(env._prev_stats)
        for a in np.flatnonzero(env.action_masks()):
            trial = env.closed_mask.copy()
            if a < env.n_segments:
                trial[a] = not trial[a]
            sim = env.backend.simulate(trial)
            r = env.reward_fn(sim, prev_stats, trial).total
            if r > best_r:
                best_a, best_r = int(a), r
        return best_a
    return choose


def zone_builder_policy(env):
    """Hand-coded planner: pick a seed, then always extend the same cluster.

    This baseline is *told* that contiguity matters. It exists to measure the
    headroom greedy leaves on the table — the return a policy can reach if it
    plans several moves ahead. The research claim is that an RL agent should
    discover this structure on its own, without being told.
    """
    def choose(env, obs):
        mask = env.action_masks()
        closed = np.flatnonzero(env.closed_mask)
        valid = np.flatnonzero(mask[: env.n_segments])
        if valid.size == 0:
            return env.n_segments
        if closed.size == 0:
            # seed on the best-connected segment we are allowed to close
            return int(valid[np.argmax(env._seg_degree[valid])])
        touching = [a for a in valid if env._adjacency[a][closed].any()]
        return int(touching[0]) if touching else env.n_segments
    return choose


def flow_ranked_policy(env, descending: bool):
    order = np.argsort(env._baseline_sim.segment_flow)
    if descending:
        order = order[::-1]
    state = {"i": 0}

    def choose(env, obs):
        mask = env.action_masks()
        while state["i"] < len(order):
            a = int(order[state["i"]])
            state["i"] += 1
            if mask[a]:
                return a
        return env.n_segments  # no-op
    return choose


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--model", default=None)
    ap.add_argument("--episodes", type=int, default=5)
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)
    rng = np.random.default_rng(cfg.seed)

    policies = {
        "random": random_policy(rng),
        "greedy": greedy_policy(),
        "highest_flow": flow_ranked_policy(env, descending=True),
        "lowest_flow": flow_ranked_policy(env, descending=False),
        "zone_builder": zone_builder_policy(env),
    }

    if args.model:
        # train.py prefers MaskablePPO; fall back to plain PPO if that's what
        # was saved. The masked agent must also receive the mask at predict
        # time, otherwise it can propose actions it was never trained to use.
        # SB3 appends ".zip" itself, so "model.zip" becomes "model.zip.zip".
        model_path = args.model[:-4] if args.model.endswith(".zip") else args.model
        try:
            from sb3_contrib import MaskablePPO

            model = MaskablePPO.load(model_path)

            def rl_policy(env, obs):
                a, _ = model.predict(
                    obs, action_masks=env.action_masks(), deterministic=True
                )
                return int(a)
        except (ImportError, ValueError):
            from stable_baselines3 import PPO

            model = PPO.load(args.model)

            def rl_policy(env, obs):
                return int(model.predict(obs, deterministic=True)[0])

        policies["rl_agent"] = rl_policy

    print(f"{'policy':<14} {'mean return':>12} {'std':>8}")
    for name, choose in policies.items():
        returns = [run_policy(env, choose, cfg.seed + i)[0] for i in range(args.episodes)]
        print(f"{name:<14} {np.mean(returns):>12.4f} {np.std(returns):>8.4f}")


if __name__ == "__main__":
    main()
