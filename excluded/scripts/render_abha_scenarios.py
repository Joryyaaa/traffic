"""Render the physical Abha scenario interventions and their measured effects.

This is intentionally separate from the Madina flow heatmaps.  The scenario
maps answer "what changed in the network?" while the impact chart answers
"what changed relative to S0?".

Outputs (high-DPI PNG):
  results/abha_scenario_maps/scenario_render_{s0,s1a,s1b,s2}.png
  results/abha_scenario_maps/scenario_render_comparison.png
  results/abha_scenario_maps/scenario_impact_comparison.png
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "abha_scenario_maps"
S0_PATH = ROOT / "data" / "raw" / "abha_s0" / "streets.geojson"
S1A_PATH = ROOT / "data" / "abha_baseline" / "s1a_king_abdulaziz.geojson"
S1B_PATH = ROOT / "data" / "abha_baseline" / "s1b_king_abdulaziz.geojson"
S2_PATH = ROOT / "data" / "raw" / "abha_s2" / "streets.geojson"
METRICS_PATH = OUT_DIR / "scenario_metrics.json"
DPI = 260

COLORS = {
    "network": "#c9ced6",
    "baseline": "#7356a8",
    "open": "#16845b",
    "removed": "#d04444",
    "green_road": "#00a651",
    "endpoint": "#173b57",
    "S1A": "#2d6cdf",
    "S1B": "#db7c26",
    "S2": "#149c68",
}


def read_features(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def coordinates(feature: dict) -> list[tuple[float, float]]:
    geometry = feature["geometry"]
    if geometry["type"] == "MultiLineString":
        return max(geometry["coordinates"], key=len)
    return geometry["coordinates"]


def segment_collection(features: list[dict], **kwargs) -> LineCollection:
    return LineCollection([coordinates(feature) for feature in features], **kwargs)


def add_direction_arrows(ax, features: list[dict], color: str, max_arrows: int = 7):
    ranked = sorted(features, key=lambda feature: float((feature.get("properties") or {}).get("length") or 0), reverse=True)
    selected = ranked[:max_arrows]
    for feature in selected:
        coords = coordinates(feature)
        if len(coords) < 2:
            continue
        lengths = np.asarray([
            math.hypot(coords[i + 1][0] - coords[i][0], coords[i + 1][1] - coords[i][1])
            for i in range(len(coords) - 1)
        ])
        index = int(np.argmax(lengths))
        x1, y1 = coords[index]
        x2, y2 = coords[index + 1]
        start_x = x1 + 0.30 * (x2 - x1)
        start_y = y1 + 0.30 * (y2 - y1)
        dx = 0.40 * (x2 - x1)
        dy = 0.40 * (y2 - y1)
        ax.annotate(
            "", xy=(start_x + dx, start_y + dy), xytext=(start_x, start_y),
            arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.4, "mutation_scale": 10},
            zorder=8,
        )


def common_extent(features: list[dict]) -> tuple[float, float, float, float]:
    points = [point for feature in features for point in coordinates(feature)]
    xs, ys = np.asarray([p[0] for p in points]), np.asarray([p[1] for p in points])
    pad_x = (xs.max() - xs.min()) * 0.025
    pad_y = (ys.max() - ys.min()) * 0.025
    return xs.min() - pad_x, xs.max() + pad_x, ys.min() - pad_y, ys.max() + pad_y


def setup_axis(ax, extent, title: str, subtitle: str):
    xmin, xmax, ymin, ymax = extent
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    mean_lat = (ymin + ymax) / 2
    ax.set_aspect(1 / math.cos(math.radians(mean_lat)))
    ax.set_axis_off()
    ax.set_title(title, fontsize=12, fontweight="bold", pad=8)
    ax.text(0.5, 0.985, subtitle, transform=ax.transAxes, ha="center", va="top", fontsize=8, color="#4d5560")


def draw_base(ax, s0_features: list[dict]):
    ax.add_collection(segment_collection(s0_features, colors=COLORS["network"], linewidths=0.35, alpha=0.52, zorder=1))


def draw_s0(ax, s0_features, king_features, extent):
    setup_axis(ax, extent, "S0 - Baseline", "Existing directed road network; no intervention")
    draw_base(ax, s0_features)
    ax.add_collection(segment_collection(king_features, colors=COLORS["baseline"], linewidths=1.8, alpha=0.95, zorder=4))
    add_direction_arrows(ax, king_features, COLORS["baseline"], max_arrows=8)
    ax.legend(
        handles=[
            Line2D([0], [0], color=COLORS["network"], lw=1.2, label="Existing network"),
            Line2D([0], [0], color=COLORS["baseline"], lw=2.4, label="King Abdulaziz baseline directions"),
        ],
        loc="lower left", frameon=False, fontsize=8,
    )


def draw_s1(ax, s0_features, scenario_features, extent, tag: str, direction: str):
    opened = [f for f in scenario_features if (f.get("properties") or {}).get("road_open") is True]
    removed = [f for f in scenario_features if (f.get("properties") or {}).get("road_open") is False]
    setup_axis(
        ax, extent, f"{tag} - King Abdulaziz one-way {direction}",
        f"{len(opened)} directed edges retained; {len(removed)} opposite-direction edges removed",
    )
    draw_base(ax, s0_features)
    ax.add_collection(segment_collection(removed, colors=COLORS["removed"], linewidths=1.6, linestyles="dashed", alpha=0.9, zorder=4))
    ax.add_collection(segment_collection(opened, colors=COLORS["open"], linewidths=2.2, alpha=0.98, zorder=5))
    add_direction_arrows(ax, opened, COLORS["open"], max_arrows=8)
    ax.legend(
        handles=[
            Line2D([0], [0], color=COLORS["open"], lw=2.6, label=f"Retained {direction}-bound direction"),
            Line2D([0], [0], color=COLORS["removed"], lw=2, ls="--", label="Removed opposite direction"),
        ],
        loc="lower left", frameon=False, fontsize=8,
    )


def draw_s2(ax, s0_features, s2_features, extent):
    green = [f for f in s2_features if (f.get("properties") or {}).get("green_road") is True]
    setup_axis(
        ax, extent, "S2 - Green Road", "Hypothetical 2.0 km alignment for pipeline testing; not ASDA geometry",
    )
    draw_base(ax, s0_features)
    ax.add_collection(segment_collection(green, colors=COLORS["green_road"], linewidths=2.8, alpha=1.0, zorder=5))
    forward = green[::2]
    add_direction_arrows(ax, forward, COLORS["green_road"], max_arrows=6)
    first = coordinates(green[0])[0]
    last = coordinates(green[-2])[-1]
    ax.scatter([first[0], last[0]], [first[1], last[1]], s=34, color=COLORS["endpoint"], zorder=7)
    ax.annotate("Khamis approach", xy=first, xytext=(6, 5), textcoords="offset points", fontsize=7, color=COLORS["endpoint"])
    ax.annotate("toward Sali (assumed)", xy=last, xytext=(6, -11), textcoords="offset points", fontsize=7, color=COLORS["endpoint"])
    ax.legend(
        handles=[
            Line2D([0], [0], color=COLORS["network"], lw=1.2, label="Existing S0 network"),
            Line2D([0], [0], color=COLORS["green_road"], lw=3, label="New bidirectional road"),
        ],
        loc="lower left", frameon=False, fontsize=8,
    )


def render_scenarios():
    s0_features = read_features(S0_PATH)
    s1a_features = read_features(S1A_PATH)
    s1b_features = read_features(S1B_PATH)
    s2_features = read_features(S2_PATH)
    king_features = s1a_features
    extent = common_extent(s0_features)
    drawers = {
        "s0": lambda ax: draw_s0(ax, s0_features, king_features, extent),
        "s1a": lambda ax: draw_s1(ax, s0_features, s1a_features, extent, "S1A", "NE"),
        "s1b": lambda ax: draw_s1(ax, s0_features, s1b_features, extent, "S1B", "SW"),
        "s2": lambda ax: draw_s2(ax, s0_features, s2_features, extent),
    }
    for tag, drawer in drawers.items():
        fig, ax = plt.subplots(figsize=(9, 7))
        drawer(ax)
        fig.tight_layout()
        path = OUT_DIR / f"scenario_render_{tag}.png"
        fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
        plt.close(fig)
        print(f"Saved -> {path}")

    fig, axes = plt.subplots(2, 2, figsize=(17, 13))
    for ax, drawer in zip(axes.flat, drawers.values()):
        drawer(ax)
    fig.suptitle("Abha scenario designs - physical network interventions", fontsize=16, fontweight="bold", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.975])
    path = OUT_DIR / "scenario_render_comparison.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved -> {path}")


def render_impacts():
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    tags = ["S1A", "S1B", "S2"]
    metric_specs = [
        ("mean_access", "Accessibility", "% vs S0"),
        ("vkt_proxy_km", "VKT proxy", "% vs S0"),
        ("total_flow", "Network flow", "% vs S0"),
        ("access_gini", "Accessibility inequality", "Gini change vs S0"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    for ax, (key, title, unit) in zip(axes.flat, metric_specs):
        baseline = metrics["S0"][key]
        if key == "access_gini":
            values = [metrics[tag][key] - baseline for tag in tags]
        else:
            values = [100 * (metrics[tag][key] - baseline) / baseline for tag in tags]
        colors = [COLORS[tag] for tag in tags]
        bars = ax.bar(tags, values, color=colors, width=0.58)
        ax.axhline(0, color="#4d5560", linewidth=0.8)
        ax.grid(axis="y", alpha=0.18, linewidth=0.6)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylabel(unit, fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        for bar, value in zip(bars, values):
            offset = max(max(abs(v) for v in values) * 0.04, 0.00008)
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + (offset if value >= 0 else -offset),
                f"{value:+.2f}" if key != "access_gini" else f"{value:+.4f}",
                ha="center", va="bottom" if value >= 0 else "top", fontsize=9,
            )
        span = max(max(abs(v) for v in values), 0.001)
        ax.set_ylim(-span * 1.35, span * 1.35)

    fig.suptitle("Abha scenario impacts relative to S0", fontsize=15, fontweight="bold")
    fig.text(
        0.5, 0.01,
        "VKT proxy = sum(Madina segment betweenness x segment length); not observed traffic VKT. "
        "S2 uses a hypothetical alignment.",
        ha="center", fontsize=9, color="#4d5560",
    )
    fig.tight_layout(rect=[0, 0.035, 1, 0.96])
    path = OUT_DIR / "scenario_impact_comparison.png"
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved -> {path}")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    render_scenarios()
    render_impacts()


if __name__ == "__main__":
    main()
