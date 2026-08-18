#!/usr/bin/env python3
"""Validate Makkah Ibrahim B0 and network-safe geometry scenarios."""
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
    "S1_partial_closure_streets.geojson",
    "S1_partial_closure_targets.geojson",
    "S2_corridor_restriction_streets.geojson",
    "S2_corridor_restriction_targets.geojson",
    "S3_entry_direction_streets.geojson",
    "S3_entry_direction_targets.geojson",
    "S3_exit_direction_streets.geojson",
    "S3_exit_direction_targets.geojson",
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
assert qa["demand_status"] == "no synthetic demand added", qa
assert "forbid_disconnection=True" in qa["connectivity_rule"], qa

b0 = gpd.read_file(D / "B0_baseline_streets.geojson")
targets = gpd.read_file(D / "intervention_targets.geojson")
assert len(b0) == qa["B0_segments"]
assert len(targets) == qa["intervention_target_segments"]


def components(gdf):
    graph = nx.Graph()
    for _, row in gdf.iterrows():
        graph.add_edge(int(row["u"]), int(row["v"]))
    return nx.number_connected_components(graph)


assert components(b0) == 1
print("PASS: B0 connected and unchanged:", len(b0), "segments")
print("PASS: reviewed Ibrahim target geometry:", len(targets), "segments")

checks = [
    ("S1", "S1_partial_closure"),
    ("S2", "S2_corridor_restriction"),
    ("S3_entry", "S3_entry_direction"),
    ("S3_exit", "S3_exit_direction"),
]
for qa_key, stem in checks:
    streets = gpd.read_file(D / f"{stem}_streets.geojson")
    removed = gpd.read_file(D / f"{stem}_targets.geojson")
    expected = qa[qa_key]
    assert len(removed) == expected["removed_segments"], (qa_key, len(removed), expected)
    assert len(streets) == expected["remaining_segments"], (qa_key, len(streets), expected)
    assert len(streets) + len(removed) == len(b0), (qa_key, len(streets), len(removed), len(b0))
    actual_components = components(streets)
    assert actual_components == 1, (qa_key, "scenario disconnected", actual_components, expected)
    assert expected["remaining_components"] == 1, (qa_key, expected)
    assert expected["network_safe"] is True, (qa_key, expected)
    print(
        f"PASS: {qa_key} {expected['name']} — accepted {len(removed)}/"
        f"{expected['candidate_segments']} candidate closures; "
        f"blocked={expected['blocked_by_connectivity']}; connected=1"
    )

print("PASS: every Makkah scenario preserves one connected network")
print("PASS: connectivity filtering follows forbid_disconnection=True legality")
print("PASS: no synthetic demand introduced")
print(json.dumps(qa, indent=2, ensure_ascii=False))
