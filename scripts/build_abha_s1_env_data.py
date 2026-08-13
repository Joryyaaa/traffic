"""Build S1A and S1B env data from S0 streets + scenario GeoJSON files.

S1A = King Abdulaziz one-way NE (close SW-bearing segments)
S1B = King Abdulaziz one-way SW (close NE-bearing segments)

For each scenario, reads the scenario GeoJSON (data/abha_baseline/s1{a,b}_king_abdulaziz.geojson),
extracts road_segment_ids where road_open=False, then filters those out of the S0 streets.geojson.
Origins/destinations are unchanged — same residential/amenities as S0.

Output: data/raw/abha_s1{a,b}/streets.geojson (+ symlinks to S0 residential/amenities)
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def get_closed_ids(scenario_path: Path) -> set[int]:
    data = json.loads(scenario_path.read_text(encoding="utf-8"))
    return {
        f["properties"]["road_segment_id"]
        for f in data["features"]
        if not f["properties"]["road_open"]
    }


def filter_streets(s0_path: Path, closed_ids: set[int]) -> dict:
    data = json.loads(s0_path.read_text(encoding="utf-8"))
    kept = [
        f for f in data["features"]
        if f["properties"].get("road_segment_id") not in closed_ids
    ]
    data["features"] = kept
    return data


def main():
    s0_streets = ROOT / "data" / "raw" / "abha_s0" / "streets.geojson"
    s0_residential = ROOT / "data" / "raw" / "abha_s0" / "residential.geojson"
    s0_amenities = ROOT / "data" / "raw" / "abha_s0" / "amenities.geojson"

    scenarios = {
        "s1a": ROOT / "data" / "abha_baseline" / "s1a_king_abdulaziz.geojson",
        "s1b": ROOT / "data" / "abha_baseline" / "s1b_king_abdulaziz.geojson",
    }

    for tag, scenario_path in scenarios.items():
        out_dir = ROOT / "data" / "raw" / f"abha_{tag}"
        out_dir.mkdir(parents=True, exist_ok=True)

        closed_ids = get_closed_ids(scenario_path)
        print(f"{tag.upper()}: {len(closed_ids)} closed segment IDs: {sorted(closed_ids)}")

        filtered = filter_streets(s0_streets, closed_ids)
        n_s0 = len(json.loads(s0_streets.read_text(encoding="utf-8"))["features"])
        n_kept = len(filtered["features"])
        print(f"  S0 had {n_s0} segments, {tag.upper()} keeps {n_kept} (removed {n_s0 - n_kept})")

        out_streets = out_dir / "streets.geojson"
        out_streets.write_text(json.dumps(filtered), encoding="utf-8")
        print(f"  -> {out_streets}")

        for name in ("residential.geojson", "amenities.geojson"):
            src = ROOT / "data" / "raw" / "abha_s0" / name
            dst = out_dir / name
            shutil.copy2(src, dst)
            print(f"  -> {dst} (copied from S0)")

        print()


if __name__ == "__main__":
    main()
