"""Pull a real street network + residential + amenity layers from OpenStreetMap
for the Riyadh (Al Olaya) case study, in the format MadinaBackend expects
(see configs/city_madina.yaml).

Run:
    conda activate snrl
    pip install osmnx
    python scripts/fetch_osm_data.py
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import osmnx as ox

# --- study area: central Riyadh (Al Olaya district), 3 km radius ---
CENTER_LAT, CENTER_LON = 24.6913, 46.6851   # King Fahd Rd / Tahlia St, Al Olaya
RADIUS_M = 3000
NETWORK_TYPE = "walk"  # pedestrian/bike project -> walkable network, not car-only roads

# UTM 38N: correct metric CRS for this longitude (~46.7E). Used only to compute
# areas accurately; saved files stay in EPSG:4326 (MadinaBackend reprojects itself).
METRIC_CRS = "EPSG:32638"

OUT_DIR = Path("data/raw/riyadh")

# OSM building tags we treat as "residential" (origins)
RESIDENTIAL_BUILDING_TYPES = {
    "residential", "house", "apartments", "detached", "terrace",
    "semidetached_house", "bungalow", "dormitory",
}


def fetch_streets() -> gpd.GeoDataFrame:
    print(f"[1/3] Downloading '{NETWORK_TYPE}' street network within {RADIUS_M}m of "
          f"({CENTER_LAT}, {CENTER_LON}) ...")
    G = ox.graph_from_point(
        (CENTER_LAT, CENTER_LON), dist=RADIUS_M, network_type=NETWORK_TYPE, simplify=True
    )
    _, edges = ox.graph_to_gdfs(G)
    edges = edges.reset_index(drop=True)[["geometry"]].copy()
    print(f"    -> {len(edges)} street segments")
    return edges


def fetch_residential() -> gpd.GeoDataFrame:
    print("[2/3] Downloading residential buildings (origins) ...")
    buildings = ox.features_from_point(
        (CENTER_LAT, CENTER_LON), tags={"building": True}, dist=RADIUS_M
    )
    buildings = buildings[buildings["building"].isin(RESIDENTIAL_BUILDING_TYPES)].copy()

    # centroid: madina snaps origin *points* onto the nearest street edge
    metric = buildings.to_crs(METRIC_CRS)
    footprint_area = metric.geometry.area
    buildings = buildings.set_geometry(buildings.geometry.centroid)

    # PLACEHOLDER proxy: no real census data yet, so estimate occupants from
    # footprint area (~30 m^2 per resident). Flag with mentor before the real run.
    buildings["residents"] = (footprint_area / 30.0).clip(lower=1.0).round(1)
    buildings = buildings.reset_index(drop=True)[["geometry", "residents"]]
    print(f"    -> {len(buildings)} residential buildings")
    return buildings


def fetch_amenities() -> gpd.GeoDataFrame:
    print("[3/3] Downloading amenities (destinations) ...")
    amenities = ox.features_from_point(
        (CENTER_LAT, CENTER_LON), tags={"amenity": True, "shop": True}, dist=RADIUS_M
    )

    metric = amenities.to_crs(METRIC_CRS)
    footprint_area = metric.geometry.area
    amenities = amenities.set_geometry(amenities.geometry.centroid)

    # PLACEHOLDER proxy: real floor_area only exists for polygon features;
    # point-only amenities (most shops/mosques in OSM) get a flat nominal value.
    amenities["floor_area"] = footprint_area.where(footprint_area > 0, 50.0).round(1)
    amenities = amenities.reset_index(drop=True)[["geometry", "floor_area"]]
    print(f"    -> {len(amenities)} amenities")
    return amenities


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    streets = fetch_streets()
    residential = fetch_residential()
    amenities = fetch_amenities()

    streets.to_file(OUT_DIR / "streets.geojson", driver="GeoJSON")
    residential.to_file(OUT_DIR / "residential.geojson", driver="GeoJSON")
    amenities.to_file(OUT_DIR / "amenities.geojson", driver="GeoJSON")

    print(f"\nSaved to {OUT_DIR}/ -- update configs/city_madina.yaml paths if needed.")


if __name__ == "__main__":
    main()
