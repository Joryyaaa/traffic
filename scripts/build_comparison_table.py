"""Build the final Abha scenario comparison table.

Reads baseline results and scenario metrics, produces a formatted table
comparing S0 vs S1A vs S1B (and S2 when available).

Output: results/abha_scenario_maps/comparison_table.txt
        results/abha_scenario_maps/comparison_table.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results" / "abha_scenario_maps"


def load_baseline_results(tag: str) -> dict | None:
    path = ROOT / "results" / f"abha_{tag.lower()}_baselines" / "cheap_baselines.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_scenario_metrics() -> dict | None:
    path = OUT_DIR / "scenario_metrics.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tags = ["S0", "S1A", "S1B"]
    metrics = load_scenario_metrics()

    rows = []
    for tag in tags:
        baselines = load_baseline_results(tag)
        m = (metrics or {}).get(tag, {})

        row = {
            "scenario": tag,
            "segments": m.get("n_segments", "—"),
            "mean_access": m.get("mean_access", "—"),
            "total_flow": m.get("total_flow", "—"),
            "trip_dist_m": m.get("mean_trip_dist_m", "—"),
        }

        if baselines:
            for policy in ["random", "highest_flow", "lowest_flow", "zone_builder"]:
                if policy in baselines:
                    row[f"{policy}_mean"] = baselines[policy]["mean_return"]
                    row[f"{policy}_std"] = baselines[policy]["std"]
                else:
                    row[f"{policy}_mean"] = "—"
                    row[f"{policy}_std"] = "—"
        else:
            for policy in ["random", "highest_flow", "lowest_flow", "zone_builder"]:
                row[f"{policy}_mean"] = "—"
                row[f"{policy}_std"] = "—"

        rows.append(row)

    print("\n" + "=" * 90)
    print("  ABHA SCENARIO COMPARISON TABLE")
    print("=" * 90)

    header = f"{'scenario':<6} {'seg':>5} {'access':>8} {'flow':>9} {'trip_m':>7}"
    for p in ["random", "highest_flow", "lowest_flow", "zone_builder"]:
        header += f"  {p[:10]:>10}"
    print(header)
    print("-" * len(header))

    for r in rows:
        line = f"{r['scenario']:<6} {r['segments']:>5}"
        if isinstance(r["mean_access"], float):
            line += f" {r['mean_access']:>8.4f}"
        else:
            line += f" {r['mean_access']:>8}"
        if isinstance(r["total_flow"], float):
            line += f" {r['total_flow']:>9.1f}"
        else:
            line += f" {r['total_flow']:>9}"
        if isinstance(r["trip_dist_m"], float):
            line += f" {r['trip_dist_m']:>7.1f}"
        else:
            line += f" {r['trip_dist_m']:>7}"
        for p in ["random", "highest_flow", "lowest_flow", "zone_builder"]:
            v = r.get(f"{p}_mean", "—")
            if isinstance(v, float):
                line += f"  {v:>10.4f}"
            else:
                line += f"  {v:>10}"
            s = r.get(f"{p}_std", "—")
        print(line)

    # Deltas vs S0
    if len(rows) > 1 and isinstance(rows[0]["mean_access"], float):
        print("\n  Change vs S0:")
        s0 = rows[0]
        for r in rows[1:]:
            parts = [f"  {r['scenario']}:"]
            if isinstance(r["mean_access"], float) and isinstance(s0["mean_access"], float):
                d = r["mean_access"] - s0["mean_access"]
                pct = 100 * d / s0["mean_access"] if s0["mean_access"] else 0
                parts.append(f"access {d:+.4f} ({pct:+.1f}%)")
            if isinstance(r["total_flow"], float) and isinstance(s0["total_flow"], float):
                d = r["total_flow"] - s0["total_flow"]
                pct = 100 * d / s0["total_flow"] if s0["total_flow"] else 0
                parts.append(f"flow {d:+.1f} ({pct:+.2f}%)")
            if isinstance(r["trip_dist_m"], float) and isinstance(s0["trip_dist_m"], float):
                d = r["trip_dist_m"] - s0["trip_dist_m"]
                parts.append(f"trip_dist {d:+.1f}m")
            print("  ".join(parts))

    # Save CSV
    csv_path = OUT_DIR / "comparison_table.csv"
    fields = list(rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n  -> {csv_path}")

    # Save text
    txt_path = OUT_DIR / "comparison_table.txt"
    import io
    old_stdout = sys.stdout
    buf = io.StringIO()
    sys.stdout = buf
    print(header)
    print("-" * len(header))
    for r in rows:
        line = f"{r['scenario']:<6} {r['segments']:>5}"
        if isinstance(r["mean_access"], float):
            line += f" {r['mean_access']:>8.4f}"
        else:
            line += f" {r['mean_access']:>8}"
        if isinstance(r["total_flow"], float):
            line += f" {r['total_flow']:>9.1f}"
        else:
            line += f" {r['total_flow']:>9}"
        if isinstance(r["trip_dist_m"], float):
            line += f" {r['trip_dist_m']:>7.1f}"
        else:
            line += f" {r['trip_dist_m']:>7}"
        for p in ["random", "highest_flow", "lowest_flow", "zone_builder"]:
            v = r.get(f"{p}_mean", "—")
            if isinstance(v, float):
                line += f"  {v:>10.4f}"
            else:
                line += f"  {v:>10}"
        print(line)
    sys.stdout = old_stdout
    txt_path.write_text(buf.getvalue(), encoding="utf-8")
    print(f"  -> {txt_path}")


if __name__ == "__main__":
    main()
