"""Pre-flight validation for the MLP adjacency-observation experiment.

Run this BEFORE submitting the Slurm jobs to verify:
  - MaskablePPO imports
  - both observation modes construct and step correctly
  - observation shapes match expected dimensions
  - adjacency features are populated when segments close
  - the two experiment configs parse identically except for the switch

Usage:
    python scripts/validate_adjacency_experiment.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    failures = 0

    def check(label: str, condition: bool, detail: str = ""):
        nonlocal failures
        status = "PASS" if condition else "FAIL"
        msg = f"  [{status}] {label}"
        if detail:
            msg += f"  ({detail})"
        print(msg)
        if not condition:
            failures += 1

    print("=== MLP adjacency-observation experiment validation ===\n")

    # 1. MaskablePPO
    print("1. MaskablePPO import")
    try:
        from sb3_contrib import MaskablePPO  # noqa: F401
        check("sb3_contrib.MaskablePPO", True)
    except ImportError as e:
        check("sb3_contrib.MaskablePPO", False, str(e))

    # 2. Observation modes with stub backend
    from snrl.config import EnvConfig
    from snrl.env import N_FEATURES_ADJACENCY, N_FEATURES_BASE, StreetNetworkEnv

    print("\n2. Baseline (5-feature) environment")
    cfg_base = EnvConfig()
    cfg_base.include_adjacency_state = False
    env_base = StreetNetworkEnv(cfg_base)
    obs_base, _ = env_base.reset(seed=1)
    n_seg = env_base.n_segments
    check("obs shape", obs_base.shape == (n_seg + 1, N_FEATURES_BASE),
          f"{obs_base.shape} vs ({n_seg + 1}, {N_FEATURES_BASE})")
    obs2, rew, term, trunc, _ = env_base.step(0)
    check("step shape stable", obs2.shape == obs_base.shape)
    check("action mask shape", env_base.action_masks().shape[0] > 0)

    print("\n3. Adjacency (7-feature) environment")
    cfg_adj = EnvConfig()
    cfg_adj.include_adjacency_state = True
    env_adj = StreetNetworkEnv(cfg_adj)
    obs_adj, _ = env_adj.reset(seed=1)
    check("obs shape", obs_adj.shape == (n_seg + 1, N_FEATURES_ADJACENCY),
          f"{obs_adj.shape} vs ({n_seg + 1}, {N_FEATURES_ADJACENCY})")
    obs_adj2, _, _, _, _ = env_adj.step(0)
    check("step shape stable", obs_adj2.shape == obs_adj.shape)

    # Verify adjacency features
    neighbors = np.flatnonzero(np.asarray(env_adj._adjacency[0]))
    if len(neighbors) > 0:
        check("closed_neighbour_count > 0 for neighbors",
              all(obs_adj2[n, 5] >= 1.0 for n in neighbors))
        check("touches_closed == 1 for neighbors",
              all(obs_adj2[n, 6] == 1.0 for n in neighbors))
    else:
        check("segment 0 has neighbors", False, "cannot verify adjacency features")

    # Global row padding
    check("global row baseline length", len(obs_base[-1]) == N_FEATURES_BASE)
    check("global row adjacency length", len(obs_adj[-1]) == N_FEATURES_ADJACENCY)
    check("adjacency global padding zeros",
          obs_adj[-1][5] == 0.0 and obs_adj[-1][6] == 0.0)

    # Feature parity
    print("\n4. Feature parity between modes")
    env_b2 = StreetNetworkEnv(EnvConfig())
    cfg_a2 = EnvConfig()
    cfg_a2.include_adjacency_state = True
    env_a2 = StreetNetworkEnv(cfg_a2)
    ob1, _ = env_b2.reset(seed=42)
    ob2, _ = env_a2.reset(seed=42)
    check("first 5 features match", np.allclose(ob1[:, :5], ob2[:, :5]))

    # 5. Config parsing
    print("\n5. Experiment config parsing")
    from snrl.config import load_config

    base_path = Path("configs/city_madina_ablation_r400_mlp_baseline.yaml")
    adj_path = Path("configs/city_madina_ablation_r400_mlp_adjacency.yaml")

    if base_path.exists() and adj_path.exists():
        cb = load_config(base_path)
        ca = load_config(adj_path)
        check("baseline flag is False", cb.include_adjacency_state is False)
        check("adjacency flag is True", ca.include_adjacency_state is True)
        check("network identical", cb.network == ca.network)
        check("simulation identical", cb.simulation == ca.simulation)
        check("action identical", cb.action == ca.action)
        check("reward identical", cb.reward == ca.reward)
        check("seed identical", cb.seed == ca.seed)
    else:
        check("experiment configs exist", False, "missing YAML files")

    print(f"\n{'=' * 50}")
    if failures == 0:
        print("ALL CHECKS PASSED — ready to submit to Ibex.")
    else:
        print(f"{failures} CHECK(S) FAILED — fix before submitting.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
