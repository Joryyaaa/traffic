#!/usr/bin/env python3
"""Render Makkah Ibrahim Al Khalil B0/S1/S2/S3 comparison as Folium HTML.

This follows the same interactive-map pattern used by the Abha baseline and
Abha S1 scenario scripts in this repository:
- OpenStreetMap tiles
- FeatureGroup layers
- grey full network
- orange reviewed study corridor
- red dashed scenario closures
- LayerControl, Fullscreen, and MeasureControl

The map is for visual scenario validation before simulation/model runs.
"""
from __future__ import annotations

import json
from pathlib import Path

import folium
from folium import FeatureGroup
from folium.plugins import Fullscreen, MeasureControl
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "makkah_ibrahim_osm"
OUT_PATH = DATA_DIR / "makkah_ibrahim_scenario_comparison_map.html"

MAKKAH_CENTER_LAT = 21.4177
MAKKAH_CENTER_LON = 39.8228

SCENARIOS = [
    (
        "S1 — Ibrahim Al Khalil Partial Closure",
        "S1_partial_closure_targets.geojson",
        True,
    ),
    (
        "S2 — Network-Safe Corridor Restriction",
        "S2_corridor_restriction_targets.geojson",
        False,
    ),
    (
        "S3 Entry — Direction Management",
        "S3_entry_direction_targets.geojson",
        False,
    ),
    (
        "S3 Exit — Direction Management",
        "S3_exit_direction_targets.geojson",
        False,
    ),
]


def read_geojson(name: str) -> gpd.GeoDataFrame:
    path = DATA_DIR / name
    if not path.exists():
        raise SystemExit(f"Missing required file: {path}")
    return gpd.read_file(path).to_crs("EPSG:4326")


def folium_data(gdf: gpd.GeoDataFrame) -> dict:
    """Convert GeoDataFrame to plain JSON-safe GeoJSON for Folium.

    Some OSM attributes are loaded as numpy arrays. Passing the GeoDataFrame
    directly to Folium can therefore fail with 'ndarray is not JSON serializable'.
    GeoPandas' to_json normalizes those values first.
    """
    return json.loads(gdf.to_json())


def add_closure_layer(m: folium.Map, name: str, filename: str, show: bool) -> None:
    targets = read_geojson(filename)
    group = FeatureGroup(name=name, show=show)
    if not targets.empty:
        folium.GeoJson(
            folium_data(targets),
            style_function=lambda _: {
                "color": "#d73027",
                "weight": 6,
                "opacity": 0.95,
                "dashArray": "8,6",
            },
        ).add_to(group)
    group.add_to(m)


def create_comparison_map() -> folium.Map:
    streets = read_geojson("B0_baseline_streets.geojson")
    corridor = read_geojson("intervention_targets.geojson")

    m = folium.Map(
        location=[MAKKAH_CENTER_LAT, MAKKAH_CENTER_LON],
        zoom_start=14,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    base = FeatureGroup(name="B0 — Full Network", show=True)
    folium.GeoJson(
        folium_data(streets),
        style_function=lambda _: {
            "color": "#8c8c8c",
            "weight": 1,
            "opacity": 0.20,
        },
    ).add_to(base)
    base.add_to(m)

    study = FeatureGroup(name="B0 — Reviewed Ibrahim Corridor", show=True)
    folium.GeoJson(
        folium_data(corridor),
        style_function=lambda _: {
            "color": "#ff7f00",
            "weight": 3,
            "opacity": 0.65,
        },
    ).add_to(study)
    study.add_to(m)

    for name, filename, show in SCENARIOS:
        add_closure_layer(m, name, filename, show)

    folium.Marker(
        [MAKKAH_CENTER_LAT, MAKKAH_CENTER_LON],
        tooltip="Makkah Ibrahim Al Khalil study center",
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen().add_to(m)
    MeasureControl(position="topleft").add_to(m)
    return m


def main() -> None:
    comparison_map = create_comparison_map()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    comparison_map.save(OUT_PATH)

    print("=" * 70)
    print("MAKKAH IBRAHIM AL KHALIL — SCENARIO COMPARISON MAP")
    print("=" * 70)
    print("B0 layer: full OSM drive network")
    print("Study layer: reviewed Ibrahim corridor")
    print("Scenario layers: S1, S2, S3 Entry, S3 Exit")
    print("Open:", OUT_PATH)


if __name__ == "__main__":
    main()
