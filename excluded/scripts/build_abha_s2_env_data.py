"""Build S2 (Green Road) env data: S0 streets + hypothetical bypass road.

S2 adds a proposed bypass road connecting the Khamis Mushait approach (eastern
motorway entry) to the Sali area (southern network edge), allowing traffic to
avoid the congested central ring road.

IMPORTANT — HYPOTHETICAL ROUTE: The exact ASDA-proposed alignment is not yet
available. This script uses a placeholder route designed from the network
geography:
  - Start: existing node 2918462198 at (42.5177, 18.2282)
    — motorway_link junction on the eastern edge, main Khamis Mushait approach
  - End: existing node 1107465655 at (42.5114, 18.2130)
    — southern network edge, used here as the assumed direction toward Sali
  - Path: gentle southeast curve through the less-developed SE quadrant,
    8 segments (~2.3 km total), bidirectional secondary road
  - 7 new intermediate nodes (IDs 99000001–99000007) at waypoints
    along the curve
When ASDA provides the real geometry, replace GREEN_ROAD_WAYPOINTS below
and re-run.

Usage:
    python scripts/build_abha_s2_env_data.py
"""
from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------- #
# Green Road geometry — HYPOTHETICAL placeholder route                   #
# Replace these waypoints when ASDA provides the real alignment.         #
# Format: list of (lon, lat, node_id) tuples.                            #
# First and last entries reuse existing S0 node IDs; intermediate        #
# entries use synthetic IDs (99_000_001+).                               #
# --------------------------------------------------------------------- #
GREEN_ROAD_WAYPOINTS = [
    (42.5176878, 18.2281583, 2918462198),   # existing: motorway_link junction (Khamis Mushait approach)
    (42.5186,    18.2265,    99_000_001),    # WP1 — heading SE
    (42.5190,    18.2245,    99_000_002),    # WP2 — curving south
    (42.5186,    18.2225,    99_000_003),    # WP3 — turning SW
    (42.5175,    18.2205,    99_000_004),    # WP4 — continuing SW
    (42.5160,    18.2185,    99_000_005),    # WP5 — approaching Sali
    (42.5142,    18.2165,    99_000_006),    # WP6 — nearing south edge
    (42.5128,    18.2148,    99_000_007),    # WP7 — final approach
    (42.5113526, 18.2129547, 1107465655),   # existing: southern edge (Sali district)
]


def _haversine_m(lon1, lat1, lon2, lat2):
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def build_green_road_features(start_id: int) -> list[dict]:
    """Return GeoJSON features for the Green Road (paired forward + reverse)."""
    features = []
    seg_id = start_id
    wps = GREEN_ROAD_WAYPOINTS

    for i in range(len(wps) - 1):
        lon1, lat1, node1 = wps[i]
        lon2, lat2, node2 = wps[i + 1]
        length_m = _haversine_m(lon1, lat1, lon2, lat2)

        base_props = {
            "highway": "secondary",
            "junction": None,
            "lanes": "2",
            "maxspeed": "80",
            "name": "Green Road (proposed — hypothetical)",
            "oneway": False,
            "osmid": None,
            "length": length_m,
            "green_road": True,
            "scenario": "S2",
        }

        # Forward edge (u→v)
        fwd = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon1, lat1], [lon2, lat2]],
            },
            "properties": {
                **base_props,
                "u": node1,
                "v": node2,
                "key": 0,
                "road_segment_id": seg_id,
            },
        }
        features.append(fwd)
        seg_id += 1

        # Reverse edge (v→u)
        rev = {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [[lon2, lat2], [lon1, lat1]],
            },
            "properties": {
                **base_props,
                "u": node2,
                "v": node1,
                "key": 0,
                "road_segment_id": seg_id,
            },
        }
        features.append(rev)
        seg_id += 1

    return features


def main():
    s0_streets = ROOT / "data" / "raw" / "abha_s0" / "streets.geojson"
    if not s0_streets.exists():
        print(f"ERROR: S0 streets not found at {s0_streets}")
        print("Run `python scripts/build_abha_s0_env_data.py` first.")
        raise SystemExit(1)

    s0_data = json.loads(s0_streets.read_text(encoding="utf-8"))
    n_s0 = len(s0_data["features"])

    max_id = max(f["properties"].get("road_segment_id", 0) for f in s0_data["features"])
    green_features = build_green_road_features(start_id=max_id + 1)
    s0_data["features"].extend(green_features)

    n_total = len(s0_data["features"])
    n_green = len(green_features)

    total_length_m = sum(
        _haversine_m(*GREEN_ROAD_WAYPOINTS[i][:2], *GREEN_ROAD_WAYPOINTS[i + 1][:2])
        for i in range(len(GREEN_ROAD_WAYPOINTS) - 1)
    )

    out_dir = ROOT / "data" / "raw" / "abha_s2"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_streets = out_dir / "streets.geojson"
    out_streets.write_text(json.dumps(s0_data), encoding="utf-8")

    for name in ("residential.geojson", "amenities.geojson"):
        src = ROOT / "data" / "raw" / "abha_s0" / name
        dst = out_dir / name
        shutil.copy2(src, dst)

    print(f"S2 Green Road — hypothetical bypass (Khamis Mushait → Sali)")
    print(f"  S0 segments:       {n_s0}")
    print(f"  Green Road added:  {n_green} ({n_green // 2} edges × 2 directions)")
    print(f"  Total segments:    {n_total}")
    print(f"  Green Road length: {total_length_m:.0f} m ({total_length_m/1000:.1f} km)")
    print(f"  Waypoints:         {len(GREEN_ROAD_WAYPOINTS)}")
    print(f"  Connection east:   node {GREEN_ROAD_WAYPOINTS[0][2]} "
          f"({GREEN_ROAD_WAYPOINTS[0][0]:.4f}, {GREEN_ROAD_WAYPOINTS[0][1]:.4f})")
    print(f"  Connection south:  node {GREEN_ROAD_WAYPOINTS[-1][2]} "
          f"({GREEN_ROAD_WAYPOINTS[-1][0]:.4f}, {GREEN_ROAD_WAYPOINTS[-1][1]:.4f})")
    print(f"  -> {out_streets}")
    for name in ("residential.geojson", "amenities.geojson"):
        print(f"  -> {out_dir / name} (copied from S0)")
    print()
    print("NOTE: This route is a HYPOTHETICAL placeholder.")
    print("Replace GREEN_ROAD_WAYPOINTS when ASDA provides the real alignment.")


if __name__ == "__main__":
    main()
