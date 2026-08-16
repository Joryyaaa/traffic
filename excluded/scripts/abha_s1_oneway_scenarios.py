"""Build S1A/S1B one-way candidate scenarios for King Abdulaziz Road in Abha.

This script intentionally keeps S0 untouched. It reuses the Abha baseline pipeline,
then creates two opposite candidate one-way interventions and saves a comparison map
and scenario summaries for visual validation before traffic simulation.
"""

from __future__ import annotations

import math
from pathlib import Path

import folium
from folium import FeatureGroup
from folium.plugins import Fullscreen, MeasureControl
import numpy as np
import pandas as pd

from abha_network_baseline import (
    ABHA_CENTER_LAT,
    ABHA_CENTER_LON,
    build_ring_corridor,
    clean_ring_corridor,
    create_baseline,
    download_abha_osm,
    extract_main_roads,
)

TARGET_ROAD = "King Abdulaziz Road"
OUT_DIR = Path("data/abha_baseline")

S1_DIRECTIONS = {
    "S1A": {"name": "King Abdulaziz One-Way — NE", "target_bearing": 45.0},
    "S1B": {"name": "King Abdulaziz One-Way — SW", "target_bearing": 225.0},
}


def unwrap_primary(value):
    """Return the primary GeoDataFrame when a baseline helper returns a tuple."""
    return value[0] if isinstance(value, tuple) else value


