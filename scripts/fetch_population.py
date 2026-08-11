"""Clip WorldPop's Saudi Arabia population-density raster to a study area.

WorldPop (https://www.worldpop.org/) publishes gridded population estimates
as direct-download GeoTIFFs, no account needed. Verified working 2026-08-10:

    https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/SAU/sau_ppp_2020_1km_Aggregated_UNadj.tif

HTTP 200, ~10MB, confirmed downloadable. (A 100m-resolution version also
exists but is ~954MB for the whole country -- not used here.) This script
downloads that ~10MB file ONCE, caches it under --cache-dir, then clips
locally to the requested study area on every subsequent run (no re-download).

A windowed *remote* read (rasterio's /vsicurl/, reading only the small area
needed without downloading the whole file) was tried first and does NOT work
here: the server advertises `Accept-Ranges: bytes` but GDAL's actual range
request fails with "Range downloading not supported by this server" --
confirmed 2026-08-10, not assumed. Hence the download-then-clip approach
instead.

Run:
    python scripts/fetch_population.py --radius 1000 --out data/raw/abha_population --lat 18.2264426 --lon 42.5053914

Requires: pip install rasterio (not in requirements.txt/environment.yml yet --
add it there if this script is kept).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import requests
from pyproj import Transformer
from rasterio.mask import mask
from shapely.geometry import box, Point

WORLDPOP_URL = (
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/2020/SAU/"
    "sau_ppp_2020_1km_Aggregated_UNadj.tif"
)
EXPECTED_SIZE_MB = 10  # actual file, confirmed via HEAD request 2026-08-10


def download_raster(cache_path: Path) -> Path:
    if cache_path.exists():
        print(f"[1/3] Using cached {cache_path} ({cache_path.stat().st_size / 1e6:.1f}MB)")
        return cache_path
    print(f"[1/3] Downloading WorldPop Saudi Arabia raster (~{EXPECTED_SIZE_MB}MB) -> {cache_path} ...")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(WORLDPOP_URL, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(cache_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    print(f"  -> {cache_path.stat().st_size / 1e6:.1f}MB")
    return cache_path


def bbox_around(lat: float, lon: float, radius_m: float):
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32638", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:32638", "EPSG:4326", always_xy=True)
    x, y = to_utm.transform(lon, lat)
    minlon, minlat = to_wgs.transform(x - radius_m, y - radius_m)
    maxlon, maxlat = to_wgs.transform(x + radius_m, y + radius_m)
    return box(minlon, minlat, maxlon, maxlat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=float, default=1000, help="Radius in meters (default: 1000)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--cache-dir", default="data/raw/_worldpop_cache", help="Where the ~10MB country raster is cached so repeated runs don't re-download it")
    args = ap.parse_args()

    raster_path = download_raster(Path(args.cache_dir) / "sau_ppp_2020_1km_UNadj.tif")

    print("[2/3] Clipping to study area ...")
    aoi = bbox_around(args.lat, args.lon, args.radius)
    with rasterio.open(raster_path) as src:
        clipped, transform = mask(src, [aoi], crop=True, filled=True, nodata=src.nodata)
        band = clipped[0]
        nodata = src.nodata

    valid = band != nodata if nodata is not None else np.isfinite(band)
    rows, cols = np.where(valid)
    values = band[valid]

    print("[3/3] Saving ...")
    to_wgs = Transformer.from_crs("EPSG:32638", "EPSG:4326", always_xy=True)
    points, pops = [], []
    for r, c, v in zip(rows, cols, values):
        x, y = transform * (c + 0.5, r + 0.5)
        # transform is in the raster's native CRS (WGS84 for WorldPop), no
        # reprojection needed -- x,y are already lon,lat.
        points.append(Point(x, y))
        pops.append(float(v))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    gdf = gpd.GeoDataFrame({"population": pops, "geometry": points}, crs="EPSG:4326")
    gdf.to_file(out_dir / "population.geojson", driver="GeoJSON")

    total = float(np.sum(pops)) if pops else 0.0
    print(f"\nSaved to {out_dir}/population.geojson -- {len(gdf)} grid cells (1km resolution -- "
          f"a {args.radius}m-radius study area may only cover 1-4 cells), "
          f"estimated population in clipped window: {total:.0f}")
    if len(gdf) <= 4:
        print("  NOTE: at 1km native resolution, a small neighborhood radius resolves to only a "
              "handful of cells -- useful as a coarse density estimate, not per-street granularity.")


if __name__ == "__main__":
    main()
