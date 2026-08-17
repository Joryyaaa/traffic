#!/usr/bin/env python3
"""Rebuild Event Hotspot GeoJSON inputs directly from the reviewed HTML map."""
from pathlib import Path
import json, re

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "data/abha_baseline/abha_event_hotspot_baseline2_scenarios.html"
OUT = ROOT / "data/abha_event_hotspot"

def object_const(text, name):
    m = re.search(rf"const\s+{re.escape(name)}=(\{{.*?\}});", text, re.S)
    if not m:
        raise RuntimeError(f"Missing map constant: {name}")
    return json.loads(m.group(1))

def point_const(text, name):
    m = re.search(rf"const\s+{re.escape(name)}=\[([0-9.\-]+),([0-9.\-]+)\];", text)
    if not m:
        raise RuntimeError(f"Missing map point: {name}")
    lat, lon = map(float, m.groups())
    return [lon, lat]

def endpoints(features):
    out=[]
    for f in features:
        if f.get("geometry",{}).get("type")=="LineString":
            c=f["geometry"]["coordinates"]
            if c:
                out.extend((c[0],c[-1]))
    return out

text=MAP.read_text(encoding="utf-8")
roads=object_const(text,"roads")
king=object_const(text,"kingAbdulaziz")
closure=object_const(text,"closure")
entry=object_const(text,"entry")
exit_road=object_const(text,"exitRoad")
Z=point_const(text,"Z")
P=point_const(text,"P")

def split_closed_rings(features):
    """Split closed ways so Madina can hold them.

    A LineString whose first coordinate equals its last is one closed way. Madina
    builds light_graph purely from edge start/end pairs, so a closed way becomes a
    self-loop, its Network drops it, and the endpoint it left behind is then a
    street node belonging to no edge -- at which point madina's own create_graph()
    raises KeyError on nodes[idx]['type']. That is the crash this map hit: 88
    input segments produced 87 edges and orphaned node 27, an unnamed trunk ring
    of 29 points at (42.488569, 18.220095).

    Three arcs rather than two: two arcs share both endpoints, and light_graph is
    a plain nx.Graph, so the second would silently overwrite the first and only
    one arc's weight would survive. Three gives three distinct node pairs. The
    coordinates are re-emitted unchanged, so the geometry is identical and the
    id is preserved -- the S1 closure filter matches on properties.id and must
    keep treating the ring as one road.
    """
    out=[]
    for f in features:
        g=f.get("geometry") or {}
        c=g.get("coordinates")
        if (g.get("type")!="LineString" or not c or len(c)<4
                or tuple(c[0])!=tuple(c[-1])):
            out.append(f); continue
        n=len(c)-1  # the closing point repeats index 0
        cuts=[0, n//3, (2*n)//3, n]
        for a,b in zip(cuts, cuts[1:]):
            arc=c[a:b+1]
            if len(arc)<2:
                continue
            props=dict(f.get("properties") or {})
            props["snrl_ring_split"]=True
            out.append({"type":"Feature","properties":props,
                        "geometry":{"type":"LineString","coordinates":arc}})
    return out


seen=set(); feats=[]
for f in roads["features"]+king["features"]:
    fid=f.get("properties",{}).get("id")
    key=("id",fid) if fid is not None else ("geom",json.dumps(f.get("geometry"),sort_keys=True))
    if key not in seen:
        seen.add(key); feats.append(f)

feats=split_closed_rings(feats)

baseline={"type":"FeatureCollection","features":feats}
closure_ids={f.get("properties",{}).get("id") for f in closure["features"]}
s1={"type":"FeatureCollection","features":[f for f in feats if f.get("properties",{}).get("id") not in closure_ids]}

pts=endpoints(feats)
extremes=[
    ("north",max(pts,key=lambda p:p[1])),
    ("south",min(pts,key=lambda p:p[1])),
    ("east",max(pts,key=lambda p:p[0])),
    ("west",min(pts,key=lambda p:p[0])),
]
unique=[]
for label,p in extremes:
    if p not in [x[1] for x in unique]:
        unique.append((label,p))
origins={"type":"FeatureCollection","features":[
    {"type":"Feature","properties":{"origin_id":f"ref_{label}","demand_weight":1.0,"demand_type":"provisional_reference"},
     "geometry":{"type":"Point","coordinates":p}} for label,p in unique
]}

def near(fc,target):
    return min(endpoints(fc["features"]),key=lambda p:(p[0]-target[0])**2+(p[1]-target[1])**2)
def far(fc,target):
    return max(endpoints(fc["features"]),key=lambda p:(p[0]-target[0])**2+(p[1]-target[1])**2)

files={
 "event_baseline_streets.geojson":baseline,
 "event_s1_restricted_streets.geojson":s1,
 "event_reference_origins.geojson":origins,
 "event_zone_destinations.geojson":{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"destination_id":"event_zone","destination_weight":1.0},"geometry":{"type":"Point","coordinates":Z}}]},
 "event_parking_destination.geojson":{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"destination_id":"main_parking_P","destination_weight":1.0},"geometry":{"type":"Point","coordinates":P}}]},
 "event_s3_entry_destination.geojson":{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"destination_id":"managed_entry","destination_weight":1.0},"geometry":{"type":"Point","coordinates":near(entry,Z)}}]},
 "event_s3_exit_origins.geojson":{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"origin_id":"event_zone_exit","demand_weight":1.0},"geometry":{"type":"Point","coordinates":Z}}]},
 "event_s3_exit_destination.geojson":{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"destination_id":"managed_exit","destination_weight":1.0},"geometry":{"type":"Point","coordinates":far(exit_road,Z)}}]},
 "event_s1_closure_reference.geojson":closure,
 "event_s3_entry_reference.geojson":entry,
 "event_s3_exit_reference.geojson":exit_road,
}
OUT.mkdir(parents=True,exist_ok=True)
for name,obj in files.items():
    (OUT/name).write_text(json.dumps(obj,indent=2),encoding="utf-8")
print(f"Built {len(files)} Event Hotspot data files in {OUT}")
print(f"Baseline segments: {len(baseline['features'])}")
print(f"S1 segments: {len(s1['features'])} (removed {len(baseline['features'])-len(s1['features'])})")
print(f"Reference origins: {len(origins['features'])}")
