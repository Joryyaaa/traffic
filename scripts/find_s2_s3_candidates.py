"""Find S2 hub and S3 exit gate candidates using actual network shortest-path distance.

Builds the Madina-ready graph, computes shortest paths from origins,
and evaluates candidate vertices by network distance (not straight-line).
"""
from __future__ import annotations
import json, math, heapq
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
STREETS = ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "streets_madina_ready.geojson"
ORIGINS = ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "B0" / "origins.geojson"
EXIT_ORIGIN = ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km" / "S3" / "exit_origin.geojson"

SEARCH_RADIUS = 3500.0
CRS_ZONE = 36  # UTM 36N


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def to_utm(lat, lon):
    """Approximate UTM projection for zone 36N (NEOM area)."""
    import math
    lon0 = (CRS_ZONE - 1) * 6 - 180 + 3  # central meridian = 33
    x = (lon - lon0) * math.cos(math.radians(lat)) * 111319.49
    y = lat * 110574.27
    return x, y


def haversine_m(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def segment_length_m(coords):
    """Length in meters of a 2-point segment."""
    c0, c1 = coords
    return haversine_m(c0[1], c0[0], c1[1], c1[0])


def build_graph(streets_gj):
    """Build adjacency list graph from Madina-ready segments.

    Nodes are (lon, lat) tuples (matching GeoJSON coordinate order).
    Edge weights are segment lengths in meters.
    """
    adj = defaultdict(list)
    node_info = {}  # node -> list of parent_osm_ids touching it

    for feat in streets_gj["features"]:
        coords = feat["geometry"]["coordinates"]
        u = tuple(coords[0])
        v = tuple(coords[1])
        w = segment_length_m(coords)
        pid = feat["properties"]["parent_osm_id"]
        hw = feat["properties"]["highway"]

        adj[u].append((v, w, pid, hw))
        adj[v].append((u, w, pid, hw))

        node_info.setdefault(u, set()).add(pid)
        node_info.setdefault(v, set()).add(pid)

    return adj, node_info


def dijkstra(adj, source, max_dist=None):
    """Single-source Dijkstra. Returns {node: distance}."""
    dist = {source: 0.0}
    pq = [(0.0, source)]

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float("inf")):
            continue
        if max_dist and d > max_dist:
            continue
        for v, w, _, _ in adj[u]:
            nd = d + w
            if max_dist and nd > max_dist:
                continue
            if nd < dist.get(v, float("inf")):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))

    return dist


def snap_to_network(point_coords, adj, max_snap=5000):
    """Find the nearest network node to a point (by haversine)."""
    lon, lat = point_coords
    best_node = None
    best_d = float("inf")
    for node in adj:
        d = haversine_m(lat, lon, node[1], node[0])
        if d < best_d:
            best_d = d
            best_node = node
    return best_node, best_d


