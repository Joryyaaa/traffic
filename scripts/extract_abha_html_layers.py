"""One-off: pull the embedded GeoJSON layers back out of the mentor's folium HTML maps.

The S0 baseline was only committed to git as two folium HTML files (the full network
geometry was never saved as a standalone .geojson) -- folium embeds each layer's GeoJSON
as a `var geo_json_XXX = {...};` JS literal inside the page. This walks the HTML with a
brace-matching scan (stdlib only, no bs4/geopandas needed) and writes each layer back out
as a real .geojson file, in the same order the source scripts added them.

Usage:
    python scripts/extract_abha_html_layers.py
"""
from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path

SRC_DIR = Path("data/abha_baseline")
OUT_DIR = Path("data/abha_baseline/extracted")

# (html file, [layer names in the order folium's FeatureGroups were added])
FILES = {
    "abha_corridor_validation_map.html": [
        "s0_full_network",
        "s0_main_roads",
        "s0_study_corridor",
    ],
    "abha_s1_oneway_comparison_map.html": [
        "s0_full_network_v2",
        "s0_study_corridor_v2",
        "s1a_target_open",
        "s1a_target_closed",
        "s1b_target_open",
        "s1b_target_closed",
    ],
}


def extract_geo_json_blocks(html: str) -> list[dict]:
    """Find every `var geo_json_XXX = { ... };` and brace-match to the closing `}`."""
    blocks = []
    for m in re.finditer(r"geo_json_[a-f0-9]+_add\(\s*", html):
        start = m.end()
        assert html[start] == "{", html[start:start + 40]
        depth = 0
        i = start
        in_string = False
        escape = False
        while i < len(html):
            ch = html[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
            i += 1
        blocks.append(json.loads(html_lib.unescape(html[start:i])))
    return blocks


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for fname, layer_names in FILES.items():
        path = SRC_DIR / fname
        html = path.read_text(encoding="utf-8")
        blocks = extract_geo_json_blocks(html)
        print(f"{fname}: found {len(blocks)} geo_json blocks, expected {len(layer_names)}")
        for name, block in zip(layer_names, blocks):
            n_features = len(block.get("features", []))
            out_path = OUT_DIR / f"{name}.geojson"
            out_path.write_text(json.dumps(block), encoding="utf-8")
            print(f"  -> {out_path} ({n_features} features)")


if __name__ == "__main__":
    main()
