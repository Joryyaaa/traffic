"""Pull a real street network + residential + amenity layers from OpenStreetMap
for the Riyadh (Al Olaya) case study, in the format MadinaBackend expects
(see configs/city_madina.yaml).

Run (full 3km study area, the default):
    conda activate snrl
    python scripts/fetch_osm_data.py

Run (small radius, for a fast sanity check before committing to the full area):
    python scripts/fetch_osm_data.py --radius 400 --out data/raw/riyadh_smoketest
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import osmnx as ox

# --- study area: central Riyadh (Al Olaya district) ---
CENTER_LAT, CENTER_LON = 24.6913, 46.6851   # King Fahd Rd / Tahlia St, Al Olaya
NETWORK_TYPE = "walk"  # pedestrian/bike project -> walkable network, not car-only roads

# UTM 38N: correct metric CRS for this longitude (~46.7E). Used only to compute
# areas accurately; saved files stay in EPSG:4326 (MadinaBackend reprojects itself).
METRIC_CRS = "EPSG:32638"

# OSM building tags we treat as "residential" (origins)
RESIDENTIAL_BUILDING_TYPES = {
    "residential", "house", "apartments", "detached", "terrace",
    "semidetached_house", "bungalow", "dormitory",
}


def fetch_streets(radius_m: float) -> gpd.GeoDataFrame:
    print(f"[1/3] Downloading '{NETWORK_TYPE}' street network within {radius_m}m of "
          f"({CENTER_LAT}, {CENTER_LON}) ...")
    G = ox.graph_from_point(
        (CENTER_LAT, CENTER_LON), dist=radius_m, network_type=NETWORK_TYPE, simplify=True
    )
    _, edges = ox.graph_to_gdfs(G)
    edges = edges.reset_index(drop=True)[["geometry"]].copy()
    print(f"    -> {len(edges)} street segments")
    return edges


def fetch_residential(radius_m: float) -> gpd.GeoDataFrame:
    print("[2/3] Downloading residential buildings (origins) ...")
    buildings = ox.features_from_point(
        (CENTER_LAT, CENTER_LON), tags={"building": True}, dist=radius_m
    )
    buildings = buildings[buildings["building"].isin(RESIDENTIAL_BUILDING_TYPES)].copy()

    # Project first: centroid/area must be computed in meters, not degrees.
    metric = buildings.to_crs(METRIC_CRS)
    footprint_area = metric.geometry.area
    centroids = metric.geometry.centroid.to_crs(buildings.crs)
    buildings = buildings.set_geometry(centroids)

    # PLACEHOLDER proxy: no real census data yet, so estimate occupants from
    # footprint area (~30 m^2 per resident). Flag with mentor before the real run.
    buildings["residents"] = (footprint_area / 30.0).clip(lower=1.0).round(1)
    buildings = buildings.reset_index(drop=True)[["geometry", "residents"]]
    print(f"    -> {len(buildings)} residential buildings")
    return buildings


def fetch_amenities(radius_m: float) -> gpd.GeoDataFrame:
    print("[3/3] Downloading amenities (destinations) ...")
    amenities = ox.features_from_point(
        (CENTER_LAT, CENTER_LON), tags={"amenity": True, "shop": True}, dist=radius_m
    )

    metric = amenities.to_crs(METRIC_CRS)
    footprint_area = metric.geometry.area
    centroids = metric.geometry.centroid.to_crs(amenities.crs)
    amenities = amenities.set_geometry(centroids)

    # PLACEHOLDER proxy: real floor_area only exists for polygon features;
    # point-only amenities (most shops/mosques in OSM) get a flat nominal value.
    amenities["floor_area"] = footprint_area.where(footprint_area > 0, 50.0).round(1)
    amenities = amenities.reset_index(drop=True)[["geometry", "floor_area"]]
    print(f"    -> {len(amenities)} amenities")
    return amenities


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=3000, help="Radius in meters (default: 3000)")
    ap.add_argument("--out", default="data/raw/riyadh", help="Output folder")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    streets = fetch_streets(args.radius)
    residential = fetch_residential(args.radius)
    amenities = fetch_amenities(args.radius)

    streets.to_file(out_dir / "streets.geojson", driver="GeoJSON")
    residential.to_file(out_dir / "residential.geojson", driver="GeoJSON")
    amenities.to_file(out_dir / "amenities.geojson", driver="GeoJSON")

    print(f"\nSaved to {out_dir}/ -- update configs/city_madina.yaml paths if needed.")


if __name__ == "__main__":
    main()
