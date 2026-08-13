"""Generate Madina flow maps and metrics for Abha S0/S1A/S1B/S2.

The flow-difference maps align edges by the persistent ``road_segment_id``
property.  They must not align rows by position because S1A/S1B physically
remove directed edges and therefore shift every later row.

``vkt_proxy_km`` is a demand-weighted network-load proxy:
``sum(Madina segment betweenness * segment length_km)``.  It is not observed
vehicle-kilometres travelled; measured traffic counts are still unavailable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LogNorm, TwoSlopeNorm
from shapely.geometry import shape

from snrl import StreetNetworkEnv, load_config

SCENARIOS = {
    "S0": {
        "config": "configs/city_madina_abha_s0.yaml",
        "label": "S0 - Baseline",
        "streets": "data/raw/abha_s0/streets.geojson",
    },
    "S1A": {
        "config": "configs/city_madina_abha_s1a.yaml",
        "label": "S1A - King Abdulaziz one-way NE",
        "streets": "data/raw/abha_s1a/streets.geojson",
    },
    "S1B": {
        "config": "configs/city_madina_abha_s1b.yaml",
        "label": "S1B - King Abdulaziz one-way SW",
        "streets": "data/raw/abha_s1b/streets.geojson",
    },
    "S2": {
        "config": "configs/city_madina_abha_s2.yaml",
        "label": "S2 - Green Road (hypothetical alignment)",
        "streets": "data/raw/abha_s2/streets.geojson",
    },
}

OUT_DIR = Path("results/abha_scenario_maps")
DPI = 240


def _gini(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0 or np.allclose(values, 0):
        return 0.0
    values = np.sort(np.maximum(values, 0))
    n = values.size
    return float((2 * np.sum(np.arange(1, n + 1) * values) / (n * values.sum())) - (n + 1) / n)


def load_street_features(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for index, feature in enumerate(data["features"]):
        props = feature.get("properties") or {}
        geom = shape(feature["geometry"])
        if geom.geom_type == "MultiLineString":
            geom = max(geom.geoms, key=lambda part: part.length)
        rows.append({
            "road_segment_id": int(props.get("road_segment_id", index)),
            "coords": list(geom.coords),
            "length_m": float(props.get("length") or 0.0),
            "green_road": bool(props.get("green_road", False)),
        })
    return rows


def run_scenario(tag: str, info: dict) -> dict:
    print(f"\n{'=' * 64}\n  {tag}: {info['label']}\n{'=' * 64}", flush=True)
    cfg = load_config(info["config"])
    env = StreetNetworkEnv(cfg)
    sim = env.backend.simulate(np.zeros(env.n_segments, dtype=bool))
    features = load_street_features(info["streets"])
    if len(features) != env.n_segments:
        raise RuntimeError(f"{tag}: {len(features)} geometries != {env.n_segments} simulated segments")

    flow = np.asarray(sim.segment_flow, dtype=float)
    lengths_m = np.asarray([row["length_m"] for row in features], dtype=float)
    vkt_proxy_km = float(np.sum(flow * lengths_m) / 1000.0)
    flow_by_id = {row["road_segment_id"]: float(flow[i]) for i, row in enumerate(features)}
    feature_by_id = {row["road_segment_id"]: row for row in features}

    result = {
        "tag": tag,
        "label": info["label"],
        "flow": flow,
        "features": features,
        "flow_by_id": flow_by_id,
        "feature_by_id": feature_by_id,
        "n_segments": env.n_segments,
        "mean_access": float(np.mean(sim.origin_access)),
        "access_gini": _gini(sim.origin_access),
        "total_flow": float(np.sum(flow)),
        "vkt_proxy_km": vkt_proxy_km,
        "mean_trip_dist_m": float(sim.mean_trip_distance),
        "n_components": int(sim.n_components),
        "unreachable_fraction": float(sim.unreachable_fraction),
    }
    print(
        f"  segments={env.n_segments} access={result['mean_access']:.4f} "
        f"flow={result['total_flow']:.1f} vkt_proxy={vkt_proxy_km:.1f} km "
        f"trip={result['mean_trip_dist_m']:.1f} m",
        flush=True,
    )
    return result


def plot_flow_map(result: dict, ax, vmin: float, vmax: float, show_colorbar: bool = True):
    values = result["flow"]
    features = result["features"]
    inactive = [row["coords"] for row, value in zip(features, values) if value <= 0]
    active = [(row["coords"], value) for row, value in zip(features, values) if value > 0]
    if inactive:
        ax.add_collection(LineCollection(inactive, colors="#d5d5d5", linewidths=0.35, alpha=0.45))
    active.sort(key=lambda item: item[1])
    lc = LineCollection(
        [item[0] for item in active], cmap="inferno",
        norm=LogNorm(vmin=vmin, vmax=vmax, clip=True), linewidths=0.8, alpha=0.95,
    )
    lc.set_array(np.asarray([item[1] for item in active]))
    ax.add_collection(lc)

    green = [row["coords"] for row in features if row["green_road"]]
    if green:
        ax.add_collection(LineCollection(green, colors="#00b050", linewidths=2.0, alpha=0.95))

    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_axis_off()
    ax.set_title(result["label"], fontsize=10, fontweight="bold")
    ax.text(
        0.01, 0.01,
        f"access={result['mean_access']:.3f} | VKT proxy={result['vkt_proxy_km']:.0f} km\n"
        f"flow={result['total_flow']:.0f} | trip={result['mean_trip_dist_m']:.1f} m",
        transform=ax.transAxes, fontsize=7, bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )
    if show_colorbar:
        cb = plt.colorbar(lc, ax=ax, fraction=0.035, pad=0.015)
        cb.set_label("Madina betweenness flow", fontsize=7)
        cb.ax.tick_params(labelsize=6)
    return lc


def plot_difference(s0: dict, other: dict, out_path: Path):
    ids = sorted(set(s0["flow_by_id"]) | set(other["flow_by_id"]))
    diffs = {
        segment_id: other["flow_by_id"].get(segment_id, 0.0) - s0["flow_by_id"].get(segment_id, 0.0)
        for segment_id in ids
    }
    max_abs = max(max(abs(value) for value in diffs.values()), 1.0)
    features = {**s0["feature_by_id"], **other["feature_by_id"]}
    unchanged, changed, changed_values = [], [], []
    for segment_id in ids:
        coords = features[segment_id]["coords"]
        value = diffs[segment_id]
        if abs(value) <= 0.1:
            unchanged.append(coords)
        else:
            changed.append(coords)
            changed_values.append(value)

    fig, ax = plt.subplots(figsize=(9, 7))
    if unchanged:
        ax.add_collection(LineCollection(unchanged, colors="#dddddd", linewidths=0.3, alpha=0.35))
    lc = LineCollection(
        changed, cmap="RdBu_r", norm=TwoSlopeNorm(vmin=-max_abs, vcenter=0, vmax=max_abs),
        linewidths=0.9, alpha=0.95,
    )
    lc.set_array(np.asarray(changed_values))
    ax.add_collection(lc)
    green = [row["coords"] for row in other["features"] if row["green_road"]]
    if green:
        ax.add_collection(LineCollection(green, colors="#00b050", linewidths=2.2, alpha=0.95))
    ax.set_aspect("equal")
    ax.autoscale_view()
    ax.set_axis_off()
    ax.set_title(f"Flow change: {other['tag']} minus S0\nred = increase, blue = decrease", fontsize=10)
    cb = plt.colorbar(lc, ax=ax, fraction=0.035, pad=0.015)
    cb.set_label("Change in Madina betweenness flow", fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {tag: run_scenario(tag, info) for tag, info in SCENARIOS.items()}
    positive = np.concatenate([r["flow"][r["flow"] > 0] for r in results.values()])
    vmin, vmax = max(float(positive.min()), 0.01), float(positive.max())

    for tag, result in results.items():
        fig, ax = plt.subplots(figsize=(9, 7))
        plot_flow_map(result, ax, vmin, vmax)
        fig.tight_layout()
        path = OUT_DIR / f"madina_flow_{tag.lower()}.png"
        fig.savefig(path, dpi=DPI, bbox_inches="tight")
        plt.close(fig)
        print(f"  -> {path}")

    fig, axes = plt.subplots(2, 2, figsize=(16, 13))
    for ax, result in zip(axes.flat, results.values()):
        plot_flow_map(result, ax, vmin, vmax, show_colorbar=False)
    fig.suptitle("Abha scenario comparison - Madina simulation", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    comparison = OUT_DIR / "madina_flow_comparison_s0_s1a_s1b_s2.png"
    fig.savefig(comparison, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  -> {comparison}")

    for tag in ("S1A", "S1B", "S2"):
        path = OUT_DIR / f"madina_flow_diff_{tag.lower()}_vs_s0.png"
        plot_difference(results["S0"], results[tag], path)
        print(f"  -> {path}")

    metrics = {
        tag: {key: value for key, value in result.items() if key in {
            "label", "n_segments", "mean_access", "access_gini", "total_flow",
            "vkt_proxy_km", "mean_trip_dist_m", "n_components", "unreachable_fraction",
        }}
        for tag, result in results.items()
    }
    metrics_path = OUT_DIR / "scenario_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"  -> {metrics_path}")


if __name__ == "__main__":
    main()
