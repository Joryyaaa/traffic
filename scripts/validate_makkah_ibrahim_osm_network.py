#!/usr/bin/env python3
"""Validate the Makkah Ibrahim Al Khalil OSM package before any scenario run."""
from pathlib import Path
import json
import geopandas as gpd
import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data/makkah_ibrahim_osm"
REQUIRED = [
    "B0_baseline_streets.geojson",
    "road_metadata.geojson",
    "intervention_targets.geojson",
    "qa_report.json",
]

missing = [name for name in REQUIRED if not (D / name).exists()]
if missing:
    raise SystemExit("Missing files:\n" + "\n".join(missing))

qa = json.loads((D / "qa_report.json").read_text(encoding="utf-8"))
assert qa["components"] == 1, qa
assert qa["required_way_id_present"], qa
assert all(qa["required_node_ids_present"].values()), qa
assert qa["closed_geometry_rows_after_split"] == 0, qa
assert qa["intervention_target_segments"] == 34, qa
assert qa["selected_target_groups"] == [1, 2], qa

streets = gpd.read_file(D / "B0_baseline_streets.geojson")
targets = gpd.read_file(D / "intervention_targets.geojson")
graph = nx.Graph()
for _, row in streets.iterrows():
    graph.add_edge(int(row["u"]), int(row["v"]))
assert nx.number_connected_components(graph) == 1
assert len(streets) == qa["B0_segments"]
assert len(targets) == qa["intervention_target_segments"]

print("PASS: one connected Makkah OSM component")
print("PASS: Ibrahim Al Khalil OSM way present:", qa["required_way_id"])
print("PASS: required Makkah OSM nodes present:", qa["required_node_ids"])
print("PASS: no closed street geometries remain")
print("PASS: clean B0 baseline only; no scenario modifications")
print("PASS: reviewed Ibrahim intervention target geometry:", len(targets), "segments")
print("PASS: no synthetic demand or scenario policy introduced")
print(json.dumps(qa, indent=2, ensure_ascii=False))
