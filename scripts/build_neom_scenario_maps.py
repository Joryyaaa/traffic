"""Generate Leaflet HTML maps for NEOM B0/S1/S2/S3 scenarios + combined comparison."""
from __future__ import annotations
import json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_DIR = ROOT / "data" / "neom_baseline" / "sharma_camp26_r5km"
SCENARIO_DIR = ROOT / "data" / "neom_scenarios" / "sharma_camp26_r5km"
OUT_DIR = ROOT / "results" / "neom_scenarios" / "sharma_camp26_r5km" / "maps"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CENTER = [28.03066, 35.24203]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def geojson_to_js(gj):
    return json.dumps(gj, ensure_ascii=False)


def leaflet_head(title):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
body{{margin:0;padding:0}}
#map{{width:100%;height:100vh}}
.legend{{background:white;padding:10px;border-radius:5px;box-shadow:0 0 5px rgba(0,0,0,.3);line-height:1.6;font-family:sans-serif;font-size:12px}}
.legend i{{width:12px;height:12px;display:inline-block;margin-right:5px;border-radius:2px}}
</style></head><body>
<div id="map"></div>
<script>
"""


def leaflet_tail():
    return """</script></body></html>"""


def add_streets_layer(var_name, gj_str, color, weight, label):
    return f"""
var {var_name} = L.geoJSON({gj_str}, {{
  style: function(){{ return {{color:'{color}',weight:{weight},opacity:0.7}}; }}
}}).bindPopup(function(l){{
  var p = l.feature.properties;
  return '<b>{label}</b><br>OSM ID: '+p.osm_id+'<br>highway: '+(p.highway||'');
}});
"""


def add_points_layer(var_name, gj_str, color, radius, label, popup_fn=""):
    if not popup_fn:
        popup_fn = f"'<b>{label}</b><br>OSM ID: '+p.osm_id"
    return f"""
var {var_name} = L.geoJSON({gj_str}, {{
  pointToLayer: function(f,ll){{
    return L.circleMarker(ll, {{radius:{radius},color:'{color}',fillColor:'{color}',fillOpacity:0.8,weight:1}});
  }}
}}).bindPopup(function(l){{
  var p = l.feature.properties;
  return {popup_fn};
}});
"""


def legend_html(items):
    html = '<div class="legend">'
    for color, label in items:
        html += f'<div><i style="background:{color}"></i> {label}</div>'
    html += '</div>'
    return html


def init_map(layers_shown, legend_items, extra_layers=""):
    layers_str = ", ".join(layers_shown)
    return f"""
var map = L.map('map', {{
  center: [{CENTER[0]}, {CENTER[1]}],
  zoom: 13,
  layers: [{layers_str}]
}});
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: 'OSM',
  maxZoom: 18
}}).addTo(map);
{extra_layers}
var legend = L.control({{position:'bottomright'}});
legend.onAdd = function(){{
  var div = L.DomUtil.create('div');
  div.innerHTML = '{legend_html(legend_items).replace(chr(10),"").replace(chr(39),chr(92)+chr(39))}';
  return div;
}};
legend.addTo(map);
"""


def build_b0_map():
    streets = load_json(BASELINE_DIR / "streets_largest_component.geojson")
    origins = load_json(SCENARIO_DIR / "B0" / "origins.geojson")
    dests = load_json(SCENARIO_DIR / "B0" / "destinations.geojson")
    construction = load_json(BASELINE_DIR / "construction.geojson")

    html = leaflet_head("NEOM B0 — Baseline Scenario")
    html += add_streets_layer("streets", geojson_to_js(streets), "#3388ff", 2, "Street")
    html += add_points_layer("origins", geojson_to_js(origins), "#e74c3c", 6, "Worker Origin",
                             "'<b>Worker Origin</b><br>OSM ID: '+p.osm_id+'<br>Type: '+(p.origin_type||'')+'<br>Name: '+(p.name||'-')")
    html += add_points_layer("dests", geojson_to_js(dests), "#2ecc71", 7, "Construction Dest",
                             "'<b>Construction Destination</b><br>OSM ID: '+p.osm_id+'<br>ID: '+(p.destination_id||'')")
    html += f"""
