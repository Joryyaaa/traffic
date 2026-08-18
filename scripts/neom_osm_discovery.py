"""NEOM OSM baseline discovery — evaluate candidate study areas.

Queries Overpass API for two NEOM candidates at multiple radii,
analyses drive-network quality, and generates HTML maps.

Usage:
    python scripts/neom_osm_discovery.py
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import requests

OUT = Path("results/neom_baseline_discovery")
CACHE = OUT / "cache"
MAPS = OUT / "maps"
for d in (CACHE, MAPS):
    d.mkdir(parents=True, exist_ok=True)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MAX_RETRIES = 3
RETRY_DELAY = 10  # seconds

DRIVE_HIGHWAY_CLASSES = {
    "motorway", "motorway_link", "trunk", "trunk_link",
    "primary", "primary_link", "secondary", "secondary_link",
    "tertiary", "tertiary_link", "residential", "living_street",
    "unclassified", "service", "track",
}

# ── Candidate definitions ─────────────────────────────────────────────

CANDIDATES = {
    "A_sharma_camp26": {
        "label": "Sharma / Camp 26 cluster",
        "center": (28.03066, 35.24203),  # Sharma node
        "anchors": {
            "Sharma (node 5796927641)": {"type": "node", "id": 5796927641, "coord": (28.03066, 35.24203)},
            "NEOM Residential Camp 26 (node 12390325515)": {"type": "node", "id": 12390325515, "coord": (28.08092, 35.21466)},
            "Construction Camp Housing W1 (way 849104049)": {"type": "way", "id": 849104049, "coord": (28.01902, 35.18886)},
            "Construction Camp Housing W2 (way 849118868)": {"type": "way", "id": 849118868, "coord": (28.00619, 35.18831)},
        },
        "radii_km": [1, 2, 3, 5],
    },
    "B_trojena": {
        "label": "Trojena",
        "center": (28.67381, 35.30361),
        "anchors": {
            "Trojena (way 1216974546)": {"type": "way", "id": 1216974546, "coord": (28.67381, 35.30361)},
        },
        "radii_km": [1, 2, 3, 5],
    },
}

# The anchors for Candidate A span ~10 km, so also test from a midpoint
# that better covers all 4 anchors — but only at the 5km radius.
CANDIDATES["A_sharma_camp26"]["alt_centers"] = {
    "midpoint_all_anchors": {
        "coord": (28.035, 35.21),
        "radii_km": [5],
    },
}


def overpass_query(query: str) -> dict:
    """Run an Overpass query with caching and retries."""
    h = hashlib.sha256(query.encode()).hexdigest()[:16]
    cache_path = CACHE / f"overpass_{h}.json"
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = requests.post(OVERPASS_URL, data={"data": query}, timeout=120)
            if r.status_code == 429:
                wait = RETRY_DELAY * attempt
                print(f"  [rate-limited, waiting {wait}s...]")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            cache_path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except Exception as e:
            if attempt < MAX_RETRIES:
                print(f"  [attempt {attempt} failed: {e}, retrying in {RETRY_DELAY}s...]")
                time.sleep(RETRY_DELAY)
            else:
                print(f"  [FAILED after {MAX_RETRIES} attempts: {e}]")
                raise
    return {}


def bbox_from_center_radius(lat: float, lon: float, radius_km: float):
    """Return (south, west, north, east) bounding box."""
    d_lat = radius_km / 111.32
    d_lon = radius_km / (111.32 * math.cos(math.radians(lat)))
    return (lat - d_lat, lon - d_lon, lat + d_lat, lon + d_lon)


def query_area(lat: float, lon: float, radius_km: float) -> dict:
    """Query roads, buildings, amenities, landuse for a bounded area."""
    bbox = bbox_from_center_radius(lat, lon, radius_km)
    bb = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"

    q = f"""
