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

# Two opposite candidate directions. These are hypotheses only: the model does not
# assume which direction is better. Simulation/official traffic data should decide.
S1_DIRECTIONS = {
    "S1A": {
        "name": "King Abdulaziz One-Way — NE",
        "target_bearing": 45.0,
    },
    "S1B": {
        "name": "King Abdulaziz One-Way — SW",
        "target_bearing": 225.0,
    },
}


def calculate_segment_bearing(geometry) -> float:
    """Estimate travel bearing from the first to the last coordinate."""
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
        - math.sin(lat1_rad)
        * math.cos(lat2_rad)
        * math.cos(delta_lon)
    )

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360.0) % 360.0


def angular_difference(bearing_a: float, bearing_b: float) -> float:
    """Return the smallest absolute angular difference between two bearings."""
    return abs((bearing_a - bearing_b + 180.0) % 360.0 - 180.0)


def create_one_way_scenario(
    baseline_network,
    main_roads,
    scenario_id: str,
    scenario_name: str,
    target_bearing: float,
):
    """Create one candidate one-way scenario without modifying S0.

    King Abdulaziz segments aligned within 90 degrees of ``target_bearing`` remain
    open. Opposite-direction target-road segments are marked closed for this
    candidate scenario. No physical road geometry is deleted.
    """
    scenario_network = baseline_network.copy()

    scenario_network["scenario"] = scenario_name
    scenario_network["scenario_id"] = scenario_id
    scenario_network["intervention"] = "None"
    scenario_network["target_road"] = False
    scenario_network["target_direction"] = False

    king_abdulaziz_ids = set(
        main_roads.loc[
            main_roads["display_name"] == TARGET_ROAD,
            "road_segment_id",
        ]
    )

    if not king_abdulaziz_ids:
        raise RuntimeError("King Abdulaziz Road was not found in the OSM main-road set.")

    target_mask = scenario_network["road_segment_id"].isin(king_abdulaziz_ids)
    scenario_network.loc[target_mask, "target_road"] = True

    scenario_network["segment_bearing"] = scenario_network.geometry.apply(
        calculate_segment_bearing
    )

    scenario_network["bearing_difference"] = scenario_network[
        "segment_bearing"
    ].apply(
        lambda bearing: (
            angular_difference(bearing, target_bearing)
            if pd.notna(bearing)
            else np.nan
        )
    )

    preferred_direction = target_mask & (
        scenario_network["bearing_difference"] <= 90.0
    )
    opposite_direction = target_mask & ~preferred_direction

    scenario_network.loc[preferred_direction, "target_direction"] = True
    scenario_network.loc[target_mask, "intervention"] = (
        "King Abdulaziz one-way candidate"
    )
    scenario_network.loc[target_mask, "direction_modified"] = True
    scenario_network.loc[preferred_direction, "road_open"] = True
    scenario_network.loc[opposite_direction, "road_open"] = False

    target_segments = scenario_network.loc[target_mask].copy()
    open_segments = target_segments[target_segments["road_open"]].copy()
    closed_segments = target_segments[~target_segments["road_open"]].copy()

    summary = pd.DataFrame(
        {
            "metric": [
                "Scenario ID",
                "Scenario Name",
                "Target Road",
                "Target Bearing",
                "Target Road Segments",
                "Open Target Segments",
                "Closed Target Segments",
                "Open Target Length (km)",
                "Closed Target Length (km)",
            ],
            "value": [
                scenario_id,
                scenario_name,
                TARGET_ROAD,
                target_bearing,
                len(target_segments),
                len(open_segments),
                len(closed_segments),
                round(open_segments["length"].sum() / 1000.0, 2),
                round(closed_segments["length"].sum() / 1000.0, 2),
            ],
        }
    )

    return scenario_network, summary


def add_scenario_layer(map_obj, network, scenario_id: str, show: bool) -> None:
    """Add open/closed King Abdulaziz segments for one scenario to a Folium map."""
    target = network[network["target_road"]].to_crs("EPSG:4326").copy()

    group = FeatureGroup(name=f"{scenario_id} — one-way candidate", show=show)

    open_target = target[target["road_open"]]
    closed_target = target[~target["road_open"]]

    if not open_target.empty:
        folium.GeoJson(
            open_target,
            name=f"{scenario_id} open direction",
            style_function=lambda _: {
                "color": "#1a9850",
                "weight": 6,
                "opacity": 0.95,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["display_name", "segment_bearing", "road_open"],
                aliases=["Road", "Bearing", "Open"],
                localize=True,
            ),
        ).add_to(group)

    if not closed_target.empty:
        folium.GeoJson(
            closed_target,
            name=f"{scenario_id} closed direction",
            style_function=lambda _: {
                "color": "#d73027",
                "weight": 6,
                "opacity": 0.95,
                "dashArray": "8,6",
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["display_name", "segment_bearing", "road_open"],
                aliases=["Road", "Bearing", "Open"],
                localize=True,
            ),
        ).add_to(group)

    group.add_to(map_obj)


