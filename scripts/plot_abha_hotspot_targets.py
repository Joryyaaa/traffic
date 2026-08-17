"""Render high-DPI network and intervention-target maps by place name."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

from build_abha_hotspot_data import _read_geojson


ROOT = Path("data/raw/abha_hotspots")
OUT = Path("results/abha_hotspot_scenarios/maps")
DPI = 300
LABELS = {
    "art_street_baseline": "Fully open Art Street and Al-Muftaha baseline",
    "central_market": "Abha central marketplace",
    "asir_central_hospital": "Asir Central Hospital",
    "school_cluster": "Highest OSM school concentration",
    "king_abdulaziz_grand_mosque": "King Abdulaziz Grand Mosque",
    "abu_kheyal_park": "Abu Kheyal Park",
}


def render(scenario: str) -> None:
    folder = ROOT / scenario
    qa = json.loads((folder / "qa.json").read_text(encoding="utf-8"))
    roads = _read_geojson(folder / "road_metadata.geojson")
    targets = _read_geojson(folder / "intervention_targets.geojson")

    fig, ax = plt.subplots(figsize=(8, 8))
    roads.plot(ax=ax, color="#8f969e", linewidth=1.15, alpha=0.72)
    if not targets.empty:
        targets.plot(ax=ax, color="#d62728", linewidth=4.0, alpha=0.95)
    ax.scatter(
        [qa["center_lon"]], [qa["center_lat"]],
        s=85, marker="*", color="#f2b134", edgecolor="#222222", linewidth=0.8,
        zorder=5,
    )
    status = "runnable" if qa.get("runnable", True) else "geometry only — OSM origins missing"
    ax.set_title(
        f"{LABELS[scenario]}\n"
        f"{qa['street_segments']} drive segments | r={qa['selected_radius_m']} m | {status}",
        fontsize=12,
    )
    ax.text(
        0.01, 0.01,
        "grey = OSM drive network\nred = requested intervention targets\nstar = POI",
        transform=ax.transAxes,
        fontsize=8,
        bbox={"facecolor": "white", "alpha": 0.88, "edgecolor": "#cccccc"},
    )
    ax.set_aspect("equal")
    ax.set_axis_off()
    fig.tight_layout()
    path = OUT / f"{scenario}_network_targets.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for scenario in LABELS:
        render(scenario)


if __name__ == "__main__":
    main()
