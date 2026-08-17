"""Build the six small Abha drive-network datasets from OpenStreetMap.

The network/demand extraction mirrors ``scripts/fetch_osm_data.py`` exactly:
OSMnx graph/features, reciprocal-edge deduplication with
physical-link deduplication, metric building areas, and the same
``residents``/``floor_area`` proxy columns.  The only deliberate difference is
``network_type='drive'``, required by the Abha hotspot experiment.

Each requested radius is tried first.  A nearby radius is used only when the
deduplicated network is outside the requested 30--100 segment range or demand
is empty.  Every attempted and selected radius is written to QA metadata.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely.geometry import shape

from fetch_osm_data import fetch_amenities, fetch_residential


METRIC_CRS = "EPSG:32638"
ROOT = Path("data/raw/abha_hotspots")
SELECTION_PATH = Path("data/raw/abha_hotspot_pois/hotspot_selection.json")
DEFAULT_SNAPSHOT = Path(
    "../optimized-abha-ibex/data/raw/abha_full_belt_s0"
)
MAJOR_CLASSES = {"motorway", "trunk", "primary", "secondary"}

SCENARIOS = {
    "art_street_baseline": {"selection": "art_street_baseline_location", "requested_radius_m": 300, "target_count": 0},
    "central_market": {"selection": "central_market_location", "requested_radius_m": 300, "target_count": 4},
    "asir_central_hospital": {"selection": "asir_central_hospital_location", "requested_radius_m": 250, "target_count": 3},
    "school_cluster": {"selection": "school_cluster_location", "requested_radius_m": 300, "target_count": 4},
    "king_abdulaziz_grand_mosque": {"selection": "king_abdulaziz_grand_mosque_location", "requested_radius_m": 250, "target_count": 2},
    # The first non-empty crop (350 m) contains one origin and one destination,
    # but Madina preflight gives zero reachable trips. Require the next crop
    # with at least two of each; this is a data-validity guard, not synthetic
    # demand. The requested study radius remains 300 m and every attempt is
    # preserved in qa.json.
    "abu_kheyal_park": {
        "selection": "abu_kheyal_park_location",
        "requested_radius_m": 300,
        "target_count": 4,
        "min_origins": 2,
        "min_destinations": 2,
    },
}


def _plain(value):
    if isinstance(value, (list, tuple, set)):
        return ";".join(str(item) for item in value)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value)


def _write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(gdf.to_json(drop_id=True), encoding="utf-8")


def _read_geojson(path: Path) -> gpd.GeoDataFrame:
    data = json.loads(path.read_text(encoding="utf-8"))
    properties = pd.DataFrame([feature.get("properties") or {} for feature in data["features"]])
    geometries = [shape(feature["geometry"]) for feature in data["features"]]
    return gpd.GeoDataFrame(properties, geometry=geometries, crs="EPSG:4326")


def _load_snapshot(root: Path) -> dict[str, gpd.GeoDataFrame]:
    required = ("streets.geojson", "residential.geojson", "amenities.geojson")
    missing = [name for name in required if not (root / name).exists()]
    if missing:
        raise FileNotFoundError(f"OSM snapshot missing {missing} under {root}")
    return {
        "streets": _read_geojson(root / "streets.geojson"),
        "residential": _read_geojson(root / "residential.geojson"),
        "amenities": _read_geojson(root / "amenities.geojson"),
    }


def _radius_candidates(requested: int) -> list[int]:
    values = [requested]
    for delta in (25, 50, 75, 100, 125, 150, 175, 200):
        values.extend([requested + delta, requested - delta])
    return [value for value in values if 150 <= value <= 500]


def _fetch_drive(radius_m: float, center: tuple[float, float]):
    graph = ox.graph_from_point(
        center, dist=radius_m, network_type="drive", simplify=True
    )
    graph = ox.convert.to_undirected(graph)
    _, edges = ox.graph_to_gdfs(graph)
    edges = edges.reset_index()
    metadata = gpd.GeoDataFrame(
        {
            "segment_id": np.arange(len(edges), dtype=int),
            "u": edges["u"].astype(str),
            "v": edges["v"].astype(str),
            "key": edges["key"].astype(str),
            "osmid": edges["osmid"].apply(_plain) if "osmid" in edges else "",
            "name": edges["name"].apply(_plain) if "name" in edges else "",
            "highway": edges["highway"].apply(_plain) if "highway" in edges else "",
            "length": edges["length"].astype(float),
            "geometry": edges.geometry,
        },
        crs=edges.crs,
    )
    streets = metadata.copy()
    return streets, metadata


def _snapshot_crop(
    snapshot: dict[str, gpd.GeoDataFrame],
    radius_m: float,
    center: tuple[float, float],
):
    point = gpd.GeoSeries.from_xy([center[1]], [center[0]], crs="EPSG:4326").to_crs(METRIC_CRS).iloc[0]
    area = point.buffer(radius_m)

    raw = snapshot["streets"].to_crs(METRIC_CRS)
    raw = raw[raw.geometry.intersects(area)].copy()
    if raw.empty:
        return raw.to_crs("EPSG:4326"), raw.to_crs("EPSG:4326"), raw, raw

    # Match fetch_osm_data.py's reciprocal-edge deduplication for the drive
    # snapshot. A reciprocal OSM pair has the same osmid and unordered u/v.
    raw["_physical_key"] = raw.apply(
        lambda row: (
            str(row.get("osmid", "")),
            min(str(row.get("u", "")), str(row.get("v", ""))),
            max(str(row.get("u", "")), str(row.get("v", ""))),
        ),
        axis=1,
    )
    raw = raw.drop_duplicates("_physical_key", keep="first").copy()

    graph = nx.Graph()
    for _, row in raw.iterrows():
        graph.add_edge(str(row["u"]), str(row["v"]))
    if graph.number_of_nodes():
        largest_nodes = max(nx.connected_components(graph), key=len)
        raw = raw[
            raw["u"].astype(str).isin(largest_nodes)
            & raw["v"].astype(str).isin(largest_nodes)
        ].copy()
    raw = raw.drop(columns=["_physical_key"]).reset_index(drop=True)
    raw["segment_id"] = np.arange(len(raw), dtype=int)
    metadata = raw.to_crs("EPSG:4326")
    # Preserve u/v/oneway so the mentor's directed Madina path can enforce the
    # drive network's legal directions.  Earlier preview-only files kept just
    # geometry and therefore could not use respect_oneway.
    streets = metadata.copy()

    residential = snapshot["residential"].to_crs(METRIC_CRS)
    residential = residential[residential.geometry.intersects(area)].copy().to_crs("EPSG:4326")
    amenities = snapshot["amenities"].to_crs(METRIC_CRS)
    amenities = amenities[amenities.geometry.intersects(area)].copy().to_crs("EPSG:4326")
    return streets, metadata, residential, amenities


def _is_major(highway: str) -> bool:
    return bool(set(str(highway).split(";")) & MAJOR_CLASSES)


def _target_segments(
    scenario: str,
    metadata: gpd.GeoDataFrame,
    center: tuple[float, float],
    count: int,
) -> gpd.GeoDataFrame:
    if count == 0:
        return metadata.iloc[0:0].copy()

    metric = metadata.to_crs(METRIC_CRS).copy()
    point = gpd.GeoSeries.from_xy([center[1]], [center[0]], crs="EPSG:4326").to_crs(METRIC_CRS).iloc[0]
    metric["distance_to_poi_m"] = metric.geometry.distance(point)

    # The intervention definitions all call for internal/side streets.  Keep
    # major through roads open; for the hospital this is especially important
    # because OSM does not identify the emergency entrance itself.
    candidates = metric[~metric["highway"].map(_is_major)].copy()
    if len(candidates) < count:
        raise RuntimeError(f"{scenario}: only {len(candidates)} non-major target candidates")
    chosen = candidates.sort_values(["distance_to_poi_m", "segment_id"]).head(count)
    return chosen.to_crs("EPSG:4326")


def build_one(
    scenario: str,
    spec: dict,
    selections: dict,
    snapshot: dict,
    allow_geometry_only: bool = False,
) -> dict:
    selected = selections[spec["selection"]]
    center = (float(selected["lat"]), float(selected["lon"]))
    min_origins = int(spec.get("min_origins", 1))
    min_destinations = int(spec.get("min_destinations", 1))
    attempts = []
    chosen = None
    geometry_candidate = None

    for radius in _radius_candidates(int(spec["requested_radius_m"])):
        streets, metadata, residential, amenities = _snapshot_crop(snapshot, radius, center)
        attempt = {
            "radius_m": radius,
            "street_segments": len(streets),
            "residential_origins": len(residential),
            "amenity_destinations": len(amenities),
        }
        if (
            30 <= len(streets) <= 100
            and len(residential) >= min_origins
            and len(amenities) >= min_destinations
        ):
            chosen = (radius, streets, metadata, residential, amenities)
            attempts.append(attempt)
            break
        if 30 <= len(streets) <= 100 and geometry_candidate is None:
            geometry_candidate = (radius, streets, metadata, residential, amenities)
        attempts.append(attempt)
    if chosen is None:
        if allow_geometry_only and geometry_candidate is not None:
            chosen = geometry_candidate
        else:
            raise RuntimeError(
                f"{scenario}: no radius produced 30--100 segments with non-empty demand: {attempts}"
            )

    radius, streets, metadata, residential, amenities = chosen

    targets = _target_segments(
        scenario, metadata, center, int(spec["target_count"])
    )
    out_dir = ROOT / scenario
    _write_geojson(metadata, out_dir / "streets.geojson")
    _write_geojson(residential, out_dir / "residential.geojson")
    _write_geojson(amenities, out_dir / "amenities.geojson")
    _write_geojson(metadata, out_dir / "road_metadata.geojson")
    _write_geojson(targets, out_dir / "intervention_targets.geojson")

    qa = {
        "scenario": scenario,
        "selection_key": spec["selection"],
        "center_lat": center[0],
        "center_lon": center[1],
        "requested_radius_m": spec["requested_radius_m"],
        "selected_radius_m": radius,
        "radius_attempts": attempts,
        "network_type": "drive",
        "osm_snapshot": "origin/optimized-abha-jabal-soudah-ibex (mentor-run full-belt snapshot)",
        "deduplication": "reciprocal OSM rows collapsed by osmid + unordered u/v, matching fetch_osm_data.py",
        "street_segments": len(streets),
        "residential_origins": len(residential),
        "amenity_destinations": len(amenities),
        "minimum_demand_counts": {
            "origins": min_origins,
            "destinations": min_destinations,
        },
        "runnable": bool(len(residential) and len(amenities)),
        "intervention_target_segments": targets["segment_id"].astype(int).tolist(),
        "target_selection_rule": "nearest non-major OSM drive segments to POI; major through roads remain open",
        "source": selected,
    }
    (out_dir / "qa.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(qa, ensure_ascii=False), flush=True)
    return qa


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenarios",
        default=",".join(SCENARIOS),
        help="Comma-separated subset of: " + ",".join(SCENARIOS),
    )
    parser.add_argument(
        "--allow-geometry-only",
        action="store_true",
        help="Write a non-runnable geometry package when OSM demand is empty",
    )
    parser.add_argument(
        "--source-snapshot",
        type=Path,
        default=DEFAULT_SNAPSHOT,
        help="Folder containing the committed full-belt OSM streets/residential/amenities snapshot",
    )
    args = parser.parse_args()
    selection_data = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    selections = selection_data["scenarios"]
    requested = [item.strip() for item in args.scenarios.split(",") if item.strip()]
    snapshot = _load_snapshot(args.source_snapshot.resolve())

    ROOT.mkdir(parents=True, exist_ok=True)
    summary = []
    for scenario in requested:
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
        summary.append(
            build_one(
                scenario,
                SCENARIOS[scenario],
                selections,
                snapshot,
                allow_geometry_only=args.allow_geometry_only,
            )
        )
    (ROOT / "build_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