def calculate_segment_bearing(geometry):
    if geometry is None or geometry.is_empty:
        return np.nan
    if geometry.geom_type == "MultiLineString":
        geometry = max(geometry.geoms, key=lambda geom: geom.length)
    coords = list(geometry.coords)
    if len(coords) < 2:
        return np.nan
    lon1, lat1 = coords[0]
    lon2, lat2 = coords[-1]
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    x = math.sin(delta_lon) * math.cos(lat2_rad)
    y = (
        math.cos(lat1_rad) * math.sin(lat2_rad)
        - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    )
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def angular_difference(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def create_one_way_scenario(baseline_network, main_roads, scenario_id, scenario_name, target_bearing):
    network = baseline_network.copy()
    network["scenario"] = scenario_name
    network["scenario_id"] = scenario_id
    network["target_road"] = False
    network["target_direction"] = False

    target_ids = set(
        main_roads.loc[
            main_roads["display_name"] == TARGET_ROAD,
            "road_segment_id",
        ]
    )
    if not target_ids:
        raise RuntimeError("King Abdulaziz Road was not found.")

    target_mask = network["road_segment_id"].isin(target_ids)
    network.loc[target_mask, "target_road"] = True
    network["segment_bearing"] = network.geometry.apply(calculate_segment_bearing)
    network["bearing_difference"] = network["segment_bearing"].apply(
        lambda x: angular_difference(x, target_bearing) if pd.notna(x) else np.nan
    )

    preferred = target_mask & (network["bearing_difference"] <= 90.0)
    opposite = target_mask & ~preferred

    network.loc[preferred, "target_direction"] = True
    network.loc[target_mask, "intervention"] = "King Abdulaziz one-way candidate"
    network.loc[target_mask, "direction_modified"] = True
    network.loc[preferred, "road_open"] = True
    network.loc[opposite, "road_open"] = False

    target = network.loc[target_mask]
    opened = target[target["road_open"]]
    closed = target[~target["road_open"]]

    summary = pd.DataFrame({
        "metric": [
            "Scenario ID", "Scenario Name", "Target Road", "Target Bearing",
            "Target Road Segments", "Open Target Segments", "Closed Target Segments",
            "Open Target Length (km)", "Closed Target Length (km)"
        ],
        "value": [
            scenario_id, scenario_name, TARGET_ROAD, target_bearing,
            len(target), len(opened), len(closed),
            round(opened["length"].sum() / 1000, 2),
            round(closed["length"].sum() / 1000, 2),
        ],
    })
    return network, summary


def add_scenario_layer(m, network, scenario_id, show):
    target = network[network["target_road"]].to_crs("EPSG:4326")
    group = FeatureGroup(name=f"{scenario_id} — one-way candidate", show=show)
    opened = target[target["road_open"]]
    closed = target[~target["road_open"]]

    if not opened.empty:
        folium.GeoJson(
            opened,
            style_function=lambda _: {"color": "#1a9850", "weight": 6, "opacity": 0.95},
        ).add_to(group)

    if not closed.empty:
        folium.GeoJson(
            closed,
            style_function=lambda _: {
                "color": "#d73027", "weight": 6, "opacity": 0.95, "dashArray": "8,6"
            },
        ).add_to(group)

    group.add_to(m)


def create_comparison_map(streets, corridor, s1a, s1b):
    m = folium.Map(
        location=[ABHA_CENTER_LAT, ABHA_CENTER_LON],
        zoom_start=14,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    base = FeatureGroup(name="S0 — Full Network", show=True)
    folium.GeoJson(
        streets.to_crs("EPSG:4326"),
        style_function=lambda _: {"color": "#8c8c8c", "weight": 1, "opacity": 0.2},
    ).add_to(base)
    base.add_to(m)

    study = FeatureGroup(name="S0 — Cleaned Study Corridor", show=True)
    folium.GeoJson(
        corridor.to_crs("EPSG:4326"),
        style_function=lambda _: {"color": "#ff7f00", "weight": 3, "opacity": 0.6},
    ).add_to(study)
    study.add_to(m)

    add_scenario_layer(m, s1a, "S1A", True)
    add_scenario_layer(m, s1b, "S1B", False)

    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen().add_to(m)
    MeasureControl(position="topleft").add_to(m)
    return m


def main():
    print("=" * 70)
    print("ABHA S1 ONE-WAY CANDIDATE SCENARIOS")
    print("=" * 70)

    _, streets, origins, destinations = download_abha_osm()
    main_roads = extract_main_roads(streets)

    ring_result = build_ring_corridor(streets, main_roads)
    ring = unwrap_primary(ring_result)

    clean_result = clean_ring_corridor(ring)
    corridor = unwrap_primary(clean_result)

    baseline_result = create_baseline(streets, corridor, origins, destinations)
    baseline_network = baseline_result[0] if isinstance(baseline_result, tuple) else baseline_result

    s1a, s1a_summary = create_one_way_scenario(
        baseline_network,
        main_roads,
        "S1A",
        S1_DIRECTIONS["S1A"]["name"],
        S1_DIRECTIONS["S1A"]["target_bearing"],
    )
    s1b, s1b_summary = create_one_way_scenario(
        baseline_network,
        main_roads,
        "S1B",
        S1_DIRECTIONS["S1B"]["name"],
        S1_DIRECTIONS["S1B"]["target_bearing"],
    )

    comparison_map = create_comparison_map(streets, corridor, s1a, s1b)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    s1a_summary.to_csv(OUT_DIR / "s1a_oneway_summary.csv", index=False)
    s1b_summary.to_csv(OUT_DIR / "s1b_oneway_summary.csv", index=False)
    s1a[s1a["target_road"]].to_crs("EPSG:4326").to_file(
        OUT_DIR / "s1a_king_abdulaziz.geojson", driver="GeoJSON"
    )
    s1b[s1b["target_road"]].to_crs("EPSG:4326").to_file(
        OUT_DIR / "s1b_king_abdulaziz.geojson", driver="GeoJSON"
    )
    comparison_map.save(OUT_DIR / "abha_s1_oneway_comparison_map.html")

    print("\nS1A SUMMARY")
    print(s1a_summary.to_string(index=False))
    print("\nS1B SUMMARY")
    print(s1b_summary.to_string(index=False))
    print("\nDone. Outputs saved to:", OUT_DIR)
    print("Open: data/abha_baseline/abha_s1_oneway_comparison_map.html")


if __name__ == "__main__":
    main()
