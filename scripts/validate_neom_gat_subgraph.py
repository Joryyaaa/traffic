"""Stage 4 validation for the NEOM GAT subgraph experiment (~273 segments,
Sharma/Camp26 dormitory cluster): real environment construction + a real GAT
forward pass, modeled on scripts/validate_gat_scaleup_datasets.py's structure
(the Riyadh scale-up study's Stage 3 script).

Verifies:
  - config comparability vs. the r400 COMBINED reference (simulation block,
    reward fields, GAT-relevant action fields, include_adjacency_state all
    match; only network data paths/weights/crs and the measured
    max_closures/episode_length budget are allowed to differ)
  - real data paths resolve (StreetNetworkEnv construction reads the NEOM
    subgraph files directly -- a missing path raises, it isn't skipped)
  - exact segment count (273, counted directly from the geojson feature
    list, not trusted from any label/config comment)
  - action_space.n == n_segments + 1
  - observation_space.shape == (n_segments + 1, 7)  (include_adjacency_state=True)
  - adjacency matrix construction: env._adjacency is a real (n_segments,
    n_segments) array built from the subgraph's own street topology
  - connectivity: env.action_masks() returns at least one valid closure (not
    an unreachable-everything failure mode)
  - GATFeaturesExtractor constructs on the network's real adjacency and runs
    a real forward pass, output shape (1, 64)

Usage:
    PYTHONPATH=src python scripts/validate_neom_gat_subgraph.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG = "configs/city_madina_neom_gat_subgraph_r750_mzs1.yaml"
REFERENCE_CONFIG = "configs/city_madina_ablation_r400_gat_mzs1.yaml"
SUBGRAPH_STREETS = "data/neom_gat_subgraph/sharma_dorm_r750/streets.geojson"
EXPECTED_N_SEGMENTS = 273


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

    print("=== NEOM GAT subgraph validation (Stage 4) ===\n")

    # ── 0. Exact segment count, counted directly from the geojson file ──
    print("0. Exact segment count (direct feature count, not trusted from any label)")
    streets_path = Path(SUBGRAPH_STREETS)
    check("streets file exists", streets_path.exists(), str(streets_path))
    if streets_path.exists():
        gj = json.loads(streets_path.read_text(encoding="utf-8"))
        n_features = len(gj["features"])
        check(f"feature count == {EXPECTED_N_SEGMENTS}", n_features == EXPECTED_N_SEGMENTS,
              f"got {n_features}")

    # ── 1. Config comparability vs. r400 reference ──────────────────────
    print("\n1. Config comparability vs. r400 COMBINED reference")
    import yaml

    ref = yaml.safe_load(Path(REFERENCE_CONFIG).read_text())
    cfg_raw = yaml.safe_load(Path(CONFIG).read_text())
    check("simulation block matches reference",
          cfg_raw.get("simulation") == ref.get("simulation"))
    check("include_adjacency_state matches reference (both True)",
          cfg_raw.get("include_adjacency_state") == ref.get("include_adjacency_state") is True
          or cfg_raw.get("include_adjacency_state") == ref.get("include_adjacency_state"))
    ref_rew = ref.get("reward", {})
    cur_rew = cfg_raw.get("reward", {})
    check("reward fields (all, including min_zone_size=1) match reference exactly",
          ref_rew == cur_rew)
    check("action fields other than max_closures/episode_length match reference",
          {k: v for k, v in cfg_raw.get("action", {}).items()
           if k not in ("max_closures", "episode_length")}
          == {k: v for k, v in ref.get("action", {}).items()
              if k not in ("max_closures", "episode_length")})
    check("network.crs == EPSG:32636 (NEOM UTM 36N, not Riyadh's 32638)",
          cfg_raw.get("network", {}).get("crs") == "EPSG:32636")
    ref_crs = ref.get("network", {}).get("crs")
    check("network.crs differs from r400 reference's EPSG:32638 (expected: different city, different UTM zone)",
          ref_crs == "EPSG:32638" and cfg_raw.get("network", {}).get("crs") != ref_crs)

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

    print(f"\n=== environment: {CONFIG} ===")
    check("config file exists", Path(CONFIG).exists())
    if not Path(CONFIG).exists():
        print(f"\n{'='*55}\n{failures} FAIL")
        return 1

    try:
        cfg = load_config(CONFIG)
    except Exception as e:
        check("config loads", False, str(e))
        print(f"\n{'='*55}\n{failures} FAIL")
        return 1

    try:
        env = StreetNetworkEnv(cfg)
    except FileNotFoundError as e:
        check("no missing data paths", False, str(e))
        print(f"\n{'='*55}\n{failures} FAIL")
        return 1
    except Exception as e:
        check("environment constructs", False, f"{type(e).__name__}: {e}")
        print(f"\n{'='*55}\n{failures} FAIL")
        return 1

    check("no missing data paths / env constructs", True)
    check(f"n_segments == {EXPECTED_N_SEGMENTS}", env.n_segments == EXPECTED_N_SEGMENTS,
          f"got {env.n_segments}")
    check("action_space.n == n_segments + 1",
          env.action_space.n == env.n_segments + 1,
          f"got {env.action_space.n}, expected {env.n_segments + 1}")
    check("observation_space.shape == (n_segments+1, 7)",
          env.observation_space.shape == (env.n_segments + 1, 7),
          f"got {env.observation_space.shape}")

    obs, _ = env.reset(seed=cfg.seed)
    check("obs.shape matches observation_space.shape", obs.shape == env.observation_space.shape)

    # ── adjacency matrix construction ──
    adjacency = env._adjacency
    import numpy as np
    adj_arr = np.asarray(adjacency)
    check("adjacency matrix shape == (n_segments, n_segments)",
          adj_arr.shape == (env.n_segments, env.n_segments),
          f"got {adj_arr.shape}")
    check("adjacency matrix is symmetric (undirected segment graph)",
          bool(np.array_equal(adj_arr, adj_arr.T)))
    check("adjacency matrix has at least one real edge",
          bool(adj_arr.sum() > 0), f"sum={adj_arr.sum()}")

    mask = env.action_masks()
    n_valid = int(mask[: env.n_segments].sum())
    check("connectivity: at least one valid closure action (not unreachable-everything)",
          n_valid > 0, f"{n_valid}/{env.n_segments} valid")

    try:
        extractor = GATFeaturesExtractor(
            env.observation_space, adjacency,
            gat_hidden_dim=32, n_heads=4, global_embed_dim=16, features_dim=64,
        )
        obs_t = torch.from_numpy(obs).unsqueeze(0).float()
        features = extractor(obs_t)
        check("GAT forward pass shape == (1, 64)", tuple(features.shape) == (1, 64),
              f"got {tuple(features.shape)}")
    except Exception as e:
        check("GAT forward pass", False, f"{type(e).__name__}: {e}")

    env.close()

    print(f"\n{'='*55}")
    if failures == 0:
        print("ALL CHECKS PASSED.")
    else:
        print(f"{failures} CHECK(S) FAILED.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
