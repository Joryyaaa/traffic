"""Split frozen B0 OSM ways into edge-level segments for Madina connectivity.

Madina (and our _build_topology) builds graph nodes from LineString endpoints
only. OSM ways that share interior vertices don't connect. This script splits
each way's multi-vertex LineString into consecutive 2-point segments, each
inheriting the parent way's osm_id and attributes.

Input:  data/neom_baseline/sharma_camp26_r5km/streets_largest_component.geojson
Output: data/neom_scenarios/sharma_camp26_r5km/streets_madina_ready.geojson
        (plus topology QA report)

Does NOT modify the frozen baseline.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "neom_baseline" / "sharma_camp26_r5km" / "streets_largest_component.geojson"
OUTPUT = ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "streets_madina_ready.geojson"
S1_OUTPUT = ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "S1" / "streets_restricted_madina_ready.geojson"
QA_OUTPUT = ROOT / "results" / "neom_scenarios" / "sharma_camp26_r5km" / "qa" / "madina_ready_topology.json"

S1_CLOSURE_WAY_IDS = {849103822, 996697456, 849103837, 849103835, 849103823}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def split_ways(features):
    """Split each multi-vertex LineString into consecutive 2-point segments."""
    segments = []
    for feat in features:
        coords = feat["geometry"]["coordinates"]
        props = feat["properties"].copy()
        osm_id = props["osm_id"]

        for i in range(len(coords) - 1):
            seg_props = props.copy()
            seg_props["parent_osm_id"] = osm_id
            seg_props["segment_index"] = i
            seg_props["segments"] = 1
            segment = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [coords[i], coords[i + 1]]
                },
                "properties": seg_props
            }
            segments.append(segment)
    return segments


def compute_topology(segments, snapping_tol=1e-6):
    """Build a simple adjacency graph from segment endpoints and count components."""
    def snap(coord):
        return (round(coord[0] / snapping_tol) * snapping_tol,
                round(coord[1] / snapping_tol) * snapping_tol)

    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[a] = b

    node_set = set()
    edges = []
    for seg in segments:
        coords = seg["geometry"]["coordinates"]
        u = snap(coords[0])
        v = snap(coords[1])
        node_set.add(u)
        node_set.add(v)
        edges.append((u, v))

    for n in node_set:
        parent[n] = n
    for u, v in edges:
        union(u, v)

    components = Counter(find(n) for n in node_set)
    n_components = len(components)
    largest = max(components.values())
    return {
        "n_nodes": len(node_set),
        "n_edges": len(edges),
        "n_components": n_components,
        "largest_component_nodes": largest,
        "component_sizes": sorted(components.values(), reverse=True)
    }


def main():
    print("Loading frozen B0 streets...")
    gj = load_json(INPUT)
    features = gj["features"]
    print(f"  Input: {len(features)} OSM ways")

    total_original_segments = sum(len(f['geometry']['coordinates']) - 1 for f in features)
    print(f"  Total vertex-to-vertex segments in input: {total_original_segments}")

    print("\nSplitting ways into edge-level segments...")
    segments = split_ways(features)
    print(f"  Output: {len(segments)} segments")

    # Build full B0 Madina-ready network
    madina_gj = {
        "type": "FeatureCollection",
        "features": segments
    }
    save_json(madina_gj, OUTPUT)
    print(f"  Saved: {OUTPUT.relative_to(ROOT)}")

    # Topology check on full network
    print("\nComputing B0 topology...")
    topo = compute_topology(segments)
    print(f"  Nodes: {topo['n_nodes']}")
    print(f"  Edges: {topo['n_edges']}")
    print(f"  Components: {topo['n_components']}")
    print(f"  Largest component: {topo['largest_component_nodes']} nodes")
    if topo['n_components'] > 1:
        print(f"  Component sizes: {topo['component_sizes']}")

    # Build S1 restricted version (remove closure ways)
    print("\nBuilding S1 restricted Madina-ready network...")
    s1_segments = [s for s in segments
                   if s["properties"]["parent_osm_id"] not in S1_CLOSURE_WAY_IDS]
    removed = len(segments) - len(s1_segments)
    print(f"  Removed {removed} segments from {len(S1_CLOSURE_WAY_IDS)} closure ways")
    print(f"  Remaining: {len(s1_segments)} segments")

    s1_gj = {
        "type": "FeatureCollection",
        "features": s1_segments
    }
    save_json(s1_gj, S1_OUTPUT)
    print(f"  Saved: {S1_OUTPUT.relative_to(ROOT)}")

    # Topology check on S1
    print("\nComputing S1 topology...")
    s1_topo = compute_topology(s1_segments)
    print(f"  Nodes: {s1_topo['n_nodes']}")
    print(f"  Edges: {s1_topo['n_edges']}")
    print(f"  Components: {s1_topo['n_components']}")
    print(f"  Largest component: {s1_topo['largest_component_nodes']} nodes")

    # OD reachability check
    print("\nChecking OD reachability...")
    network_nodes = set()
    for seg in segments:
        coords = seg["geometry"]["coordinates"]
        network_nodes.add(tuple(coords[0]))
        network_nodes.add(tuple(coords[1]))

    # Check origins
    origins = load_json(ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "B0" / "origins.geojson")
    dests = load_json(ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "B0" / "destinations.geojson")
    s2_dests = load_json(ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "S2" / "destinations.geojson")
    s3_entry_dest = load_json(ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "S3" / "entry_destination.geojson")
    s3_exit_orig = load_json(ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "S3" / "exit_origin.geojson")
    s3_exit_dest = load_json(ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "S3" / "exit_destination.geojson")

    def nearest_dist(point_coords, node_set):
        """Find distance to nearest network node (in degrees, rough)."""
        px, py = point_coords
        best = float("inf")
        for nx, ny in node_set:
            d = ((px - nx)**2 + (py - ny)**2)**0.5
            if d < best:
                best = d
        return best

    print("  Origin proximity to network:")
    origin_dists = []
    for f in origins["features"]:
        d = nearest_dist(f["geometry"]["coordinates"], network_nodes)
        origin_dists.append(d)
    print(f"    min={min(origin_dists):.6f} max={max(origin_dists):.6f} deg")
    print(f"    (~{min(origin_dists)*111000:.1f}m to ~{max(origin_dists)*111000:.1f}m)")

    print("  B0 destination proximity:")
    dest_dists = []
    for f in dests["features"]:
        d = nearest_dist(f["geometry"]["coordinates"], network_nodes)
        dest_dists.append(d)
    print(f"    min={min(dest_dists):.6f} max={max(dest_dists):.6f} deg")
    print(f"    (~{min(dest_dists)*111000:.1f}m to ~{max(dest_dists)*111000:.1f}m)")

    print("  S2 Camp 26 hub proximity:")
    for f in s2_dests["features"]:
        d = nearest_dist(f["geometry"]["coordinates"], network_nodes)
        print(f"    {d:.6f} deg (~{d*111000:.1f}m)")

    print("  S3 entry dest proximity:")
    for f in s3_entry_dest["features"]:
        d = nearest_dist(f["geometry"]["coordinates"], network_nodes)
        print(f"    {d:.6f} deg (~{d*111000:.1f}m)")

    print("  S3 exit origin proximity:")
    for f in s3_exit_orig["features"]:
        d = nearest_dist(f["geometry"]["coordinates"], network_nodes)
        print(f"    {d:.6f} deg (~{d*111000:.1f}m)")

    print("  S3 exit dest proximity:")
    for f in s3_exit_dest["features"]:
        d = nearest_dist(f["geometry"]["coordinates"], network_nodes)
        print(f"    {d:.6f} deg (~{d*111000:.1f}m)")

    # Save QA
    qa = {
        "source": str(INPUT.relative_to(ROOT)),
        "output": str(OUTPUT.relative_to(ROOT)),
        "input_ways": len(features),
        "output_segments": len(segments),
        "b0_topology": topo,
        "s1_topology": s1_topo,
        "s1_removed_segments": removed,
        "s1_closure_way_ids": sorted(S1_CLOSURE_WAY_IDS),
        "origin_max_dist_deg": max(origin_dists),
        "dest_max_dist_deg": max(dest_dists),
    }
    save_json(qa, QA_OUTPUT)
    print(f"\nQA report: {QA_OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
