#!/usr/bin/env python3
"""Derive Makkah Ibrahim Al Khalil corridor scenarios from the clean OSM B0 baseline.

B0 is never modified. The two largest connected sets of streets named Ibrahim Al Khalil
are treated as the two carriageways of the reviewed corridor; tiny disconnected name
matches are excluded. Demand weights are provisional sensitivity units, not observed counts.
"""
from __future__ import annotations
import json
from pathlib import Path
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/makkah_ibrahim_osm/B0_baseline_streets.geojson"
OUT = ROOT / "data/makkah_ibrahim_scenarios"


def feature_collection(features):
    return {"type": "FeatureCollection", "features": features}


def write_json(path: Path, obj: dict):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def point_feature(point: Point, props: dict):
    return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [point.x, point.y]}}


def main():
    if not SRC.exists():
        raise SystemExit(f"Missing B0 baseline: {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)

    edges = gpd.read_file(SRC).to_crs("EPSG:4326")
    named = edges[edges["name"].astype(str).str.contains("Ibrahim|إبراهيم|ابراهيم|Khalil|خليل", case=False, na=False)].copy()

    G = nx.Graph()
    for idx, row in named.iterrows():
        G.add_edge(str(row["u"]), str(row["v"]), idx=idx)
    components = sorted(nx.connected_components(G), key=len, reverse=True)
    if len(components) < 2:
        raise RuntimeError("Expected two main Ibrahim Al Khalil carriageway groups")

    groups = []
    for comp in components:
        idxs = [d["idx"] for u, v, d in G.edges(data=True) if u in comp and v in comp]
        groups.append(named.loc[idxs].copy())

    corridor = gpd.GeoDataFrame(
        gpd.pd.concat([groups[0], groups[1]], ignore_index=True),
        crs=named.crs,
    )
    corridor["corridor_group"] = [1] * len(groups[0]) + [2] * len(groups[1])
    corridor.to_file(OUT / "ibrahim_al_khalil_corridor.geojson", driver="GeoJSON")

    # Use the full clean B0 street network for simulation; corridor is a reviewed target overlay.
    edges.to_file(OUT / "B0_streets.geojson", driver="GeoJSON")

    # South edge(s) as provisional inbound origins; north edge as destination near the Haram.
    metric = corridor.to_crs("EPSG:32637")
    endpoints = []
    for geom in corridor.geometry:
        coords = list(geom.coords)
        endpoints.extend([Point(coords[0]), Point(coords[-1])])
    pts = gpd.GeoSeries(endpoints, crs="EPSG:4326")
    south = pts.iloc[pts.y.argsort()[:2].tolist()]
    north = pts.iloc[int(pts.y.argmax())]

    dest = feature_collection([point_feature(north, {"destination_id": "ibrahim_north_haram", "destination_weight": 1.0})])
    write_json(OUT / "destination.geojson", dest)

    for label, mult in (("reference", 1.0), ("peak_1_5", 1.5), ("peak_2_0", 2.0)):
        origins = []
        for i, p in enumerate(south):
            origins.append(point_feature(p, {"origin_id": f"ibrahim_south_{i+1}", "demand_weight": mult, "demand_type": "provisional_sensitivity"}))
        write_json(OUT / f"origins_{label}.geojson", feature_collection(origins))

    qa = {
        "baseline_source": str(SRC.relative_to(ROOT)),
        "B0_segments": int(len(edges)),
        "named_ibrahim_segments": int(len(named)),
        "connected_name_groups": len(groups),
        "selected_groups": [1, 2],
        "selected_corridor_segments": int(len(corridor)),
        "selected_corridor_length_m": float(corridor["length"].sum()),
        "excluded_tiny_groups": [
            {"group": i + 1, "segments": int(len(g)), "length_m": float(g["length"].sum())}
            for i, g in enumerate(groups[2:], start=2)
        ],
        "scenarios": {
            "B0_reference": 1.0,
            "S1_peak_1_5x": 1.5,
            "S2_peak_2_0x": 2.0,
        },
        "note": "Demand multipliers are sensitivity units, not measured vehicle counts; B0 street geometry is unchanged across scenarios.",
    }
    write_json(OUT / "qa_report.json", qa)
    print(json.dumps(qa, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
