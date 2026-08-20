"""Pre-flight validation for the credit-assignment ablation.

Verifies:
  - mzs1 config parses and differs from GAT control ONLY in min_zone_size
  - zone_score behaves differently with min_zone_size=1 vs 4
  - GAT extractor still constructs and runs with the mzs1 config (Ibex only)
  - Slurm script references the correct config and output dir
  - seed_sweep_gat.py exists

Usage:
    PYTHONPATH=src python scripts/validate_credit_assignment_ablation.py
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

    def skip(label: str, reason: str):
        print(f"  [SKIP] {label}  ({reason})")

    print("=== credit-assignment ablation validation ===\n")

    # ── 1. Config parsing (YAML only, no gym/torch needed) ─────────────
    print("1. Config parsing")
    import yaml

    mzs1_path = Path("configs/city_madina_ablation_r400_gat_mzs1.yaml")
    ctrl_path = Path("configs/city_madina_ablation_r400_gat.yaml")

    check("mzs1 config exists", mzs1_path.exists())
    check("control config exists", ctrl_path.exists())
    if not (mzs1_path.exists() and ctrl_path.exists()):
        print("\nCANNOT CONTINUE without both configs")
        return 1

    with open(mzs1_path) as f:
        mzs1 = yaml.safe_load(f)
    with open(ctrl_path) as f:
        ctrl = yaml.safe_load(f)

    check("mzs1 min_zone_size == 1",
          mzs1.get("reward", {}).get("min_zone_size") == 1,
          f"got {mzs1.get('reward', {}).get('min_zone_size')}")
    check("control min_zone_size == 4",
          ctrl.get("reward", {}).get("min_zone_size") == 4,
          f"got {ctrl.get('reward', {}).get('min_zone_size')}")

    # ── 2. Controlled comparison: only min_zone_size differs ───────────
    print("\n2. Controlled comparison (only min_zone_size should differ)")
    check("network identical", mzs1.get("network") == ctrl.get("network"))
    check("simulation identical", mzs1.get("simulation") == ctrl.get("simulation"))
    check("action identical", mzs1.get("action") == ctrl.get("action"))
    check("seed identical", mzs1.get("seed") == ctrl.get("seed"))
    check("include_adjacency_state identical",
          mzs1.get("include_adjacency_state") == ctrl.get("include_adjacency_state"))

    mzs1_rew = dict(mzs1.get("reward", {}))
    ctrl_rew = dict(ctrl.get("reward", {}))
    mzs1_rew_no_mzs = {k: v for k, v in mzs1_rew.items() if k != "min_zone_size"}
    ctrl_rew_no_mzs = {k: v for k, v in ctrl_rew.items() if k != "min_zone_size"}
    check("all reward fields except min_zone_size identical",
          mzs1_rew_no_mzs == ctrl_rew_no_mzs)

    # ── 3. zone_score behaviour with mzs=1 vs mzs=4 ──────────────────
    print("\n3. zone_score difference (mzs=1 vs mzs=4)")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "snrl.metrics",
        str(Path(__file__).resolve().parent.parent / "src" / "snrl" / "metrics.py"),
    )
    metrics_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(metrics_mod)
    zone_score = metrics_mod.zone_score

    adj = np.zeros((6, 6), dtype=bool)
    adj[0, 1] = adj[1, 0] = True
    adj[1, 2] = adj[2, 1] = True
    adj[3, 4] = adj[4, 3] = True
    closed = np.array([True, True, True, False, False, False])

    zs_mzs1 = zone_score(closed, adj, min_size=1, exponent=2.0)
    zs_mzs4 = zone_score(closed, adj, min_size=4, exponent=2.0)

    check("mzs=1 scores group of 3", zs_mzs1 > 0, f"zone_score={zs_mzs1}")
    check("mzs=4 ignores group of 3", zs_mzs4 == 0.0, f"zone_score={zs_mzs4}")
    check("mzs=1 gives 3**2=9.0", zs_mzs1 == 9.0, f"got {zs_mzs1}")

    closed_1 = np.array([True, False, False, False, False, False])
    zs1_single = zone_score(closed_1, adj, min_size=1, exponent=2.0)
    zs4_single = zone_score(closed_1, adj, min_size=4, exponent=2.0)
    check("mzs=1 rewards single closure", zs1_single == 1.0, f"got {zs1_single}")
    check("mzs=4 ignores single closure", zs4_single == 0.0, f"got {zs4_single}")

    closed_4 = np.zeros(6, dtype=bool)
    adj_chain = np.zeros((6, 6), dtype=bool)
    for i in range(3):
        adj_chain[i, i + 1] = adj_chain[i + 1, i] = True
    closed_4[:4] = True
    zs1_4 = zone_score(closed_4, adj_chain, min_size=1, exponent=2.0)
    zs4_4 = zone_score(closed_4, adj_chain, min_size=4, exponent=2.0)
    check("mzs=1 group of 4 = 16.0", zs1_4 == 16.0, f"got {zs1_4}")
    check("mzs=4 group of 4 = 16.0", zs4_4 == 16.0, f"got {zs4_4}")

    # ── 4. GAT extractor (requires torch/gymnasium — Ibex only) ───────
    print("\n4. GAT extractor (smoke test)")
    try:
        import torch
        from sb3_contrib import MaskablePPO
        from snrl.gnn import GATFeaturesExtractor
        from snrl.env import StreetNetworkEnv
        HAS_RL = True
    except ImportError as e:
        HAS_RL = False
        skip("GAT extractor", f"missing dependency: {e}")
        skip("forward pass", "skipped (no torch/gymnasium)")

    if HAS_RL:
        try:
            from snrl.config import load_config as _load_config
            cfg_env = _load_config(mzs1_path)
            cfg_env.include_adjacency_state = True
            env = StreetNetworkEnv(cfg_env)
            adjacency = env._adjacency
            obs, _ = env.reset(seed=1)
            extractor = GATFeaturesExtractor(
                env.observation_space, adjacency,
                gat_hidden_dim=32, n_heads=4, global_embed_dim=16, features_dim=64,
            )
            obs_t = torch.from_numpy(obs).unsqueeze(0).float()
            features = extractor(obs_t)
            check("GAT forward pass shape", features.shape == (1, 64), f"{features.shape}")
        except Exception as e:
            check("GAT forward pass", False, str(e))

    # ── 5. File existence checks ──────────────────────────────────────
    print("\n5. File existence")
    check("seed_sweep_gat.py exists", Path("scripts/seed_sweep_gat.py").exists())
    check("aggregate_sweep.py exists", Path("scripts/aggregate_sweep.py").exists())
    check("Slurm script exists", Path("slurm/credit_assignment_ablation.sbatch").exists())
    check("PROVENANCE.md exists", Path("results/credit_assignment_ablation/PROVENANCE.md").exists())

    # ── 6. Slurm script references ────────────────────────────────────
    print("\n6. Slurm script references")
    sbatch = Path("slurm/credit_assignment_ablation.sbatch").read_text()
    check("uses mzs1 config", "city_madina_ablation_r400_gat_mzs1.yaml" in sbatch)
    check("uses seed_sweep_gat.py", "seed_sweep_gat.py" in sbatch)
    check("output dir r400_gat_mzs1_30k", "r400_gat_mzs1_30k" in sbatch)
    check("project dir alblueja", "/home/alblueja/traffic" in sbatch)

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'=' * 55}")
    if failures == 0:
        print("ALL CHECKS PASSED — ready to submit to Ibex.")
        if not HAS_RL:
            print("(GAT smoke test skipped — run again on Ibex for full validation)")
    else:
        print(f"{failures} CHECK(S) FAILED — fix before submitting.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
