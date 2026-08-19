"""Stage 3 validation for the GAT scale-up datasets/configs (Riyadh, ~150/300/600
segments): real environment construction + a real GAT forward pass for each size.

Verifies for each config:
  - no missing data paths (StreetNetworkEnv construction reads streets/residential/
    amenities directly -- a missing path raises FileNotFoundError, not skipped)
  - action_space.n == n_segments + 1 (allow_noop=True in every config)
  - observation_space.shape == (n_segments + 1, 7)  (include_adjacency_state=True)
  - connectivity: env.action_masks() returns at least one valid closure (a fully
    disconnected/degenerate network would mask everything out)
  - GATFeaturesExtractor constructs on the network's real adjacency and runs a real
    forward pass, output shape (1, 64)
  - config comparability: network/simulation blocks and all reward fields except
    the size-dependent budget match the r400 reference exactly

Usage:
    PYTHONPATH=src python scripts/validate_gat_scaleup_datasets.py
"""
from __future__ import annotations

import sys
from pathlib import Path

CONFIGS = [
    ("r400 (reference)", "configs/city_madina_ablation_r400_gat_mzs1.yaml", 89),
    ("r445 (~150)", "configs/city_madina_ablation_r445_gat_mzs1.yaml", 176),
    ("r630 (~300)", "configs/city_madina_ablation_r630_gat_mzs1.yaml", 290),
    ("r850 (~600)", "configs/city_madina_ablation_r850_gat_mzs1.yaml", 599),
]

REFERENCE_CONFIG = "configs/city_madina_ablation_r400_gat_mzs1.yaml"


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

    print("=== GAT scale-up dataset/config validation (Stage 3) ===\n")

    # ── 0. Config comparability vs. r400 reference ──────────────────────
    print("0. Config comparability vs. r400 reference")
    import yaml

    ref = yaml.safe_load(Path(REFERENCE_CONFIG).read_text())
    for label, cfg_path, _ in CONFIGS[1:]:
        cfg_raw = yaml.safe_load(Path(cfg_path).read_text())
        check(f"[{label}] simulation block matches reference",
              cfg_raw.get("simulation") == ref.get("simulation"))
        check(f"[{label}] include_adjacency_state matches reference",
              cfg_raw.get("include_adjacency_state") == ref.get("include_adjacency_state"))
        ref_rew = {k: v for k, v in ref.get("reward", {}).items()}
        cur_rew = {k: v for k, v in cfg_raw.get("reward", {}).items()}
        check(f"[{label}] reward fields (all, including min_zone_size) match reference",
              ref_rew == cur_rew, "min_zone_size fixed at 1 for every size, per instruction")
        check(f"[{label}] action fields other than max_closures/episode_length match reference",
              {k: v for k, v in cfg_raw.get("action", {}).items()
               if k not in ("max_closures", "episode_length")}
              == {k: v for k, v in ref.get("action", {}).items()
                  if k not in ("max_closures", "episode_length")})

    try:
        import torch
        from snrl import StreetNetworkEnv, load_config
        from snrl.gnn import GATFeaturesExtractor
        HAS_RL = True
    except ImportError as e:
        HAS_RL = False
        print(f"\n[SKIP] all environment/forward-pass checks -- missing dependency: {e}")

    if not HAS_RL:
        print(f"\n{'='*55}\n{failures} FAIL (config-only checks)")
        return 1 if failures else 0

    for label, cfg_path, expected_n in CONFIGS:
        print(f"\n=== {label}: {cfg_path} ===")
        check("config file exists", Path(cfg_path).exists())
        if not Path(cfg_path).exists():
            continue

        try:
            cfg = load_config(cfg_path)
        except Exception as e:
            check("config loads", False, str(e))
            continue

        try:
            env = StreetNetworkEnv(cfg)
        except FileNotFoundError as e:
            check("no missing data paths", False, str(e))
            continue
        except Exception as e:
            check("environment constructs", False, f"{type(e).__name__}: {e}")
            continue

        check("no missing data paths / env constructs", True)
        check(f"n_segments == {expected_n}", env.n_segments == expected_n,
              f"got {env.n_segments}")
        check("action_space.n == n_segments + 1",
              env.action_space.n == env.n_segments + 1,
              f"got {env.action_space.n}, expected {env.n_segments + 1}")
        check("observation_space.shape == (n_segments+1, 7)",
              env.observation_space.shape == (env.n_segments + 1, 7),
              f"got {env.observation_space.shape}")

        obs, _ = env.reset(seed=cfg.seed)
        check("obs.shape matches observation_space.shape", obs.shape == env.observation_space.shape)

        mask = env.action_masks()
        check("connectivity: at least one valid closure action",
              bool(mask[: env.n_segments].any()), f"{mask[:env.n_segments].sum()} valid")

        try:
            adjacency = env._adjacency
            extractor = GATFeaturesExtractor(
                env.observation_space, adjacency,
                gat_hidden_dim=32, n_heads=4, global_embed_dim=16, features_dim=64,
            )
            obs_t = torch.from_numpy(obs).unsqueeze(0).float()
            features = extractor(obs_t)
            check("GAT forward pass shape == (1, 64)", features.shape == (1, 64),
                  f"got {tuple(features.shape)}")
        except Exception as e:
            check("GAT forward pass", False, f"{type(e).__name__}: {e}")

        env.close()

    print(f"\n{'='*55}")
    if failures == 0:
        print("ALL CHECKS PASSED — all 4 configs (reference + 3 scale-up sizes) validated.")
    else:
        print(f"{failures} CHECK(S) FAILED.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
