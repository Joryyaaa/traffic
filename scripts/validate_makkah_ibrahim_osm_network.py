#!/usr/bin/env python3
from pathlib import Path
import json
import geopandas as gpd
import networkx as nx
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data/makkah_ibrahim_osm'
required=['B0_baseline_streets.geojson','qa_report.json']
missing=[x for x in required if not (D/x).exists()]
if missing:raise SystemExit('Missing files:\n'+'\n'.join(missing))
qa=json.loads((D/'qa_report.json').read_text())
assert qa['components']==1,qa
assert qa['required_way_id_present'],qa
assert all(qa['required_node_ids_present'].values()),qa
assert qa['closed_geometry_rows_after_split']==0,qa
streets=gpd.read_file(D/'B0_baseline_streets.geojson'); G=nx.Graph()
for _,r in streets.iterrows():G.add_edge(int(r['u']),int(r['v']))
assert nx.number_connected_components(G)==1
print('PASS: one connected Makkah OSM component')
print('PASS: Ibrahim Al Khalil OSM way present:',qa['required_way_id'])
print('PASS: required Makkah OSM nodes present:',qa['required_node_ids'])
print('PASS: no closed street geometries remain')
print('PASS: clean B0 baseline only; no scenario modifications')
print(json.dumps(qa,indent=2))
