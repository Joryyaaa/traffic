#!/usr/bin/env python3
"""Build Makkah Ibrahim Al Khalil B0 and network-safe geometry scenarios.

Repository-style flow:
OSM drive network -> clean B0 -> scenario candidates derived from the same B0 ->
connectivity-safe filtering -> QA.

The filtering mirrors the repository rule used by StreetNetworkEnv when
forbid_disconnection=True: a closure is accepted only if the network remains
connected after that closure. No synthetic demand, reward changes, or model
outputs are created here.
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
from shapely.geometry import LineString

CENTER = (21.4177, 39.8228)
DEFAULT_RADIUS_M = 1800
IBRAHIM_AL_KHALIL_WAY_ID = 263016253
REQUIRED_NODE_IDS = (5129445142, 5077724339)


def contains_osmid(value, target):
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return any(contains_osmid(v, target) for v in value)
    return any(
        x.strip() == str(target)
        for x in str(value).replace("[", "").replace("]", "").split(",")
    )


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
                r["closed_way_split"] = True
                rows.append(r)
        else:
            r = row.copy()
            r["closed_way_split"] = False
            rows.append(r)
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


def connectivity_graph(edges):
    graph = nx.MultiGraph()
    for idx, row in edges.iterrows():
        graph.add_edge(int(row["u"]), int(row["v"]), key=int(idx), source_index=int(idx))
    return graph


def network_safe_subset(edges, candidate_indices):
    """Return deterministic closure subset that never disconnects B0.

    Candidates are tested in source-index order. Each accepted closure is kept;
    any closure that would disconnect the current graph is rejected. This is the
    same legality rule as StreetNetworkEnv with forbid_disconnection=True.
    """
    graph = connectivity_graph(edges)
    if not nx.is_connected(nx.Graph(graph)):
        raise RuntimeError("B0 must be connected before network-safe filtering")

    accepted = []
    rejected = []
    for idx in sorted(set(int(i) for i in candidate_indices)):
        row = edges.loc[idx]
        u = int(row["u"])
        v = int(row["v"])
        if not graph.has_edge(u, v, key=idx):
            raise RuntimeError(f"Missing candidate edge {idx} in connectivity graph")
        graph.remove_edge(u, v, key=idx)
        if nx.is_connected(nx.Graph(graph)):
            accepted.append(idx)
        else:
            graph.add_edge(u, v, key=idx, source_index=idx)
            rejected.append(idx)
    return accepted, rejected


def named_ibrahim_groups(edges):
    named = edges[
        edges["name"].astype(str).str.contains(
            "Ibrahim|إبراهيم|ابراهيم|Khalil|خليل", case=False, na=False
        )
    ].copy()
    graph = nx.Graph()
    for idx, row in named.iterrows():
        graph.add_edge(str(row["u"]), str(row["v"]), idx=idx)
    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    groups = []
    for comp in components:
        idxs = [
            data["idx"]
            for u, v, data in graph.edges(data=True)
            if u in comp and v in comp
        ]
        group = named.loc[idxs].copy()
        group["source_index"] = group.index.astype(int)
        groups.append(group)
    return named, groups


def direction_role(geom):
    coords = list(geom.coords)
    if len(coords) < 2:
        return "unknown"
    return "toward_haram" if coords[-1][1] > coords[0][1] else "away_from_haram"


def save_scenario(out, stem, base_edges, candidate_indices, network_safe=True):
    candidates = sorted(set(int(i) for i in candidate_indices))
    if network_safe:
        accepted, rejected = network_safe_subset(base_edges, candidates)
    else:
        accepted, rejected = candidates, []

    targets = base_edges.loc[accepted].copy()
    rejected_targets = base_edges.loc[rejected].copy() if rejected else base_edges.iloc[0:0].copy()
    streets = base_edges.drop(index=accepted).copy()

    streets.to_file(out / f"{stem}_streets.geojson", driver="GeoJSON")
    targets.to_file(out / f"{stem}_targets.geojson", driver="GeoJSON")
    if len(rejected_targets):
        rejected_targets.to_file(out / f"{stem}_blocked_targets.geojson", driver="GeoJSON")

    check = component_check(streets)
    return {
        "candidate_segments": int(len(candidates)),
        "removed_segments": int(len(targets)),
        "blocked_by_connectivity": int(len(rejected)),
        "blocked_source_indices": rejected,
        "removed_length_m": float(targets["length"].sum()) if len(targets) else 0.0,
        "remaining_segments": int(len(streets)),
        "remaining_components": int(check["components"]),
        "remaining_component_node_sizes": check["component_node_sizes"],
        "network_safe": bool(check["components"] == 1),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius", type=float, default=DEFAULT_RADIUS_M)
    parser.add_argument("--out", default="data/makkah_ibrahim_osm")
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"Fetching Makkah OSM drive network: center={CENTER}, radius={args.radius}m")
    graph = ox.graph_from_point(
        CENTER,
        dist=args.radius,
        network_type="drive",
        simplify=True,
        retain_all=False,
        truncate_by_edge=True,
    )
    _, edges = ox.graph_to_gdfs(graph, nodes=True, edges=True, fill_edge_geometry=True)
    edges = edges.reset_index()

    keep = [
        "u", "v", "key", "osmid", "oneway", "junction",
        "name", "highway", "length", "geometry",
    ]
    for col in keep:
        if col not in edges.columns:
            edges[col] = None
    edges = edges[keep].copy()
    edges["osmid"] = edges["osmid"].map(normalize_osmid)
    edges = split_closed_rows(edges)

    qa = component_check(edges)
    if qa["components"] != 1:
        raise RuntimeError(
            f"OSM crop disconnected ({qa['components']} components). "
            "Adjust crop/builder; do not fix with node snapping."
        )

    way_mask = edges["osmid"].map(
        lambda x: contains_osmid(x, IBRAHIM_AL_KHALIL_WAY_ID)
    )
    way_present = bool(way_mask.any())
    node_presence = {str(n): bool(n in graph.nodes) for n in REQUIRED_NODE_IDS}
    if not way_present:
        raise RuntimeError(
            f"Required Ibrahim Al Khalil OSM way {IBRAHIM_AL_KHALIL_WAY_ID} not present"
        )
    if not all(node_presence.values()):
        raise RuntimeError(
            "Required Makkah OSM nodes missing: "
            + str([n for n, present in node_presence.items() if not present])
        )

    named, groups = named_ibrahim_groups(edges)
    if len(groups) < 2:
        raise RuntimeError("Expected two main connected Ibrahim Al Khalil carriageway groups")

    corridor = gpd.GeoDataFrame(
        pd.concat([groups[0], groups[1]], ignore_index=True), crs=edges.crs
    )
    corridor["corridor_group"] = [1] * len(groups[0]) + [2] * len(groups[1])
    corridor["direction_role"] = corridor.geometry.map(direction_role)

    # B0 and reviewed target geometry.
    edges.to_file(out / "B0_baseline_streets.geojson", driver="GeoJSON")
    edges.to_file(out / "road_metadata.geojson", driver="GeoJSON")
    corridor.to_file(out / "intervention_targets.geojson", driver="GeoJSON")

    # S1 — exact OSM-way partial closure; already network-safe in prior validation.
    s1 = save_scenario(
        out,
        "S1_partial_closure",
        edges,
        edges.index[way_mask].tolist(),
        network_safe=True,
    )
    s1.update({
        "name": "Ibrahim Al Khalil Partial Closure",
        "definition": "network-safe removal of OSM way 263016253 from B0",
        "removed_osm_way_id": IBRAHIM_AL_KHALIL_WAY_ID,
    })

    full_indices = corridor["source_index"].astype(int).tolist()
    s2 = save_scenario(
        out,
        "S2_corridor_restriction",
        edges,
        full_indices,
        network_safe=True,
    )
    s2.update({
        "name": "Ibrahim Al Khalil Network-Safe Corridor Restriction",
        "definition": "attempt all 34 reviewed corridor segments; keep only closures that preserve connectivity",
    })

    toward_indices = corridor.loc[
        corridor["direction_role"] == "toward_haram", "source_index"
    ].astype(int).tolist()
    away_indices = corridor.loc[
        corridor["direction_role"] == "away_from_haram", "source_index"
    ].astype(int).tolist()

    s3a = save_scenario(
        out,
        "S3_entry_direction",
        edges,
        toward_indices,
        network_safe=True,
    )
    s3a.update({
        "name": "Ibrahim Al Khalil Entry-Direction Management",
        "definition": "network-safe restriction of northward corridor edges toward the Haram",
        "direction_rule": "last latitude > first latitude",
    })

    s3b = save_scenario(
        out,
        "S3_exit_direction",
        edges,
        away_indices,
        network_safe=True,
    )
    s3b.update({
        "name": "Ibrahim Al Khalil Exit-Direction Management",
        "definition": "network-safe restriction of southward corridor edges away from the Haram",
        "direction_rule": "last latitude <= first latitude",
    })

    qa.update({
        "center": list(CENTER),
        "radius_m": args.radius,
        "network_type": "drive",
        "required_way_id": IBRAHIM_AL_KHALIL_WAY_ID,
        "required_way_id_present": way_present,
        "required_node_ids": list(REQUIRED_NODE_IDS),
        "required_node_ids_present": node_presence,
        "closed_geometry_rows_after_split": sum(
            list(g.coords)[0] == list(g.coords)[-1] for g in edges.geometry
        ),
        "B0_segments": len(edges),
        "named_ibrahim_segments": len(named),
        "connected_name_groups": len(groups),
        "selected_target_groups": [1, 2],
        "intervention_target_segments": len(corridor),
        "intervention_target_length_m": float(corridor["length"].sum()),
        "direction_counts": corridor["direction_role"].value_counts().to_dict(),
        "excluded_same_name_groups": [
            {
                "group": i + 1,
                "segments": len(group),
                "length_m": float(group["length"].sum()),
            }
            for i, group in enumerate(groups[2:], start=2)
        ],
        "baseline": "B0 clean OSM drive network; no scenario modifications",
        "connectivity_rule": "same legality principle as StreetNetworkEnv forbid_disconnection=True",
        "S1": s1,
        "S2": s2,
        "S3_entry": s3a,
        "S3_exit": s3b,
        "target_status": "reviewed Ibrahim corridor geometry; not a model result",
        "demand_status": "no synthetic demand added",
    })
    (out / "qa_report.json").write_text(
        json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(qa, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