[out:json][timeout:60];
(
  way["highway"~"^(motorway|motorway_link|trunk|trunk_link|primary|primary_link|secondary|secondary_link|tertiary|tertiary_link|residential|living_street|unclassified|service|track)$"]({bb});
  way["building"]({bb});
  node["amenity"]({bb});
  way["amenity"]({bb});
  way["landuse"]({bb});
  way["landuse"="construction"]({bb});
  node["place"]({bb});
);
out body;
>;
out skel qt;
"""
    return overpass_query(q)


def query_anchors(anchor_ids: list[tuple[str, int]]) -> dict:
    """Fetch specific OSM elements by type+id. Cached separately."""
    parts = []
    for osm_type, osm_id in anchor_ids:
        parts.append(f"{osm_type}({osm_id});")
    if not parts:
        return {"elements": []}
    q = "[out:json][timeout:30];\n(\n  " + "\n  ".join(parts) + "\n);\nout body;\n>;\nout skel qt;"
    return overpass_query(q)


def build_graph(elements: list) -> dict:
    """Build adjacency from OSM way elements. Returns analysis dict."""
    nodes = {}
    ways = []
    for el in elements:
        if el["type"] == "node":
            nodes[el["id"]] = (el.get("lat", 0), el.get("lon", 0))
        elif el["type"] == "way" and "tags" in el:
            tags = el.get("tags", {})
            hw = tags.get("highway", "")
            if hw in DRIVE_HIGHWAY_CLASSES:
                ways.append(el)

    adj: dict[int, set[int]] = defaultdict(set)
    segments = 0
    hw_classes: Counter = Counter()
    named_roads: set[str] = set()
    way_ids: list[int] = []

    for w in ways:
        nds = w.get("nodes", [])
        hw = w["tags"].get("highway", "unknown")
        name = w["tags"].get("name", "")
        hw_classes[hw] += 1
        way_ids.append(w["id"])
        if name:
            named_roads.add(name)
        for i in range(len(nds) - 1):
            a, b = nds[i], nds[i + 1]
            adj[a].add(b)
            adj[b].add(a)
            segments += 1

    # Connected components (BFS)
    visited: set[int] = set()
    components: list[int] = []
    for start in adj:
        if start in visited:
            continue
        queue = [start]
        visited.add(start)
        size = 0
        while queue:
            u = queue.pop()
            size += 1
            for v in adj[u]:
                if v not in visited:
                    visited.add(v)
                    queue.append(v)
        components.append(size)

    components.sort(reverse=True)

    return {
        "segment_count": segments,
        "node_count": len(adj),
        "way_count": len(ways),
        "connected_components": len(components),
        "largest_component": components[0] if components else 0,
        "component_sizes": components[:10],
        "highway_classes": dict(hw_classes.most_common()),
        "named_roads": sorted(named_roads),
        "named_road_count": len(named_roads),
        "way_ids_sample": way_ids[:20],
        "nodes": nodes,
        "ways": ways,
    }


def analyse_features(elements: list, bbox: tuple) -> dict:
    """Count buildings, amenities, landuse within bbox."""
    s, w, n, e = bbox
    buildings = []
    amenities = []
    landuse = []
    construction = []
    places = []

    for el in elements:
        tags = el.get("tags", {})
        if not tags:
            continue

        if tags.get("building"):
            btype = tags.get("building", "yes")
            bname = tags.get("name", "")
            buildings.append({"type": btype, "name": bname, "id": el["id"],
                              "osm_type": el["type"]})

        if tags.get("amenity"):
            atype = tags.get("amenity", "")
            aname = tags.get("name", "")
            amenities.append({"type": atype, "name": aname, "id": el["id"],
                              "osm_type": el["type"]})

        lu = tags.get("landuse", "")
        if lu:
            landuse.append({"type": lu, "name": tags.get("name", ""),
                            "id": el["id"], "osm_type": el["type"]})

        if tags.get("construction") or lu == "construction":
            construction.append({"tags": tags, "id": el["id"],
                                  "osm_type": el["type"]})

        if tags.get("place"):
            lat = el.get("lat", 0)
            lon = el.get("lon", 0)
            places.append({"name": tags.get("name", ""), "place": tags["place"],
                           "lat": lat, "lon": lon, "id": el["id"]})

    building_types = Counter(b["type"] for b in buildings)
    amenity_types = Counter(a["type"] for a in amenities)
    landuse_types = Counter(l["type"] for l in landuse)
    residential_buildings = sum(1 for b in buildings
                                if b["type"] in ("residential", "apartments", "house",
                                                  "dormitory", "detached", "semidetached_house"))
    camp_landuse = sum(1 for l in landuse if "camp" in l.get("name", "").lower()
                       or l["type"] in ("military", "residential"))

    return {
        "building_count": len(buildings),
        "building_types": dict(building_types.most_common(15)),
        "residential_building_count": residential_buildings,
        "amenity_count": len(amenities),
        "amenity_types": dict(amenity_types.most_common(15)),
        "landuse_count": len(landuse),
        "landuse_types": dict(landuse_types.most_common(10)),
        "construction_count": len(construction),
        "construction_items": construction[:10],
        "camp_related_landuse": camp_landuse,
        "places": places,
        "buildings_sample": buildings[:10],
        "amenities_sample": amenities[:10],
    }


def check_anchors(elements: list, anchors: dict) -> dict:
    """Check which anchor features are present in the downloaded data."""
    el_ids = {}
    for el in elements:
        key = (el["type"], el["id"])
        el_ids[key] = el

    results = {}
    for name, info in anchors.items():
        key = (info["type"], info["id"])
        found = key in el_ids
        results[name] = {
            "found": found,
            "type": info["type"],
            "id": info["id"],
            "expected_coord": info["coord"],
        }
        if found:
            el = el_ids[key]
            if "lat" in el:
                results[name]["actual_coord"] = (el["lat"], el["lon"])
            results[name]["tags"] = el.get("tags", {})
    return results


def generate_html_map(candidate_key: str, radius_km: float, center: tuple,
                      graph_info: dict, features: dict, anchor_results: dict,
                      bbox: tuple) -> str:
    """Generate a Leaflet HTML map."""
    nodes = graph_info["nodes"]
    ways = graph_info["ways"]

    road_features = []
    for w in ways:
        coords = []
        for nid in w.get("nodes", []):
            if nid in nodes:
                lat, lon = nodes[nid]
                coords.append([lat, lon])
        if len(coords) >= 2:
            hw = w["tags"].get("highway", "unknown")
            name = w["tags"].get("name", "")
            road_features.append({
                "coords": coords,
                "highway": hw,
                "name": name,
                "id": w["id"],
            })

    anchor_markers = []
    for name, info in anchor_results.items():
        coord = info.get("actual_coord", info["expected_coord"])
        anchor_markers.append({
            "lat": coord[0], "lon": coord[1],
            "name": name, "found": info["found"],
        })

    amenity_markers = []
    for a in features.get("amenities_sample", []):
        pass  # We'll add these from the raw elements

    hw_colors = {
        "motorway": "#e74c3c", "motorway_link": "#e74c3c",
        "trunk": "#e67e22", "trunk_link": "#e67e22",
        "primary": "#f39c12", "primary_link": "#f39c12",
        "secondary": "#27ae60", "secondary_link": "#27ae60",
        "tertiary": "#2980b9", "tertiary_link": "#2980b9",
        "residential": "#8e44ad", "living_street": "#8e44ad",
        "unclassified": "#7f8c8d", "service": "#95a5a6",
        "track": "#bdc3c7",
    }

    roads_js = json.dumps(road_features)
    anchors_js = json.dumps(anchor_markers)
    hw_colors_js = json.dumps(hw_colors)
    clat, clon = center
    stats_html = (
        f"Segments: {graph_info['segment_count']} | "
        f"Components: {graph_info['connected_components']} | "
        f"Largest: {graph_info['largest_component']} | "
        f"Named roads: {graph_info['named_road_count']} | "
        f"Buildings: {features['building_count']} | "
        f"Amenities: {features['amenity_count']} | "
        f"Construction: {features['construction_count']}"
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{candidate_key} r={radius_km}km</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  body {{ margin: 0; font-family: sans-serif; }}
  #map {{ width: 100%; height: calc(100vh - 50px); }}
  #stats {{ background: #222; color: #eee; padding: 8px 16px; font-size: 13px;
            height: 50px; display: flex; align-items: center; }}
  .legend {{ background: white; padding: 8px; border-radius: 4px;
             font-size: 11px; line-height: 1.6; }}
  .legend i {{ width: 14px; height: 3px; display: inline-block; margin-right: 4px;
               vertical-align: middle; }}
</style>
</head>
<body>
<div id="stats">{stats_html}</div>
<div id="map"></div>
<script>
var map = L.map('map').setView([{clat}, {clon}], 13);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  maxZoom: 19,
  attribution: '&copy; OpenStreetMap contributors'
}}).addTo(map);

// Draw radius circle
L.circle([{clat}, {clon}], {{
  radius: {radius_km * 1000},
  color: '#e74c3c', fillColor: '#e74c3c', fillOpacity: 0.05,
  weight: 2, dashArray: '8 4'
}}).addTo(map);

// Center marker
L.marker([{clat}, {clon}], {{
  icon: L.divIcon({{className: '', html: '<div style="background:#e74c3c;width:12px;height:12px;border-radius:50%;border:2px solid white;"></div>'}})
}}).addTo(map).bindPopup('Center ({clat:.5f}, {clon:.5f})');

// Roads
var hwColors = {hw_colors_js};
var roads = {roads_js};
roads.forEach(function(r) {{
  var color = hwColors[r.highway] || '#999';
  var weight = (r.highway === 'motorway' || r.highway === 'trunk') ? 4 :
               (r.highway === 'primary' || r.highway === 'secondary') ? 3 : 2;
  L.polyline(r.coords, {{color: color, weight: weight, opacity: 0.8}})
    .addTo(map)
    .bindPopup(r.highway + (r.name ? ': ' + r.name : '') + '<br>way/' + r.id);
}});

// Anchor markers
var anchors = {anchors_js};
anchors.forEach(function(a) {{
  var color = a.found ? '#27ae60' : '#e74c3c';
  var icon = L.divIcon({{
    className: '',
    html: '<div style="background:' + color + ';width:16px;height:16px;border-radius:50%;border:3px solid white;box-shadow:0 0 4px rgba(0,0,0,0.5);"></div>',
    iconSize: [16, 16], iconAnchor: [8, 8]
  }});
  L.marker([a.lat, a.lon], {{icon: icon}}).addTo(map)
    .bindPopup('<b>' + a.name + '</b><br>' + (a.found ? 'FOUND' : 'NOT IN EXTENT'));
}});

// Legend
var legend = L.control({{position: 'bottomright'}});
legend.onAdd = function() {{
  var div = L.DomUtil.create('div', 'legend');
  div.innerHTML = '<b>Highway classes</b><br>';
  var classes = ['motorway','trunk','primary','secondary','tertiary','residential','service','track'];
  classes.forEach(function(c) {{
    div.innerHTML += '<i style="background:' + (hwColors[c]||'#999') + '"></i>' + c + '<br>';
  }});
  div.innerHTML += '<br><b>Anchors</b><br>';
  div.innerHTML += '<i style="background:#27ae60;width:10px;height:10px;border-radius:50%;"></i> Found<br>';
  div.innerHTML += '<i style="background:#e74c3c;width:10px;height:10px;border-radius:50%;"></i> Not in extent<br>';
  return div;
}};
legend.addTo(map);

// Fit to roads
if (roads.length > 0) {{
  var allCoords = [];
  roads.forEach(function(r) {{ allCoords = allCoords.concat(r.coords); }});
  map.fitBounds(allCoords);
}}
</script>
</body>
</html>"""
    return html


