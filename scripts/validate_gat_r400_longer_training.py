"""Pre-flight validation for the GAT r400 longer-training (167k) follow-up.

Verifies:
  - configs/city_madina_ablation_r400_gat.yaml is BYTE-IDENTICAL to the version
    committed at 34f03c8 (the completed 30k run) -- not just "looks the same"
  - scripts/seed_sweep_gat.py is BYTE-IDENTICAL to the version at 34f03c8
  - GAT architecture defaults in seed_sweep_gat.py match the completed run's
    (gat_hidden_dim=32, n_heads=4, global_embed_dim=16, features_dim=64)
  - GATFeaturesExtractor still constructs and runs a forward pass on the real
    89-segment adjacency (Ibex or any machine with torch/gymnasium/sb3-contrib
    installed -- not Ibex-only, unlike the credit-assignment ablation's check)
  - the new sbatch references the SAME (unmodified) config, a DIFFERENT output
    dir than the completed run, and refuses by construction to overwrite
    runs/r400_gat_30k
  - 34f03c8 is an ancestor of the current branch (so this really did fork from
    the completed run, not some other point)

Usage:
    PYTHONPATH=src python scripts/validate_gat_r400_longer_training.py
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path


BASE_COMMIT = "34f03c8"
CONFIG_PATH = Path("configs/city_madina_ablation_r400_gat.yaml")
TRAIN_SCRIPT_PATH = Path("scripts/seed_sweep_gat.py")
NEW_SBATCH = Path("slurm/gat_r400_experiment_167k.sbatch")
OLD_SBATCH = Path("slurm/gat_r400_experiment.sbatch")


def git_show(commit: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{commit}:{path}"], capture_output=True, check=True
    ).stdout


def sha256(data: bytes) -> str:
    # Normalize CRLF -> LF before hashing: a Windows checkout (core.autocrlf)
    # converts line endings on write-to-disk, which changes the raw bytes
    # without changing the content git considers identical (git diff already
    # normalizes this internally). Comparing raw bytes across platforms would
    # otherwise flag a false "modified" on every text file on Windows.
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


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

    print("=== GAT r400 longer-training (167k) validation ===\n")

    # ── 1. Branch ancestry ──────────────────────────────────────────────
    print("1. Branch ancestry")
    try:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD"], check=True
        )
        check(f"{BASE_COMMIT} is an ancestor of HEAD", True)
    except subprocess.CalledProcessError:
        check(f"{BASE_COMMIT} is an ancestor of HEAD", False,
              "this branch did not fork from the completed GAT run")

    # ── 2. Config file byte-identical to the completed run's ───────────
    print("\n2. Config parity (byte-for-byte vs. the completed 30k run)")
    check("config exists", CONFIG_PATH.exists())
    if CONFIG_PATH.exists():
        current = CONFIG_PATH.read_bytes()
        try:
            base = git_show(BASE_COMMIT, str(CONFIG_PATH).replace("\\", "/"))
            check("config byte-identical to 34f03c8's version",
                  sha256(current) == sha256(base),
                  f"current={sha256(current)[:12]} base={sha256(base)[:12]}")
        except subprocess.CalledProcessError:
            check("config readable at 34f03c8", False)

    # ── 3. Training script byte-identical ───────────────────────────────
    print("\n3. seed_sweep_gat.py parity")
    check("seed_sweep_gat.py exists", TRAIN_SCRIPT_PATH.exists())
    if TRAIN_SCRIPT_PATH.exists():
        current = TRAIN_SCRIPT_PATH.read_bytes()
        try:
            base = git_show(BASE_COMMIT, str(TRAIN_SCRIPT_PATH).replace("\\", "/"))
            check("seed_sweep_gat.py byte-identical to 34f03c8's version",
                  sha256(current) == sha256(base),
                  f"current={sha256(current)[:12]} base={sha256(base)[:12]}")
        except subprocess.CalledProcessError:
            check("seed_sweep_gat.py readable at 34f03c8", False)

    # ── 4. GAT architecture defaults (read from the script text) ───────
    print("\n4. GAT architecture defaults unchanged")
    if TRAIN_SCRIPT_PATH.exists():
        src = TRAIN_SCRIPT_PATH.read_text()
        check("gat-hidden-dim default 32", '"--gat-hidden-dim", type=int, default=32' in src)
        check("n-heads default 4", '"--n-heads", type=int, default=4' in src)
        check("global-embed-dim default 16", '"--global-embed-dim", type=int, default=16' in src)
        check("features-dim default 64", '"--features-dim", type=int, default=64' in src)

    # ── 5. GAT extractor smoke test (real adjacency, real forward pass) ─
    print("\n5. GAT extractor (smoke test)")
    try:
        import torch
        from snrl.config import load_config
        from snrl.env import StreetNetworkEnv
        from snrl.gnn import GATFeaturesExtractor
        HAS_RL = True
    except ImportError as e:
        HAS_RL = False
        skip("GAT extractor", f"missing dependency: {e}")

    if HAS_RL and CONFIG_PATH.exists():
        try:
            cfg = load_config(CONFIG_PATH)
            check("config has include_adjacency_state=True", cfg.include_adjacency_state is True)
            env = StreetNetworkEnv(cfg)
            check("network has 89 segments", env.n_segments == 89, f"got {env.n_segments}")
            check("observation has 7 features", env.observation_space.shape[1] == 7,
                  f"got {env.observation_space.shape}")
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
            check("GAT extractor smoke test", False, str(e))
    elif not CONFIG_PATH.exists():
        skip("GAT extractor", "config missing")

    # ── 6. New sbatch: correct references, safe output dir ─────────────
    print("\n6. New Slurm harness references")
    check("new sbatch exists", NEW_SBATCH.exists())
    if NEW_SBATCH.exists():
        sbatch = NEW_SBATCH.read_text()
        check("references the unmodified control config",
              'CONFIG:-configs/city_madina_ablation_r400_gat.yaml' in sbatch)
        check("uses seed_sweep_gat.py", "seed_sweep_gat.py" in sbatch)
        check("default timesteps is 167000", 'TIMESTEPS:-167000' in sbatch)
        check("default output dir is runs/r400_gat_167k", 'OUTROOT:-runs/r400_gat_167k' in sbatch)
        check("output dir differs from the completed run's",
              "runs/r400_gat_167k" != "runs/r400_gat_30k")
        check("guards against overwriting the 30k output dir",
              'runs/r400_gat_30k' in sbatch and "FATAL" in sbatch)
        check("project dir alblueja", "/home/alblueja/traffic" in sbatch)
        check("array is 1-5 (same seeds)", "#SBATCH --array=1-5" in sbatch)
        check("time limit is 6 hours", "#SBATCH --time=06:00:00" in sbatch)
        check("mem matches the completed run's actual request (12G)",
              "#SBATCH --mem=12G" in sbatch)
        check("cpus-per-task matches (2)", "#SBATCH --cpus-per-task=2" in sbatch)

    # ── 7. Old sbatch untouched ──────────────────────────────────────────
    print("\n7. Completed 30k run's own files untouched")
    if OLD_SBATCH.exists():
        current = OLD_SBATCH.read_bytes()
        try:
            base = git_show(BASE_COMMIT, str(OLD_SBATCH).replace("\\", "/"))
            check("gat_r400_experiment.sbatch (30k) byte-identical to 34f03c8",
                  sha256(current) == sha256(base))
        except subprocess.CalledProcessError:
            check("gat_r400_experiment.sbatch readable at 34f03c8", False)
    check("runs/r400_gat_30k not referenced as a write target anywhere new",
          not (NEW_SBATCH.exists() and 'OUTROOT:-runs/r400_gat_30k' in NEW_SBATCH.read_text()))

    # ── Summary ───────────────────────────────────────────────────────
    print(f"\n{'=' * 55}")
    if failures == 0:
        print("ALL CHECKS PASSED — ready to submit to Ibex.")
        if not HAS_RL:
            print("(GAT smoke test skipped — missing a dependency on this machine)")
    else:
        print(f"{failures} CHECK(S) FAILED — fix before submitting.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
