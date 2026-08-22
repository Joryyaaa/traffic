"""Full pre-submission validation for the Riyadh r660 GAT scale-up point."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

CONFIG = ROOT / "configs/city_madina_ablation_r660_gat_mzs1.yaml"
REFERENCE = ROOT / "configs/city_madina_ablation_r400_gat_mzs1.yaml"
DATA_DIR = ROOT / "data/raw/riyadh_r660"
MEASUREMENTS = ROOT / "results/gat_scaleup_riyadh_r660/budget_measurements.json"
SBATCH = ROOT / "slurm/gat_scaleup_r660.sbatch"
EXPECTED_COUNTS = {"streets.geojson": 338, "residential.geojson": 135, "amenities.geojson": 36}
SELECTED_BUDGET = (8, 20)
SELECTED_ZONE_BUILDER = 0.3586685709


def feature_count(path: Path) -> int:
    return len(json.loads(path.read_text(encoding="utf-8"))["features"])


def main() -> int:
    from snrl import StreetNetworkEnv, load_config
    from snrl.gnn import GATFeaturesExtractor
    import torch

    failures = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        status = "PASS" if condition else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"  [{status}] {label}{suffix}")
        failures += int(not condition)

    print("=== Riyadh r660 / ~340-segment GAT scale-up validation ===\n")

    print("0. Frozen data counts")
    for filename, expected in EXPECTED_COUNTS.items():
        path = DATA_DIR / filename
        check(f"{filename} exists", path.exists(), str(path.relative_to(ROOT)))
        if path.exists():
            actual = feature_count(path)
            check(f"{filename} feature count == {expected}", actual == expected, f"got {actual}")

    print("\n1. COMBINED comparability vs r400 reference")
    cfg_raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    ref_raw = yaml.safe_load(REFERENCE.read_text(encoding="utf-8"))
    check("simulation block matches reference", cfg_raw["simulation"] == ref_raw["simulation"])
    check("reward block matches reference exactly", cfg_raw["reward"] == ref_raw["reward"])
    check("min_zone_size == 1", cfg_raw["reward"]["min_zone_size"] == 1)
    check(
        "include_adjacency_state matches reference and is true",
        cfg_raw["include_adjacency_state"] is True
        and cfg_raw["include_adjacency_state"] == ref_raw["include_adjacency_state"],
    )
    varying_action = {"max_closures", "episode_length"}
    cur_action = {k: v for k, v in cfg_raw["action"].items() if k not in varying_action}
    ref_action = {k: v for k, v in ref_raw["action"].items() if k not in varying_action}
    check("action fields except measured budget match reference", cur_action == ref_action)
    check("Riyadh CRS remains EPSG:32638", cfg_raw["network"]["crs"] == "EPSG:32638")

    print("\n2. Fresh budget measurement")
    measured = json.loads(MEASUREMENTS.read_text(encoding="utf-8"))
    check("measurement belongs to 338-segment network", measured["segments"] == 338)
    selected_rows = [
        row for row in measured["measurements"]
        if (row["max_closures"], row["episode_length"]) == SELECTED_BUDGET
    ]
    check("selected 8/20 candidate is present", len(selected_rows) == 1)
    if selected_rows:
        actual_return = selected_rows[0]["zone_builder_return"]
        check(
            "selected zone_builder benchmark matches measured value",
            abs(actual_return - SELECTED_ZONE_BUILDER) < 1e-10,
            f"got {actual_return:+.10f}",
        )
    check(
        "config uses selected 8/20 budget",
        (cfg_raw["action"]["max_closures"], cfg_raw["action"]["episode_length"])
        == SELECTED_BUDGET,
    )

    print("\n3. Real environment and GAT forward pass")
    cfg = load_config(CONFIG)
    env = StreetNetworkEnv(cfg)
    check("environment constructs", True)
    check("n_segments == 338", env.n_segments == 338, f"got {env.n_segments}")
    check("action_space.n == 339", env.action_space.n == 339, f"got {env.action_space.n}")
    check(
        "observation shape == (339, 7)",
        env.observation_space.shape == (339, 7),
        f"got {env.observation_space.shape}",
    )
    observation, _ = env.reset(seed=cfg.seed)
    check("reset observation matches declared shape", observation.shape == (339, 7))
    adjacency = np.asarray(env._adjacency)
    check("adjacency shape == (338, 338)", adjacency.shape == (338, 338), f"got {adjacency.shape}")
    check("adjacency is symmetric", np.array_equal(adjacency, adjacency.T))
    check("adjacency contains real edges", adjacency.sum() > 0, f"sum={adjacency.sum()}")
    valid = int(env.action_masks()[: env.n_segments].sum())
    check("at least one valid closure action", valid > 0, f"{valid}/338 valid")
    extractor = GATFeaturesExtractor(
        env.observation_space,
        env._adjacency,
        gat_hidden_dim=32,
        n_heads=4,
        global_embed_dim=16,
        features_dim=64,
    )
    features = extractor(torch.from_numpy(observation).unsqueeze(0).float())
    check("GAT forward output == (1, 64)", tuple(features.shape) == (1, 64), f"got {tuple(features.shape)}")
    env.close()

    print("\n4. Slurm/preemption contract")
    sbatch = SBATCH.read_text(encoding="utf-8")
    required_text = {
        "5-seed array": "#SBATCH --array=1-5",
        "20-hour walltime": "#SBATCH --time=20:00:00",
        "portable submit directory": 'PROJECT_DIR="${PROJECT_DIR:-$SLURM_SUBMIT_DIR}"',
        "portable matplotlib cache": 'MPLCONFIGDIR="${MPLCONFIGDIR:-$HOME/.cache/matplotlib}"',
        "167k timesteps": 'TIMESTEPS="${TIMESTEPS:-167000}"',
        "10k checkpoints": 'CHECKPOINT_FREQ="${CHECKPOINT_FREQ:-10000}"',
        "checkpoint CLI": '--checkpoint-freq "$CHECKPOINT_FREQ"',
        "isolated output root": 'OUTROOT="${OUTROOT:-runs/gat_scaleup_r660_5seed}"',
    }
    for label, needle in required_text.items():
        check(label, needle in sbatch)

    print(f"\n{'=' * 62}")
    if failures:
        print(f"{failures} CHECK(S) FAILED")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
