#!/usr/bin/env python3

from pathlib import Path
import json
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "data/neom_scenarios/sharma_camp26_r5km"
BASE = ROOT / "data/neom_baseline/sharma_camp26_r5km"
RESULTS = ROOT / "results/neom_scenarios/sharma_camp26_r5km/madina"
OUT = ROOT / "results/neom_scenarios/sharma_camp26_r5km/visualization"
OUT.mkdir(parents=True, exist_ok=True)

BASE_STREETS = DATA / "streets_madina_ready.geojson"

SCENARIOS = {
    "B0": {
        "title": "B0 — Baseline",
        "streets": BASE_STREETS,
        "origins": DATA / "B0/origins.geojson",
        "destinations": DATA / "B0/destinations.geojson",
        "result": RESULTS / "B0_Baseline.json",
    },
    "S1": {
        "title": "S1 — Vehicle Restriction",
        "streets": DATA / "S1/streets_restricted_madina_ready.geojson",
        "origins": DATA / "S1/origins.geojson",
        "destinations": DATA / "S1/destinations.geojson",
        "result": RESULTS / "S1_Vehicle_Restriction.json",
    },
    "S2": {
        "title": "S2 — Parking Hub",
        "streets": BASE_STREETS,
        "origins": DATA / "S2/origins.geojson",
        "destinations": DATA / "S2/destinations.geojson",
        "result": RESULTS / "S2_Parking_Hub.json",
    },
    "S3_ENTRY": {
        "title": "S3 — Managed Entry",
        "streets": BASE_STREETS,
        "origins": DATA / "S3/entry_origins.geojson",
        "destinations": DATA / "S3/entry_destination.geojson",
        "result": RESULTS / "S3_Managed_Entry_Exit.json",
        "run_index": 0,
    },
    "S3_EXIT": {
        "title": "S3 — Managed Exit",
        "streets": BASE_STREETS,
        "origins": DATA / "S3/exit_origin.geojson",
        "destinations": DATA / "S3/exit_destination.geojson",
        "result": RESULTS / "S3_Managed_Entry_Exit.json",
        "run_index": 1,
    },
}


def existing(path):
    return path if path and Path(path).exists() else None


def read_layer(path, crs="EPSG:32636"):
    if not existing(path):
        return None
    g = gpd.read_file(path)
    if g.empty:
        return g
    return g.to_crs(crs)


def metrics(cfg):
    p = cfg.get("result")
    if not existing(p):
        return {}

    d = json.loads(Path(p).read_text())
    runs = d.get("runs", [])
    if not runs:
        return {}

    idx = cfg.get("run_index", 0)
    idx = min(idx, len(runs) - 1)
    return runs[idx]


def get_bounds():
    g = read_layer(BASE_STREETS)
    if g is None or g.empty:
        return None
    minx, miny, maxx, maxy = g.total_bounds
    dx = maxx - minx
    dy = maxy - miny
    return (
        minx - dx * 0.04,
        maxx + dx * 0.04,
        miny - dy * 0.04,
        maxy + dy * 0.04,
    )


BOUNDS = get_bounds()


def draw(ax, key, cfg):
    streets = read_layer(cfg["streets"])
    origins = read_layer(cfg["origins"])
    destinations = read_layer(cfg["destinations"])
    m = metrics(cfg)

    ax.set_facecolor("#07111f")

    if streets is not None and not streets.empty:
        streets.plot(
            ax=ax,
            color="#8fa3b8",
            linewidth=0.7,
            alpha=0.70,
            zorder=1,
        )

    # For S1, show roads removed relative to B0.
    if key == "S1":
        base = read_layer(BASE_STREETS)
        if base is not None and streets is not None:
            if "parent_osm_id" in base.columns and "parent_osm_id" in streets.columns:
                active_ids = set(streets["parent_osm_id"].astype(str))
                removed = base[
                    ~base["parent_osm_id"].astype(str).isin(active_ids)
                ]
                if not removed.empty:
                    removed.plot(
                        ax=ax,
                        color="#ff4d4d",
                        linewidth=3.0,
                        alpha=0.95,
                        zorder=3,
                    )

    if origins is not None and not origins.empty:
        origins.plot(
            ax=ax,
            color="#31c6ff",
            markersize=28,
            marker="o",
            edgecolor="white",
            linewidth=0.5,
            zorder=5,
            label="Origins",
        )

    if destinations is not None and not destinations.empty:
        destinations.plot(
            ax=ax,
            color="#ffd84d",
            markersize=100,
            marker="*",
            edgecolor="black",
            linewidth=0.7,
            zorder=6,
            label="Destination / Gate",
        )

    if BOUNDS:
        ax.set_xlim(BOUNDS[0], BOUNDS[1])
        ax.set_ylim(BOUNDS[2], BOUNDS[3])

    ax.set_aspect("equal")
    ax.set_axis_off()

    ax.set_title(
        cfg["title"],
        fontsize=20,
        fontweight="bold",
        color="white",
        pad=15,
    )

    access = m.get("mean_accessibility")
    trip = m.get("mean_trip_distance")
    unr = m.get("unreachable_fraction")
    comps = m.get("n_components")
    flow = m.get("total_segment_flow")

    text = []

    if access is not None:
        text.append(f"Accessibility: {access:.3f}")
    if trip is not None:
        text.append(f"Mean trip: {trip:.0f} m")
    if unr is not None:
        text.append(f"Unreachable: {unr*100:.1f}%")
    if comps is not None:
        text.append(f"Components: {comps}")
    if flow is not None:
        text.append(f"Total flow: {flow:.1f}")

    if text:
        ax.text(
            0.02,
            0.02,
            "\n".join(text),
            transform=ax.transAxes,
            fontsize=11,
            color="white",
            verticalalignment="bottom",
            bbox=dict(
                boxstyle="round,pad=0.6",
                facecolor="black",
                alpha=0.72,
                edgecolor="white",
            ),
            zorder=20,
        )

    handles, labels = ax.get_legend_handles_labels()
    if handles:
        leg = ax.legend(
            handles,
            labels,
            loc="upper right",
            framealpha=0.8,
        )
        for t in leg.get_texts():
            t.set_fontsize(9)


