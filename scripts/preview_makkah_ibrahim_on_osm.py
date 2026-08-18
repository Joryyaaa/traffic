#!/usr/bin/env python3
"""Render high-DPI Makkah Ibrahim network and intervention-target maps.

This intentionally follows scripts/plot_abha_hotspot_targets.py in the repo:
matplotlib PNG output, grey OSM drive network, red requested/accepted targets,
center star, 300 DPI, equal aspect, no basemap tiles.
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "makkah_ibrahim_osm"
OUT = ROOT / "results" / "makkah_ibrahim_scenarios" / "maps"
DPI = 300
CENTER_LON = 39.8228
CENTER_LAT = 21.4177
RADIUS_M = 1800

SCENARIOS = {
    "B0_baseline": {
        "label": "B0 — Current OSM Baseline",
        "roads": "B0_baseline_streets.geojson",
        "targets": None,
        "qa_key": None,
    },
    "S1_partial_closure": {
        "label": "S1 — Ibrahim Al Khalil Partial Closure",
        "roads": "S1_partial_closure_streets.geojson",
        "targets": "S1_partial_closure_targets.geojson",
        "qa_key": "S1",
    },
    "S2_corridor_restriction": {
        "label": "S2 — Ibrahim Al Khalil Network-Safe Corridor Restriction",
        "roads": "S2_corridor_restriction_streets.geojson",
        "targets": "S2_corridor_restriction_targets.geojson",
        "qa_key": "S2",
    },
    "S3_entry_direction": {
        "label": "S3 Entry — Ibrahim Al Khalil Entry-Direction Management",
        "roads": "S3_entry_direction_streets.geojson",
        "targets": "S3_entry_direction_targets.geojson",
        "qa_key": "S3_entry",
    },
    "S3_exit_direction": {
        "label": "S3 Exit — Ibrahim Al Khalil Exit-Direction Management",
        "roads": "S3_exit_direction_streets.geojson",
        "targets": "S3_exit_direction_targets.geojson",
        "qa_key": "S3_exit",
    },
}


def render(key: str, qa: dict) -> None:
    info = SCENARIOS[key]
    roads = gpd.read_file(DATA / info["roads"]).to_crs("EPSG:4326")
    targets = (
        gpd.read_file(DATA / info["targets"]).to_crs("EPSG:4326")
        if info["targets"]
        else roads.iloc[0:0].copy()
    )

    fig, ax = plt.subplots(figsize=(8, 8))
    roads.plot(ax=ax, color="#8f969e", linewidth=1.15, alpha=0.72)
    if not targets.empty:
        targets.plot(ax=ax, color="#d62728", linewidth=4.0, alpha=0.95)

    ax.scatter(
        [CENTER_LON],
        [CENTER_LAT],
        s=85,
        marker="*",
        color="#f2b134",
        edgecolor="#222222",
        linewidth=0.8,
        zorder=5,
    )

    if info["qa_key"] is None:
        status = "baseline — no intervention"
        detail = "0 requested intervention targets"
    else:
        row = qa[info["qa_key"]]
        status = "runnable — connected network"
        detail = (
            f"{row['removed_segments']} accepted targets | "
            f"{row['blocked_by_connectivity']} blocked by connectivity"
        )

    ax.set_title(
        f"{info['label']}\n"
        f"{len(roads)} drive segments | r={RADIUS_M} m | {status}",
        fontsize=12,
    )
    ax.text(
        0.01,
        0.01,
        "grey = OSM drive network\n"
        "red = accepted intervention targets\n"
        "star = Makkah Ibrahim Al Khalil study center\n"
        f"{detail}",
        transform=ax.transAxes,
        fontsize=8,
        bbox={"facecolor": "white", "alpha": 0.88, "edgecolor": "#cccccc"},
    )
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.tight_layout()

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{key}_network_targets.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(path)


def main() -> None:
    qa_path = DATA / "qa_report.json"
    if not qa_path.exists():
        raise SystemExit(
            f"Missing QA report: {qa_path}. Run build_makkah_ibrahim_osm_network.py first."
        )
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    for key in SCENARIOS:
        render(key, qa)


if __name__ == "__main__":
    main()