var construction = L.geoJSON({geojson_to_js(construction)}, {{
  style: function(){{ return {{color:'#f39c12',weight:1,fillColor:'#f39c12',fillOpacity:0.2}}; }}
}}).bindPopup(function(l){{
  var p = l.feature.properties;
  return '<b>Construction Zone</b><br>OSM ID: '+p.osm_id;
}});
"""
    html += init_map(["streets","origins","dests","construction"],
                     [("#3388ff","Streets (B0 full network)"),
                      ("#e74c3c","Worker origins (21 dormitories)"),
                      ("#2ecc71","Construction destinations (12 zones)"),
                      ("#f39c12","Construction areas")])
    html += leaflet_tail()
    (OUT_DIR / "scenario_b0.html").write_text(html, encoding="utf-8")
    print("  wrote scenario_b0.html")


def build_s1_map():
    streets_r = load_json(SCENARIO_DIR / "S1" / "streets_restricted.geojson")
    closure = load_json(SCENARIO_DIR / "S1" / "closure_reference.geojson")
    origins = load_json(SCENARIO_DIR / "S1" / "origins.geojson")
    dests = load_json(SCENARIO_DIR / "S1" / "destinations.geojson")

    html = leaflet_head("NEOM S1 — Construction Zone Restriction")
    html += add_streets_layer("streets", geojson_to_js(streets_r), "#3388ff", 2, "Restricted Network")
    html += f"""
var closure = L.geoJSON({geojson_to_js(closure)}, {{
  style: function(){{ return {{color:'#e74c3c',weight:4,opacity:0.9,dashArray:'6,4'}}; }}
}}).bindPopup(function(l){{
  var p = l.feature.properties;
  return '<b>CLOSED Road</b><br>OSM ID: '+p.osm_id+'<br>highway: '+(p.highway||'');
}});
"""
    html += add_points_layer("origins", geojson_to_js(origins), "#e67e22", 5, "Worker Origin")
    html += add_points_layer("dests", geojson_to_js(dests), "#2ecc71", 7, "Construction Dest")
    html += init_map(["streets","closure","origins","dests"],
                     [("#3388ff","Restricted network (269 ways)"),
                      ("#e74c3c","Closed roads (5 ways, dashed)"),
                      ("#e67e22","Worker origins (21)"),
                      ("#2ecc71","Construction destinations (12)")])
    html += leaflet_tail()
    (OUT_DIR / "scenario_s1.html").write_text(html, encoding="utf-8")
    print("  wrote scenario_s1.html")


def build_s2_map():
    streets = load_json(BASELINE_DIR / "streets_largest_component.geojson")
    origins = load_json(SCENARIO_DIR / "S2" / "origins.geojson")
    dests = load_json(SCENARIO_DIR / "S2" / "destinations.geojson")

    html = leaflet_head("NEOM S2 — Parking Hub at Camp 26")
    html += add_streets_layer("streets", geojson_to_js(streets), "#3388ff", 2, "Street")
    html += add_points_layer("origins", geojson_to_js(origins), "#e74c3c", 5, "Worker Origin")
    html += add_points_layer("dests", geojson_to_js(dests), "#9b59b6", 10, "Camp 26 Parking Hub",
                             "'<b>Camp 26 Parking Hub</b><br>OSM ID: '+p.osm_id")
    html += init_map(["streets","origins","dests"],
                     [("#3388ff","Streets (full network)"),
                      ("#e74c3c","Worker origins (21)"),
                      ("#9b59b6","Camp 26 parking hub (1 dest)")])
    html += leaflet_tail()
    (OUT_DIR / "scenario_s2.html").write_text(html, encoding="utf-8")
    print("  wrote scenario_s2.html")


def build_s3_map():
    streets = load_json(BASELINE_DIR / "streets_largest_component.geojson")
    entry_orig = load_json(SCENARIO_DIR / "S3" / "entry_origins.geojson")
    entry_dest = load_json(SCENARIO_DIR / "S3" / "entry_destination.geojson")
    exit_orig = load_json(SCENARIO_DIR / "S3" / "exit_origin.geojson")
    exit_dest = load_json(SCENARIO_DIR / "S3" / "exit_destination.geojson")

    html = leaflet_head("NEOM S3 — Managed Entry/Exit Gates")
    html += add_streets_layer("streets", geojson_to_js(streets), "#95a5a6", 1.5, "Street")
    html += add_points_layer("entryOrig", geojson_to_js(entry_orig), "#e74c3c", 5, "Entry Origin (worker)")
    html += add_points_layer("entryDest", geojson_to_js(entry_dest), "#2ecc71", 10, "Entry Gate",
                             "'<b>Entry Gate (trunk junction)</b><br>lat: '+l.feature.geometry.coordinates[1].toFixed(5)+'<br>lon: '+l.feature.geometry.coordinates[0].toFixed(5)")
    html += add_points_layer("exitOrig", geojson_to_js(exit_orig), "#f39c12", 10, "Exit Origin (construction center)",
                             "'<b>Exit Origin (construction center)</b>'")
    html += add_points_layer("exitDest", geojson_to_js(exit_dest), "#8e44ad", 10, "Exit Gate (south)",
                             "'<b>Exit Gate (trunk south)</b>'")
    html += init_map(["streets","entryOrig","entryDest","exitOrig","exitDest"],
                     [("#95a5a6","Streets (full network)"),
                      ("#e74c3c","Entry: worker origins (21)"),
                      ("#2ecc71","Entry gate (trunk junction)"),
                      ("#f39c12","Exit origin (construction center)"),
                      ("#8e44ad","Exit gate (trunk south)")])
    html += leaflet_tail()
    (OUT_DIR / "scenario_s3.html").write_text(html, encoding="utf-8")
    print("  wrote scenario_s3.html")


def build_combined_map():
    streets = load_json(BASELINE_DIR / "streets_largest_component.geojson")
    closure = load_json(SCENARIO_DIR / "S1" / "closure_reference.geojson")
    b0_origins = load_json(SCENARIO_DIR / "B0" / "origins.geojson")
    b0_dests = load_json(SCENARIO_DIR / "B0" / "destinations.geojson")
    s2_dests = load_json(SCENARIO_DIR / "S2" / "destinations.geojson")
    s3_entry_dest = load_json(SCENARIO_DIR / "S3" / "entry_destination.geojson")
    s3_exit_orig = load_json(SCENARIO_DIR / "S3" / "exit_origin.geojson")
    s3_exit_dest = load_json(SCENARIO_DIR / "S3" / "exit_destination.geojson")

    html = leaflet_head("NEOM Scenarios — Combined Comparison")
    html += add_streets_layer("streets", geojson_to_js(streets), "#bdc3c7", 1.5, "Street")
    html += f"""
