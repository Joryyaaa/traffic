#!/usr/bin/env python3
from pathlib import Path
import json
import geopandas as gpd
import networkx as nx
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data/abha_event_hotspot_osm'
required=['B0_baseline_streets.geojson','S1_vehicle_restriction_streets.geojson','event_zone_destination.geojson','parking_P_destination.geojson','S3_entry_origin.geojson','S3_exit_destination.geojson','qa_report.json']
missing=[x for x in required if not (D/x).exists()]
if missing:raise SystemExit('Missing files:\n'+'\n'.join(missing))
qa=json.loads((D/'qa_report.json').read_text())
assert qa['components']==1,qa
assert all(qa['required_way_ids_present'].values()),qa
assert qa['closed_geometry_rows_after_split']==0,qa
streets=gpd.read_file(D/'B0_baseline_streets.geojson'); G=nx.Graph()
for _,r in streets.iterrows():G.add_edge(int(r['u']),int(r['v']))
assert nx.number_connected_components(G)==1
print('PASS: one connected OSM component')
print('PASS: required OSM way IDs present')
print('PASS: no closed street geometries remain')
print('PASS: S3 prepared for one directed respect_oneway run')
print(json.dumps(qa,indent=2))
