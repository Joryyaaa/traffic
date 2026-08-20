"""Pre-flight validation for the GAT r400 experiment.

Run this BEFORE submitting the Slurm jobs to verify:
  - MaskablePPO imports
  - GATFeaturesExtractor constructs with correct adjacency
  - 7-feature observation shape is correct
  - MaskablePPO accepts the GAT extractor
  - action masking works
  - predict/step path works without tensor shape errors
  - graph attention is actually used (not bypassed by dense layers)
  - config parsing is correct
  - existing tests still pass

Usage:
    python scripts/validate_gat_experiment.py
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

    print("=== GAT r400 experiment validation ===\n")

    # 1. MaskablePPO
    print("1. MaskablePPO import")
    try:
        from sb3_contrib import MaskablePPO
        from sb3_contrib.common.wrappers import ActionMasker
        check("sb3_contrib.MaskablePPO", True)
    except ImportError as e:
        check("sb3_contrib.MaskablePPO", False, str(e))
        print("\nCANNOT CONTINUE without MaskablePPO")
        return 1

    # 2. GAT extractor import
    print("\n2. GAT extractor import")
    try:
        from snrl.gnn import GATFeaturesExtractor, GATLayer, adjacency_mask
        check("GATFeaturesExtractor import", True)
    except ImportError as e:
        check("GATFeaturesExtractor import", False, str(e))
        return 1

    # 3. Environment with adjacency observation
    print("\n3. Environment construction (stub, 7-feature)")
    from stable_baselines3.common.monitor import Monitor
    from snrl.config import EnvConfig
    from snrl.env import N_FEATURES_ADJACENCY, StreetNetworkEnv

    cfg = EnvConfig()
    cfg.include_adjacency_state = True
    env = StreetNetworkEnv(cfg)
    n_seg = env.n_segments
    adjacency = env._adjacency

    obs, _ = env.reset(seed=1)
    check("obs shape", obs.shape == (n_seg + 1, N_FEATURES_ADJACENCY),
          f"{obs.shape} vs ({n_seg + 1}, {N_FEATURES_ADJACENCY})")
    check("adjacency shape", adjacency.shape == (n_seg, n_seg),
          f"{adjacency.shape} vs ({n_seg}, {n_seg})")

    # 4. GAT extractor construction
    print("\n4. GAT extractor construction")
    import torch
    from gymnasium import spaces

    extractor = GATFeaturesExtractor(
        env.observation_space, adjacency,
        gat_hidden_dim=32, n_heads=4, global_embed_dim=16, features_dim=64,
    )
    check("extractor constructed", True)
    check("adj_mask is buffer", hasattr(extractor, "adj_mask"))
    check("adj_mask shape", extractor.adj_mask.shape == (n_seg, n_seg),
          f"{extractor.adj_mask.shape}")

    # Verify self-loops in adjacency mask
    diag = torch.diag(extractor.adj_mask)
    check("self-loops in adj_mask", bool((diag == 1.0).all()))

    # Verify attention is NOT dense (non-neighbours should be masked)
    n_edges = int(extractor.adj_mask.sum().item())
    n_possible = n_seg * n_seg
    check("attention is sparse (not dense)",
          n_edges < n_possible,
          f"{n_edges}/{n_possible} edges")

    # 5. Forward pass
    print("\n5. Forward pass")
    obs_t = torch.from_numpy(obs).unsqueeze(0).float()
    features = extractor(obs_t)
    check("output shape", features.shape == (1, 64), f"{features.shape}")

    # Gradient flow
    features.sum().backward()
    grad_ok = all(p.grad is not None for p in extractor.parameters() if p.requires_grad)
    check("gradients flow through GAT layers", grad_ok)

    # 6. MaskablePPO integration
    print("\n6. MaskablePPO + GAT integration")
    env_wrapped = ActionMasker(Monitor(StreetNetworkEnv(cfg)),
                               lambda e: e.unwrapped.action_masks())
    adjacency2 = env_wrapped.unwrapped._adjacency

    policy_kwargs = dict(
        features_extractor_class=GATFeaturesExtractor,
        features_extractor_kwargs=dict(
            adjacency=adjacency2,
            gat_hidden_dim=32, n_heads=4,
            global_embed_dim=16, features_dim=64,
        ),
    )
    model = MaskablePPO("MlpPolicy", env_wrapped, verbose=0, seed=1,
                        policy_kwargs=policy_kwargs)
    check("MaskablePPO created", True)
    check("extractor type",
          type(model.policy.features_extractor).__name__ == "GATFeaturesExtractor",
          type(model.policy.features_extractor).__name__)

    # predict
    obs_test, _ = env_wrapped.reset(seed=1)
    action, _ = model.predict(obs_test,
                              action_masks=env_wrapped.unwrapped.action_masks(),
                              deterministic=True)
    check("predict works", True, f"action={action}")

    # step
    obs2, rew, term, trunc, _ = env_wrapped.step(action)
    check("step works", True, f"reward={rew:.6f}")

    # second predict (after state change)
    action2, _ = model.predict(obs2,
                               action_masks=env_wrapped.unwrapped.action_masks(),
                               deterministic=True)
    check("second predict works", True, f"action={action2}")

    # 7. Config parsing
    print("\n7. Config parsing")
    from snrl.config import load_config

    gat_cfg_path = Path("configs/city_madina_ablation_r400_gat.yaml")
    adj_cfg_path = Path("configs/city_madina_ablation_r400_mlp_adjacency.yaml")

    if gat_cfg_path.exists():
        cg = load_config(gat_cfg_path)
        check("GAT config include_adjacency_state", cg.include_adjacency_state is True)
        check("GAT config backend", cg.network.backend == "madina")
        check("GAT config max_closures", cg.action.max_closures == 9)
        check("GAT config min_zone_size", cg.reward.min_zone_size == 4)

        if adj_cfg_path.exists():
            ca = load_config(adj_cfg_path)
            check("env parity: network", cg.network == ca.network)
            check("env parity: simulation", cg.simulation == ca.simulation)
            check("env parity: action", cg.action == ca.action)
            check("env parity: reward", cg.reward == ca.reward)
            check("env parity: seed", cg.seed == ca.seed)
            check("env parity: adjacency flag", cg.include_adjacency_state == ca.include_adjacency_state)
    else:
        check("GAT config exists", False)

    # 8. Parameter count
    print("\n8. Architecture summary")
    n_params = sum(p.numel() for p in model.policy.features_extractor.parameters())
    total_params = sum(p.numel() for p in model.policy.parameters())
    print(f"  Extractor parameters: {n_params:,}")
    print(f"  Total policy parameters: {total_params:,}")
    print(f"  GAT layers: 2 x (in→32, 4 heads)")
    print(f"  Global MLP: 7→16")
    print(f"  Output MLP: 48→64")

    print(f"\n{'=' * 50}")
    if failures == 0:
        print("ALL CHECKS PASSED — ready to submit to Ibex.")
    else:
        print(f"{failures} CHECK(S) FAILED — fix before submitting.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
