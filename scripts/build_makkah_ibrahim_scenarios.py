#!/usr/bin/env python3
"""Prepare the reviewed Ibrahim Al Khalil corridor from the clean OSM B0 baseline.

This file does not invent traffic scenarios. It only derives the reviewed target corridor
from B0 so future scenarios can be applied on top of the same baseline.
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import geopandas as gpd
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/makkah_ibrahim_osm/B0_baseline_streets.geojson"
OUT = ROOT / "data/makkah_ibrahim_scenarios"


def main():
    if not SRC.exists():
        raise SystemExit(f"Missing B0 baseline: {SRC}")
    OUT.mkdir(parents=True, exist_ok=True)

    edges = gpd.read_file(SRC).to_crs("EPSG:4326")
    named = edges[
        edges["name"].astype(str).str.contains(
            "Ibrahim|إبراهيم|ابراهيم|Khalil|خليل",
            case=False,
            na=False,
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
        groups.append(named.loc[idxs].copy())

    if len(groups) < 2:
        raise RuntimeError("Expected two main Ibrahim Al Khalil carriageway groups")

    corridor = gpd.GeoDataFrame(
        pd.concat([groups[0], groups[1]], ignore_index=True),
        crs=named.crs,
    )
    corridor["corridor_group"] = [1] * len(groups[0]) + [2] * len(groups[1])
    corridor.to_file(OUT / "ibrahim_al_khalil_corridor.geojson", driver="GeoJSON")

    qa = {
        "baseline_source": str(SRC.relative_to(ROOT)),
        "B0_segments": int(len(edges)),
        "named_ibrahim_segments": int(len(named)),
        "connected_name_groups": int(len(groups)),
        "selected_groups": [1, 2],
        "selected_corridor_segments": int(len(corridor)),
        "selected_corridor_length_m": float(corridor["length"].sum()),
        "excluded_groups": [
            {
                "group": i + 1,
                "segments": int(len(group)),
                "length_m": float(group["length"].sum()),
            }
            for i, group in enumerate(groups[2:], start=2)
        ],
        "status": "B0 + reviewed corridor only; no traffic scenario assumptions added",
    }
    (OUT / "qa_report.json").write_text(
        json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(qa, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
