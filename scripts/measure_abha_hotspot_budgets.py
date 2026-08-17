"""Measure configured intervention budgets with the repository's exact policy.

This imports StreetNetworkEnv, the current reward, and evaluate.py's
deterministic zone_builder policy.  It does not reimplement any metric.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate import zone_builder_policy  # noqa: E402
from snrl import StreetNetworkEnv, load_config  # noqa: E402


CONFIGS = {
    "art_street_baseline": "configs/city_madina_abha_art_street_baseline.yaml",
    "central_market": "configs/city_madina_abha_central_market.yaml",
    "asir_central_hospital": "configs/city_madina_abha_asir_central_hospital.yaml",
    "king_abdulaziz_grand_mosque": "configs/city_madina_abha_king_abdulaziz_grand_mosque.yaml",
    "abu_kheyal_park": "configs/city_madina_abha_abu_kheyal_park.yaml",
}


def vkt_proxy_km(env: StreetNetworkEnv) -> float:
    return float(np.sum(env._last_sim.segment_flow * env.backend.segment_lengths) / 1000.0)


def snapshot(env: StreetNetworkEnv) -> dict:
    return {
        "mean_access": float(env._prev_stats["mean_access"]),
        "access_gini": float(env._prev_stats["access_gini"]),
        "total_flow": float(env._prev_stats["total_flow"]),
        "mean_trip_distance_m": float(env._prev_stats["mean_trip_distance"]),
        "vkt_proxy_km": vkt_proxy_km(env),
    }


def measure(config_path: str) -> dict:
    cfg = load_config(ROOT / config_path)
    start = time.perf_counter()
    env = StreetNetworkEnv(cfg)
    try:
        obs, _ = env.reset(seed=cfg.seed)
        baseline = snapshot(env)
        total_return = 0.0
        actions: list[int] = []
        if cfg.action.max_closures:
            choose = zone_builder_policy(env)
            while True:
                action = int(choose(env, obs))
                obs, reward, terminated, truncated, _ = env.step(action)
                total_return += float(reward)
                actions.append(action)
                if terminated or truncated:
                    break
        final = snapshot(env)
        return {
            "config": config_path,
            "segments": int(env.n_segments),
            "max_closures": int(cfg.action.max_closures),
            "min_zone_size": int(cfg.reward.min_zone_size),
            "episode_length": int(cfg.action.episode_length),
            "zone_builder_return": total_return,
            "accepted_positive_return": bool(
                total_return > 1e-6 and baseline["mean_access"] > 1e-9
            ),
            "actions": actions,
            "baseline": baseline,
            "final": final,
            "wall_s": time.perf_counter() - start,
        }
    finally:
        env.close()


def main() -> None:
    output = ROOT / "results" / "abha_hotspot_scenarios" / "budget_measurements.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    measurements = {}
    for name, config in CONFIGS.items():
        row = measure(config)
        if row["max_closures"] == 0:
            row["status"] = "baseline_no_intervention"
        elif row["baseline"]["mean_access"] <= 1e-9:
            row["status"] = "blocked_zero_baseline_access"
        elif row["accepted_positive_return"]:
            row["status"] = "accepted_positive_return"
        else:
            row["status"] = "rejected_nonpositive_return"
        measurements[name] = row
        print(
            f"{name}: return={row['zone_builder_return']:.4f} "
            f"access={row['baseline']['mean_access']:.3f}->{row['final']['mean_access']:.3f} "
            f"wall={row['wall_s']:.1f}s",
            flush=True,
        )
    measurements["school_cluster"] = {
        "status": "blocked_missing_residential_origins",
        "config": "configs/city_madina_abha_school_cluster.yaml",
        "zone_builder_return": None,
    }
    payload = {
        "method": "scripts/evaluate.py zone_builder, one deterministic episode, current reward unchanged",
        "acceptance_rule": "positive total return (>1e-6) on a data-valid network with positive baseline accessibility; accessibility change is reported separately and is not hidden",
        "measurements": measurements,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"saved {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