print("=" * 70)
print("CREATING INDIVIDUAL SCENARIO MAPS")
print("=" * 70)

pngs = []

for key, cfg in SCENARIOS.items():
    print("Rendering", key)

    fig, ax = plt.subplots(figsize=(12, 10))
    fig.patch.set_facecolor("#07111f")

    draw(ax, key, cfg)

    path = OUT / f"{key}.png"

    plt.tight_layout()
    fig.savefig(
        path,
        dpi=180,
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)

    pngs.append(path)
    print("Saved:", path)


print()
print("=" * 70)
print("CREATING COMPARISON FIGURE")
print("=" * 70)

fig, axes = plt.subplots(2, 3, figsize=(21, 13))
fig.patch.set_facecolor("#07111f")

for ax in axes.flat:
    ax.set_facecolor("#07111f")

for ax, (key, cfg) in zip(axes.flat, SCENARIOS.items()):
    draw(ax, key, cfg)

# Last empty panel = summary
summary_ax = axes.flat[-1]
summary_ax.clear()
summary_ax.set_facecolor("#07111f")
summary_ax.axis("off")

summary_ax.text(
    0.5,
    0.75,
    "NEOM Traffic Scenarios",
    ha="center",
    va="center",
    fontsize=25,
    fontweight="bold",
    color="white",
)

summary_ax.text(
    0.5,
    0.52,
    "B0  Baseline\n"
    "S1  Vehicle Restriction\n"
    "S2  Parking Hub\n"
    "S3  Managed Entry / Exit",
    ha="center",
    va="center",
    fontsize=17,
    color="white",
    linespacing=1.8,
)

summary_ax.text(
    0.5,
    0.20,
    "Madina network simulation",
    ha="center",
    va="center",
    fontsize=13,
    color="#b8c5d1",
)

comparison = OUT / "NEOM_scenarios_comparison.png"

plt.tight_layout()
fig.savefig(
    comparison,
    dpi=180,
    bbox_inches="tight",
    facecolor=fig.get_facecolor(),
)
plt.close(fig)

print("Saved:", comparison)


print()
print("=" * 70)
print("CREATING MP4")
print("=" * 70)

frames = list(SCENARIOS.items())

fig, ax = plt.subplots(figsize=(12, 10))
fig.patch.set_facecolor("#07111f")


def update(frame):
    ax.clear()

    # Hold every scenario for several animation frames.
    scenario_index = min(frame // 24, len(frames) - 1)

    key, cfg = frames[scenario_index]
    draw(ax, key, cfg)

    fig.suptitle(
        "NEOM Scenario Simulation",
        color="white",
        fontsize=16,
        y=0.98,
    )


total_frames = len(frames) * 24

animation = FuncAnimation(
    fig,
    update,
    frames=total_frames,
    interval=125,
    repeat=True,
)

video = OUT / "NEOM_scenarios.mp4"

try:
    writer = FFMpegWriter(
        fps=8,
        bitrate=3000,
        metadata={"title": "NEOM Traffic Scenarios"},
    )

    animation.save(
        video,
        writer=writer,
        dpi=140,
    )

    print("Saved:", video)

except Exception as e:
    print("MP4 creation skipped/failed:")
    print(e)
    print("PNGs and comparison figure were still created.")

plt.close(fig)


print()
print("=" * 70)
print("DONE")
print("=" * 70)

for p in sorted(OUT.iterdir()):
    print(p.name, round(p.stat().st_size / 1024, 1), "KB")
