"""Build S2 (Green Road) env data — PLACEHOLDER awaiting ASDA geometry.

S2 adds a proposed bypass road (alternative route for Khamis Mushait -> Sali
traffic) to the S0 baseline network. The exact alignment comes from ASDA and
is not yet available.

Once the geometry is provided (as a GeoJSON LineString or set of LineStrings
in WGS84), this script will:
1. Read the S0 streets.geojson
2. Append the new road segment(s) with appropriate properties
3. Write data/raw/abha_s2/streets.geojson
4. Copy origins/destinations from S0 (same residential/amenities)

Usage (once geometry is available):
    python scripts/build_abha_s2_env_data.py --green-road path/to/green_road.geojson

For now, running without --green-road prints this help and exits.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--green-road", type=str, default=None,
                    help="GeoJSON file with the proposed Green Road geometry")
    args = ap.parse_args()

    if args.green_road is None:
        print("S2 (Green Road) — ASDA geometry not yet provided.")
        print("Once the proposed road alignment is available as a GeoJSON file, run:")
        print("  python scripts/build_abha_s2_env_data.py --green-road <path>")
        print()
        print("Then create the config:")
        print("  cp configs/city_madina_abha_s0.yaml configs/city_madina_abha_s2.yaml")
        print("  # edit streets_path to data/raw/abha_s2/streets.geojson")
        print()
        print("Then run baselines:")
        print("  python scripts/run_abha_s0_baselines_cheap.py --config configs/city_madina_abha_s2.yaml --episodes 5")
        return

    green_road_path = Path(args.green_road)
    if not green_road_path.exists():
        raise FileNotFoundError(f"Green Road GeoJSON not found: {green_road_path}")

    s0_streets = ROOT / "data" / "raw" / "abha_s0" / "streets.geojson"
    s0_data = json.loads(s0_streets.read_text(encoding="utf-8"))
    green_data = json.loads(green_road_path.read_text(encoding="utf-8"))

    max_id = max(f["properties"].get("road_segment_id", 0)
                 for f in s0_data["features"])

    for i, feature in enumerate(green_data["features"]):
        props = feature.setdefault("properties", {})
        props["road_segment_id"] = max_id + 1 + i
        props.setdefault("name", "Green Road (proposed)")
        props.setdefault("highway", "secondary")
        props.setdefault("oneway", False)
        props.setdefault("road_open", True)
        props.setdefault("is_study_corridor", False)
        props.setdefault("scenario", "S2")
        props.setdefault("scenario_id", "S2")
        s0_data["features"].append(feature)

    out_dir = ROOT / "data" / "raw" / "abha_s2"
    out_dir.mkdir(parents=True, exist_ok=True)

    n_original = len(json.loads(s0_streets.read_text(encoding="utf-8"))["features"])
    n_new = len(s0_data["features"])
    print(f"S2: S0 had {n_original} segments, added {n_new - n_original} Green Road segments")
    print(f"  Total: {n_new} segments")

    out_streets = out_dir / "streets.geojson"
    out_streets.write_text(json.dumps(s0_data), encoding="utf-8")
    print(f"  -> {out_streets}")

    for name in ("residential.geojson", "amenities.geojson"):
        src = ROOT / "data" / "raw" / "abha_s0" / name
        dst = out_dir / name
        shutil.copy2(src, dst)
        print(f"  -> {dst} (copied from S0)")


if __name__ == "__main__":
    main()
