"""Generate Madina-based flow heatmaps for Abha scenarios (S0, S1A, S1B).

Uses actual Madina betweenness simulation (not a graph-theory proxy).
Each scenario: load config → build env → simulate(no closures) → plot
segment_flow on the street geometry.

Output: results/abha_scenario_maps/*.png (DPI=220)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm, Normalize
from mpl_toolkits.axes_grid1 import make_axes_locatable
from shapely.geometry import shape

from snrl import StreetNetworkEnv, load_config

SCENARIOS = {
    "S0": {
        "config": "configs/city_madina_abha_s0.yaml",
        "label": "S0 — Baseline (fully open)",
        "streets": "data/raw/abha_s0/streets.geojson",
    },
    "S1A": {
        "config": "configs/city_madina_abha_s1a.yaml",
        "label": "S1A — King Abdulaziz One-Way NE",
        "streets": "data/raw/abha_s1a/streets.geojson",
    },
    "S1B": {
        "config": "configs/city_madina_abha_s1b.yaml",
        "label": "S1B — King Abdulaziz One-Way SW",
        "streets": "data/raw/abha_s1b/streets.geojson",
    },
}

OUT_DIR = Path("results/abha_scenario_maps")
DPI = 220


def load_street_coords(geojson_path: str) -> list[list[tuple[float, float]]]:
    data = json.loads(Path(geojson_path).read_text(encoding="utf-8"))
    coords = []
    for f in data["features"]:
        geom = shape(f["geometry"])
        if geom.geom_type == "MultiLineString":
            for part in geom.geoms:
                coords.append(list(part.coords))
        else:
            coords.append(list(geom.coords))
    return coords


def run_scenario(tag: str, info: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"  {tag}: {info['label']}")
    print(f"{'='*60}")
    cfg = load_config(info["config"])
    env = StreetNetworkEnv(cfg)
    closed = np.zeros(env.n_segments, dtype=bool)
    sim = env.backend.simulate(closed)
    print(f"  segments={env.n_segments}  mean_access={np.mean(sim.origin_access):.4f}  "
          f"total_flow={np.sum(sim.segment_flow):.1f}  "
          f"mean_trip_dist={sim.mean_trip_distance:.1f}m")
    coords = load_street_coords(info["streets"])
    return {
        "tag": tag,
        "label": info["label"],
        "flow": sim.segment_flow,
        "access": sim.origin_access,
        "mean_access": float(np.mean(sim.origin_access)),
        "total_flow": float(np.sum(sim.segment_flow)),
        "mean_trip_dist": sim.mean_trip_distance,
        "n_segments": env.n_segments,
        "coords": coords,
    }


def plot_flow_map(result: dict, ax, vmin=None, vmax=None, show_colorbar=True):
    coords = result["coords"]
    flow = result["flow"]
    n = min(len(coords), len(flow))
    segments = [coords[i] for i in range(n)]
    values = flow[:n]

    if vmin is None:
        vmin = max(values[values > 0].min(), 0.01) if np.any(values > 0) else 0.01
    if vmax is None:
        vmax = values.max() if values.max() > 0 else 1.0

    bg_segs = [coords[i] for i in range(n) if values[i] <= 0]
    if bg_segs:
        bg_lc = LineCollection(bg_segs, colors="#cccccc", linewidths=0.3, alpha=0.4)
        ax.add_collection(bg_lc)

    active_idx = [i for i in range(n) if values[i] > 0]
    active_segs = [coords[i] for i in active_idx]
    active_vals = np.array([values[i] for i in active_idx])

    order = np.argsort(active_vals)
    active_segs = [active_segs[i] for i in order]
    active_vals = active_vals[order]

    norm = LogNorm(vmin=vmin, vmax=vmax, clip=True)
    lc = LineCollection(active_segs, cmap="YlOrRd", norm=norm, linewidths=0.6, alpha=0.9)
    lc.set_array(active_vals)
    ax.add_collection(lc)

    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_title(result["label"], fontsize=8, fontweight="bold")
    stats = (f"segments={result['n_segments']}  access={result['mean_access']:.3f}  "
             f"flow={result['total_flow']:.0f}")
    ax.set_xlabel(stats, fontsize=5.5)
    ax.tick_params(labelsize=5)

    if show_colorbar:
        divider = make_axes_locatable(ax)
        cax = divider.append_axes("right", size="3%", pad=0.04)
        cb = plt.colorbar(lc, cax=cax)
        cb.set_label("Betweenness flow", fontsize=5.5)
        cb.ax.tick_params(labelsize=5)

    return lc


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}

    for tag, info in SCENARIOS.items():
        results[tag] = run_scenario(tag, info)

    all_flows = np.concatenate([r["flow"][r["flow"] > 0] for r in results.values()])
    vmin = max(all_flows.min(), 0.01)
    vmax = all_flows.max()

    for tag, r in results.items():
        fig, ax = plt.subplots(figsize=(8, 6))
        plot_flow_map(r, ax, vmin=vmin, vmax=vmax)
        fig.tight_layout()
        out = OUT_DIR / f"flow_{tag.lower()}.png"
        fig.savefig(out, dpi=DPI, bbox_inches="tight")
        plt.close(fig)
        print(f"  -> {out}")

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, (tag, r) in zip(axes, results.items()):
        plot_flow_map(r, ax, vmin=vmin, vmax=vmax, show_colorbar=(tag == "S1B"))
    fig.suptitle("Abha Traffic Flow Comparison — Madina Betweenness Simulation",
                 fontsize=11, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = OUT_DIR / "flow_comparison_s0_s1a_s1b.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"\n  -> {out}")

    s0 = results["S0"]
    n0 = s0["n_segments"]
    for other_tag in ["S1A", "S1B"]:
        r = results[other_tag]
        n_other = r["n_segments"]
        diff = np.zeros(n0, dtype=float)
        n_shared = min(n0, n_other)
        diff[:n_shared] = r["flow"][:n_shared] - s0["flow"][:n_shared]

        fig, ax = plt.subplots(figsize=(8, 6))
        coords = s0["coords"]
        n = min(len(coords), n0)
        pos_idx = [i for i in range(n) if diff[i] > 0.1]
        neg_idx = [i for i in range(n) if diff[i] < -0.1]
        zero_idx = [i for i in range(n) if abs(diff[i]) <= 0.1]

        if zero_idx:
            lc0 = LineCollection([coords[i] for i in zero_idx],
                                 colors="#dddddd", linewidths=0.3, alpha=0.3)
            ax.add_collection(lc0)

        max_abs = max(abs(diff).max(), 1.0)
        if neg_idx:
            neg_segs = [coords[i] for i in neg_idx]
            neg_vals = np.array([abs(diff[i]) for i in neg_idx])
            norm_n = Normalize(vmin=0, vmax=max_abs, clip=True)
            lc_neg = LineCollection(neg_segs, cmap="Blues", norm=norm_n,
                                    linewidths=0.7, alpha=0.8)
            lc_neg.set_array(neg_vals)
            ax.add_collection(lc_neg)

        if pos_idx:
            pos_segs = [coords[i] for i in pos_idx]
            pos_vals = np.array([diff[i] for i in pos_idx])
            norm_p = Normalize(vmin=0, vmax=max_abs, clip=True)
            lc_pos = LineCollection(pos_segs, cmap="Reds", norm=norm_p,
                                    linewidths=0.7, alpha=0.8)
            lc_pos.set_array(pos_vals)
            ax.add_collection(lc_pos)

        ax.set_aspect("equal")
        ax.autoscale_view()
        ax.set_title(f"Flow difference: {other_tag} minus S0\n"
                     f"Red = more flow, Blue = less flow", fontsize=9)
        ax.tick_params(labelsize=5)
        fig.tight_layout()
        out = OUT_DIR / f"flow_diff_{other_tag.lower()}_vs_s0.png"
        fig.savefig(out, dpi=DPI, bbox_inches="tight")
        plt.close(fig)
        print(f"  -> {out}")

    metrics_path = OUT_DIR / "scenario_metrics.json"
    metrics = {}
    for tag, r in results.items():
        metrics[tag] = {
            "label": r["label"],
            "n_segments": r["n_segments"],
            "mean_access": r["mean_access"],
            "total_flow": r["total_flow"],
            "mean_trip_dist_m": r["mean_trip_dist"],
        }
    Path(metrics_path).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"\n  -> {metrics_path}")

    print("\n" + "="*60)
    print("  SCENARIO COMPARISON")
    print("="*60)
    print(f"{'scenario':<8} {'segments':>8} {'mean_access':>12} {'total_flow':>11} {'trip_dist_m':>11}")
    for tag, m in metrics.items():
        print(f"{tag:<8} {m['n_segments']:>8} {m['mean_access']:>12.4f} "
              f"{m['total_flow']:>11.1f} {m['mean_trip_dist_m']:>11.1f}")


if __name__ == "__main__":
    main()
