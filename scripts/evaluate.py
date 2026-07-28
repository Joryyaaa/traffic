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
            r = env.reward_fn(sim, prev_stats, int(trial.sum())).total
            if r > best_r:
                best_a, best_r = int(a), r
        return best_a
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
    }

    if args.model:
        from stable_baselines3 import PPO

        model = PPO.load(args.model)
        policies["rl_agent"] = lambda env, obs: int(model.predict(obs, deterministic=True)[0])

    print(f"{'policy':<14} {'mean return':>12} {'std':>8}")
    for name, choose in policies.items():
        returns = [run_policy(env, choose, cfg.seed + i)[0] for i in range(args.episodes)]
        print(f"{name:<14} {np.mean(returns):>12.4f} {np.std(returns):>8.4f}")


if __name__ == "__main__":
    main()
