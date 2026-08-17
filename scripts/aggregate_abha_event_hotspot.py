#!/usr/bin/env python3
from pathlib import Path
import csv, json
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/"results/abha_event_hotspot_madina"
NAMES={
 "B0":"B0_Baseline",
 "S1":"S1_Event_Zone_Vehicle_Restriction",
 "S2":"S2_Main_Parking_Hub",
 "S3":"S3_Managed_Entry_Exit",
}
required=[R/f"{NAMES[s]}.json" for s in ("B0","S1","S2","S3")]
missing=[str(p) for p in required if not p.exists()]
if missing:
    raise SystemExit("Missing successful scenario result(s):\n"+"\n".join(missing))
rows=[]
full={}
for p in required:
    d=json.loads(p.read_text())
    if d.get("backend")!="madina":
        raise SystemExit(f"{p} is not a real Madina result")
    full[d["scenario"]]=d
    runs=d["runs"]
    rows.append({
      "scenario":d["scenario"],
      "scenario_name":d.get("scenario_name",d["scenario"]),
      "runtime_seconds":sum(x["runtime_seconds"] for x in runs),
      "mean_accessibility":sum(x["mean_accessibility"] for x in runs)/len(runs),
      "mean_trip_distance":sum(x["mean_trip_distance"] for x in runs)/len(runs),
      "unreachable_fraction":sum(x["unreachable_fraction"] for x in runs)/len(runs),
      "n_components_max":max(x["n_components"] for x in runs),
      "total_segment_flow":sum(x["total_segment_flow"] for x in runs),
    })
(R/"scenario_comparison.json").write_text(json.dumps({"scenarios":full,"summary":rows},indent=2))
with (R/"scenario_comparison.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
lines=["# Abha Event Hotspot — Madina Comparison","",
       "| Scenario | Name | Runtime (s) | Mean accessibility | Mean trip distance | Unreachable fraction | Max components | Total segment flow |",
       "|---|---|---:|---:|---:|---:|---:|---:|"]
for r in rows:
    lines.append(f"| {r['scenario']} | {r['scenario_name']} | {r['runtime_seconds']:.3f} | {r['mean_accessibility']:.6g} | {r['mean_trip_distance']:.3f} | {r['unreachable_fraction']:.6g} | {r['n_components_max']} | {r['total_segment_flow']:.6g} |")
(R/"scenario_comparison.md").write_text("\n".join(lines))
print("Wrote scenario_comparison.json/csv/md")
