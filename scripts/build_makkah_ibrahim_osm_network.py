#!/usr/bin/env python3
"""Build the clean Makkah Ibrahim Al Khalil B0 baseline from OpenStreetMap."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
from shapely.geometry import LineString

CENTER = (21.4177, 39.8228)
DEFAULT_RADIUS_M = 1800
IBRAHIM_AL_KHALIL_WAY_ID = 263016253
REQUIRED_NODE_IDS = (5129445142, 5077724339)


def contains_osmid(value, target):
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return any(contains_osmid(v, target) for v in value)
    return any(x.strip() == str(target) for x in str(value).replace("[", "").replace("]", "").split(","))


def normalize_osmid(value):
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return [int(v) if str(v).isdigit() else str(v) for v in value]
    try:
        return int(value)
    except Exception:
        return str(value)


def split_closed_rows(edges):
    rows = []
    count = 0
    for _, row in edges.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty or geom.geom_type != "LineString":
            continue
        coords = list(geom.coords)
        if len(coords) >= 4 and coords[0] == coords[-1]:
            count += 1
            for i in range(len(coords) - 1):
                if coords[i] == coords[i + 1]:
                    continue
                r = row.copy()
                r.geometry = LineString([coords[i], coords[i + 1]])
                rows.append(r)
        else:
            rows.append(row.copy())
    print("Closed/ring geometries split:", count)
    return gpd.GeoDataFrame(rows, crs=edges.crs).reset_index(drop=True)


def component_check(edges):
    graph = nx.Graph()
    for _, row in edges.iterrows():
        graph.add_edge(int(row["u"]), int(row["v"]))
    comps = list(nx.connected_components(graph))
    return {
        "components": len(comps),
        "nodes": graph.number_of_nodes(),
        "edges": graph.number_of_edges(),
        "component_node_sizes": sorted((len(c) for c in comps), reverse=True)[:20],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius", type=float, default=DEFAULT_RADIUS_M)
    parser.add_argument("--out", default="data/makkah_ibrahim_osm")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Fetching Makkah OSM drive network: center={CENTER}, radius={args.radius}m")
    graph = ox.graph_from_point(CENTER, dist=args.radius, network_type="drive", simplify=True, retain_all=False, truncate_by_edge=True)
    _, edges = ox.graph_to_gdfs(graph, nodes=True, edges=True, fill_edge_geometry=True)
    edges = edges.reset_index()

    keep = ["u", "v", "key", "osmid", "oneway", "junction", "name", "highway", "length", "geometry"]
    for col in keep:
        if col not in edges.columns:
            edges[col] = None
    edges = edges[keep].copy()
    edges["osmid"] = edges["osmid"].map(normalize_osmid)
    edges = split_closed_rows(edges)

    qa = component_check(edges)
    if qa["components"] != 1:
        raise RuntimeError(f"OSM crop disconnected ({qa['components']} components). Adjust crop/builder; do not fix with node snapping.")

    way_present = bool(edges["osmid"].map(lambda x: contains_osmid(x, IBRAHIM_AL_KHALIL_WAY_ID)).any())
    node_presence = {str(n): bool(n in graph.nodes) for n in REQUIRED_NODE_IDS}
    if not way_present:
        raise RuntimeError(f"Required Ibrahim Al Khalil OSM way {IBRAHIM_AL_KHALIL_WAY_ID} not present")
    if not all(node_presence.values()):
        raise RuntimeError("Required Makkah OSM nodes missing")

    edges.to_file(out / "B0_baseline_streets.geojson", driver="GeoJSON")
    edges.to_file(out / "road_metadata.geojson", driver="GeoJSON")

    qa.update({
        "center": list(CENTER),
        "radius_m": args.radius,
        "network_type": "drive",
        "required_way_id": IBRAHIM_AL_KHALIL_WAY_ID,
        "required_way_id_present": way_present,
        "required_node_ids": list(REQUIRED_NODE_IDS),
        "required_node_ids_present": node_presence,
        "B0_segments": len(edges),
        "baseline": "B0 clean OSM drive network; no scenario modifications",
        "scenario_status": "not defined",
    })
    (out / "qa_report.json").write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(qa, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
