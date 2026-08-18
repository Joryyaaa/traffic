#!/usr/bin/env python3
"""Render pre-run Makkah Ibrahim scenario previews over OpenStreetMap.

Geometry preview only. These maps validate B0 and accepted intervention targets;
they do not call Madina, train a model, or report simulated results.
"""
from __future__ import annotations
from pathlib import Path
import json
import geopandas as gpd
import folium

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/makkah_ibrahim_osm"
OUT = ROOT / "results/makkah_ibrahim_scenarios/maps"

SCENARIOS = {
    "B0_baseline": {
        "title": "B0 — Current OSM Baseline",
        "streets": "B0_baseline_streets.geojson",
        "targets": None,
        "qa_key": None,
        "description": "Current OSM drive network; no intervention",
    },
    "S1_partial_closure": {
        "title": "S1 — Ibrahim Al Khalil Partial Closure",
        "streets": "S1_partial_closure_streets.geojson",
        "targets": "S1_partial_closure_targets.geojson",
        "qa_key": "S1",
        "description": "Network-safe closure of the validated OSM way 263016253",
    },
    "S2_corridor_restriction": {
        "title": "S2 — Ibrahim Al Khalil Network-Safe Corridor Restriction",
        "streets": "S2_corridor_restriction_streets.geojson",
        "targets": "S2_corridor_restriction_targets.geojson",
        "qa_key": "S2",
        "description": "Connectivity-safe restriction selected from the reviewed corridor",
    },
    "S3_entry_direction": {
        "title": "S3 Entry — Ibrahim Al Khalil Entry-Direction Management",
        "streets": "S3_entry_direction_streets.geojson",
        "targets": "S3_entry_direction_targets.geojson",
        "qa_key": "S3_entry",
        "description": "Connectivity-safe restriction of corridor edges toward the Haram",
    },
    "S3_exit_direction": {
        "title": "S3 Exit — Ibrahim Al Khalil Exit-Direction Management",
        "streets": "S3_exit_direction_streets.geojson",
        "targets": "S3_exit_direction_targets.geojson",
        "qa_key": "S3_exit",
        "description": "Connectivity-safe restriction of corridor edges away from the Haram",
    },
}


def geometry_only(gdf: gpd.GeoDataFrame) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {}, "geometry": geom.__geo_interface__}
            for geom in gdf.geometry
            if geom is not None and not geom.is_empty
        ],
    }


def add_title(m: folium.Map, title: str, description: str, status: str) -> None:
    html = f"""
    <div style="position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
                z-index: 9999; background: white; border: 1px solid #777;
                border-radius: 6px; padding: 8px 12px; font-family: sans-serif;
                box-shadow: 0 1px 4px rgba(0,0,0,.25); text-align: center;">
      <div style="font-weight: 700; font-size: 16px;">{title}</div>
      <div style="font-size: 12px; margin-top: 2px;">{description}</div>
      <div style="font-size: 11px; margin-top: 3px; color: #555;">{status}</div>
      <div style="font-size: 10px; margin-top: 2px; color: #777;">PRE-RUN GEOMETRY PREVIEW — no model result</div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(html))


def render(key: str, qa: dict) -> Path:
    info = SCENARIOS[key]
    streets_path = DATA / info["streets"]
    if not streets_path.exists():
        raise SystemExit(f"Missing scenario streets: {streets_path}")
    streets = gpd.read_file(streets_path).to_crs("EPSG:4326")

    reviewed = gpd.read_file(DATA / "intervention_targets.geojson").to_crs("EPSG:4326")
    bounds = reviewed.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    m = folium.Map(location=center, zoom_start=14, tiles="OpenStreetMap")

    folium.GeoJson(
        geometry_only(streets),
        name="Drive network after scenario",
        style_function=lambda _: {"color": "#3568a8", "weight": 1.5, "opacity": 0.45},
    ).add_to(m)

    folium.GeoJson(
        geometry_only(reviewed),
        name="Reviewed Ibrahim corridor",
        style_function=lambda _: {"color": "#777777", "weight": 3.0, "opacity": 0.45},
    ).add_to(m)

    status = f"Network: {len(streets)} segments"
    if info["targets"]:
        target_path = DATA / info["targets"]
        if not target_path.exists():
            raise SystemExit(f"Missing scenario targets: {target_path}")
        targets = gpd.read_file(target_path).to_crs("EPSG:4326")
        folium.GeoJson(
            geometry_only(targets),
            name="Accepted intervention targets",
            style_function=lambda _: {"color": "#d7191c", "weight": 6.0, "opacity": 1.0},
        ).add_to(m)
        row = qa[info["qa_key"]]
        status = (
            f"Accepted {row['removed_segments']}/{row['candidate_segments']} candidate closures | "
            f"blocked by connectivity: {row['blocked_by_connectivity']} | connected: {row['remaining_components']}"
        )

        blocked_path = DATA / f"{key}_blocked_targets.geojson"
        if blocked_path.exists():
            blocked = gpd.read_file(blocked_path).to_crs("EPSG:4326")
            if len(blocked):
                folium.GeoJson(
                    geometry_only(blocked),
                    name="Blocked by connectivity",
                    style_function=lambda _: {"color": "#f2a900", "weight": 5.0, "opacity": 0.95, "dashArray": "8,6"},
                ).add_to(m)

    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]], padding=(35, 35))
    add_title(m, info["title"], info["description"], status)
    folium.LayerControl(collapsed=False).add_to(m)

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{key}_geometry_preview.html"
    m.save(path)
    print(f"MAP: {path}")
    return path


def main():
    qa_path = DATA / "qa_report.json"
    if not qa_path.exists():
        raise SystemExit(f"Missing QA report: {qa_path}. Run build_makkah_ibrahim_osm_network.py first.")
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    for key in SCENARIOS:
        render(key, qa)


if __name__ == "__main__":
    main()
