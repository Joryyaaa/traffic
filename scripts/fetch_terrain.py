"""Pull elevation data for a study area from Open Topo Data's public SRTM
API (https://www.opentopodata.org/) -- no account, no API key.

Verified working 2026-08-10 for Abha's neighborhood point: a single query at
(18.2264426, 42.5053914) returned 2225m, consistent with Asir's known
high-altitude terrain. This matters more for Abha than for Riyadh/Jeddah --
mountain terrain plausibly changes which street closures are walkable at all,
something flat-plateau/coastal Riyadh and Jeddah can't test.

This is a *point* API, not a bulk raster download: max 100 locations per
call, max 1 call/sec, max 1000 calls/day on the free tier (rate limits
enforced by their server -- this script respects them client-side too, but a
very large --radius/small --spacing combination can still burn through the
daily cap). For bulk/offline DEM tiles instead, OpenTopography.org's SRTM GL1
raster requires a free API key (unlike this endpoint) -- not used here to
keep this script credential-free.

Run:
    python scripts/fetch_terrain.py --radius 1000 --out data/raw/abha_terrain --lat 18.2264426 --lon 42.5053914
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import requests
from pyproj import Transformer
from shapely.geometry import Point

API_URL = "https://api.opentopodata.org/v1/srtm30m"
BATCH_SIZE = 100
SECONDS_PER_CALL = 1.1  # stay under the API's 1 call/sec limit with margin


def build_grid(center: tuple[float, float], radius_m: float, spacing_m: float) -> list[tuple[float, float]]:
    lat, lon = center
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32638", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:32638", "EPSG:4326", always_xy=True)
    cx, cy = to_utm.transform(lon, lat)

    n = int(radius_m // spacing_m) + 1
    points = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            x, y = cx + i * spacing_m, cy + j * spacing_m
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius_m**2:
                lon2, lat2 = to_wgs.transform(x, y)
                points.append((lat2, lon2))
    return points


def query_elevations(points: list[tuple[float, float]]) -> list[float]:
    elevations = []
    for i in range(0, len(points), BATCH_SIZE):
        batch = points[i : i + BATCH_SIZE]
        locs = "|".join(f"{lat},{lon}" for lat, lon in batch)
        r = requests.get(API_URL, params={"locations": locs}, timeout=30)
        r.raise_for_status()
        data = r.json()
        if data["status"] != "OK":
            raise RuntimeError(f"Open Topo Data returned status={data['status']}")
        elevations.extend(res["elevation"] for res in data["results"])
        print(f"  {min(i + BATCH_SIZE, len(points))}/{len(points)} points queried", flush=True)
        if i + BATCH_SIZE < len(points):
            time.sleep(SECONDS_PER_CALL)
    return elevations


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=1000, help="Radius in meters (default: 1000)")
    ap.add_argument("--spacing", type=float, default=100, help="Grid spacing in meters (default: 100 -- SRTM itself is ~30m native resolution, finer spacing mostly re-samples the same cell and burns API calls)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    args = ap.parse_args()

    points = build_grid((args.lat, args.lon), args.radius, args.spacing)
    print(f"[1/2] Querying elevation for {len(points)} grid points (spacing={args.spacing}m) ...")
    if len(points) > 900:
        print(f"  WARNING: {len(points)} points is close to the free API's 1000-calls/day cap "
              f"(each batch of {BATCH_SIZE} points is 1 call) -- consider a larger --spacing.")
    elevations = query_elevations(points)

    print("[2/2] Saving ...")
    gdf = gpd.GeoDataFrame(
        {
            "elevation_m": elevations,
            "geometry": [Point(lon, lat) for lat, lon in points],
        },
        crs="EPSG:4326",
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out_dir / "terrain.geojson", driver="GeoJSON")

    elev = np.array(elevations)
    print(f"\nSaved to {out_dir}/terrain.geojson -- {len(gdf)} points, "
          f"elevation range {elev.min():.0f}-{elev.max():.0f}m, relief {elev.max()-elev.min():.0f}m")


if __name__ == "__main__":
    main()