def main():
    print("Loading network and OD data...")
    streets_gj = load_json(STREETS)
    origins_gj = load_json(ORIGINS)
    exit_orig_gj = load_json(EXIT_ORIGIN)

    print(f"  {len(streets_gj['features'])} segments")
    adj, node_info = build_graph(streets_gj)
    print(f"  {len(adj)} graph nodes")

    # Snap all 21 origins to network
    print("\n--- Snapping origins to network ---")
    origin_nodes = []
    for feat in origins_gj["features"]:
        c = feat["geometry"]["coordinates"]
        node, snap_d = snap_to_network(c, adj)
        origin_nodes.append((node, feat["properties"]["osm_id"], snap_d))
        if snap_d > 500:
            print(f"  WARNING: origin {feat['properties']['osm_id']} snaps at {snap_d:.0f}m")

    print(f"  {len(origin_nodes)} origins snapped")

    # Compute shortest paths from each origin (up to search_radius * 1.5 for analysis)
    print("\n--- Computing shortest paths from all origins ---")
    origin_dists = {}  # {origin_osm_id: {node: dist}}
    for node, osm_id, _ in origin_nodes:
        origin_dists[osm_id] = dijkstra(adj, node, max_dist=SEARCH_RADIUS * 1.5)

    # ==================== S2 HUB ====================
    print("\n" + "=" * 60)
    print("S2 PARKING HUB ANALYSIS")
    print("=" * 60)

    # For each network node, count how many origins can reach it within search_radius
    print("\nEvaluating all network nodes as candidate hubs...")
    candidates = []
    for node in adj:
        reachable = 0
        total_dist = 0
        dists = []
        for osm_id in origin_dists:
            d = origin_dists[osm_id].get(node, float("inf"))
            if d <= SEARCH_RADIUS:
                reachable += 1
                total_dist += d
                dists.append(d)

        if reachable > 0:
            ways = node_info.get(node, set())
            candidates.append({
                "node": node,
                "reachable": reachable,
                "pct": reachable / len(origin_nodes) * 100,
                "mean_dist": total_dist / reachable,
                "max_dist": max(dists),
                "min_dist": min(dists),
                "ways": ways,
            })

    # Sort by reachable count (desc), then mean distance (asc)
    candidates.sort(key=lambda c: (-c["reachable"], c["mean_dist"]))

    print(f"\nTop 20 candidate hub vertices (by reachable origin count):")
    print(f"{'Rank':>4} {'Reach':>5} {'%':>6} {'MeanD':>7} {'MaxD':>7} {'Lat':>10} {'Lon':>10} {'Ways'}")
    for i, c in enumerate(candidates[:20]):
        ways_str = ",".join(str(w) for w in sorted(c["ways"]))
        print(f"{i+1:4d} {c['reachable']:5d} {c['pct']:5.1f}% {c['mean_dist']:7.0f} {c['max_dist']:7.0f} {c['node'][1]:10.6f} {c['node'][0]:10.6f} {ways_str}")

    # Best candidate
    if candidates:
        best = candidates[0]
        print(f"\n*** BEST S2 HUB: [{best['node'][1]:.6f}, {best['node'][0]:.6f}]")
        print(f"    Reachable: {best['reachable']}/{len(origin_nodes)} origins ({best['pct']:.1f}%)")
        print(f"    Network dist: min={best['min_dist']:.0f}m, mean={best['mean_dist']:.0f}m, max={best['max_dist']:.0f}m")
        print(f"    On ways: {sorted(best['ways'])}")

        # Show per-origin breakdown for the best
        print(f"\n    Per-origin network distance to best hub:")
        for node, osm_id, snap_d in origin_nodes:
            d = origin_dists[osm_id].get(best["node"], float("inf"))
            status = "REACHABLE" if d <= SEARCH_RADIUS else "UNREACHABLE"
            print(f"      origin {osm_id}: {d:.0f}m [{status}]")

    # ==================== S3 EXIT ====================
    print("\n" + "=" * 60)
    print("S3 EXIT GATE ANALYSIS")
    print("=" * 60)

    # Snap exit origin
    exit_c = exit_orig_gj["features"][0]["geometry"]["coordinates"]
    exit_node, exit_snap = snap_to_network(exit_c, adj)
    print(f"\nExit origin snapped to [{exit_node[1]:.6f}, {exit_node[0]:.6f}] ({exit_snap:.0f}m snap)")

    # Dijkstra from exit origin
    exit_dists = dijkstra(adj, exit_node, max_dist=SEARCH_RADIUS)

    print(f"\nReachable nodes within {SEARCH_RADIUS}m: {len(exit_dists)}")

    # Find candidate exit gates: prefer trunk/primary roads, southward direction
    print("\nCandidate exit gates on trunk/primary roads (within search_radius):")
    exit_candidates = []
    for node, d in exit_dists.items():
        if d < 100:  # too close to origin
            continue
        ways = node_info.get(node, set())
        # Check if any adjacent edge is trunk/primary
        trunk_ways = set()
        for neighbor, w, pid, hw in adj[node]:
            if hw in ("trunk", "primary"):
                trunk_ways.add(pid)
        if trunk_ways:
            exit_candidates.append({
                "node": node,
                "net_dist": d,
                "trunk_ways": trunk_ways,
                "all_ways": ways,
                "lat": node[1],
                "lon": node[0],
            })

    # Sort by network distance (want a meaningful gate, not too close)
    exit_candidates.sort(key=lambda c: -c["net_dist"])  # farthest within radius first

    print(f"\n{'Rank':>4} {'NetDist':>8} {'Lat':>10} {'Lon':>10} {'TrunkWays'}")
    for i, c in enumerate(exit_candidates[:15]):
        tw = ",".join(str(w) for w in sorted(c["trunk_ways"]))
        print(f"{i+1:4d} {c['net_dist']:8.0f} {c['lat']:10.6f} {c['lon']:10.6f} {tw}")

    if exit_candidates:
        # Choose the farthest trunk point within search_radius (best gate semantics)
        best_exit = exit_candidates[0]
        print(f"\n*** BEST S3 EXIT GATE: [{best_exit['lat']:.6f}, {best_exit['lon']:.6f}]")
        print(f"    Network distance from exit origin: {best_exit['net_dist']:.0f}m")
        print(f"    On trunk ways: {sorted(best_exit['trunk_ways'])}")
    else:
        print("\n*** NO trunk/primary candidates found within search_radius!")
        # Show all reachable nodes sorted by distance
        print("All reachable nodes (farthest first):")
        all_reachable = sorted(exit_dists.items(), key=lambda x: -x[1])
        for node, d in all_reachable[:20]:
            ways = node_info.get(node, set())
            hws = set()
            for neighbor, w, pid, hw in adj[node]:
                hws.add(hw)
            print(f"  {d:.0f}m: [{node[1]:.6f}, {node[0]:.6f}] ways={sorted(ways)} hw={sorted(hws)}")


if __name__ == "__main__":
    main()
