"""Abha OSM Network Preparation + Corridor Extraction/Cleaning + S0 Baseline.

Converted from the project notebook. Official measured traffic data is intentionally
left empty until authority data is received.
"""
from pathlib import Path
import folium
from folium import FeatureGroup
from folium.plugins import Fullscreen, MeasureControl
import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd

ABHA_CENTER_LAT = 18.2264426
ABHA_CENTER_LON = 42.5053914
CENTER = (ABHA_CENTER_LAT, ABHA_CENTER_LON)
RADIUS_M = 1500
NETWORK_TYPE = "drive"
METRIC_CRS = "EPSG:32638"
OUT_DIR = Path("data/processed/abha_baseline")
MAX_DISTANCE_TO_ANCHOR_M = 250
MIN_CENTER_DISTANCE_M = 400
MIN_SEGMENT_LENGTH_M = 50
SHORT_DEAD_END_M = 100
ROAD_COLUMNS = ["u", "v", "key", "osmid", "name", "highway", "lanes", "maxspeed", "oneway", "junction", "length", "geometry"]
NON_RESIDENTIAL_TYPES = {"commercial", "retail", "industrial", "warehouse", "office", "school", "university", "college", "hospital", "clinic", "mosque", "church", "government", "public", "civic", "garage", "garages", "parking", "service", "construction", "roof", "hotel"}
MAIN_ROAD_KEYWORDS = ["الملك عبدالعزيز", "King Abdulaziz", "الملك فيصل", "King Faisal", "الملك خالد", "King Khalid", "الحزام", "Ring Road"]
ROAD_NAME_MAP = {"طريق الملك عبدالعزيز": "King Abdulaziz Road", "شارع الملك عبدالعزيز": "King Abdulaziz Road", "الملك عبدالعزيز": "King Abdulaziz Road", "طريق الملك فيصل": "King Faisal Road", "شارع الملك فيصل": "King Faisal Road", "الملك فيصل": "King Faisal Road", "طريق الملك خالد": "King Khalid Road", "شارع الملك خالد": "King Khalid Road", "الملك خالد": "King Khalid Road", "طريق الحزام": "Ring Road", "شارع الحزام": "Ring Road", "الحزام": "Ring Road"}
MAJOR_HIGHWAY_CLASSES = ["motorway", "motorway_link", "trunk", "trunk_link", "primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link"]
LINK_TYPES = {"motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}

def normalize_osm_value(value):
    return ";".join(map(str, value)) if isinstance(value, (list, tuple, set)) else value

def road_matches_keywords(name):
    if pd.isna(name):
        return False
    low = str(name).lower()
    return any(k.lower() in low for k in MAIN_ROAD_KEYWORDS)

def get_english_road_name(name):
    if pd.isna(name):
        return "Unknown Road"
    text = str(name)
    for osm_name, english_name in ROAD_NAME_MAP.items():
        if osm_name.lower() in text.lower():
            return english_name
    return "King Faisal Road" if "king fisal" in text.lower() else text

def coverage_report(df, column):
    known = int(df[column].notna().sum())
    return known, round(100 * known / max(len(df), 1), 1)

def download_abha_osm():
    print("=" * 70)
    print("ABHA OSM VEHICULAR NETWORK")
    print("=" * 70)
    graph = ox.graph_from_point(CENTER, dist=RADIUS_M, network_type=NETWORK_TYPE, simplify=True, retain_all=False)
    nodes, edges = ox.graph_to_gdfs(graph)
    edges = edges.reset_index()
    for column in ROAD_COLUMNS:
        if column not in edges.columns:
            edges[column] = None
    streets = edges[ROAD_COLUMNS].copy()
    for column in ["osmid", "name", "highway", "lanes", "maxspeed", "junction"]:
        streets[column] = streets[column].apply(normalize_osm_value)
    streets["oneway"] = streets["oneway"].fillna(False)
    streets = streets.reset_index(drop=True)
    streets["road_segment_id"] = np.arange(len(streets), dtype=int)

    buildings = ox.features_from_point(CENTER, tags={"building": True}, dist=RADIUS_M)
    if not buildings.empty:
        buildings = buildings.copy()
        if "building" not in buildings.columns:
            buildings["building"] = "unknown"
        origins = buildings[~buildings["building"].isin(NON_RESIDENTIAL_TYPES)].copy()
        metric = origins.to_crs(METRIC_CRS)
        area = metric.geometry.area
        origins = origins.set_geometry(metric.geometry.centroid.to_crs(origins.crs))
        origins["origin_weight"] = (area / 30).clip(lower=1).round(1)
        origins = origins.reset_index(drop=True)[["geometry", "origin_weight"]]
    else:
        origins = gpd.GeoDataFrame({"origin_weight": []}, geometry=[], crs="EPSG:4326")

    destinations = ox.features_from_point(CENTER, tags={"amenity": True, "shop": True}, dist=RADIUS_M)
    if not destinations.empty:
        metric = destinations.to_crs(METRIC_CRS)
        area = metric.geometry.area
        destinations = destinations.set_geometry(metric.geometry.centroid.to_crs(destinations.crs))
        destinations["floor_area"] = area.where(area > 0, 50).fillna(50).round(1)
        destinations = destinations.reset_index(drop=True)[["geometry", "floor_area"]]
    else:
        destinations = gpd.GeoDataFrame({"floor_area": []}, geometry=[], crs="EPSG:4326")

    print(f"Nodes: {len(nodes):,}")
    print(f"Directed road segments: {len(streets):,}")
    print(f"Provisional origins: {len(origins):,}")
    print(f"Destinations: {len(destinations):,}")
    return nodes, streets, origins, destinations

def print_network_report(nodes, streets):
    print("\n" + "=" * 70)
    print("ABHA ROAD NETWORK REPORT")
    print("=" * 70)
    print(f"Total nodes: {len(nodes):,}")
    print(f"Total directed road segments: {len(streets):,}")
    print("\nRoad types:")
    print(streets["highway"].fillna("unknown").value_counts().head(20))
    print("\nAttribute coverage:")
    for column in ["lanes", "maxspeed", "oneway", "name"]:
        known, pct = coverage_report(streets, column)
        print(f"{column:<10}: {known:,}/{len(streets):,} ({pct}%)")

def extract_main_roads(streets):
    main_roads = streets[streets["name"].apply(road_matches_keywords)].copy()
    main_roads["display_name"] = main_roads["name"].apply(get_english_road_name)
    print("\n" + "=" * 70)
    print("MAIN CORRIDORS")
    print("=" * 70)
    print(f"Target main-road segments found: {len(main_roads):,}")
    if not main_roads.empty:
        print(main_roads["display_name"].value_counts())
    return main_roads

def classify_directionality(road_df):
    pairs = set(zip(road_df["u"].astype(int), road_df["v"].astype(int)))
    two_way = sum((v, u) in pairs for u, v in pairs)
    one_way = len(pairs) - two_way
    total = len(pairs)
    return {"two_way_edges": two_way, "one_way_edges": one_way, "two_way_pct": round(100 * two_way / total, 1) if total else 0.0, "one_way_pct": round(100 * one_way / total, 1) if total else 0.0}

def build_directionality_report(main_roads):
    rows = []
    for road_name in main_roads["display_name"].dropna().unique():
        result = classify_directionality(main_roads[main_roads["display_name"] == road_name])
        result["road_name"] = road_name
        rows.append(result)
    return pd.DataFrame(rows)[["road_name", "two_way_edges", "one_way_edges", "two_way_pct", "one_way_pct"]] if rows else pd.DataFrame()

def build_ring_corridor(streets, main_roads):
    anchor = main_roads[main_roads["display_name"] == "King Abdulaziz Road"].copy()
    if anchor.empty:
        raise RuntimeError("King Abdulaziz Road was not found in the current OSM study area.")
    streets_metric = streets.to_crs(METRIC_CRS).copy()
    anchor_metric = anchor.to_crs(METRIC_CRS).copy()
    major = streets_metric[streets_metric["highway"].isin(MAJOR_HIGHWAY_CLASSES)].copy()
    anchor_geometry = anchor_metric.geometry.union_all()
    major["distance_to_king_abdulaziz_m"] = major.geometry.distance(anchor_geometry)
    seed = major[major["distance_to_king_abdulaziz_m"] <= MAX_DISTANCE_TO_ANCHOR_M].copy()
    node_map = {}
    for idx, row in seed.iterrows():
        for node in [int(row["u"]), int(row["v"])]:
            node_map.setdefault(node, set()).add(idx)
    anchor_ids = set(seed[seed["road_segment_id"].isin(anchor["road_segment_id"])].index)
    visited, queue = set(anchor_ids), list(anchor_ids)
    while queue:
        current = queue.pop(0)
        connected = set()
        for node in [int(seed.loc[current, "u"]), int(seed.loc[current, "v"])]:
            connected.update(node_map.get(node, set()))
        for nxt in connected:
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    corridor = seed.loc[sorted(visited)].copy()
    center_point = gpd.GeoSeries(gpd.points_from_xy([ABHA_CENTER_LON], [ABHA_CENTER_LAT]), crs="EPSG:4326").to_crs(METRIC_CRS).iloc[0]
    corridor["distance_to_center_m"] = corridor.geometry.distance(center_point)
    is_anchor = corridor["road_segment_id"].isin(anchor["road_segment_id"])
    corridor = corridor[is_anchor | (corridor["distance_to_center_m"] >= MIN_CENTER_DISTANCE_M)].copy()
    corridor["display_name"] = corridor["name"].apply(get_english_road_name)
    corridor.loc[corridor["name"].isna(), "display_name"] = "Unnamed Major Road"
    print(f"\nRing corridor candidate segments: {len(corridor):,}")
    return corridor

def clean_ring_corridor(ring_corridor):
    clean = ring_corridor[~ring_corridor["highway"].isin(LINK_TYPES)].copy()
    clean = clean[(clean["display_name"] == "King Abdulaziz Road") | (clean["length"] >= MIN_SEGMENT_LENGTH_M)].copy()
    node_map = {}
    for idx, row in clean.iterrows():
        for node in [int(row["u"]), int(row["v"])]:
            node_map.setdefault(node, set()).add(idx)
    anchor_indices = set(clean[clean["display_name"] == "King Abdulaziz Road"].index)
    visited, queue = set(anchor_indices), list(anchor_indices)
    while queue:
        current = queue.pop(0)
        connected = set()
        for node in [int(clean.loc[current, "u"]), int(clean.loc[current, "v"])]:
            connected.update(node_map.get(node, set()))
        for nxt in connected:
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)
    clean = clean.loc[sorted(visited)].copy()
    degree = {}
    for _, row in clean.iterrows():
        for node in [int(row["u"]), int(row["v"])]:
            degree[node] = degree.get(node, 0) + 1
    dead_end = clean.apply(lambda r: (degree.get(int(r["u"]), 0) == 1 or degree.get(int(r["v"]), 0) == 1) and r["length"] < SHORT_DEAD_END_M and r["display_name"] != "King Abdulaziz Road", axis=1)
    clean = clean[~dead_end].copy()
    print(f"Cleaned study corridor segments: {len(clean):,}")
    return clean

