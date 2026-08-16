"""Create CSV and Markdown summaries from the Ibex scenario array outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


FIELDS = [
    "scenario",
    "demand_scope",
    "execution_method",
    "origins",
    "mean_access",
    "access_gini",
    "flow_weighted_vkt_proxy_km",
    "mean_trip_distance",
    "total_flow",
    "major_road_flow_share",
    "protected_local_flow_share",
    "unreachable_fraction",
    "simulation_seconds",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    root = Path(args.root)
    metric_files = sorted(root.glob("*/metrics.json"))
    if not metric_files:
        raise FileNotFoundError(f"No scenario metrics found below {root}")
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in metric_files]
    for row in rows:
        row.setdefault(
            "demand_scope",
            (
                "city_accessibility"
                if row.get("scenario") == "current_full_belt"
                else "khamis_to_jabal_soudah_viewpoint"
            ),
        )
        row.setdefault(
            "execution_method",
            (
                "exact_linear_derivation"
                if row.get("derived_without_new_madina_run")
                else "madina_simulation"
            ),
        )

    csv_path = root / "scenario_comparison.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Abha Khamis-Jabal Soudah Viewpoint Madina results",
        "",
        "| Scenario | Method | Demand scope | Access | Access Gini | VKT proxy (km) | Trip distance (m) | Major-road flow | Protected-local flow | Unreachable | Runtime (s) |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {scenario} | {execution_method} | {demand_scope} | {mean_access:.6f} | {access_gini:.4f} | "
            "{flow_weighted_vkt_proxy_km:.1f} | {mean_trip_distance:.1f} | "
            "{major_road_flow_share:.1%} | {protected_local_flow_share:.1%} | "
            "{unreachable_fraction:.1%} | {simulation_seconds:.1f} |".format(**row)
        )
    lines.extend(
        [
            "",
            "Demand multipliers are sensitivity weights, not measured traffic counts. ",
            "VKT is a Madina flow-distance proxy. Peak-load cases do not model queues or capacity-dependent congestion.",
            "The city-accessibility row is context only and must not be compared numerically with the Khamis-to-viewpoint demand rows.",
        ]
    )
    (root / "scenario_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Aggregated {len(rows)} scenarios -> {csv_path}")


if __name__ == "__main__":
    main()