var closure = L.geoJSON({geojson_to_js(closure)}, {{
  style: function(){{ return {{color:'#e74c3c',weight:4,opacity:0.9,dashArray:'6,4'}}; }}
}}).bindPopup(function(l){{
  return '<b>S1 Closed Road</b><br>OSM ID: '+l.feature.properties.osm_id;
}});
"""
    html += add_points_layer("origins", geojson_to_js(b0_origins), "#e67e22", 5, "Worker Origin")
    html += add_points_layer("b0Dests", geojson_to_js(b0_dests), "#2ecc71", 6, "B0 Construction Dest")
    html += add_points_layer("s2Dest", geojson_to_js(s2_dests), "#9b59b6", 10, "S2 Camp 26 Hub",
                             "'<b>S2 Parking Hub (Camp 26)</b>'")
    html += add_points_layer("s3EntryGate", geojson_to_js(s3_entry_dest), "#3498db", 10, "S3 Entry Gate",
                             "'<b>S3 Entry Gate</b>'")
    html += add_points_layer("s3ExitOrig", geojson_to_js(s3_exit_orig), "#f1c40f", 9, "S3 Exit Origin",
                             "'<b>S3 Exit Origin (construction center)</b>'")
    html += add_points_layer("s3ExitGate", geojson_to_js(s3_exit_dest), "#1abc9c", 10, "S3 Exit Gate",
                             "'<b>S3 Exit Gate (south)</b>'")

    html += f"""
var map = L.map('map', {{
  center: [{CENTER[0]}, {CENTER[1]}],
  zoom: 12,
  layers: [streets, origins, b0Dests, closure, s2Dest, s3EntryGate, s3ExitOrig, s3ExitGate]
}});
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: 'OSM', maxZoom: 18
}}).addTo(map);

var overlays = {{
  "Streets": streets,
  "Worker Origins (B0/S1/S2/S3-entry)": origins,
  "B0 Construction Destinations": b0Dests,
  "S1 Closed Roads": closure,
  "S2 Camp 26 Hub": s2Dest,
  "S3 Entry Gate": s3EntryGate,
  "S3 Exit Origin": s3ExitOrig,
  "S3 Exit Gate": s3ExitGate
}};
L.control.layers(null, overlays, {{collapsed: false}}).addTo(map);

var legend = L.control({{position:'bottomright'}});
legend.onAdd = function(){{
  var div = L.DomUtil.create('div');
  div.innerHTML = '{legend_html([
      ("#bdc3c7","Streets (full network)"),
      ("#e74c3c","S1 closed roads (dashed)"),
      ("#e67e22","Worker origins (shared)"),
      ("#2ecc71","B0 construction dests"),
      ("#9b59b6","S2 Camp 26 hub"),
      ("#3498db","S3 entry gate"),
      ("#f1c40f","S3 exit origin"),
      ("#1abc9c","S3 exit gate (south)")
  ]).replace(chr(10),"").replace(chr(39),chr(92)+chr(39))}';
  return div;
}};
legend.addTo(map);
"""
    html += leaflet_tail()
    (OUT_DIR / "scenarios_combined.html").write_text(html, encoding="utf-8")
    print("  wrote scenarios_combined.html")


def main():
    print("Building NEOM scenario maps...")
    build_b0_map()
    build_s1_map()
    build_s2_map()
    build_s3_map()
    build_combined_map()
    print(f"\nAll maps written to results/neom_scenarios/sharma_camp26_r5km/maps/")


if __name__ == "__main__":
    main()
