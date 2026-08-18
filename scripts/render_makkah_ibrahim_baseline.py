#!/usr/bin/env python3
from pathlib import Path
import geopandas as gpd
import folium
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'data/makkah_ibrahim_osm/B0_baseline_streets.geojson'
OUT=ROOT/'results/makkah_ibrahim_osm/makkah_ibrahim_baseline.html'
if not SRC.exists():raise SystemExit(f'Missing baseline: {SRC}')
edges=gpd.read_file(SRC).to_crs('EPSG:4326')
center=[float(edges.geometry.centroid.y.mean()),float(edges.geometry.centroid.x.mean())]
m=folium.Map(location=center,zoom_start=15,tiles='CartoDB positron')
folium.GeoJson(edges[['geometry']],name='B0 Baseline',style_function=lambda _: {'color':'#3568a8','weight':2.2,'opacity':0.8}).add_to(m)
ibrahim=edges[edges['osmid'].astype(str).str.contains('263016253',regex=False)]
if not ibrahim.empty:
    folium.GeoJson(ibrahim[['geometry']],name='Ibrahim Al Khalil (OSM way 263016253)',style_function=lambda _: {'color':'#d62728','weight':5,'opacity':1}).add_to(m)
folium.LayerControl().add_to(m)
OUT.parent.mkdir(parents=True,exist_ok=True); m.save(OUT)
print('MAP:',OUT)
