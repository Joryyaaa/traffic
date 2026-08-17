"""Run one approved Abha Madina scenario and save auditable outputs."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from snrl.backends.madina_backend import MadinaBackend  # noqa: E402
from snrl.config import load_config  # noqa: E402
from snrl.metrics import summarize  # noqa: E402


MAJOR_HIGHWAYS = {"motorway", "trunk", "primary", "secondary"}
PROTECTED_LOCAL_HIGHWAYS = {
    "residential",
    "service",
    "living_street",
    "unclassified",
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve(path: str | None) -> Path:
    if not path:
        raise ValueError("Scenario config is missing a required data path")
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def highway_values(value: object) -> set[str]:
    if isinstance(value, list):
        return {str(item).lower() for item in value}
    return {str(value).lower()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    config_path = resolve(args.config)
    cfg = load_config(config_path)
    paths = {
        "streets": resolve(cfg.network.streets_path),
        "origins": resolve(cfg.network.origins_path),
        "destinations": resolve(cfg.network.destinations_path),
    }
    for label, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {label}: {path}")

    streets_data = read_json(paths["streets"])
    origins_data = read_json(paths["origins"])
    destinations_data = read_json(paths["destinations"])
    demand_scope = (
        "city_accessibility"
        if paths["origins"].parent.name == "abha_full_belt_s0"
        else "khamis_to_jabal_soudah_viewpoint"
    )
    validation = {
        "scenario": args.scenario,
        "config": str(config_path.relative_to(ROOT)).replace("\\", "/"),
        "street_segments": len(streets_data["features"]),
        "origins": len(origins_data["features"]),
        "destinations": len(destinations_data["features"]),
        "search_radius_m": cfg.simulation.search_radius,
        "detour_ratio": cfg.simulation.detour_ratio,
        "decay_beta_per_m": cfg.simulation.beta,
        "respect_oneway": cfg.network.respect_oneway,
        "demand_scope": demand_scope,
        "execution_method": "madina_simulation",
    }
    if args.validate_only:
        print(json.dumps({**validation, "status": "validated"}, indent=2))
        return

    output_dir = resolve(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    backend = MadinaBackend(cfg)
    setup_seconds = time.perf_counter() - started
    started = time.perf_counter()
    simulation = backend.simulate(np.zeros(backend.n_segments, dtype=bool))
    simulation_seconds = time.perf_counter() - started

    metrics = summarize(simulation)
    flow = np.asarray(simulation.segment_flow, dtype=float)
    lengths = np.asarray(backend.segment_lengths, dtype=float)
    total_flow = float(flow.sum())
    protected_ids = {
        int((feature.get("properties") or {}).get("road_segment_id", index))
        for index, feature in enumerate(streets_data["features"])
        if highway_values((feature.get("properties") or {}).get("highway"))
        & PROTECTED_LOCAL_HIGHWAYS
    }
    approved_destination_access_ids = {
        int(value)
        for feature in destinations_data["features"]
        for value in (feature.get("properties") or {}).get(
            "destination_access_segment_ids", []
        )
    }
    protected_ids -= approved_destination_access_ids

    flow_features: list[dict] = []
    protected_flow = 0.0
    major_flow = 0.0
    segment_rows: list[dict] = []
    for index, (feature, segment_flow, length) in enumerate(
        zip(streets_data["features"], flow, lengths)
    ):
        props = dict(feature.get("properties") or {})
        segment_id = int(props.get("road_segment_id", index))
        is_protected = segment_id in protected_ids
        is_major = bool(highway_values(props.get("highway")) & MAJOR_HIGHWAYS)
        protected_flow += float(segment_flow) if is_protected else 0.0
        major_flow += float(segment_flow) if is_major else 0.0
        props.update(
            {
                "madina_flow": float(segment_flow),
                "flow_distance_km": float(segment_flow * length / 1000.0),
                "protected_local_street": is_protected,
                "major_road": is_major,
            }
        )
        flow_features.append(
            {"type": "Feature", "geometry": feature["geometry"], "properties": props}
        )
        segment_rows.append(
            {
                "segment_index": index,
                "road_segment_id": segment_id,
                "name": props.get("name"),
                "highway": props.get("highway"),
                "length_m": float(length),
                "madina_flow": float(segment_flow),
                "flow_distance_km": float(segment_flow * length / 1000.0),
                "protected_local_street": is_protected,
                "major_road": is_major,
            }
        )

    origin_access = np.asarray(simulation.origin_access, dtype=float)
    origin_rows: list[dict] = []
    for index, (feature, access) in enumerate(
        zip(origins_data["features"], origin_access)
    ):
        props = feature.get("properties") or {}
        origin_rows.append(
            {
                "origin_index": index,
                "endpoint_key": props.get("endpoint_key"),
                "name": props.get("name"),
                "demand_weight": props.get("demand_weight"),
                "accessibility": float(access),
                "reachable": bool(access > 0),
            }
        )

    result = {
        **validation,
        **metrics,
        "setup_seconds": setup_seconds,
        "simulation_seconds": simulation_seconds,
        "flow_weighted_vkt_proxy_km": float(np.sum(flow * lengths) / 1000.0),
        "protected_local_flow": protected_flow,
        "protected_local_flow_share": protected_flow / total_flow if total_flow else 0.0,
        "major_road_flow": major_flow,
        "major_road_flow_share": major_flow / total_flow if total_flow else 0.0,
        "positive_flow_segments": int(np.count_nonzero(flow > 0)),
        "approved_destination_access_segment_ids": sorted(
            approved_destination_access_ids
        ),
        "protected_local_highway_classes": sorted(PROTECTED_LOCAL_HIGHWAYS),
        "origin_results": origin_rows,
        "interpretation_notes": [
            "Demand weights are sensitivity units, not observed vehicle counts.",
            "VKT is a flow-weighted network-distance proxy, not observed traffic VKT.",
            "Demand multipliers scale assigned load; this Madina run does not model queues or capacity-dependent congestion.",
            "City accessibility demand and Khamis-Al Soudah corridor demand are intentionally evaluated separately.",
        ],
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output_dir / "segment_flows.geojson").write_text(
        json.dumps(
            {"type": "FeatureCollection", "features": flow_features},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for filename, rows in (
        ("segment_flows.csv", segment_rows),
        ("origin_accessibility.csv", origin_rows),
    ):
        with (output_dir / filename).open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(result, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
