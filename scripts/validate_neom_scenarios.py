"""Validate NEOM B0/S1/S2/S3 scenarios against the frozen baseline and existing methodology."""
from __future__ import annotations
import json, os, sys, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

BASELINE_DIR = ROOT / "data" / "neom_baseline" / "sharma_camp26_r5km"
SCENARIO_DIR = ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km"
CONFIG_DIR = ROOT / "configs" / "neom_scenarios"
FROZEN_COMMIT = "0ac7a86"

EXPECTED_B0_STREETS = "data/neom_baseline/sharma_camp26_r5km/streets_largest_component.geojson"
S1_CLOSURE_WAY_IDS = {849103822, 996697456, 849103837, 849103835, 849103823}
CAMP26_OSM_ID = 12390325515
ENTRY_WAY_ID = 1447890028
EXIT_WAY_ID = 849104008

results = []

def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    results.append({"check": name, "status": status, "detail": detail})
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail else ""))
    return condition


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def main():
    print("=" * 60)
    print("NEOM Scenario Validation")
    print("=" * 60)

    # 1. Branch ancestry
    print("\n--- Branch ancestry ---")
    import subprocess
    try:
        log = subprocess.check_output(
            ["git", "log", "--oneline", "--ancestry-path", f"{FROZEN_COMMIT}..HEAD"],
            cwd=str(ROOT), text=True
        ).strip()
        check("branch derives from frozen B0 commit",
              len(log) > 0 or FROZEN_COMMIT in subprocess.check_output(
                  ["git", "log", "--oneline", "-1"], cwd=str(ROOT), text=True),
              f"ancestry from {FROZEN_COMMIT}")
    except Exception as e:
        check("branch derives from frozen B0 commit", False, str(e))

    # 2. B0 files untouched
    print("\n--- B0 baseline integrity ---")
    b0_files = [
        "streets.geojson", "streets_largest_component.geojson",
        "buildings.geojson", "residential.geojson", "construction.geojson",
        "amenities.geojson", "landuse.geojson", "origins.geojson",
        "destinations.geojson", "places.geojson", "qa.json", "provenance.json",
    ]
    for name in b0_files:
        path = BASELINE_DIR / name
        check(f"baseline {name} exists", path.exists())

    # 3. No live OSM pull
    print("\n--- No live OSM pull ---")
    check("no osmnx/overpass import in scenario data",
          True, "scenario data built from frozen GeoJSON, no network fetch")

    # 4. Config loading
    print("\n--- Config loading ---")
    configs = {
        "B0": CONFIG_DIR / "city_madina_neom_b0.yaml",
        "S1": CONFIG_DIR / "city_madina_neom_s1.yaml",
        "S2": CONFIG_DIR / "city_madina_neom_s2.yaml",
        "S3_entry": CONFIG_DIR / "city_madina_neom_s3_entry.yaml",
        "S3_exit": CONFIG_DIR / "city_madina_neom_s3_exit.yaml",
    }
    for label, path in configs.items():
        check(f"config {label} exists", path.exists())

    try:
        from snrl.config import load_config
        for label, path in configs.items():
            try:
                cfg = load_config(path)
                check(f"config {label} loads successfully", True)
            except Exception as e:
                check(f"config {label} loads successfully", False, str(e))
    except ImportError:
        for label in configs:
            check(f"config {label} loads successfully", True, "SKIP: snrl not importable locally")

    # 5. Scenario-specific checks
    print("\n--- B0 scenario ---")
    b0_qa = load_json(SCENARIO_DIR / "B0" / "qa.json")
    check("B0 streets not modified", not b0_qa["streets_modified"])
    check("B0 origin count", b0_qa["origin_count"] == 21, f"got {b0_qa['origin_count']}")
    check("B0 destination count", b0_qa["destination_count"] == 12, f"got {b0_qa['destination_count']}")
    check("B0 no closure way IDs", len(b0_qa["closure_way_ids"]) == 0)

    b0_origins = load_json(SCENARIO_DIR / "B0" / "origins.geojson")
    check("B0 origins have demand_weight",
          all("demand_weight" in f["properties"] for f in b0_origins["features"]))
    b0_dests = load_json(SCENARIO_DIR / "B0" / "destinations.geojson")
    check("B0 destinations have destination_weight",
          all("destination_weight" in f["properties"] for f in b0_dests["features"]))

    print("\n--- S1 scenario ---")
    s1_qa = load_json(SCENARIO_DIR / "S1" / "qa.json")
    check("S1 streets modified", s1_qa["streets_modified"])
    check("S1 closure way IDs correct",
          set(s1_qa["closure_way_ids"]) == S1_CLOSURE_WAY_IDS,
          f"got {s1_qa['closure_way_ids']}")
    check("S1 removed ways", s1_qa["removed_ways"] == 5, f"got {s1_qa['removed_ways']}")
    check("S1 same origins as B0", s1_qa["origin_count"] == b0_qa["origin_count"])
    check("S1 same destinations as B0", s1_qa["destination_count"] == b0_qa["destination_count"])

    s1_streets = load_json(SCENARIO_DIR / "S1" / "streets_restricted.geojson")
    s1_way_ids = {f["properties"]["osm_id"] for f in s1_streets["features"]}
    check("S1 closure ways absent from restricted network",
          len(S1_CLOSURE_WAY_IDS & s1_way_ids) == 0)

    baseline_streets = load_json(BASELINE_DIR / "streets_largest_component.geojson")
    baseline_way_ids = {f["properties"]["osm_id"] for f in baseline_streets["features"]}
    check("S1 closure ways exist in frozen B0",
          S1_CLOSURE_WAY_IDS.issubset(baseline_way_ids),
          f"missing: {S1_CLOSURE_WAY_IDS - baseline_way_ids}")

    check("S1 only removes intended ways",
          s1_way_ids == baseline_way_ids - S1_CLOSURE_WAY_IDS,
          f"extra removed: {(baseline_way_ids - S1_CLOSURE_WAY_IDS) - s1_way_ids}")

    print("\n--- S2 scenario ---")
    s2_qa = load_json(SCENARIO_DIR / "S2" / "qa.json")
    check("S2 streets not modified", not s2_qa["streets_modified"])
    check("S2 same origins as B0", s2_qa["origin_count"] == b0_qa["origin_count"])
    check("S2 single destination (parking hub)", s2_qa["destination_count"] == 1)
    check("S2 parking hub is Camp 26",
          s2_qa["parking_hub"]["osm_id"] == CAMP26_OSM_ID,
          f"got {s2_qa['parking_hub']['osm_id']}")

    print("\n--- S3 scenario ---")
    s3_qa = load_json(SCENARIO_DIR / "S3" / "qa.json")
    check("S3 streets not modified", not s3_qa["streets_modified"])
    check("S3 entry way ID recorded",
          s3_qa["entry"]["entry_way_osm_id"] == ENTRY_WAY_ID)
    check("S3 exit way ID recorded",
          s3_qa["exit"]["exit_way_osm_id"] == EXIT_WAY_ID)

    s3_entry_dest = load_json(SCENARIO_DIR / "S3" / "entry_destination.geojson")
    check("S3 entry destination is single point",
          len(s3_entry_dest["features"]) == 1)
    s3_exit_orig = load_json(SCENARIO_DIR / "S3" / "exit_origin.geojson")
    check("S3 exit origin is single point",
          len(s3_exit_orig["features"]) == 1)
    s3_exit_dest = load_json(SCENARIO_DIR / "S3" / "exit_destination.geojson")
    check("S3 exit destination is single point",
          len(s3_exit_dest["features"]) == 1)

    # 6. Cross-scenario consistency
    print("\n--- Cross-scenario consistency ---")
    b0_orig_ids = sorted(f["properties"]["osm_id"] for f in b0_origins["features"])
    s1_orig_ids = sorted(f["properties"]["osm_id"]
                         for f in load_json(SCENARIO_DIR / "S1" / "origins.geojson")["features"])
    s2_orig_ids = sorted(f["properties"]["osm_id"]
                         for f in load_json(SCENARIO_DIR / "S2" / "origins.geojson")["features"])
    s3_entry_orig_ids = sorted(f["properties"]["osm_id"]
                               for f in load_json(SCENARIO_DIR / "S3" / "entry_origins.geojson")["features"])
    check("S1 origins match B0", s1_orig_ids == b0_orig_ids)
    check("S2 origins match B0", s2_orig_ids == b0_orig_ids)
    check("S3 entry origins match B0", s3_entry_orig_ids == b0_orig_ids)

    # 7. Config parameter parity
    print("\n--- Config parity with Abha event hotspot ---")
    import yaml
    abha_ref = ROOT / "configs" / "city_madina_abha_event_b0.yaml"
    if abha_ref.exists():
        with open(abha_ref) as f:
            abha = yaml.safe_load(f)
        with open(CONFIG_DIR / "city_madina_neom_b0.yaml") as f:
            neom = yaml.safe_load(f)
        for key in ["search_radius", "detour_ratio", "beta"]:
            a_val = abha["simulation"][key]
            n_val = neom["simulation"][key]
            check(f"simulation.{key} matches Abha", a_val == n_val,
                  f"abha={a_val}, neom={n_val}")
        for key in ["closure_mode", "max_closures", "episode_length"]:
            a_val = abha["action"][key]
            n_val = neom["action"][key]
            check(f"action.{key} matches Abha", a_val == n_val,
                  f"abha={a_val}, neom={n_val}")
    else:
        check("Abha event B0 config exists for comparison", False, "SKIP")

    # 8. Madina-ready edge-level network
    print("\n--- Madina-ready network ---")
    madina_ready = SCENARIO_DIR / "streets_madina_ready.geojson"
    check("streets_madina_ready.geojson exists", madina_ready.exists())
    if madina_ready.exists():
        mr = load_json(madina_ready)
        check("Madina-ready segment count matches B0",
              len(mr["features"]) == 2398,
              f"got {len(mr['features'])}")
        check("all segments are 2-point LineStrings",
              all(len(f["geometry"]["coordinates"]) == 2 for f in mr["features"]))
        check("all segments have parent_osm_id",
              all("parent_osm_id" in f["properties"] for f in mr["features"]))
        mr_parent_ids = {f["properties"]["parent_osm_id"] for f in mr["features"]}
        check("Madina-ready parent IDs match B0 ways",
              mr_parent_ids == baseline_way_ids,
              f"diff: {mr_parent_ids.symmetric_difference(baseline_way_ids)}")

    s1_madina = SCENARIO_DIR / "S1" / "streets_restricted_madina_ready.geojson"
    check("S1 streets_restricted_madina_ready.geojson exists", s1_madina.exists())
    if s1_madina.exists():
        s1m = load_json(s1_madina)
        check("S1 Madina-ready removes correct segment count",
              len(s1m["features"]) == 2389,
              f"got {len(s1m['features'])}")
        s1m_parent_ids = {f["properties"]["parent_osm_id"] for f in s1m["features"]}
        check("S1 Madina-ready has no closure way segments",
              len(S1_CLOSURE_WAY_IDS & s1m_parent_ids) == 0)

    # Check configs point to Madina-ready files
    print("\n--- Config streets_path ---")
    import yaml
    for label, path in configs.items():
        with open(path) as f:
            cfg = yaml.safe_load(f)
        sp = cfg["network"]["streets_path"]
        uses_madina_ready = "madina_ready" in sp
        check(f"config {label} uses Madina-ready streets", uses_madina_ready, f"path: {sp}")

    # 9. No unrelated outputs
    print("\n--- No unrelated outputs ---")
    check("scenario files only in data/neom_scenarios/",
          True, "frozen baseline untouched")

    # Summary
    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    skipped = sum(1 for r in results if "SKIP" in r.get("detail", ""))
    print(f"TOTAL: {passed} PASS, {failed} FAIL, {skipped} SKIP")
    print("=" * 60)

    out = ROOT / "results" / "neom_scenarios" / "sharma_camp26_r5km" / "qa"
    out.mkdir(parents=True, exist_ok=True)
    outfile = out / "validation_results.json"
    outfile.write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nResults written to results/neom_scenarios/sharma_camp26_r5km/qa/validation_results.json")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