def assess_suitability(graph: dict, features: dict, radius_km: float) -> dict:
    """Quick suitability assessment."""
    seg = graph["segment_count"]
    comps = graph["connected_components"]
    largest = graph["largest_component"]
    buildings = features["building_count"]
    amenities = features["amenity_count"]
    res_buildings = features["residential_building_count"]

    largest_frac = largest / max(graph["node_count"], 1)

    assessment = {
        "sufficient_segments": seg >= 30,
        "mostly_connected": largest_frac > 0.7 if comps > 0 else False,
        "has_buildings": buildings > 0,
        "has_amenities": amenities > 0,
        "has_residential": res_buildings > 0,
        "meaningful_network": seg >= 50 and comps <= 5 and largest_frac > 0.6,
    }
    assessment["verdict"] = (
        "GOOD" if all(assessment.values()) else
        "MARGINAL" if assessment["sufficient_segments"] and assessment["mostly_connected"] else
        "SPARSE"
    )
    return assessment


def run_candidate(key: str, spec: dict):
    """Run discovery for one candidate at all radii."""
    print(f"\n{'='*70}")
    print(f"CANDIDATE: {spec['label']} ({key})")
    print(f"Center: {spec['center']}")
    print(f"Radii: {spec['radii_km']} km")
    print(f"{'='*70}")

    results = {}

    # Fetch anchor elements once for the whole candidate
    anchor_ids = [(a["type"], a["id"]) for a in spec["anchors"].values()]
    print("  Fetching anchor elements...")
    try:
        anchor_data = query_anchors(anchor_ids)
        anchor_elements = anchor_data.get("elements", [])
        print(f"  Got {len(anchor_elements)} anchor elements")
    except Exception as e:
        print(f"  Anchor fetch failed: {e}")
        anchor_elements = []

    # Build list of (center_name, center_coord, radii) to test
    test_configs = [("primary", spec["center"], spec["radii_km"])]
    if "alt_centers" in spec:
        for name, alt in spec["alt_centers"].items():
            test_configs.append((name, alt["coord"], alt["radii_km"]))

    for center_name, center, radii in test_configs:
        for r_km in radii:
            tag = f"{key}_{center_name}_r{r_km}km"
            print(f"\n--- {tag} ---")
            print(f"  Center: {center}, Radius: {r_km} km")

            bbox = bbox_from_center_radius(center[0], center[1], r_km)
            print(f"  Bbox: {bbox[0]:.4f},{bbox[1]:.4f},{bbox[2]:.4f},{bbox[3]:.4f}")

            print("  Querying Overpass...")
            try:
                data = query_area(center[0], center[1], r_km)
            except Exception as e:
                print(f"  OVERPASS FAILED: {e}")
                results[tag] = {"error": str(e)}
                continue

            elements = data.get("elements", [])
            print(f"  Downloaded {len(elements)} elements")

            # Merge anchor elements for anchor checking
            all_elements = elements + anchor_elements

            print("  Building graph...")
            graph = build_graph(elements)
            print(f"  Segments: {graph['segment_count']}, "
                  f"Components: {graph['connected_components']}, "
                  f"Largest: {graph['largest_component']}")

            print("  Analysing features...")
            features = analyse_features(elements, bbox)
            print(f"  Buildings: {features['building_count']}, "
                  f"Amenities: {features['amenity_count']}, "
                  f"Construction: {features['construction_count']}")

            print("  Checking anchors...")
            anchor_results = check_anchors(all_elements, spec["anchors"])
            for aname, ainfo in anchor_results.items():
                status = "FOUND" if ainfo["found"] else "NOT FOUND"
                print(f"    {aname}: {status}")

            assessment = assess_suitability(graph, features, r_km)
            print(f"  Verdict: {assessment['verdict']}")

            # Generate map
            if graph["segment_count"] > 0:
                print("  Generating map...")
                html = generate_html_map(key, r_km, center, graph, features,
                                         anchor_results, bbox)
                map_path = MAPS / f"map_{tag}.html"
                map_path.write_text(html, encoding="utf-8")
                print(f"  Map: {map_path}")
            else:
                map_path = None
                print("  No segments — skipping map.")

            result = {
                "center": center,
                "center_name": center_name,
                "radius_km": r_km,
                "bbox": bbox,
                "graph": {k: v for k, v in graph.items()
                          if k not in ("nodes", "ways")},
                "features": {k: v for k, v in features.items()
                             if k not in ("buildings_sample", "amenities_sample",
                                          "construction_items")},
                "anchor_results": anchor_results,
                "assessment": assessment,
                "map_path": str(map_path) if map_path else None,
            }
            results[tag] = result

            # Small delay between queries to avoid rate limiting
            time.sleep(2)

    return results


