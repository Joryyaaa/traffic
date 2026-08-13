"""Build the final Abha S0/S1A/S1B/S2 comparison table.

The table reports ``vkt_proxy_km`` rather than claiming observed VKT.  The
proxy is Madina betweenness multiplied by segment length and summed over the
network.  Baseline cells stay explicitly pending when only Ibex can finish
them in practical time.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "abha_scenario_maps"
TAGS = ("S0", "S1A", "S1B", "S2")
POLICIES = ("random", "highest_flow", "lowest_flow", "zone_builder", "greedy", "zone_builder_best")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_policy_results(tag: str) -> dict:
    directory = ROOT / "results" / f"abha_{tag.lower()}_baselines"
    complete = _read_json(directory / "cheap_baselines.json")
    partial = _read_json(directory / "cheap_baselines_partial.json")
    return complete or partial


def _fmt(value, decimals=3):
    return "pending" if value in (None, "") else f"{float(value):.{decimals}f}"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = _read_json(OUT_DIR / "scenario_metrics.json")
    rows = []
    for tag in TAGS:
        m = metrics.get(tag, {})
        policies = load_policy_results(tag)
        row = {
            "scenario": tag,
            "segments": m.get("n_segments"),
            "mean_access": m.get("mean_access"),
            "access_gini": m.get("access_gini"),
            "vkt_proxy_km": m.get("vkt_proxy_km"),
            "total_flow": m.get("total_flow"),
            "mean_trip_dist_m": m.get("mean_trip_dist_m"),
            "n_components": m.get("n_components"),
            "unreachable_fraction": m.get("unreachable_fraction"),
        }
        for policy in POLICIES:
            row[f"{policy}_mean_return"] = (policies.get(policy) or {}).get("mean_return")
            row[f"{policy}_std"] = (policies.get(policy) or {}).get("std")
        rows.append(row)

    s0 = rows[0]
    for row in rows:
        for metric in ("mean_access", "vkt_proxy_km", "total_flow", "mean_trip_dist_m"):
            base, value = s0.get(metric), row.get(metric)
            row[f"{metric}_delta_vs_s0"] = None if base is None or value is None else value - base
            row[f"{metric}_pct_vs_s0"] = (
                None if base in (None, 0) or value is None else 100.0 * (value - base) / base
            )

    csv_path = OUT_DIR / "comparison_table.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "ABHA SCENARIO COMPARISON",
        "VKT proxy = sum(Madina segment betweenness x segment length_km); not observed traffic VKT.",
        "",
        f"{'scenario':<9}{'segments':>10}{'access':>11}{'gini':>9}{'VKT proxy':>14}{'flow':>12}{'trip_m':>11}",
        "-" * 76,
    ]
    for row in rows:
        lines.append(
            f"{row['scenario']:<9}{str(row['segments'] or 'pending'):>10}"
            f"{_fmt(row['mean_access'], 4):>11}{_fmt(row['access_gini'], 4):>9}"
            f"{_fmt(row['vkt_proxy_km'], 1):>14}{_fmt(row['total_flow'], 1):>12}"
            f"{_fmt(row['mean_trip_dist_m'], 1):>11}"
        )
    lines.extend(["", "Change vs S0:"])
    for row in rows[1:]:
        lines.append(
            f"  {row['scenario']}: access {_fmt(row['mean_access_pct_vs_s0'], 2)}%; "
            f"VKT proxy {_fmt(row['vkt_proxy_km_pct_vs_s0'], 2)}%; "
            f"flow {_fmt(row['total_flow_pct_vs_s0'], 2)}%; "
            f"trip distance {_fmt(row['mean_trip_dist_m_delta_vs_s0'], 1)} m"
        )
    lines.extend(["", "Policy returns (pending = deferred to Ibex):"])
    for row in rows:
        values = ", ".join(f"{policy}={_fmt(row[f'{policy}_mean_return'], 4)}" for policy in POLICIES)
        lines.append(f"  {row['scenario']}: {values}")

    text = "\n".join(lines) + "\n"
    txt_path = OUT_DIR / "comparison_table.txt"
    txt_path.write_text(text, encoding="utf-8")
    print(text)
    print(f"Saved -> {csv_path}")
    print(f"Saved -> {txt_path}")


if __name__ == "__main__":
    main()