def create_validation_map(streets, main_roads, corridor, origins, destinations):
    m = folium.Map(location=[ABHA_CENTER_LAT, ABHA_CENTER_LON], zoom_start=14, tiles="OpenStreetMap", control_scale=True)
    full = FeatureGroup(name="Full Road Network", show=True)
    folium.GeoJson(streets.to_crs("EPSG:4326"), style_function=lambda _: {"color": "#8c8c8c", "weight": 1, "opacity": 0.25}).add_to(full)
    full.add_to(m)
    main = FeatureGroup(name="Named Main Corridors", show=True)
    folium.GeoJson(main_roads.to_crs("EPSG:4326"), style_function=lambda _: {"color": "#e31a1c", "weight": 4, "opacity": 0.9}).add_to(main)
    main.add_to(m)
    study = FeatureGroup(name="Cleaned Study Corridor", show=True)
    folium.GeoJson(corridor.to_crs("EPSG:4326"), style_function=lambda _: {"color": "#ff7f00", "weight": 5, "opacity": 0.9}).add_to(study)
    study.add_to(m)
    origins_group = FeatureGroup(name="Provisional Origins", show=False)
    for _, row in origins.to_crs("EPSG:4326").iterrows():
        folium.CircleMarker([row.geometry.y, row.geometry.x], radius=2, tooltip=f"Origin weight: {row['origin_weight']}").add_to(origins_group)
    origins_group.add_to(m)
    destinations_group = FeatureGroup(name="Destinations", show=False)
    for _, row in destinations.to_crs("EPSG:4326").iterrows():
        folium.CircleMarker([row.geometry.y, row.geometry.x], radius=3, tooltip=f"Destination weight: {row['floor_area']}").add_to(destinations_group)
    destinations_group.add_to(m)
    folium.LayerControl(collapsed=False).add_to(m)
    Fullscreen().add_to(m)
    MeasureControl(position="topleft").add_to(m)
    return m

