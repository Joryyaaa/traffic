#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from snrl.config import load_config
from snrl.backends.madina_backend import MadinaBackend

RESULTS = ROOT / "results/neom_scenarios/sharma_camp26_r5km/madina"

CONFIG_MAP = {
    "B0": ["configs/neom_scenarios/city_madina_neom_b0.yaml"],
    "S1": ["configs/neom_scenarios/city_madina_neom_s1.yaml"],
    "S2": ["configs/neom_scenarios/city_madina_neom_s2.yaml"],
    "S3": [
        "configs/neom_scenarios/city_madina_neom_s3_entry.yaml",
        "configs/neom_scenarios/city_madina_neom_s3_exit.yaml",
    ],
}

SCENARIO_NAMES = {
    "B0": "B0_Baseline",
    "S1": "S1_Vehicle_Restriction",
    "S2": "S2_Parking_Hub",
    "S3": "S3_Managed_Entry_Exit",
}


def one(config_rel):
    cfg = load_config(ROOT / config_rel)

    if cfg.network.backend != "madina":
        raise RuntimeError(f"{config_rel} is not configured for Madina")

    backend = MadinaBackend(cfg)

    mask = np.zeros(backend.n_segments, dtype=bool)

    t0 = time.perf_counter()
    result = backend.simulate(mask)
    runtime = time.perf_counter() - t0

    return {
        "backend": "madina",
        "config": config_rel,
        "runtime_seconds": runtime,
        "n_segments": int(backend.n_segments),
        "mean_accessibility": (
            float(np.mean(result.origin_access))
            if len(result.origin_access)
            else 0.0
        ),
        "mean_trip_distance": float(result.mean_trip_distance),
        "unreachable_fraction": float(result.unreachable_fraction),
        "n_components": int(result.n_components),
        "total_segment_flow": float(np.sum(result.segment_flow)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=CONFIG_MAP, required=True)
    args = ap.parse_args()

    import madina

    print("Madina:", madina.__file__)

    RESULTS.mkdir(parents=True, exist_ok=True)

    runs = [one(x) for x in CONFIG_MAP[args.scenario]]

    payload = {
        "scenario": args.scenario,
        "scenario_name": SCENARIO_NAMES[args.scenario],
        "backend": "madina",
        "runs": runs,
    }

    if args.scenario == "S3":
        payload["note"] = (
            "S3 is represented as separate inbound and outbound assignments "
            "because the current Madina backend is undirected."
        )

    output = RESULTS / f"{SCENARIO_NAMES[args.scenario]}.json"
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
