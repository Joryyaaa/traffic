#!/usr/bin/env python3
"""Build the clean Makkah Ibrahim Al Khalil B0 baseline directly from OpenStreetMap."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
from shapely.geometry import LineString

CENTER=(21.4177,39.8228)
DEFAULT_RADIUS_M=1800
IBRAHIM_AL_KHALIL_WAY_ID=263016253
REQUIRED_NODE_IDS=(5129445142,5077724339)

def contains_osmid(value,target):
    if isinstance(value,(list,tuple,set,np.ndarray)):
        return any(contains_osmid(v,target) for v in value)
    return any(x.strip()==str(target) for x in str(value).replace('[','').replace(']','').split(','))

def normalize_osmid(value):
    if isinstance(value,(list,tuple,set,np.ndarray)):
        return [int(v) if str(v).isdigit() else str(v) for v in value]
    try:return int(value)
    except Exception:return str(value)

def split_closed_rows(edges):
    rows=[]; n=0
    for _,row in edges.iterrows():
        g=row.geometry
        if g is None or g.is_empty or g.geom_type!='LineString':continue
        c=list(g.coords)
        if len(c)>=4 and c[0]==c[-1]:
            n+=1
            for i in range(len(c)-1):
                if c[i]==c[i+1]:continue
                r=row.copy(); r.geometry=LineString([c[i],c[i+1]]); r['closed_way_split']=True; rows.append(r)
        else:
            r=row.copy(); r['closed_way_split']=False; rows.append(r)
    print('Closed/ring geometries split:',n)
    return gpd.GeoDataFrame(rows,crs=edges.crs).reset_index(drop=True)

def component_check(edges):
    G=nx.Graph()
    for _,r in edges.iterrows():G.add_edge(int(r['u']),int(r['v']))
    comps=list(nx.connected_components(G))
    return {'components':len(comps),'nodes':G.number_of_nodes(),'edges':G.number_of_edges(),'component_node_sizes':sorted((len(c) for c in comps),reverse=True)[:20]}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--radius',type=float,default=DEFAULT_RADIUS_M); ap.add_argument('--out',default='data/makkah_ibrahim_osm'); a=ap.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    print(f'Fetching Makkah OSM drive network: center={CENTER}, radius={a.radius}m')
    G=ox.graph_from_point(CENTER,dist=a.radius,network_type='drive',simplify=True,retain_all=False,truncate_by_edge=True)
    nodes,edges=ox.graph_to_gdfs(G,nodes=True,edges=True,fill_edge_geometry=True); edges=edges.reset_index()
    keep=['u','v','key','osmid','oneway','junction','name','highway','length','geometry']
    for c in keep:
        if c not in edges.columns:edges[c]=None
    edges=edges[keep].copy(); edges['osmid']=edges['osmid'].map(normalize_osmid); edges=split_closed_rows(edges)
    qa=component_check(edges)
    if qa['components']!=1:raise RuntimeError(f"OSM crop disconnected ({qa['components']} components). Adjust crop/builder; do not fix with node snapping.")
    way_present=bool(edges['osmid'].map(lambda x:contains_osmid(x,IBRAHIM_AL_KHALIL_WAY_ID)).any())
    node_presence={str(n):bool(n in G.nodes) for n in REQUIRED_NODE_IDS}
    if not way_present:raise RuntimeError(f'Required Ibrahim Al Khalil OSM way {IBRAHIM_AL_KHALIL_WAY_ID} not present')
    if not all(node_presence.values()):raise RuntimeError('Required Makkah OSM nodes missing: '+str([n for n,v in node_presence.items() if not v]))
    qa.update({'required_way_id':IBRAHIM_AL_KHALIL_WAY_ID,'required_way_id_present':way_present,'required_node_ids':list(REQUIRED_NODE_IDS),'required_node_ids_present':node_presence,'closed_geometry_rows_after_split':sum(list(g.coords)[0]==list(g.coords)[-1] for g in edges.geometry),'baseline':'B0 only; no scenario modifications'})
    edges.to_file(out/'B0_baseline_streets.geojson',driver='GeoJSON')
    qa['B0_segments']=len(edges)
    (out/'qa_report.json').write_text(json.dumps(qa,indent=2)); print(json.dumps(qa,indent=2))
if __name__=='__main__':main()
