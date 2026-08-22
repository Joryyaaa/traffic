"""Derive a ~150-300 segment NEOM subgraph for the COMBINED GAT scale-up
experiment, by spatially clipping the already-fetched, already-committed
`neom-scenarios-existing-methodology` B0 network -- no new OSM fetch, no
synthesized data.

Source (read from that branch via `git show`, not checked out):
  data/neom_scenarios/sharma_camp26_r5km/streets_madina_ready.geojson
      2,398 edge-level segments, EPSG:32636, single connected component
      (2,247 nodes) -- the Madina-compatible derivative of the frozen B0
      baseline (commit 66b368e on neom-scenarios-existing-methodology).
  data/neom_scenarios/sharma_camp26_r5km/B0/origins.geojson
      21 real worker-origin points (17 dormitory buildings + 4 named
      anchors: Sharma village, Camp26, 2 construction camps).
  data/neom_scenarios/sharma_camp26_r5km/B0/destinations.geojson
      12 real construction-zone centroids.

Method (same "largest connected component of a radius clip" pattern this
project already used once, when `streets_largest_component.geojson` was
itself derived from `streets.geojson`):

  1. Anchor = centroid of the 17 real dormitory-building origins
     (35.2039997 E, 28.0037929 N) -- the densest real residential cluster
     in the B0 extent, adjacent to the western construction compound that
     S1's closure roads also sit in.
  2. Reproject to EPSG:32636 (meters), buffer the anchor by RADIUS_M,
     keep every street segment that intersects the buffer.
  3. Build a graph from segment endpoints (already 2-point segments in the
     Madina-ready source), take ONLY the largest connected component --
     drops small disconnected fragments/dangling stubs the circular clip
     creates at its boundary (same reason the original streets_largest_component
     step existed).
  4. Keep real origins/destinations whose point falls within the same
     buffer -- no new demand points invented, no weights changed.

Usage:
    python scripts/build_neom_gat_subgraph.py --radius 750 \
        --out data/neom_gat_subgraph/sharma_dorm_r750
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import geopandas as gpd
import networkx as nx
from shapely.geometry import Point

SOURCE_BRANCH = "origin/neom-scenarios-existing-methodology"
SOURCE_STREETS = "data/neom_scenarios/sharma_camp26_r5km/streets_madina_ready.geojson"
SOURCE_ORIGINS = "data/neom_scenarios/sharma_camp26_r5km/B0/origins.geojson"
SOURCE_DESTINATIONS = "data/neom_scenarios/sharma_camp26_r5km/B0/destinations.geojson"


def _git_show(ref: str, path: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        subprocess.run(["git", "show", f"{ref}:{path}"], check=True, stdout=f)


def _resolve_commit(ref: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", ref], check=True, capture_output=True, text=True
    ).stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=750.0,
                     help="clip radius in meters around the dormitory-cluster anchor")
    ap.add_argument("--out", required=True, help="output directory for the subgraph")
    ap.add_argument("--cache", default="tmp_inspect", help="scratch dir for the raw source files")
    args = ap.parse_args()

    cache = Path(args.cache)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    src_commit = _resolve_commit(SOURCE_BRANCH)

    streets_raw = cache / "streets_full.geojson"
    origins_raw = cache / "origins_full.geojson"
    dests_raw = cache / "destinations_full.geojson"
    if not streets_raw.exists():
        _git_show(SOURCE_BRANCH, SOURCE_STREETS, streets_raw)
    if not origins_raw.exists():
        _git_show(SOURCE_BRANCH, SOURCE_ORIGINS, origins_raw)
    if not dests_raw.exists():
        _git_show(SOURCE_BRANCH, SOURCE_DESTINATIONS, dests_raw)

    streets = gpd.read_file(streets_raw)
    origins = gpd.read_file(origins_raw)
    dests = gpd.read_file(dests_raw)

    # Anchor: centroid of the 17 real dormitory-building origins (WGS84 lon/lat)
    dorms = origins[origins["origin_type"] == "residential_building"]
    anchor_lon = float(dorms.geometry.x.mean())
    anchor_lat = float(dorms.geometry.y.mean())

    crs = "EPSG:32636"
    streets_p = streets.to_crs(crs)
    origins_p = origins.to_crs(crs)
    dests_p = dests.to_crs(crs)
    anchor_p = gpd.GeoSeries([Point(anchor_lon, anchor_lat)], crs="EPSG:4326").to_crs(crs).iloc[0]

    buf = anchor_p.buffer(args.radius)
    sel = streets_p[streets_p.intersects(buf)].copy().reset_index(drop=True)

    G = nx.Graph()
    for i, geom in enumerate(sel.geometry):
        coords = list(geom.coords)
        a = (round(coords[0][0], 3), round(coords[0][1], 3))
        b = (round(coords[-1][0], 3), round(coords[-1][1], 3))
        G.add_edge(a, b, seg_idx=i)

    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    largest_nodes = comps[0]
    largest_edges = sorted(
        d["seg_idx"] for u, v, d in G.edges(data=True) if u in largest_nodes and v in largest_nodes
    )
    dropped_components = len(comps) - 1
    dropped_segments = len(sel) - len(largest_edges)

    final_streets_p = sel.iloc[largest_edges].reset_index(drop=True)
    final_streets_p["segment_id"] = range(len(final_streets_p))

    o_sel = origins_p[origins_p.within(buf)].reset_index(drop=True)
    d_sel = dests_p[dests_p.within(buf)].reset_index(drop=True)

    # write outputs in the network's working CRS (EPSG:32636) -- matches
    # what every other config in this lineage does (streets/origins/dest
    # files carry their own CRS; the config's `network.crs` reprojects on load)
    final_streets_p.to_crs("EPSG:4326").to_file(out / "streets.geojson", driver="GeoJSON")
    o_sel.to_crs("EPSG:4326").to_file(out / "origins.geojson", driver="GeoJSON")
    d_sel.to_crs("EPSG:4326").to_file(out / "destinations.geojson", driver="GeoJSON")

    n_segments = len(final_streets_p)
    n_origins = len(o_sel)
    n_dests = len(d_sel)

    provenance = {
        "source_branch": SOURCE_BRANCH,
        "source_commit": src_commit,
        "source_streets_path": SOURCE_STREETS,
        "source_origins_path": SOURCE_ORIGINS,
        "source_destinations_path": SOURCE_DESTINATIONS,
        "source_total_segments": int(len(streets)),
        "anchor": {
            "method": "centroid of the 17 real dormitory-building B0 origins",
            "lon": anchor_lon,
            "lat": anchor_lat,
        },
        "radius_m": args.radius,
        "clip_crs": crs,
        "segments_intersecting_buffer": int(len(sel)),
        "connected_components_in_clip": len(comps),
        "component_sizes_by_segment_count": None,  # filled below
        "dropped_components": dropped_components,
        "dropped_segments_not_in_largest_component": dropped_segments,
        "final_segment_count": n_segments,
        "final_origin_count": n_origins,
        "final_destination_count": n_dests,
    }
    # per-component segment counts, for the record
    comp_sizes = []
    for c in comps:
        cnt = sum(1 for u, v, d in G.edges(data=True) if u in c and v in c)
        comp_sizes.append(cnt)
    provenance["component_sizes_by_segment_count"] = sorted(comp_sizes, reverse=True)

    (out / "provenance.json").write_text(json.dumps(provenance, indent=2))

    print(f"anchor: {anchor_lat:.7f} N, {anchor_lon:.7f} E (dormitory-cluster centroid)")
    print(f"radius: {args.radius} m")
    print(f"segments intersecting buffer: {len(sel)}")
    print(f"connected components: {len(comps)} (sizes by segment count: {sorted(comp_sizes, reverse=True)})")
    print(f"FINAL (largest component only): {n_segments} segments, {n_origins} origins, {n_dests} destinations")
    print(f"wrote -> {out}/streets.geojson, origins.geojson, destinations.geojson, provenance.json")


if __name__ == "__main__":
    main()
