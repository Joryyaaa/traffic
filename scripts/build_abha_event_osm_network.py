#!/usr/bin/env python3
"""Build Abha Event Hotspot directly from OpenStreetMap."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
from shapely.geometry import LineString, Point

CENTER=(18.21385,42.49445)
DEFAULT_RADIUS_M=2200
METRIC_CRS="EPSG:32638"
CLOSURE_WAY_ID=95507294
ENTRY_WAY_ID=787786457
EXIT_WAY_ID=135229579
EVENT_ZONE=Point(42.49445,18.21385)
PARKING_P=Point(42.49902,18.21418)

def contains_way_id(value,target):
    if isinstance(value,(list,tuple,set,np.ndarray)):
        return any(contains_way_id(v,target) for v in value)
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

def outer_endpoint(edges,way_id):
    rows=edges[edges['osmid'].map(lambda x:contains_way_id(x,way_id))]
    if rows.empty:raise RuntimeError(f'Required OSM way {way_id} not present')
    pts=[]
    for g in rows.geometry:pts.extend([Point(g.coords[0]),Point(g.coords[-1])])
    m=gpd.GeoSeries(pts,crs='EPSG:4326').to_crs(METRIC_CRS)
    cp=gpd.GeoSeries([EVENT_ZONE],crs='EPSG:4326').to_crs(METRIC_CRS).iloc[0]
    return pts[max(range(len(pts)),key=lambda i:m.iloc[i].distance(cp))]

def write_point(path,p,props):
    gpd.GeoDataFrame([props],geometry=[p],crs='EPSG:4326').to_file(path,driver='GeoJSON')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--radius',type=float,default=DEFAULT_RADIUS_M); ap.add_argument('--out',default='data/abha_event_hotspot_osm'); a=ap.parse_args()
    out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    print(f'Fetching OSM drive network: center={CENTER}, radius={a.radius}m')
    G=ox.graph_from_point(CENTER,dist=a.radius,network_type='drive',simplify=True,retain_all=False,truncate_by_edge=True)
    _,edges=ox.graph_to_gdfs(G,nodes=True,edges=True,fill_edge_geometry=True); edges=edges.reset_index()
    keep=['u','v','key','osmid','oneway','junction','name','highway','length','geometry']
    for c in keep:
        if c not in edges.columns:edges[c]=None
    edges=edges[keep].copy(); edges['osmid']=edges['osmid'].map(normalize_osmid); edges=split_closed_rows(edges)
    qa=component_check(edges)
    if qa['components']!=1:raise RuntimeError(f"OSM crop disconnected ({qa['components']} components). Adjust crop/builder; do not fix with node snapping.")
    req={'closure':CLOSURE_WAY_ID,'entry':ENTRY_WAY_ID,'exit':EXIT_WAY_ID}
    present={k:bool(edges['osmid'].map(lambda x,w=w:contains_way_id(x,w)).any()) for k,w in req.items()}
    if not all(present.values()):raise RuntimeError('Required mapped OSM ways missing: '+str({k:req[k] for k,v in present.items() if not v}))
    qa.update({'required_way_ids':req,'required_way_ids_present':present,'closed_geometry_rows_after_split':sum(list(g.coords)[0]==list(g.coords)[-1] for g in edges.geometry),'S3_mode':'single directed run; respect_oneway=True'})
    edges.to_file(out/'B0_baseline_streets.geojson',driver='GeoJSON')
    mask=edges['osmid'].map(lambda x:contains_way_id(x,CLOSURE_WAY_ID)); edges.loc[~mask].to_file(out/'S1_vehicle_restriction_streets.geojson',driver='GeoJSON')
    write_point(out/'event_zone_destination.geojson',EVENT_ZONE,{'destination_id':'event_zone','destination_weight':1.0})
    write_point(out/'parking_P_destination.geojson',PARKING_P,{'destination_id':'parking_P','destination_weight':1.0})
    write_point(out/'S3_entry_origin.geojson',outer_endpoint(edges,ENTRY_WAY_ID),{'origin_id':'managed_entry','demand_weight':1.0,'osm_way_id':ENTRY_WAY_ID})
    write_point(out/'S3_exit_destination.geojson',outer_endpoint(edges,EXIT_WAY_ID),{'destination_id':'managed_exit','destination_weight':1.0,'osm_way_id':EXIT_WAY_ID})
    qa['B0_segments']=len(edges); qa['S1_segments']=len(edges.loc[~mask]); qa['S1_removed_rows']=int(mask.sum())
    (out/'qa_report.json').write_text(json.dumps(qa,indent=2)); print(json.dumps(qa,indent=2))
if __name__=='__main__':main()
