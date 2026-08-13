"""Evaluate a trained policy against baselines.

Baselines to beat (all implemented here so comparisons are apples-to-apples):
    random             - random valid closures
    greedy             - one-step lookahead, close the segment with the best reward
    highest_flow       - close the segments carrying the most baseline flow
    lowest_flow        - close the least-used segments
    zone_builder       - hand-coded planner: seed on the highest-degree qualifying
                          segment, then always extend the same cluster
    zone_builder_best  - zone_builder repeated from every qualifying seed segment,
                          keeps the best-scoring full sequence (stronger ceiling,
                          more expensive)

    python scripts/evaluate.py --config configs/default.yaml --model runs/ppo_baseline/model.zip
"""

from __future__ import annotations

import argparse
import sys
import time
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

    Also told about zone_min_flow_fraction (see rewards.py) when it's active:
    prefers flow-qualifying segments both when seeding and when extending,
    falling back to the old degree-only behavior if none qualify or the
    constraint isn't enabled. Without this, zone_builder stops being a fair
    "best hand-coded effort" once the reward requires real usage -- it would
    just keep building on the same unused corridor it always did and score
    worse than doing nothing, which measures a stale baseline, not headroom.
    """
    def choose(env, obs):
        mask = env.action_masks()
        closed = np.flatnonzero(env.closed_mask)
        valid = np.flatnonzero(mask[: env.n_segments])
        if valid.size == 0:
            return env.n_segments
        qualifying_mask = env.reward_fn._qualifying_mask
        if closed.size == 0:
            # seed on the best-connected segment we are allowed to close,
            # preferring one that qualifies for the zone bonus if that
            # constraint is active.
            candidates = valid
            if qualifying_mask is not None:
                qualifying_valid = valid[qualifying_mask[valid]]
                if qualifying_valid.size > 0:
                    candidates = qualifying_valid
            return int(candidates[np.argmax(env._seg_degree[candidates])])
        touching = [a for a in valid if env._adjacency[a][closed].any()]
        if qualifying_mask is not None:
            qualifying_touching = [a for a in touching if qualifying_mask[a]]
            if qualifying_touching:
                touching = qualifying_touching
        return int(touching[0]) if touching else env.n_segments
    return choose


def zone_builder_best_policy(cfg):
    """Exhaustive-seed variant of zone_builder: the single-seed version always
    starts from the highest-degree segment, which can miss a better zone
    sitting elsewhere in the network. This tries every flow-qualifying
    segment as the starting seed (falls back to every segment if
    zone_min_flow_fraction is disabled), greedily extends from each exactly
    like zone_builder does, and replays whichever full sequence scored
    highest. One full episode per candidate seed -- cheap on small networks
    (candidates are usually a small qualifying subset, e.g. 11 of 52 on Al
    Nakheel), but scales with network size, so expect it to be much slower
    on the full 3km city config.

    Not a true combinatorial optimum (that's intractable -- it would mean
    trying every subset of segments, not just every starting seed), but a
    meaningfully stronger ceiling than the single-heuristic-seed version.
    """
    probe_env = StreetNetworkEnv(cfg)
    qualifying_mask = probe_env.reward_fn._qualifying_mask
    candidate_seeds = (
        np.flatnonzero(qualifying_mask)
        if qualifying_mask is not None
        else np.arange(probe_env.n_segments)
    )

    best_sequence, best_return = None, -np.inf
    for seed_segment in candidate_seeds:
        seed_segment = int(seed_segment)
        trial_env = StreetNetworkEnv(cfg)
        obs, _ = trial_env.reset()
        if not trial_env.action_masks()[seed_segment]:
            continue  # not a legal first move (e.g. would disconnect the network)

        sequence = [seed_segment]
        obs, reward, terminated, truncated, _ = trial_env.step(seed_segment)
        total = reward
        extend = zone_builder_policy(trial_env)
        while not (terminated or truncated):
            a = extend(trial_env, obs)
            obs, reward, terminated, truncated, _ = trial_env.step(a)
            sequence.append(a)
            total += reward

        if total > best_return:
            best_return, best_sequence = total, sequence

    def choose(env, obs):
        # Index by how many segments *this episode* has already closed, not
        # a manually-incremented counter -- that counter never reset between
        # episodes, so eval runs past the first one silently replayed nothing
        # (index already past the end of best_sequence). closed_mask itself
        # resets to all-False on env.reset(), so this self-corrects per episode.
        i = int(env.closed_mask.sum())
        if best_sequence is None or i >= len(best_sequence):
            return env.n_segments  # no-op fallback
        return best_sequence[i]

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
    # Run a subset instead of the whole suite. Needed on big networks: greedy is
    # the second entry in the dict below and costs one simulate() per candidate
    # action per step, so on Abha S0 (4,531 valid actions) it blocks every
    # cheaper policy behind roughly a day of compute. Splitting the suite into
    # separate jobs gets the cheap numbers back in minutes instead.
    ap.add_argument(
        "--policies",
        default=None,
        help="comma-separated subset of policy names (default: all). "
             "e.g. --policies random,zone_builder",
    )
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)
    rng = np.random.default_rng(cfg.seed)

    # Built lazily, one thunk per policy. zone_builder_best_policy() does its
    # whole exhaustive seed search *at construction time*, so building it
    # eagerly made every other policy wait for it even when it wasn't being
    # run: on Abha S0 that is 561 seeds x a 15-step episode before the first
    # row of the table prints. Constructing only what --policies selects keeps
    # the cheap policies cheap. Order is preserved, so the default run is
    # unchanged.
    policy_factories = {
        "random": lambda: random_policy(rng),
        "greedy": lambda: greedy_policy(),
        "highest_flow": lambda: flow_ranked_policy(env, descending=True),
        "lowest_flow": lambda: flow_ranked_policy(env, descending=False),
        "zone_builder": lambda: zone_builder_policy(env),
        "zone_builder_best": lambda: zone_builder_best_policy(cfg),
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

        policy_factories["rl_agent"] = lambda: rl_policy

    names = list(policy_factories)
    if args.policies:
        names = [p.strip() for p in args.policies.split(",") if p.strip()]
        unknown = [p for p in names if p not in policy_factories]
        if unknown:
            ap.error(
                f"unknown policy {unknown}; available: {sorted(policy_factories)}"
            )

    print(f"config   : {args.config}")
    print(f"segments : {env.n_segments}")
    print(f"episodes : {args.episodes}")
    print(f"policies : {', '.join(names)}\n")
    print(f"{'policy':<18} {'mean return':>12} {'std':>8} {'wall_s':>10}")
    for name in names:
        t0 = time.time()
        choose = policy_factories[name]()
        returns = [run_policy(env, choose, cfg.seed + i)[0] for i in range(args.episodes)]
        dt = time.time() - t0
        # flush: on a multi-hour policy the log should show each row as it lands,
        # not buffer the whole table until the job ends.
        print(
            f"{name:<18} {np.mean(returns):>12.4f} {np.std(returns):>8.4f} {dt:>10.1f}",
            flush=True,
        )


if __name__ == "__main__":
    main()
