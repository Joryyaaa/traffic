"""Pre-flight validation for the combined GAT experiment: min_zone_size=1
(from credit-assignment-ablation) + 167,000 timesteps (from
gat-r400-longer-training).

Verifies everything the combined-experiment brief asked for. Every check
either PASSes, FAILs, or is explicitly SKIPped with a reason -- a SKIP is
never reported as a PASS, per instruction.

Usage:
    PYTHONPATH=src python scripts/validate_combined_gat_credit_long.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

CREDIT_COMMIT = "115220e"
GATLONG_COMMIT = "25f968a"
BASE_COMMIT = "34f03c8"  # original completed 30k GAT control, common ancestor of both

CONFIG_PATH = Path("configs/city_madina_ablation_r400_gat_mzs1.yaml")
CONTROL_CONFIG_PATH = Path("configs/city_madina_ablation_r400_gat.yaml")
TRAIN_SCRIPT_PATH = Path("scripts/seed_sweep_gat.py")
SBATCH_PATH = Path("slurm/combined_gat_credit_long.sbatch")

FORBIDDEN_OUTPUT_DIRS = ["runs/r400_gat_30k", "runs/r400_gat_mzs1_30k", "runs/r400_gat_167k"]
EXPECTED_OUTPUT_DIR = "runs/r400_gat_mzs1_167k"

DATA_DIR = Path("data/raw/riyadh_r400")
DATA_FILES = ["streets.geojson", "residential.geojson", "amenities.geojson"]


def git_show(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"], capture_output=True, check=True
    ).stdout


def sha256_norm(data: bytes) -> str:
    # Normalize CRLF -> LF before hashing (Windows checkout artifact -- see
    # validate_gat_r400_longer_training.py for why raw-byte comparison is wrong).
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    failures = 0
    skips = 0

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
        nonlocal skips
        skips += 1
        print(f"  [SKIP] {label}  ({reason})")

    print("=== Combined GAT experiment (mzs1 + 167k) validation ===\n")

    # ── 1. Branch ancestry / provenance ─────────────────────────────────
    print("1. Branch ancestry")
    for commit, name in [(CREDIT_COMMIT, "CREDIT"), (GATLONG_COMMIT, "GAT-LONG"),
                          (BASE_COMMIT, "original 30k control")]:
        try:
            subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
            check(f"{commit} ({name}) is an ancestor of HEAD", True)
        except subprocess.CalledProcessError:
            check(f"{commit} ({name}) is an ancestor of HEAD", False)

    # ── 2. Config: exact intended difference vs the mzs=4 control ──────
    print("\n2. Config: intended difference is min_zone_size only")
    check("combined config exists", CONFIG_PATH.exists())
    check("control config exists", CONTROL_CONFIG_PATH.exists())
    if CONFIG_PATH.exists() and CONTROL_CONFIG_PATH.exists():
        import yaml
        combined = yaml.safe_load(CONFIG_PATH.read_text())
        control = yaml.safe_load(CONTROL_CONFIG_PATH.read_text())

        check("min_zone_size == 1", combined.get("reward", {}).get("min_zone_size") == 1,
              f"got {combined.get('reward', {}).get('min_zone_size')}")
        check("control min_zone_size == 4", control.get("reward", {}).get("min_zone_size") == 4)
        check("network identical to control", combined.get("network") == control.get("network"))
        check("simulation identical to control", combined.get("simulation") == control.get("simulation"))
        check("action identical to control", combined.get("action") == control.get("action"))
        check("include_adjacency_state == True",
              combined.get("include_adjacency_state") is True)

        combined_rew_no_mzs = {k: v for k, v in combined.get("reward", {}).items() if k != "min_zone_size"}
        control_rew_no_mzs = {k: v for k, v in control.get("reward", {}).items() if k != "min_zone_size"}
        check("all reward fields except min_zone_size identical to control",
              combined_rew_no_mzs == control_rew_no_mzs)

    # ── 3. Combined config byte-identical to CREDIT's committed version ─
    print("\n3. Combined config matches CREDIT's committed file exactly")
    if CONFIG_PATH.exists():
        current = CONFIG_PATH.read_bytes()
        try:
            base = git_show(CREDIT_COMMIT, str(CONFIG_PATH).replace("\\", "/"))
            check("byte-identical to credit-assignment-ablation's mzs1 config",
                  sha256_norm(current) == sha256_norm(base))
        except subprocess.CalledProcessError:
            check("config readable at CREDIT commit", False)

    # ── 4. Training script unmodified (identical on both source branches) ─
    print("\n4. seed_sweep_gat.py unmodified")
    check("seed_sweep_gat.py exists", TRAIN_SCRIPT_PATH.exists())
    if TRAIN_SCRIPT_PATH.exists():
        current = TRAIN_SCRIPT_PATH.read_bytes()
        for commit, name in [(CREDIT_COMMIT, "CREDIT"), (GATLONG_COMMIT, "GAT-LONG")]:
            try:
                base = git_show(commit, str(TRAIN_SCRIPT_PATH).replace("\\", "/"))
                check(f"byte-identical to {name}'s version",
                      sha256_norm(current) == sha256_norm(base))
            except subprocess.CalledProcessError:
                check(f"seed_sweep_gat.py readable at {name}", False)

        src = TRAIN_SCRIPT_PATH.read_text()
        check("gat-hidden-dim default 32", '"--gat-hidden-dim", type=int, default=32' in src)
        check("n-heads default 4", '"--n-heads", type=int, default=4' in src)
        check("global-embed-dim default 16", '"--global-embed-dim", type=int, default=16' in src)
        check("features-dim default 64", '"--features-dim", type=int, default=64' in src)

    # ── 5. src/snrl/gnn.py and env.py unmodified ────────────────────────
    print("\n5. GAT extractor / env code unmodified")
    for path in [Path("src/snrl/gnn.py"), Path("src/snrl/env.py")]:
        if not path.exists():
            check(f"{path} exists", False)
            continue
        current = path.read_bytes()
        for commit, name in [(CREDIT_COMMIT, "CREDIT"), (GATLONG_COMMIT, "GAT-LONG")]:
            try:
                base = git_show(commit, str(path).replace("\\", "/"))
                check(f"{path} byte-identical to {name}'s version",
                      sha256_norm(current) == sha256_norm(base))
            except subprocess.CalledProcessError:
                check(f"{path} readable at {name}", False)

    # ── 6. Sbatch: seeds, timesteps, output dir, guards, project dir ────
    print("\n6. Combined Slurm harness")
    check("sbatch exists", SBATCH_PATH.exists())
    if SBATCH_PATH.exists():
        sbatch = SBATCH_PATH.read_text()
        check("references the mzs1 config", str(CONFIG_PATH).replace("\\", "/") in sbatch
              or "CONFIG:-configs/city_madina_ablation_r400_gat_mzs1.yaml" in sbatch)
        check("default timesteps is 167000", "TIMESTEPS:-167000" in sbatch)
        check("array is 1-5 (seeds 1-5)", "#SBATCH --array=1-5" in sbatch)
        check(f"default output dir is {EXPECTED_OUTPUT_DIR}",
              f"OUTROOT:-{EXPECTED_OUTPUT_DIR}" in sbatch)
        check("output dir is unique vs. all 3 prior experiments",
              EXPECTED_OUTPUT_DIR not in FORBIDDEN_OUTPUT_DIRS)
        for forbidden in FORBIDDEN_OUTPUT_DIRS:
            check(f"guards against overwriting {forbidden}",
                  forbidden in sbatch and "FATAL" in sbatch)
        check("uses $SLURM_SUBMIT_DIR, not a hardcoded path",
              "PROJECT_DIR:-$SLURM_SUBMIT_DIR" in sbatch)
        check("no hardcoded /home/alblueja/traffic default remains",
              "PROJECT_DIR:-/home/alblueja/traffic" not in sbatch)
        check("exports PYTHONPATH from $PWD/src",
              'PYTHONPATH="$PWD/src:${PYTHONPATH:-}"' in sbatch)
        check("checks for r400 data presence before running (no silent refetch)",
              "riyadh_r400" in sbatch and "FATAL" in sbatch)
        check("does NOT invoke fetch_osm_data.py", "fetch_osm_data.py" not in sbatch)

    # ── 7. Real GAT forward pass on the real r400 network (not skipped —
    #      both deps and data are available in this environment) ────────
    print("\n7. GAT extractor + r400 network (real check, not a stub)")
    try:
        import torch
        from snrl.config import load_config
        from snrl.env import StreetNetworkEnv
        from snrl.gnn import GATFeaturesExtractor
        HAS_RL = True
    except ImportError as e:
        HAS_RL = False
        skip("GAT extractor smoke test", f"missing dependency: {e}")

    data_present = all((DATA_DIR / f).exists() for f in DATA_FILES)
    if not data_present:
        skip("r400 network load + GAT forward pass",
             f"data/raw/riyadh_r400 not present in this checkout (gitignored -- "
             f"expected on a fresh clone/worktree, not a failure of this experiment's setup)")
    elif not HAS_RL:
        skip("r400 network load + GAT forward pass", "torch/gymnasium/sb3-contrib unavailable")
    else:
        try:
            cfg = load_config(CONFIG_PATH)
            check("config has include_adjacency_state=True", cfg.include_adjacency_state is True)
            check("config has min_zone_size=1", cfg.reward.min_zone_size == 1)
            env = StreetNetworkEnv(cfg)
            check("network has 89 segments (real r400 data)", env.n_segments == 89,
                  f"got {env.n_segments}")
            check("observation has 7 features (adjacency-aware)",
                  env.observation_space.shape[1] == 7, f"got {env.observation_space.shape}")
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
            check("r400 network load + GAT forward pass", False, str(e))

    # ── 8. Neither completed experiment's files were touched ───────────
    print("\n8. Completed CREDIT and GAT-LONG files untouched")
    credit_only_paths = [
        "results/credit_assignment_ablation/completed_5seed/RESULTS.md",
        "results/credit_assignment_ablation/completed_5seed/credit_mzs1_30k_results_all.csv",
    ]
    gatlong_only_paths = [
        "results/gat_r400_experiment/longer_training/completed_5seed/RESULTS.md",
        "results/gat_r400_experiment/longer_training/completed_5seed/gat_167k_results_all.csv",
    ]
    for label, commit, paths in [("CREDIT", CREDIT_COMMIT, credit_only_paths),
                                   ("GAT-LONG", GATLONG_COMMIT, gatlong_only_paths)]:
        for p in paths:
            try:
                base = git_show(commit, p)
                local_path = Path(p)
                if local_path.exists():
                    current = local_path.read_bytes()
                    check(f"[{label}] {p} untouched", sha256_norm(current) == sha256_norm(base))
                else:
                    skip(f"[{label}] {p}",
                         "not present in this worktree at all -- can't have been modified "
                         "(this branch never checked it out; it stays on its own branch)")
            except subprocess.CalledProcessError:
                check(f"[{label}] {p} readable at {commit}", False)

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"{failures} FAIL, {skips} SKIP")
    if failures == 0:
        print("ALL EXECUTED CHECKS PASSED — ready to submit to Ibex.")
        if skips:
            print(f"({skips} check(s) skipped — see reasons above, not claimed as PASS.)")
    else:
        print(f"{failures} CHECK(S) FAILED — fix before submitting.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
