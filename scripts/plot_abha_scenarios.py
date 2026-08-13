"""Flow heatmaps + a side-by-side comparison map for Abha's S0 / S1A / S1B scenarios.

S0/S1A/S1B (King Abdulaziz Road baseline + two one-way candidates) were built by
`scripts/abha_network_baseline.py` / `scripts/abha_s1_oneway_scenarios.py` (run in Colab,
not locally) and live on `origin/main` as two folium HTML maps + CSV summaries + a
29-segment King Abdulaziz geojson per scenario -- the full 4,586-segment network geometry
was never committed as a standalone file, only embedded inside the HTML. This script:

  1. reads the full S0 network back out of `data/abha_baseline/extracted/s0_full_network.geojson`
     (pulled out of the HTML by `scripts/extract_abha_html_layers.py`),
  2. builds S1A/S1B by taking that same network and flipping `road_open` on the 29 King
     Abdulaziz segments per `data/abha_baseline/s1a_king_abdulaziz.geojson` /
     `s1b_king_abdulaziz.geojson` (both committed, real mentor output),
  3. computes an edge-betweenness-centrality flow proxy per scenario (networkx, weighted by
     segment length) -- NOT Madina's real betweenness/accessibility simulation. This network
     isn't wired into `StreetNetworkEnv`/the Madina backend yet (that's a separate,
     not-yet-done step), so this is a structural stand-in only: routes traffic along
     shortest paths over the whole graph with no origin/destination demand weighting. Good
     enough to see *where the King Abdulaziz closures reroute the shortest-path structure*,
     not a substitute for a real Madina accessibility run.
  4. renders one flow-heatmap PNG per scenario + one S0-vs-S1A-vs-S1B comparison PNG.

Usage:
    python scripts/plot_abha_scenarios.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

EXTRACTED = Path("data/abha_baseline/extracted/s0_full_network.geojson")
S1A_PATH = Path("data/abha_baseline/s1a_king_abdulaziz.geojson")
S1B_PATH = Path("data/abha_baseline/s1b_king_abdulaziz.geojson")
OUT_DIR = Path("results/abha_scenario_maps")
DPI = 220
ABHA_CENTER = (42.5053914, 18.2264426)  # lon, lat


def load_geojson(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["features"]


def build_base_graph(features: list[dict]) -> nx.MultiDiGraph:
    """One directed edge per feature, keyed (u, v, key) -- matches osmnx's own convention.

    A plain DiGraph silently collapses parallel edges that share a (u, v) pair (25 of
    Abha's 4,586 segments are exactly that -- two distinct OSM ways between the same node
    pair), so this has to be a MultiDiGraph to keep every segment.
    """
    g = nx.MultiDiGraph()
    for feat in features:
        p = feat["properties"]
        coords = feat["geometry"]["coordinates"]
        u, v, key = p["u"], p["v"], p["key"]
        g.add_edge(
            u, v, key=key,
            road_segment_id=p["road_segment_id"],
            length=p["length"] if p["length"] else 1.0,
            name=p.get("name"),
            highway=p.get("highway"),
            coords=coords,
        )
    return g


def apply_scenario_closures(g: nx.MultiDiGraph, scenario_features: list[dict]) -> tuple[nx.MultiDiGraph, set[int]]:
    """Return a copy of g with the scenario's `road_open == False` segments removed."""
    g2 = g.copy()
    closed_ids = {
        f["properties"]["road_segment_id"] for f in scenario_features if not f["properties"]["road_open"]
    }
    to_remove = [(u, v, k) for u, v, k, d in g2.edges(keys=True, data=True) if d["road_segment_id"] in closed_ids]
    g2.remove_edges_from(to_remove)
    return g2, closed_ids


def compute_flow(g: nx.MultiDiGraph) -> dict:
    """Edge betweenness centrality, length-weighted -- the flow proxy (see module docstring)."""
    return nx.edge_betweenness_centrality(g, weight="length", normalized=True)


def segments_for_plot(g: nx.MultiDiGraph, flow: dict):
    segs, values, road_ids = [], [], []
    for u, v, k, d in g.edges(keys=True, data=True):
        segs.append(d["coords"])
        values.append(flow.get((u, v, k), 0.0))
        road_ids.append(d["road_segment_id"])
    return segs, np.array(values), road_ids


