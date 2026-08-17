"""Build compact CSV/Markdown tables from recorded Madina states and QA.

No metric is recomputed here. Values come from the exact environment states
recorded by record_abha_hotspot_flow.py; VKT remains explicitly labelled a
simulation proxy.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path("results/abha_hotspot_scenarios")
DATA = Path("data/raw/abha_hotspots")
SCENARIOS = (
    "art_street_baseline",
    "central_market",
    "asir_central_hospital",
    "school_cluster",
    "king_abdulaziz_grand_mosque",
    "abu_kheyal_park",
)


def _pct(final: float, baseline: float):
    if baseline == 0:
        return None
    return 100.0 * (final - baseline) / baseline


def main() -> None:
    budgets = json.loads((ROOT / "budget_measurements.json").read_text(encoding="utf-8"))["measurements"]
    rows = []
    for scenario in SCENARIOS:
        qa = json.loads((DATA / scenario / "qa.json").read_text(encoding="utf-8"))
        video_meta = ROOT / "videos" / f"{scenario}.json"
        row = {
            "scenario": scenario,
            "segments": qa["street_segments"],
            "radius_m": qa["selected_radius_m"],
            "origins": qa["residential_origins"],
            "destinations": qa["amenity_destinations"],
            "budget_status": budgets[scenario]["status"],
            "baseline_accessibility": None,
            "final_accessibility": None,
            "accessibility_change_pct": None,
            "final_access_gini": None,
            "baseline_vkt_proxy_km": None,
            "final_vkt_proxy_km": None,
            "vkt_proxy_change_pct": None,
            "final_total_flow": None,
            "final_mean_trip_distance_m": None,
        }
        if video_meta.exists():
            payload = json.loads(video_meta.read_text(encoding="utf-8"))
            first, last = payload["states"][0], payload["states"][-1]
            row.update(
                baseline_accessibility=first["mean_access"],
                final_accessibility=last["mean_access"],
                accessibility_change_pct=_pct(last["mean_access"], first["mean_access"]),
                final_access_gini=last["access_gini"],
                baseline_vkt_proxy_km=first["vkt_proxy_km"],
                final_vkt_proxy_km=last["vkt_proxy_km"],
                vkt_proxy_change_pct=_pct(last["vkt_proxy_km"], first["vkt_proxy_km"]),
                final_total_flow=last["total_flow"],
                final_mean_trip_distance_m=last["mean_trip_distance_m"],
            )
        rows.append(row)

    ROOT.mkdir(parents=True, exist_ok=True)
    csv_path = ROOT / "scenario_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def f(value, digits=3):
        return "blocked" if value is None else f"{value:.{digits}f}"

    lines = [
        "# Abha hotspot Madina metrics",
        "",
        "| Scenario | Segments | O / D | Budget gate | Access baseline → final | Access change | Gini final | VKT proxy baseline → final (km) |",
        "|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        access_change = "blocked" if row["accessibility_change_pct"] is None else f"{row['accessibility_change_pct']:+.1f}%"
        lines.append(
            f"| {row['scenario']} | {row['segments']} | {row['origins']} / {row['destinations']} | "
            f"{row['budget_status']} | {f(row['baseline_accessibility'])} → {f(row['final_accessibility'])} | "
            f"{access_change} | {f(row['final_access_gini'])} | "
            f"{f(row['baseline_vkt_proxy_km'], 2)} → {f(row['final_vkt_proxy_km'], 2)} |"
        )
    lines.extend(
        [
            "",
            "The final state is the deterministic `zone_builder` sequence from `scripts/evaluate.py`.",
            "VKT is `sum(Madina segment betweenness × segment length_m) / 1000`: a flow-distance simulation proxy, not observed traffic VKT.",
            "The school-cluster scenario has no numeric row because OSM supplies zero residential origins in every valid-size crop.",
        ]
    )
    md_path = ROOT / "scenario_metrics.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(csv_path)
    print(md_path)


if __name__ == "__main__":
    main()