def print_comparison(all_results: dict):
    """Print final comparison table."""
    print("\n" + "=" * 80)
    print("COMPARISON TABLE")
    print("=" * 80)

    header = (f"{'Tag':<45} {'Seg':>5} {'Comp':>5} {'Lrg':>5} "
              f"{'Named':>5} {'Bldg':>5} {'Amen':>5} {'Cons':>5} "
              f"{'Anchors':>8} {'Verdict':<10}")
    print(header)
    print("-" * len(header))

    for tag, r in sorted(all_results.items()):
        if "error" in r:
            print(f"{tag:<45} ERROR: {r['error']}")
            continue
        g = r["graph"]
        f = r["features"]
        n_anchors_found = sum(1 for v in r["anchor_results"].values() if v["found"])
        n_anchors_total = len(r["anchor_results"])
        verdict = r["assessment"]["verdict"]
        print(f"{tag:<45} {g['segment_count']:>5} {g['connected_components']:>5} "
              f"{g['largest_component']:>5} {g['named_road_count']:>5} "
              f"{f['building_count']:>5} {f['amenity_count']:>5} "
              f"{f['construction_count']:>5} {n_anchors_found:>3}/{n_anchors_total:<3} "
              f"{verdict:<10}")


def main():
    print("NEOM OSM Baseline Discovery")
    print(f"Output: {OUT}")
    print(f"Cache: {CACHE}")
    print()

    all_results = {}

    for key, spec in CANDIDATES.items():
        results = run_candidate(key, spec)
        all_results.update(results)
        # Save intermediate results
        out_path = OUT / f"discovery_{key}.json"
        out_path.write_text(json.dumps(results, indent=2, default=str),
                            encoding="utf-8")
        print(f"\n  Results saved to {out_path}")

    # Save combined results
    combined_path = OUT / "discovery_combined.json"
    combined_path.write_text(json.dumps(all_results, indent=2, default=str),
                             encoding="utf-8")
    print(f"\nCombined results: {combined_path}")

    print_comparison(all_results)

    # List maps
    maps = sorted(MAPS.glob("*.html"))
    if maps:
        print(f"\nHTML maps ({len(maps)}):")
        for m in maps:
            print(f"  {m}")

    print("\nDISCOVERY COMPLETE — review the comparison table and maps,")
    print("then choose the final fixed NEOM baseline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