def plot_scenario_flow(ax, base_graph, scenario_graph, closed_ids, title):
    """Flow heatmap for one scenario; segments closed by that scenario drawn dashed green."""
    flow = compute_flow(scenario_graph)
    segs, values, road_ids = segments_for_plot(scenario_graph, flow)

    vmax = np.percentile(values[values > 0], 99) if (values > 0).any() else 1.0
    norm = plt.Normalize(vmin=0, vmax=vmax)
    lc = LineCollection(segs, array=values, cmap="inferno", norm=norm, linewidths=1.6)
    ax.add_collection(lc)

    if closed_ids:
        closed_segs = [
            d["coords"] for u, v, d in base_graph.edges(data=True)
            if d["road_segment_id"] in closed_ids
        ]
        lc_closed = LineCollection(closed_segs, colors="#00e676", linewidths=2.2, linestyles="dashed")
        ax.add_collection(lc_closed)

    ax.set_title(title, fontsize=12)
    ax.set_xlim(42.4905, 42.522)
    ax.set_ylim(18.2125, 18.2405)
    ax.set_aspect(1 / np.cos(np.radians(18.226)))
    ax.set_axis_off()
    return lc


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    s0_features = load_geojson(EXTRACTED)
    s1a_features = load_geojson(S1A_PATH)
    s1b_features = load_geojson(S1B_PATH)

    base_graph = build_base_graph(s0_features)
    print(f"S0 graph: {base_graph.number_of_nodes()} nodes, {base_graph.number_of_edges()} edges")

    s1a_graph, s1a_closed = apply_scenario_closures(base_graph, s1a_features)
    s1b_graph, s1b_closed = apply_scenario_closures(base_graph, s1b_features)
    print(f"S1A: {len(s1a_closed)} King Abdulaziz segments closed (one-way NE)")
    print(f"S1B: {len(s1b_closed)} King Abdulaziz segments closed (one-way SW)")

    scenarios = [
        ("S0", base_graph, set(), "S0 -- Baseline (fully open)"),
        ("S1A", s1a_graph, s1a_closed, "S1A -- King Abdulaziz one-way NE"),
        ("S1B", s1b_graph, s1b_closed, "S1B -- King Abdulaziz one-way SW"),
    ]

    # --- one PNG per scenario ---
    flows_by_scenario = {}
    for sid, graph, closed_ids, title in scenarios:
        fig, ax = plt.subplots(figsize=(10, 10))
        lc = plot_scenario_flow(ax, base_graph, graph, closed_ids, title)
        cbar = fig.colorbar(lc, ax=ax, shrink=0.6)
        cbar.set_label("shortest-path betweenness (flow proxy, length-weighted)")
        if closed_ids:
            ax.legend(
                handles=[Line2D([0], [0], color="#00e676", lw=2.2, ls="dashed", label="closed by this scenario")],
                loc="lower right", fontsize=9,
            )
        fig.tight_layout()
        out_path = OUT_DIR / f"abha_{sid.lower()}_flow.png"
        fig.savefig(out_path, dpi=DPI)
        plt.close(fig)
        print(f"Saved -> {out_path}")
        flows_by_scenario[sid] = compute_flow(graph)

    # --- side-by-side comparison ---
    fig, axes = plt.subplots(1, 3, figsize=(24, 9))
    for ax, (sid, graph, closed_ids, title) in zip(axes, scenarios):
        lc = plot_scenario_flow(ax, base_graph, graph, closed_ids, title)
    fig.colorbar(lc, ax=axes, shrink=0.5, label="shortest-path betweenness (flow proxy)")
    fig.suptitle("Abha King Abdulaziz corridor -- S0 vs S1A vs S1B", fontsize=15)
    out_path = OUT_DIR / "abha_s0_s1a_s1b_comparison.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    print(f"Saved -> {out_path}")

    # --- pure diff map: which King Abdulaziz segments flip open/closed between S1A and S1B ---
    fig, ax = plt.subplots(figsize=(11, 11))
    for u, v, d in base_graph.edges(data=True):
        ax.plot(*zip(*d["coords"]), color="#cccccc", linewidth=1.0, zorder=1)
    king_abdulaziz_ids = {f["properties"]["road_segment_id"] for f in s1a_features}
    for u, v, d in base_graph.edges(data=True):
        rid = d["road_segment_id"]
        if rid not in king_abdulaziz_ids:
            continue
        open_in_s1a = rid not in s1a_closed
        open_in_s1b = rid not in s1b_closed
        color = "#1a9850" if open_in_s1a else "#d73027"
        ax.plot(*zip(*d["coords"]), color=color, linewidth=4.5, zorder=2)
    ax.set_xlim(42.4905, 42.522)
    ax.set_ylim(18.2125, 18.2405)
    ax.set_aspect(1 / np.cos(np.radians(18.226)))
    ax.set_axis_off()
    ax.set_title("King Abdulaziz Road -- which direction is 'open' in S1A (green) vs S1B (red)\n"
                  "(same 29 segments, opposite direction kept open)", fontsize=12)
    ax.legend(
        handles=[
            Line2D([0], [0], color="#1a9850", lw=4, label="open in S1A / closed in S1B"),
            Line2D([0], [0], color="#d73027", lw=4, label="open in S1B / closed in S1A"),
        ],
        loc="lower right", fontsize=9,
    )
    out_path = OUT_DIR / "abha_s1a_vs_s1b_corridor_direction.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    print(f"Saved -> {out_path}")

    print("\nDone.")
    for sid, _, closed_ids, _ in scenarios:
        total_flow = sum(flows_by_scenario[sid].values())
        print(f"  {sid}: total_flow(betweenness sum)={total_flow:.4f}  closed_segments={len(closed_ids)}")


if __name__ == "__main__":
    main()
