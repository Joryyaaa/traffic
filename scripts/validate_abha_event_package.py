#!/usr/bin/env python3
from pathlib import Path
import json, yaml

ROOT=Path(__file__).resolve().parents[1]
CONFIGS=[
 "configs/city_madina_abha_event_b0.yaml",
 "configs/city_madina_abha_event_s1.yaml",
 "configs/city_madina_abha_event_s2.yaml",
 "configs/city_madina_abha_event_s3_entry.yaml",
 "configs/city_madina_abha_event_s3_exit.yaml",
]
ok=True
for rel in CONFIGS:
    p=ROOT/rel
    if not p.exists():
        print("MISSING CONFIG",rel); ok=False; continue
    cfg=yaml.safe_load(p.read_text())
    if cfg["network"]["backend"]!="madina":
        print("NOT MADINA",rel); ok=False
    paths=[]
    for key in ("streets_path","origins_path","destinations_path"):
        q=ROOT/cfg["network"][key]
        paths.append(q)
        if not q.exists():
            print("MISSING",rel,key,q); ok=False
    if all(q.exists() for q in paths):
        streets=json.loads(paths[0].read_text())
        origins=json.loads(paths[1].read_text())
        dests=json.loads(paths[2].read_text())
        print(f"{Path(rel).name}: streets={len(streets['features'])}, origins={len(origins['features'])}, destinations={len(dests['features'])}")
if not ok:
    raise SystemExit(1)
print("Event Hotspot package structure: OK")
