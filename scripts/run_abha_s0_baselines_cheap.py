"""Abha S0 (4,586-segment full network) baseline run -- CHEAP policies only.

`scripts/evaluate.py`'s full policy set includes `greedy` (one Madina
simulate() call per *candidate action* per step) and `zone_builder_best`
(one full episode per qualifying seed segment). Measured locally on this
network (scripts/_probe_abha_s0_timing.py): ~7.8s/simulate() call, 4,531
valid actions, 561 qualifying seeds -> greedy ~= 30 days for 5 episodes,
zone_builder_best ~= 18 hours. Both are prepped for the mentor's Ibex instead
(slurm/abha_s0_baselines.sbatch -- ~30x faster per step there per
results/gnn_prototype_test/PROVENANCE.md, so greedy ~1 day / zone_builder_best
~35 min instead of a month / 18h).

This runs the other four policies (random, highest_flow, lowest_flow,
zone_builder), which only call simulate() O(1) times per step and are fully
feasible locally on the full network -- imports the exact same policy
functions from evaluate.py, not a reimplementation, so numbers are directly
comparable to whatever evaluate.py prints for greedy/zone_builder_best once
the Ibex run comes back.

Usage:
    python scripts/run_abha_s0_baselines_cheap.py --config configs/city_madina_abha_s0.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from evaluate import (  # noqa: E402
    flow_ranked_policy,
    random_policy,
    run_policy,
    zone_builder_policy,
)
from snrl import StreetNetworkEnv, load_config  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--episodes", type=int, default=5)
    ap.add_argument("--out", default=None, help="Optional path to write results as JSON")
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)
    rng = np.random.default_rng(cfg.seed)

    policies = {
        "random": random_policy(rng),
        "highest_flow": flow_ranked_policy(env, descending=True),
        "lowest_flow": flow_ranked_policy(env, descending=False),
        "zone_builder": zone_builder_policy(env),
    }

    print(f"config: {args.config}  n_segments: {env.n_segments}  episodes: {args.episodes}")
    print("(greedy / zone_builder_best skipped -- see slurm/abha_s0_baselines.sbatch for Ibex)\n")
    print(f"{'policy':<14} {'mean return':>12} {'std':>8} {'wall_s':>8}")

    results = {}
    for name, choose in policies.items():
        t0 = time.time()
        returns = [run_policy(env, choose, cfg.seed + i)[0] for i in range(args.episodes)]
        dt = time.time() - t0
        print(f"{name:<14} {np.mean(returns):>12.4f} {np.std(returns):>8.4f} {dt:>8.1f}")
        results[name] = {"mean_return": float(np.mean(returns)), "std": float(np.std(returns)),
                          "returns": [float(r) for r in returns], "wall_s": dt}

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nSaved -> {args.out}")


if __name__ == "__main__":
    main()