def create_baseline(streets, corridor, origins, destinations):
    network = streets.copy()
    baseline_corridor = corridor.copy()
    network["scenario"] = "Baseline"
    network["scenario_id"] = "S0"
    network["is_study_corridor"] = network["road_segment_id"].isin(baseline_corridor["road_segment_id"])
    network["intervention"] = "None"
    network["road_open"] = True
    network["direction_modified"] = False
    network["lane_modified"] = False
    network["speed_modified"] = False
    network["signal_modified"] = False
    for column in ["traffic_volume", "observed_speed", "capacity", "congestion_level", "travel_time", "vkt"]:
        network[column] = np.nan
    network["needs_lane_data"] = network["lanes"].isna()
    network["needs_speed_data"] = network["maxspeed"].isna()
    summary = pd.DataFrame({"metric": ["Scenario ID", "Scenario Name", "Total Road Segments", "Total Network Length (km)", "Study Corridor Segments", "Study Corridor Length (km)", "Origins", "Destinations", "Named Road Segments", "Segments with Lane Data", "Segments with Speed Data"], "value": ["S0", "Baseline", len(network), round(network["length"].sum() / 1000, 2), len(baseline_corridor), round(baseline_corridor["length"].sum() / 1000, 2), len(origins), len(destinations), int(network["name"].notna().sum()), int(network["lanes"].notna().sum()), int(network["maxspeed"].notna().sum())]})
    return network, baseline_corridor, summary

