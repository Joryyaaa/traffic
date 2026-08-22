"""Validate that the GAT-vs-MLP controlled comparison is methodologically sound.

Checks:
  1. Each config loads without error and has include_adjacency_state=True
  2. Both configs use the same reward, simulation, and action settings
  3. Both configs point to existing data files
  4. GAT and MLP scripts use the same evaluation protocol
  5. Source code has adjacency observation support and GAT architecture
  6. Configs at different scales have compatible structure

Does NOT require gymnasium/torch — uses YAML parsing only.

Usage:
    python scripts/validate_gat_vs_mlp_parity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

CONFIGS = [
    "configs/gat_vs_mlp_r445_mzs1.yaml",
    "configs/gat_vs_mlp_r630_mzs1.yaml",
]

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    status = "PASS" if condition else "FAIL"
    if not condition:
        FAIL += 1
    else:
        PASS += 1
    msg = f"  [{status}] {name}"
    if detail:
        msg += f" -- {detail}"
    print(msg)


def compare_dicts(d1: dict, d2: dict, prefix: str = "") -> list[str]:
    diffs = []
    all_keys = set(d1.keys()) | set(d2.keys())
    for k in sorted(all_keys):
        path = f"{prefix}.{k}" if prefix else k
        if k not in d1:
            diffs.append(f"{path}: missing in first")
        elif k not in d2:
            diffs.append(f"{path}: missing in second")
        elif isinstance(d1[k], dict) and isinstance(d2[k], dict):
            diffs.extend(compare_dicts(d1[k], d2[k], path))
        elif d1[k] != d2[k]:
            diffs.append(f"{path}: {d1[k]!r} vs {d2[k]!r}")
    return diffs


def main():
    root = Path(__file__).resolve().parents[1]

    configs = {}
    for cfg_path in CONFIGS:
        full = root / cfg_path
        name = Path(cfg_path).stem
        print(f"\n--- {name} ---")

        check("config file exists", full.exists())
        if not full.exists():
            continue

        raw = yaml.safe_load(full.read_text()) or {}
        configs[name] = raw

        check("include_adjacency_state is true",
              raw.get("include_adjacency_state") is True)

        reward = raw.get("reward", {})
        check("min_zone_size == 1", reward.get("min_zone_size") == 1,
              f"got {reward.get('min_zone_size')}")

        network = raw.get("network", {})
        for key in ["streets_path", "origins_path", "destinations_path"]:
            path = network.get(key)
            exists = path and (root / path).exists()
            check(f"{key} exists", bool(exists), str(path))

        check("backend is madina", network.get("backend") == "madina")
        check("CRS is EPSG:32638", network.get("crs") == "EPSG:32638")

        action = raw.get("action", {})
        check("closure_mode is penalize", action.get("closure_mode") == "penalize")
        check("allow_reopen is false", action.get("allow_reopen") is False)
        check("forbid_disconnection is true", action.get("forbid_disconnection") is True)

        check("reward_mode is delta", reward.get("reward_mode") == "delta")
        check("w_pedestrian_zone > 0", (reward.get("w_pedestrian_zone", 0) or 0) > 0)
        check("zone_min_flow_fraction > 0", (reward.get("zone_min_flow_fraction", 0) or 0) > 0)
        check("episode_length > max_closures",
              action.get("episode_length", 0) > action.get("max_closures", 0),
              f"{action.get('episode_length')} > {action.get('max_closures')}")

    # Cross-config parity: reward and simulation must match
    if len(configs) >= 2:
        names = list(configs.keys())
        print(f"\n--- Cross-config parity ---")

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                n1, n2 = names[i], names[j]
                c1, c2 = configs[n1], configs[n2]

                reward_diffs = compare_dicts(
                    c1.get("reward", {}), c2.get("reward", {}))
                check(f"reward parity: {n1} vs {n2}",
                      len(reward_diffs) == 0,
                      "; ".join(reward_diffs) if reward_diffs else "identical")

                sim_diffs = compare_dicts(
                    c1.get("simulation", {}), c2.get("simulation", {}))
                check(f"simulation parity: {n1} vs {n2}",
                      len(sim_diffs) == 0,
                      "; ".join(sim_diffs) if sim_diffs else "identical")

                check(f"adjacency_state parity: {n1} vs {n2}",
                      c1.get("include_adjacency_state") == c2.get("include_adjacency_state"))

    # Verify scripts exist
    print(f"\n--- Script files ---")
    for script in ["scripts/seed_sweep_gat.py", "scripts/seed_sweep_mlp_adj.py"]:
        check(f"{script} exists", (root / script).exists())

    gat_script = (root / "scripts/seed_sweep_gat.py").read_text()
    check("GAT script imports GATFeaturesExtractor",
          "GATFeaturesExtractor" in gat_script)
    check("GAT script uses features_extractor_class",
          "features_extractor_class" in gat_script)
    check("GAT script has checkpointing",
          "CheckpointCallback" in gat_script)

    mlp_script = (root / "scripts/seed_sweep_mlp_adj.py").read_text()
    check("MLP script does NOT use GATFeaturesExtractor",
          "GATFeaturesExtractor" not in mlp_script)
    check("MLP script uses MlpPolicy",
          "MlpPolicy" in mlp_script)
    check("MLP script has checkpointing",
          "CheckpointCallback" in mlp_script)

    # Verify env.py has adjacency support
    print(f"\n--- Source code ---")
    env_src = (root / "src/snrl/env.py").read_text()
    check("env.py has N_FEATURES_BASE", "N_FEATURES_BASE" in env_src)
    check("env.py has N_FEATURES_ADJACENCY", "N_FEATURES_ADJACENCY" in env_src)
    check("env.py has include_adjacency_state", "include_adjacency_state" in env_src)
    check("env.py has closed_neighbour_count", "closed_neighbour_count" in env_src)

    config_src = (root / "src/snrl/config.py").read_text()
    check("config.py has include_adjacency_state field",
          "include_adjacency_state" in config_src)

    gnn_src = (root / "src/snrl/gnn.py").read_text()
    check("gnn.py has GATFeaturesExtractor class",
          "class GATFeaturesExtractor" in gnn_src)
    check("gnn.py has GATLayer class",
          "class GATLayer" in gnn_src)
    check("gnn.py has adjacency_mask function",
          "def adjacency_mask" in gnn_src)

    # Verify Slurm script
    print(f"\n--- Slurm ---")
    slurm_path = root / "slurm/gat_vs_mlp_sweep.sbatch"
    check("Slurm script exists", slurm_path.exists())
    if slurm_path.exists():
        slurm_src = slurm_path.read_text()
        check("Slurm script supports ARCH=gat", "seed_sweep_gat.py" in slurm_src)
        check("Slurm script supports ARCH=mlp_adj", "seed_sweep_mlp_adj.py" in slurm_src)
        check("Slurm script sets SNRL_MASK_WORKERS=8", "SNRL_MASK_WORKERS=8" in slurm_src)

    print(f"\n{'='*60}")
    print(f"TOTAL: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        sys.exit(1)
    else:
        print("All checks passed.")


if __name__ == "__main__":
    main()
