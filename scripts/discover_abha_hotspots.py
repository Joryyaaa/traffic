"""Discover the Abha school and mosque hotspots from OpenStreetMap.

This is deliberately separate from the RL pipeline.  It uses the project's
existing ``fetch_pois.fetch_point_layer`` function for schools, then applies
the two selection rules requested for the hotspot scenarios:

* school area: most schools within 300 metres of one another;
* mosque: largest mapped mosque footprint in the same Abha search area.

The remaining locations are pinned to existing OSM objects or to the existing
Baseline-2 map already in this repository.  No location is selected from an
unlabelled visual guess.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import osmnx as ox

from fetch_pois import METRIC_CRS, fetch_point_layer


ABHA_CENTER = (18.2164282, 42.5043596)
DISCOVERY_RADIUS_M = 6000.0
SCHOOL_CLUSTER_RADIUS_M = 300.0


def _write_geojson(gdf: gpd.GeoDataFrame, path: Path) -> None:
    """Write GeoJSON without requiring GDAL/pyogrio on Windows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(gdf.to_json(drop_id=True), encoding="utf-8")


def _school_hotspot(out_dir: Path) -> dict:
    schools = fetch_point_layer(
        "schools", {"amenity": "school"}, DISCOVERY_RADIUS_M, ABHA_CENTER
    )
    if schools is None or len(schools) < 3:
        raise RuntimeError("OSM returned fewer than three schools for Abha")

    metric = schools.to_crs(METRIC_CRS)
    xy = np.column_stack((metric.geometry.x, metric.geometry.y))
    distances = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)
    counts = (distances <= SCHOOL_CLUSTER_RADIUS_M).sum(axis=1)
    best_count = int(counts.max())
    if best_count < 3:
        raise RuntimeError(
            f"No OSM school cluster has 3+ schools within {SCHOOL_CLUSTER_RADIUS_M:.0f}m"
        )

    # Deterministic tie-break: choose the candidate with the smallest total
    # distance to the schools in its 300m cluster, then its source row index.
    candidate_indices = np.flatnonzero(counts == best_count)
    best_index = min(
        candidate_indices,
        key=lambda idx: (
            float(distances[idx, distances[idx] <= SCHOOL_CLUSTER_RADIUS_M].sum()),
            int(idx),
        ),
    )
    schools = schools.copy()
    schools["schools_within_300m"] = counts.astype(int)
    schools["selected_cluster_center"] = False
    schools.loc[int(best_index), "selected_cluster_center"] = True
    _write_geojson(schools, out_dir / "schools.geojson")

    point = schools.geometry.iloc[int(best_index)]
    return {
        "lat": float(point.y),
        "lon": float(point.x),
        "schools_within_300m": best_count,
        "source": "OpenStreetMap via scripts/fetch_pois.py",
        "selection_rule": "maximum count of mapped schools within 300 m",
    }


def _largest_mosque(out_dir: Path) -> dict:
    raw = ox.features_from_point(
        ABHA_CENTER,
        tags={"amenity": "place_of_worship"},
        dist=DISCOVERY_RADIUS_M,
    ).copy()
    raw = raw[raw.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
    if raw.empty:
        raise RuntimeError("OSM returned no polygon mosque footprints for Abha")

    metric = raw.to_crs(METRIC_CRS)
    raw["footprint_area_m2"] = metric.geometry.area.to_numpy()
    raw = raw[raw["footprint_area_m2"] > 0].copy()
    largest_key = raw["footprint_area_m2"].idxmax()
    largest = raw.loc[largest_key]
    centroid = (
        gpd.GeoSeries([largest.geometry], crs=raw.crs)
        .to_crs(METRIC_CRS)
        .centroid.to_crs("EPSG:4326")
        .iloc[0]
    )

    export = raw.reset_index()
    keep = [
        col
        for col in ("element_type", "osmid", "name", "name:ar", "name:en", "footprint_area_m2", "geometry")
        if col in export.columns
    ]
    _write_geojson(export[keep], out_dir / "mosques.geojson")

    osm_type, osm_id = largest_key
    return {
        "lat": float(centroid.y),
        "lon": float(centroid.x),
        "name": str(largest.get("name") or largest.get("name:en") or "unnamed OSM mosque"),
        "footprint_area_m2": float(largest["footprint_area_m2"]),
        "osm_type": str(osm_type),
        "osm_id": int(osm_id),
        "source": "OpenStreetMap",
        "selection_rule": "largest mapped mosque polygon footprint within 6 km of Abha centre",
    }


def main() -> None:
    out_dir = Path("data/raw/abha_hotspot_pois")
    out_dir.mkdir(parents=True, exist_ok=True)

    selections = {
        "art_street_baseline_location": {
            "lat": 18.21385,
            "lon": 42.49445,
            "source": "data/abha_baseline/abha_event_hotspot_baseline2_scenarios.html",
            "description": "existing Baseline-2 event-zone centre: Art Street + Al-Muftaha",
        },
        "central_market_location": {
            "lat": 18.2147407,
            "lon": 42.4967046,
            "osm_type": "way",
            "osm_id": 358377281,
            "source": "OpenStreetMap",
            "description": "mapped marketplace beside the central Al-Muftaha/Tuesday-market area; OSM name is blank",
        },
        "asir_central_hospital_location": {
            "lat": 18.1995204,
            "lon": 42.5243259,
            "osm_type": "way",
            "osm_id": 962550374,
            "source": "OpenStreetMap",
            "description": "Asir Central Hospital",
            "data_limit": "OSM has no emergency-entrance tag at this hospital; do not claim an exact ER door",
        },
        "school_cluster_location": _school_hotspot(out_dir),
        "king_abdulaziz_grand_mosque_location": _largest_mosque(out_dir),
        "abu_kheyal_park_location": {
            "lat": 18.2009720,
            "lon": 42.4999554,
            "osm_type": "way",
            "osm_id": 1180194802,
            "source": "OpenStreetMap",
            "description": "Abu Kheyal Park",
        },
    }

    payload = {
        "discovery_center_lat_lon": list(ABHA_CENTER),
        "discovery_radius_m": DISCOVERY_RADIUS_M,
        "school_cluster_radius_m": SCHOOL_CLUSTER_RADIUS_M,
        "scenarios": selections,
    }
    (out_dir / "hotspot_selection.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
