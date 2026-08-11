"""Pull point-of-interest layers (schools, hospitals, mosques, traffic
signals, government buildings) and road-hierarchy attributes from
OpenStreetMap, for a study area already fetched with fetch_osm_data.py.

Companion to fetch_osm_data.py, not a replacement: that script gets the
routable street network + residential/amenity origin-destination layers this
project's env.py actually consumes. This one gets extra POI layers that are
useful for a written case study (siting a plaza near a school, checking a
proposed closure doesn't block hospital access) but aren't wired into
StreetNetworkEnv yet.

Run:
    python scripts/fetch_pois.py --radius 1000 --out data/raw/abha_pois --lat 18.2264426 --lon 42.5053914

Coverage warning (verified 2026-08-10 for Abha's Jory-picked neighborhood
point, NOT assumed): schools and mosques have real if thin coverage from
r=250m. Hospitals/clinics need r>=1000m to find anything near this specific
point -- 0 results at 250/500m is not a bug, this neighborhood just doesn't
have one within a short walk. Government buildings (all three tags below) and
traffic_signals came back with ZERO features up to r=2000m at this exact
point -- OSM appears to genuinely not have these mapped for this residential
neighborhood (they likely cluster in Abha's administrative/commercial core,
elsewhere in the city). Don't assume a bigger radius fixes this without
checking -- run scripts/check_zone_feasibility.py-style: print the count
before relying on it, same lesson as the Al Olaya commercial-core / 0
residential-buildings case documented in configs/city_madina.yaml.

lanes= tag coverage was 0/160 (r=250m walk network), 0/685 (r=500m walk
network), and 8/1208 (r=1000m *drive* network -- 0.66%) in the same check --
essentially absent from OSM for this area, not literally zero at every
radius but sparse enough to be unusable as a feature without a fallback
(e.g. imputing from `highway` classification instead). road_hierarchy.geojson
below still carries the `highway` classification (present for every edge;
that's not the missing part), it just won't usefully carry `lanes`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import osmnx as ox

# UTM 38N: metric CRS for centroid computation, matching fetch_osm_data.py's
# METRIC_CRS (this project's Abha/Riyadh scenarios all sit inside zone 38N).
METRIC_CRS = "EPSG:32638"

POI_TAGS = {
    "schools": {"amenity": "school"},
    "hospitals": {"amenity": "hospital"},
    "clinics": {"amenity": "clinic"},
    "mosques": {"amenity": "place_of_worship"},
    "traffic_signals": {"highway": "traffic_signals"},
    # OSM has no single consistent tag for "government building" -- these
    # three are the common candidates. Merged into one government.geojson
    # rather than 3 near-always-empty files.
    "government": [
        {"office": "government"},
        {"amenity": "townhall"},
        {"building": "government"},
    ],
}


def fetch_point_layer(name: str, tags, radius_m: float, center) -> gpd.GeoDataFrame | None:
    tag_list = tags if isinstance(tags, list) else [tags]
    frames = []
    for t in tag_list:
        try:
            gdf = ox.features_from_point(center, tags=t, dist=radius_m)
            if len(gdf):
                frames.append(gdf)
        except Exception as exc:  # osmnx raises InsufficientResponseError on 0 results
            print(f"    ({t}: 0 features -- {type(exc).__name__})")
    if not frames:
        print(f"[{name}] 0 features within {radius_m}m -- confirmed empty, not a fetch error")
        return None

    merged = gpd.GeoDataFrame(gpd.pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    # points only: a school/hospital mapped as a building polygon still needs
    # a single representative point for the same reason fetch_osm_data.py
    # collapses buildings to centroids. Project to a metric CRS first --
    # centroid on raw lat/lon degrees is measurably wrong, same fix
    # fetch_osm_data.py already applies to residential/amenity buildings.
    centroids_metric = merged.to_crs(METRIC_CRS).geometry.centroid
    merged["geometry"] = centroids_metric.to_crs(merged.crs)
    cols = [c for c in ("name", "geometry") if c in merged.columns]
    merged = merged[cols].reset_index(drop=True)
    print(f"[{name}] -> {len(merged)} features")
    return merged


def fetch_road_hierarchy(radius_m: float, center) -> gpd.GeoDataFrame:
    """Street network with `highway` (classification) and `lanes` kept, unlike
    fetch_osm_data.py's streets.geojson which drops every attribute but
    geometry. See module docstring: `lanes` is present in the schema but was
    empty in practice for Abha."""
    G = ox.graph_from_point(center, dist=radius_m, network_type="drive", simplify=True)
    G = ox.convert.to_undirected(G)
    _, edges = ox.graph_to_gdfs(G)
    edges = edges.reset_index(drop=True)

    def first(v):
        return v[0] if isinstance(v, list) else v

    out = gpd.GeoDataFrame(
        {
            "geometry": edges["geometry"],
            "highway": edges["highway"].apply(first) if "highway" in edges.columns else None,
            "lanes": edges["lanes"].apply(first) if "lanes" in edges.columns else None,
        },
        crs=edges.crs,
    )
    n_lanes = out["lanes"].notna().sum()
    print(f"[road_hierarchy] -> {len(out)} edges, {n_lanes}/{len(out)} with a lanes= tag")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=1000, help="Radius in meters (default: 1000 -- wider than fetch_osm_data.py's default because hospitals/clinics/government POIs are sparser than the street network itself)")
    ap.add_argument("--out", required=True, help="Output folder")
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    args = ap.parse_args()
    center = (args.lat, args.lon)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    for name, tags in POI_TAGS.items():
        gdf = fetch_point_layer(name, tags, args.radius, center)
        if gdf is not None:
            gdf.to_file(out_dir / f"{name}.geojson", driver="GeoJSON")

    roads = fetch_road_hierarchy(args.radius, center)
    roads.to_file(out_dir / "road_hierarchy.geojson", driver="GeoJSON")

    print(f"\nSaved to {out_dir}/")


if __name__ == "__main__":
    main()
