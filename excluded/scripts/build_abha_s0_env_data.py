"""Regenerate Abha S0's streets/origins/destinations as RL-env-ready GeoJSON.

Reuses `abha_network_baseline.py` (the mentor's own script, unmodified, same
OSM query: center (18.2264426, 42.5053914), r=1500m, drive network) to
reproduce the exact S0 baseline, then writes out the three files
`MadinaBackend` needs (streets / origins / destinations) in the same layout
`configs/city_madina_ablation.yaml` (Al Nakheel) and `city_madina_jeddah.yaml`
use.

Only the *origins/destinations/streets* layers were ever committed for this
scenario -- the full baseline network was only embedded in a folium HTML (see
`scripts/extract_abha_html_layers.py`), and the origins/destinations layers
were never committed at all. Re-running the same OSM query reconstructs them;
this script cross-checks the printed counts against
`data/abha_baseline/run_output.txt` (1,729 nodes / 4,586 segments / 315
origins / 56 destinations / King Abdulaziz=29) to confirm OSM hasn't drifted
since the mentor's original run.

Writes plain GeoJSON via json.dumps (not GeoDataFrame.to_file) -- this dev
machine's pyogrio/GDAL DLL is blocked by an Application Control policy, see
`_read_geojson()` in `src/snrl/backends/madina_backend.py` for the read-side
equivalent of this same workaround.

Usage:
    python scripts/build_abha_s0_env_data.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import abha_network_baseline as base  # noqa: E402

OUT_DIR = Path("data/raw/abha_s0")

EXPECTED = {
    "nodes": 1729,
    "segments": 4586,
    "origins": 315,
    "destinations": 56,
    "king_abdulaziz_segments": 29,
}


def write_geojson(gdf, path: Path) -> None:
    gdf = gdf.to_crs("EPSG:4326")
    path.write_text(gdf.to_json(), encoding="utf-8")
    print(f"  -> {path} ({len(gdf)} features)")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    nodes, streets, origins, destinations = base.download_abha_osm()
    checks = {
        "nodes": len(nodes),
        "segments": len(streets),
        "origins": len(origins),
        "destinations": len(destinations),
    }

    main_roads = base.extract_main_roads(streets)
    ka_count = int((main_roads["display_name"] == "King Abdulaziz Road").sum())
    checks["king_abdulaziz_segments"] = ka_count

    print("\nCross-check against data/abha_baseline/run_output.txt:")
    all_match = True
    for k, expected in EXPECTED.items():
        actual = checks[k]
        status = "OK" if actual == expected else "MISMATCH"
        if actual != expected:
            all_match = False
        print(f"  {k:<26} expected={expected:<6} actual={actual:<6} {status}")
    if not all_match:
        print("\n  WARNING: OSM data has drifted since the mentor's original run "
              "(edits to Abha's OSM data). Numbers below won't exactly match "
              "data/abha_baseline/baseline_summary.csv.")

    print("\nWriting RL-env inputs:")
    write_geojson(streets, OUT_DIR / "streets.geojson")
    write_geojson(origins, OUT_DIR / "residential.geojson")
    write_geojson(destinations, OUT_DIR / "amenities.geojson")

    summary = {
        "checks": checks,
        "expected": EXPECTED,
        "all_match": all_match,
    }
    (OUT_DIR / "regeneration_check.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"  -> {OUT_DIR / 'regeneration_check.json'}")


if __name__ == "__main__":
    main()