def save_outputs(streets, origins, destinations, main_roads, directionality, corridor, network, baseline_corridor, summary, validation_map):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    streets.to_file(OUT_DIR / "streets_enriched.geojson", driver="GeoJSON")
    if not origins.empty:
        origins.to_file(OUT_DIR / "origins.geojson", driver="GeoJSON")
    if not destinations.empty:
        destinations.to_file(OUT_DIR / "amenities.geojson", driver="GeoJSON")
    if not main_roads.empty:
        main_roads.to_file(OUT_DIR / "main_roads.geojson", driver="GeoJSON")
    if not directionality.empty:
        directionality.to_csv(OUT_DIR / "main_road_directionality.csv", index=False)
    corridor.to_crs("EPSG:4326").to_file(OUT_DIR / "cleaned_study_corridor.geojson", driver="GeoJSON")
    network.to_file(OUT_DIR / "baseline_network.geojson", driver="GeoJSON")
    baseline_corridor.to_crs("EPSG:4326").to_file(OUT_DIR / "baseline_corridor.geojson", driver="GeoJSON")
    summary.to_csv(OUT_DIR / "baseline_summary.csv", index=False)
    validation_map.save(OUT_DIR / "abha_corridor_validation_map.html")

def main():
    nodes, streets, origins, destinations = download_abha_osm()
    print_network_report(nodes, streets)
    main_roads = extract_main_roads(streets)
    directionality = build_directionality_report(main_roads)
    if not directionality.empty:
        print("\nDirectionality diagnostic:")
        print(directionality.to_string(index=False))
    ring_corridor = build_ring_corridor(streets, main_roads)
    clean_corridor = clean_ring_corridor(ring_corridor)
    validation_map = create_validation_map(streets, main_roads, clean_corridor, origins, destinations)
    network, baseline_corridor, summary = create_baseline(streets, clean_corridor, origins, destinations)
    print("\n" + "=" * 70)
    print("S0 BASELINE SUMMARY")
    print("=" * 70)
    print(summary.to_string(index=False))
    save_outputs(streets, origins, destinations, main_roads, directionality, clean_corridor, network, baseline_corridor, summary, validation_map)
    print("\n" + "=" * 70)
    print("ABHA NETWORK BASELINE COMPLETED")
    print("=" * 70)
    print(f"Road segments: {len(network):,}")
    print(f"Cleaned corridor segments: {len(baseline_corridor):,}")
    print(f"Outputs saved in: {OUT_DIR}")
    print("Next stage: integrate official traffic data when received.")

if __name__ == "__main__":
    main()
