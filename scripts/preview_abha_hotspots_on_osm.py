"""Render pre-run Abha hotspot scenario previews over OpenStreetMap.

These videos validate geometry and proposed intervention targets only.  They do
not call Madina, train a model, or report simulated accessibility/VKT.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import urllib.request
from pathlib import Path

import imageio_ffmpeg
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter
from matplotlib.collections import LineCollection
from matplotlib.patches import Ellipse
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "data" / "raw" / "abha_hotspots"
OUT_ROOT = ROOT / "results" / "abha_hotspot_scenarios" / "map_preview_videos"

SCENARIOS = {
    "art_street_baseline": {
        "title": "Baseline — Art Street and Al-Muftaha",
        "description": "Current drive network; no intervention",
        "action": "Baseline remains fully open",
    },
    "central_market": {
        "title": "Central Al-Muftaha Marketplace",
        "description": "Candidate vehicle closures on 3–5 internal streets",
        "action": "Proposed intervention street",
    },
    "asir_central_hospital": {
        "title": "Asir Central Hospital",
        "description": "Candidate side-street closures to reduce through traffic near hospital access",
        "action": "Proposed intervention street",
    },
    "school_cluster": {
        "title": "Highest OSM School Concentration",
        "description": "Candidate temporary street closures during the morning peak",
        "action": "Proposed temporary closure",
    },
    "king_abdulaziz_grand_mosque": {
        "title": "King Abdulaziz Grand Mosque",
        "description": "Candidate temporary closures on two nearby streets after prayer",
        "action": "Proposed temporary closure",
    },
    "abu_kheyal_park": {
        "title": "Abu Kheyal Park",
        "description": "Candidate pedestrian conversion during the evening peak",
        "action": "Proposed pedestrian conversion",
    },
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def line_parts(collection: dict) -> list[np.ndarray]:
    parts: list[np.ndarray] = []
    for feature in collection.get("features", []):
        geometry = feature.get("geometry") or {}
        kind = geometry.get("type")
        coords = geometry.get("coordinates") or []
        if kind == "LineString" and len(coords) >= 2:
            parts.append(np.asarray(coords, dtype=float))
        elif kind == "MultiLineString":
            parts.extend(np.asarray(part, dtype=float) for part in coords if len(part) >= 2)
    return parts


def point_coordinates(collection: dict) -> np.ndarray:
    points = []
    for feature in collection.get("features", []):
        geometry = feature.get("geometry") or {}
        if geometry.get("type") == "Point":
            points.append(geometry["coordinates"])
    return np.asarray(points, dtype=float).reshape((-1, 2))


def lon_to_tile(lon: float, zoom: int) -> float:
    return (lon + 180.0) / 360.0 * (2**zoom)


def lat_to_tile(lat: float, zoom: int) -> float:
    lat_rad = math.radians(lat)
    return (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * (2**zoom)


def tile_to_lon(x: float, zoom: int) -> float:
    return x / (2**zoom) * 360.0 - 180.0


def tile_to_lat(y: float, zoom: int) -> float:
    return math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / (2**zoom)))))


def fetch_osm_mosaic(bounds: tuple[float, float, float, float], cache: Path, zoom: int = 16):
    west, south, east, north = bounds
    x0 = math.floor(lon_to_tile(west, zoom))
    x1 = math.floor(lon_to_tile(east, zoom))
    y0 = math.floor(lat_to_tile(north, zoom))
    y1 = math.floor(lat_to_tile(south, zoom))
    mosaic = Image.new("RGB", ((x1 - x0 + 1) * 256, (y1 - y0 + 1) * 256))
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            path = cache / str(zoom) / str(x) / f"{y}.png"
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                request = urllib.request.Request(
                    f"https://tile.openstreetmap.org/{zoom}/{x}/{y}.png",
                    headers={"User-Agent": "SNRL-Abha-geometry-preview/1.0"},
                )
                with urllib.request.urlopen(request, timeout=30) as response:
                    path.write_bytes(response.read())
            with Image.open(path) as tile:
                mosaic.paste(tile.convert("RGB"), ((x - x0) * 256, (y - y0) * 256))
    extent = (
        tile_to_lon(x0, zoom),
        tile_to_lon(x1 + 1, zoom),
        tile_to_lat(y1 + 1, zoom),
        tile_to_lat(y0, zoom),
    )
    return np.asarray(mosaic), extent


def padded_bounds(lines: list[np.ndarray], center: tuple[float, float]) -> tuple[float, float, float, float]:
    coordinates = np.vstack(lines) if lines else np.asarray([center], dtype=float)
    west, south = coordinates.min(axis=0)
    east, north = coordinates.max(axis=0)
    width = max(east - west, 0.0065)
    height = max(north - south, 0.0050)
    pad_x = width * 0.14
    pad_y = height * 0.14
    return west - pad_x, south - pad_y, east + pad_x, north + pad_y


def render_one(key: str, fps: int, seconds: float, dpi: int) -> Path:
    scenario_dir = DATA_ROOT / key
    qa = read_json(scenario_dir / "qa.json")
    streets = line_parts(read_json(scenario_dir / "streets.geojson"))
    targets = line_parts(read_json(scenario_dir / "intervention_targets.geojson"))
    origins = point_coordinates(read_json(scenario_dir / "residential.geojson"))
    destinations = point_coordinates(read_json(scenario_dir / "amenities.geojson"))
    center = (float(qa["center_lon"]), float(qa["center_lat"]))
    bounds = padded_bounds(streets, center)
    basemap, basemap_extent = fetch_osm_mosaic(bounds, OUT_ROOT / "_tile_cache")

    total_frames = max(24, int(round(fps * seconds)))
    reveal_start = int(total_frames * 0.32)
    reveal_end = int(total_frames * 0.78)
    info = SCENARIOS[key]
    out = OUT_ROOT / f"{key}_geometry_preview.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    mpl.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
    fig, ax = plt.subplots(figsize=(12.8, 7.2), facecolor="#f7f7f7")
    writer = FFMpegWriter(
        fps=fps,
        codec="libx264",
        bitrate=3600,
        metadata={"title": info["title"], "artist": "SNRL / Abha geometry review"},
        extra_args=["-pix_fmt", "yuv420p"],
    )

    with writer.saving(fig, str(out), dpi=dpi):
        for frame in range(total_frames):
            ax.clear()
            ax.imshow(basemap, extent=basemap_extent, origin="upper", zorder=0)
            ax.add_collection(LineCollection(streets, colors="#ffffff", linewidths=4.6, alpha=0.90, zorder=3))
            ax.add_collection(LineCollection(streets, colors="#245c78", linewidths=2.0, alpha=0.80, zorder=4))

            radius_lon = float(qa["selected_radius_m"]) / (111_320.0 * math.cos(math.radians(center[1])))
            radius_lat = float(qa["selected_radius_m"]) / 110_540.0
            ax.add_patch(
                Ellipse(
                    center,
                    width=2.0 * radius_lon,
                    height=2.0 * radius_lat,
                    fill=False,
                    edgecolor="#138f84",
                    linewidth=2.0,
                    linestyle=(0, (5, 4)),
                    alpha=0.78,
                    zorder=5,
                    transform=ax.transData,
                )
            )
            ax.set_aspect("auto")

            if len(origins):
                ax.scatter(origins[:, 0], origins[:, 1], s=28, marker="s", color="#2878b5", edgecolor="white", linewidth=0.7, zorder=7)
            if len(destinations):
                ax.scatter(destinations[:, 0], destinations[:, 1], s=34, marker="o", color="#f28e2b", edgecolor="white", linewidth=0.7, zorder=7)
            ax.scatter([center[0]], [center[1]], s=150, marker="*", color="#7b3294", edgecolor="white", linewidth=1.1, zorder=9)

            if targets:
                progress = np.clip((frame - reveal_start) / max(1, reveal_end - reveal_start), 0.0, 1.0)
                visible_count = int(math.ceil(progress * len(targets))) if progress > 0 else 0
                if visible_count:
                    visible = targets[:visible_count]
                    pulse = 5.7 + 0.8 * math.sin(frame * 0.45)
                    ax.add_collection(LineCollection(visible, colors="#ffffff", linewidths=pulse + 3.0, alpha=0.95, zorder=10))
                    ax.add_collection(LineCollection(visible, colors="#d7191c", linewidths=pulse, alpha=0.98, zorder=11))
                status = f"{visible_count}/{len(targets)} {info['action'].lower()}s shown"
            else:
                status = "No closures or interventions in the baseline"

            ax.set_xlim(bounds[0], bounds[2])
            ax.set_ylim(bounds[1], bounds[3])
            ax.set_axis_off()
            ax.set_title(
                f"{info['title']}\n{info['description']}",
                fontsize=15,
                fontweight="bold",
                pad=10,
            )
            data_note = (
                "DATA BLOCKED: geometry only — no residential origins available"
                if key == "school_cluster"
                else "PRE-RUN GEOMETRY PREVIEW — no model result"
            )
            ax.text(
                0.012,
                0.015,
                f"{status}\nNetwork: {qa['street_segments']} drive segments | study radius: {qa['selected_radius_m']} m\n"
                f"blue squares: residential origins | orange circles: destinations | purple star: scenario location\n"
                f"{data_note}",
                transform=ax.transAxes,
                ha="left",
                va="bottom",
                fontsize=9.5,
                color="#17324d",
                bbox={"facecolor": "white", "edgecolor": "#647887", "alpha": 0.94, "pad": 6},
                zorder=20,
            )
            ax.text(
                0.99,
                0.012,
                "© OpenStreetMap contributors",
                transform=ax.transAxes,
                ha="right",
                va="bottom",
                fontsize=8,
                color="#333333",
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 2},
                zorder=20,
            )
            fig.tight_layout()
            writer.grab_frame()

    plt.close(fig)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["all", *SCENARIOS], default="all")
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--seconds", type=float, default=7.0)
    parser.add_argument("--dpi", type=int, default=120)
    args = parser.parse_args()
    keys = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for key in keys:
        output = render_one(key, args.fps, args.seconds, args.dpi)
        print(f"saved {output.name}")


if __name__ == "__main__":
    main()
