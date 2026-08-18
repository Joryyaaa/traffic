#!/usr/bin/env python3
"""Render the reviewed Makkah Ibrahim Al Khalil B0 geometry over OpenStreetMap.

Geometry preview only: no Madina result, no RL result, and no invented scenario intervention.
"""
from __future__ import annotations
from pathlib import Path
import geopandas as gpd
import folium

ROOT = Path(__file__).resolve().parents[1]
B0 = ROOT / "data/makkah_ibrahim_osm/B0_baseline_streets.geojson"
CORRIDOR = ROOT / "data/makkah_ibrahim_scenarios/ibrahim_al_khalil_corridor.geojson"
OUT = ROOT / "results/makkah_ibrahim_osm/makkah_ibrahim_geometry_preview.html"


def main():
    if not B0.exists():
        raise SystemExit(f"Missing B0 baseline: {B0}")
    if not CORRIDOR.exists():
        raise SystemExit(f"Missing reviewed corridor: {CORRIDOR}. Run scripts/build_makkah_ibrahim_scenarios.py first.")

    streets = gpd.read_file(B0).to_crs("EPSG:4326")
    corridor = gpd.read_file(CORRIDOR).to_crs("EPSG:4326")
    bounds = corridor.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]

    m = folium.Map(location=center, zoom_start=14, tiles="OpenStreetMap")
    folium.GeoJson(
        streets[["geometry"]],
        name="B0 OSM drive network",
        style_function=lambda _: {"color": "#3568a8", "weight": 1.4, "opacity": 0.35},
    ).add_to(m)
    folium.GeoJson(
        corridor,
        name="Reviewed Ibrahim Al Khalil corridor",
        tooltip=folium.GeoJsonTooltip(fields=["corridor_group", "name", "highway", "length"], aliases=["Group", "Name", "Highway", "Length (m)"]),
        style_function=lambda _: {"color": "#d7191c", "weight": 5.5, "opacity": 1.0},
    ).add_to(m)
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(35, 35))
    folium.LayerControl(collapsed=False).add_to(m)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    m.save(OUT)
    print("PRE-RUN GEOMETRY PREVIEW — no model result")
    print("B0 segments:", len(streets))
    print("Reviewed corridor segments:", len(corridor))
    print("Reviewed corridor length (m):", round(float(corridor["length"].sum()), 2))
    print("MAP:", OUT)


if __name__ == "__main__":
    main()
