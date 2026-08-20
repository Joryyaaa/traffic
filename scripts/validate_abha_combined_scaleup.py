"""Stage 4 validation for the Abha named-site COMBINED GAT scenarios (Art
Street/Al-Muftaha baseline, Central Market, Asir Central Hospital, King
Abdulaziz Grand Mosque).

Modeled directly on scripts/validate_gat_scaleup_datasets.py (the Riyadh
scale-up study's Stage 3 script), adapted for scenarios that differ in
network/OD paths and origin_weight column (each named site has its own real
geometry) rather than only in radius. Verifies for each config:

  - config comparability vs. the r400 GAT/COMBINED reference: simulation
    block, include_adjacency_state, and every reward field (including
    min_zone_size=1) match exactly; every action field except
    max_closures/episode_length matches exactly. network.* is EXPECTED to
    differ (each scenario has its own streets/origins/destinations paths,
    origin_weight column, and respect_oneway) -- not compared field-by-field
    against the reference, only checked for internal consistency against
    that scenario's own original (pre-COMBINED) config.
  - no missing data paths (StreetNetworkEnv construction reads
    streets/residential/amenities directly -- a missing path raises
    FileNotFoundError, not skipped)
  - real segment count matches the value confirmed in Stage 1 by direct
    feature count (not the possibly-stale reported number)
  - action_space.n == n_segments + 1 (allow_noop=True in every config)
  - observation_space.shape == (n_segments + 1, 7) (include_adjacency_state=True)
  - connectivity: env.action_masks() returns at least one valid closure
  - GATFeaturesExtractor constructs on the network's real adjacency and runs
    a real forward pass, output shape (1, 64)
  - zone_builder reproduces the exact Stage 3 benchmark value for that
    scenario (regression check against results/abha_combined_scaleup/STAGE2_STAGE3.md)

Usage:
    PYTHONPATH=src python scripts/validate_abha_combined_scaleup.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REFERENCE_CONFIG = "configs/city_madina_ablation_r400_gat_mzs1.yaml"

# (label, new COMBINED config, original scenario config, expected n_segments,
#  expected zone_builder return under mzs=1, from Stage 1/Stage 3)
SCENARIOS = [
    (
        "Art Street / Al-Muftaha baseline",
        "configs/city_madina_abha_art_street_baseline_combined.yaml",
        "configs/city_madina_abha_art_street_baseline.yaml",
        57,
        0.4657,
    ),
    (
        "Central Market",
        "configs/city_madina_abha_central_market_combined.yaml",
        "configs/city_madina_abha_central_market.yaml",
        82,
        0.8363,
    ),
    (
        "Asir Central Hospital",
        "configs/city_madina_abha_asir_central_hospital_combined.yaml",
        "configs/city_madina_abha_asir_central_hospital.yaml",
        96,
        0.1383,
    ),
    (
        "King Abdulaziz Grand Mosque",
        "configs/city_madina_abha_king_abdulaziz_grand_mosque_combined.yaml",
        "configs/city_madina_abha_king_abdulaziz_grand_mosque.yaml",
        87,
        0.0503,
    ),
]


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
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

    print("=== Abha named-site COMBINED GAT scenario validation (Stage 4) ===\n")

    import yaml

    ref = yaml.safe_load(Path(REFERENCE_CONFIG).read_text())

    # ── 0. Config comparability vs. r400 reference + vs. own original config ──
    print("0. Config comparability")
    for label, new_path, orig_path, _, _ in SCENARIOS:
        cfg_raw = yaml.safe_load(Path(new_path).read_text())
        orig_raw = yaml.safe_load(Path(orig_path).read_text())

        check(f"[{label}] simulation block matches r400 reference",
              cfg_raw.get("simulation") == ref.get("simulation"))
        check(f"[{label}] include_adjacency_state matches r400 reference (True)",
              cfg_raw.get("include_adjacency_state") == ref.get("include_adjacency_state") is True
              or cfg_raw.get("include_adjacency_state") == True)  # noqa: E712
        ref_rew = dict(ref.get("reward", {}))
        cur_rew = dict(cfg_raw.get("reward", {}))
        check(f"[{label}] reward fields (incl. min_zone_size=1) match r400 reference",
              ref_rew == cur_rew)
        check(f"[{label}] action fields other than max_closures/episode_length match r400 reference",
              {k: v for k, v in cfg_raw.get("action", {}).items()
               if k not in ("max_closures", "episode_length")}
              == {k: v for k, v in ref.get("action", {}).items()
                  if k not in ("max_closures", "episode_length")})
        check(f"[{label}] network block unchanged from this scenario's own original config",
              cfg_raw.get("network") == orig_raw.get("network"))
        check(f"[{label}] min_zone_size changed from original ({orig_raw.get('reward', {}).get('min_zone_size')}) to 1",
              cfg_raw["reward"]["min_zone_size"] == 1)

    try:
        import torch
        from snrl import StreetNetworkEnv, load_config
        from snrl.gnn import GATFeaturesExtractor
        from evaluate import zone_builder_policy, run_policy
        HAS_RL = True
    except ImportError as e:
        HAS_RL = False
        print(f"\n[SKIP] all environment/forward-pass/benchmark checks -- missing dependency: {e}")

    if not HAS_RL:
        print(f"\n{'='*55}\n{failures} FAIL (config-only checks)")
        return 1 if failures else 0

    for label, new_path, _, expected_n, expected_zb in SCENARIOS:
        print(f"\n=== {label}: {new_path} ===")
        check("config file exists", Path(new_path).exists())
        if not Path(new_path).exists():
            continue

        try:
            cfg = load_config(new_path)
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
        check(f"n_segments == {expected_n} (Stage 1 direct feature count)",
              env.n_segments == expected_n, f"got {env.n_segments}")
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

        # zone_builder benchmark reproduction (fresh env, matches Stage 3 exactly)
        try:
            zb_env = StreetNetworkEnv(cfg)
            choose = zone_builder_policy(zb_env)
            total, _ = run_policy(zb_env, choose, cfg.seed)
            check(f"zone_builder reproduces Stage 3 benchmark ({expected_zb:+.4f})",
                  abs(total - expected_zb) < 1e-3, f"got {total:+.4f}")
            zb_env.close()
        except Exception as e:
            check("zone_builder benchmark reproduction", False, f"{type(e).__name__}: {e}")

    print(f"\n{'='*55}")
    if failures == 0:
        print("ALL CHECKS PASSED -- all 4 Abha COMBINED scenario configs validated.")
    else:
        print(f"{failures} CHECK(S) FAILED.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
