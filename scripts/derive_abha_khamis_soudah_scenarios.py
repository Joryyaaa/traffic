"""Derive combined and peak Abha corridor cases without extra Madina runs.

Madina's static assignment is linear in origin demand because this setup has
no capacity-dependent congestion or queue feedback. Therefore the two
single-origin simulations can be added exactly, and uniform 1.5x/2.0 demand
cases are exact scalar multiples. This reduces six Ibex simulations to three:
the separate city context plus one run for each Khamis approach.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


SOURCE_CASES = ("route10_reference", "route2120_reference")
DERIVED_CASES = {
    "khamis_viewpoint_baseline": (
        1.0,
        "configs/city_madina_abha_khamis_soudah_combined_reference.yaml",
    ),
    "combined_peak_1_5": (
        1.5,
        "configs/city_madina_abha_khamis_soudah_combined_peak_1_5.yaml",
    ),
    "combined_peak_2_0": (
        2.0,
        "configs/city_madina_abha_khamis_soudah_combined_peak_2_0.yaml",
    ),
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"Refusing to write empty CSV: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def gini(values: np.ndarray) -> float:
    values = np.clip(np.asarray(values, dtype=float), 0.0, None)
    if values.size == 0 or values.sum() == 0:
        return 0.0
    ordered = np.sort(values)
    indexes = np.arange(1, ordered.size + 1)
    return float(
        (2.0 * (indexes * ordered).sum()) / (ordered.size * ordered.sum())
        - (ordered.size + 1.0) / ordered.size
    )


def normalized_entropy(values: np.ndarray) -> float:
    values = np.clip(np.asarray(values, dtype=float), 0.0, None)
    total = values.sum()
    if total <= 0 or values.size <= 1:
        return 0.0
    probabilities = values[values > 0] / total
    return float(
        -(probabilities * np.log(probabilities)).sum() / np.log(values.size)
    )


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root

    source_dirs = [root / name for name in SOURCE_CASES]
    for directory in source_dirs:
        for filename in (
            "metrics.json",
            "segment_flows.csv",
            "segment_flows.geojson",
            "origin_accessibility.csv",
        ):
            if not (directory / filename).exists():
                raise FileNotFoundError(directory / filename)

    source_metrics = [read_json(path / "metrics.json") for path in source_dirs]
    source_segments = [read_csv(path / "segment_flows.csv") for path in source_dirs]
    source_geojson = [read_json(path / "segment_flows.geojson") for path in source_dirs]
    source_origins = [read_csv(path / "origin_accessibility.csv") for path in source_dirs]

    if len(source_segments[0]) != len(source_segments[1]):
        raise ValueError("Source segment tables do not have the same length")
    segment_ids_a = [row["road_segment_id"] for row in source_segments[0]]
    segment_ids_b = [row["road_segment_id"] for row in source_segments[1]]
    if segment_ids_a != segment_ids_b:
        raise ValueError("Source segment ordering differs")

    # mean_trip_distance below is the plain mean of the two runs' own means.
    # The backend's mean is unweighted over origins, so averaging the averages
    # only reproduces a real combined run while both sources contribute the
    # same number of origins -- today one each. Every other derived metric is
    # exact for any origin count, so an unequal split would leave this single
    # field quietly wrong in an otherwise-correct file. Refuse instead.
    origin_counts = [len(rows) for rows in source_origins]
    if len(set(origin_counts)) != 1:
        raise ValueError(
            "Source runs contribute unequal origin counts "
            f"({dict(zip(SOURCE_CASES, origin_counts))}); mean_trip_distance "
            "cannot be derived by averaging the per-run means. Weight it by "
            "origin count, or run the combined case through Madina directly."
        )

    base_flow = np.asarray(
        [float(a["madina_flow"]) + float(b["madina_flow"])
         for a, b in zip(*source_segments)],
        dtype=float,
    )
    lengths = np.asarray(
        [float(row["length_m"]) for row in source_segments[0]], dtype=float
    )
    protected = np.asarray(
        [truthy(row["protected_local_street"]) for row in source_segments[0]],
        dtype=bool,
    )
    major = np.asarray(
        [truthy(row["major_road"]) for row in source_segments[0]], dtype=bool
    )
    access = np.asarray(
        [
            float(row["accessibility"])
            for rows in source_origins
            for row in rows
        ],
        dtype=float,
    )
    mean_trip_distance = float(
        np.mean([item["mean_trip_distance"] for item in source_metrics])
    )

    for scenario, (multiplier, config) in DERIVED_CASES.items():
        output = root / scenario
        output.mkdir(parents=True, exist_ok=True)
        flow = base_flow * multiplier
        total_flow = float(flow.sum())

        segment_rows: list[dict] = []
        for source, value, length in zip(source_segments[0], flow, lengths):
            row = dict(source)
            row["madina_flow"] = float(value)
            row["flow_distance_km"] = float(value * length / 1000.0)
            segment_rows.append(row)
        write_csv(output / "segment_flows.csv", segment_rows)

        geojson = json.loads(json.dumps(source_geojson[0]))
        for feature, value, length in zip(geojson["features"], flow, lengths):
            feature["properties"]["madina_flow"] = float(value)
            feature["properties"]["flow_distance_km"] = float(
                value * length / 1000.0
            )
        write_json(output / "segment_flows.geojson", geojson)

        origin_rows: list[dict] = []
        origin_results: list[dict] = []
        for rows in source_origins:
            for source in rows:
                row = dict(source)
                row["origin_index"] = len(origin_rows)
                row["demand_weight"] = float(source["demand_weight"]) * multiplier
                origin_rows.append(row)
                origin_results.append(
                    {
                        "origin_index": int(row["origin_index"]),
                        "endpoint_key": row["endpoint_key"],
                        "name": row["name"],
                        "demand_weight": float(row["demand_weight"]),
                        "accessibility": float(row["accessibility"]),
                        "reachable": truthy(row["reachable"]),
                    }
                )
        write_csv(output / "origin_accessibility.csv", origin_rows)

        protected_flow = float(flow[protected].sum())
        major_flow = float(flow[major].sum())
        metrics = {
            **{
                key: source_metrics[0][key]
                for key in (
                    "street_segments",
                    "destinations",
                    "search_radius_m",
                    "detour_ratio",
                    "decay_beta_per_m",
                    "respect_oneway",
                )
            },
            "scenario": scenario,
            "config": config,
            "origins": len(origin_rows),
            "demand_scope": "khamis_to_jabal_soudah_viewpoint",
            "execution_method": "exact_linear_derivation",
            "mean_access": float(access.mean()),
            "access_gini": gini(access),
            "total_flow": total_flow,
            "flow_entropy": normalized_entropy(flow),
            "mean_trip_distance": mean_trip_distance,
            "n_components": max(item["n_components"] for item in source_metrics),
            "unreachable_fraction": float(
                np.mean([not item["reachable"] for item in origin_results])
            ),
            "setup_seconds": 0.0,
            "simulation_seconds": 0.0,
            "source_simulation_seconds": float(
                sum(item["simulation_seconds"] for item in source_metrics)
            ),
            "flow_weighted_vkt_proxy_km": float(
                np.sum(flow * lengths) / 1000.0
            ),
            "protected_local_flow": protected_flow,
            "protected_local_flow_share": (
                protected_flow / total_flow if total_flow else 0.0
            ),
            "major_road_flow": major_flow,
            "major_road_flow_share": major_flow / total_flow if total_flow else 0.0,
            "positive_flow_segments": int(np.count_nonzero(flow > 0)),
            "approved_destination_access_segment_ids": source_metrics[0].get(
                "approved_destination_access_segment_ids", []
            ),
            "protected_local_highway_classes": source_metrics[0].get(
                "protected_local_highway_classes", []
            ),
            "origin_results": origin_results,
            "derived_from": list(SOURCE_CASES),
            "demand_multiplier": multiplier,
            "derived_without_new_madina_run": True,
            "derivation_basis": (
                "Exact linear superposition of static Madina origin flows; "
                "no capacity-dependent congestion or queue feedback is enabled."
            ),
            "interpretation_notes": source_metrics[0].get(
                "interpretation_notes", []
            ),
        }
        write_json(output / "metrics.json", metrics)
        print(f"derived {scenario} ({multiplier:g}x) -> {output}")


if __name__ == "__main__":
    main()