def create_comparison_map(streets, clean_corridor, s1a_network, s1b_network):
    """Create one interactive map for visual comparison of S0, S1A, and S1B."""
    m = folium.Map(
        location=[ABHA_CENTER_LAT, ABHA_CENTER_LON],
        zoom_start=14,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    network_layer = FeatureGroup(name="S0 — Full Network", show=True)
    folium.GeoJson(
        streets.to_crs("EPSG:4326"),
        style_function=lambda _: {
            "color": "#8c8c8c",
            "weight": 1,
            "opacity": 0.20,
        },
    ).add_to(network_layer)
    network_layer.add_to(m)

    corridor_layer = FeatureGroup(name="S0 — Cleaned Study Corridor", show=True)
    folium.GeoJson(
        clean_corridor.to_crs("EPSG:4326"),
        style_function=lambda _: {
            "color": "#ff7f00",
            "weight": 3,
            "opacity": 0.60,
        },
    ).add_to(corridor_layer)
    corridor_layer.add_to(m)

    add_scenario_layer(m, s1a_network, "S1A", show=True)
    add_scenario_layer(m, s1b_network, "S1B", show=False)

    legend_html = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index:9999;
                background:white; padding:10px 14px; border:1px solid #999;
                border-radius:5px; font-size:13px;">
      <b>Abha one-way scenario validation</b><br>
      <span style="color:#1a9850; font-weight:bold;">━━</span> Open direction<br>
      <span style="color:#d73027; font-weight:bold;">┄┄</span> Closed opposite direction<br>
      <span style="color:#ff7f00; font-weight:bold;">━━</span> S0 cleaned corridor
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen().add_to(m)
    MeasureControl(position="topleft").add_to(m)

    return m


def save_scenario_outputs(
    s1a_network,
    s1b_network,
    s1a_summary,
    s1b_summary,
    comparison_map,
):
    """Save scenario artifacts for review before simulation."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    s1a_summary.to_csv(OUT_DIR / "s1a_oneway_summary.csv", index=False)
    s1b_summary.to_csv(OUT_DIR / "s1b_oneway_summary.csv", index=False)

    s1a_target = s1a_network[s1a_network["target_road"]].copy()
    s1b_target = s1b_network[s1b_network["target_road"]].copy()

    s1a_target.to_crs("EPSG:4326").to_file(
        OUT_DIR / "s1a_king_abdulaziz.geojson",
        driver="GeoJSON",
    )
    s1b_target.to_crs("EPSG:4326").to_file(
        OUT_DIR / "s1b_king_abdulaziz.geojson",
        driver="GeoJSON",
    )

    comparison_map.save(OUT_DIR / "abha_s1_oneway_comparison_map.html")


def main():
    print("=" * 72)
    print("ABHA S1 ONE-WAY CANDIDATE SCENARIOS")
    print("=" * 72)
    print("S0 stays unchanged. S1A/S1B are candidate interventions only.\n")

    _, streets, origins, destinations = download_abha_osm()
    main_roads = extract_main_roads(streets)
    ring_corridor = build_ring_corridor(streets, main_roads)
    clean_corridor = clean_ring_corridor(ring_corridor)

    baseline_network, _, _ = create_baseline(
        streets,
        clean_corridor,
        origins,
        destinations,
    )

    s1a_network, s1a_summary = create_one_way_scenario(
        baseline_network=baseline_network,
        main_roads=main_roads,
        scenario_id="S1A",
        scenario_name=S1_DIRECTIONS["S1A"]["name"],
        target_bearing=S1_DIRECTIONS["S1A"]["target_bearing"],
    )

    s1b_network, s1b_summary = create_one_way_scenario(
        baseline_network=baseline_network,
        main_roads=main_roads,
        scenario_id="S1B",
        scenario_name=S1_DIRECTIONS["S1B"]["name"],
        target_bearing=S1_DIRECTIONS["S1B"]["target_bearing"],
    )

    comparison_map = create_comparison_map(
        streets,
        clean_corridor,
        s1a_network,
        s1b_network,
    )

    print("S1A SUMMARY")
    print(s1a_summary.to_string(index=False))
    print("\nS1B SUMMARY")
    print(s1b_summary.to_string(index=False))

    save_scenario_outputs(
        s1a_network,
        s1b_network,
        s1a_summary,
        s1b_summary,
        comparison_map,
    )

    print("\nSaved review artifacts to:")
    print(OUT_DIR)
    print("\nFiles:")
    print("- s1a_oneway_summary.csv")
    print("- s1b_oneway_summary.csv")
    print("- s1a_king_abdulaziz.geojson")
    print("- s1b_king_abdulaziz.geojson")
    print("- abha_s1_oneway_comparison_map.html")
    print("\nNext: visually validate the two directions, then simulate S0 vs S1A vs S1B.")


if __name__ == "__main__":
    main()
