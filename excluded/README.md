# Excluded Abha Files

This folder contains Abha files that were removed from the active scenario workflow.

They are kept only for traceability and development history and should not be used as current scenario inputs or current results.

## Folder Structure

```text
excluded/
├── README.md
├── maps/
│   ├── abha_corridor_validation_map.html
│   └── abha_s1_oneway_comparison_map_fixed.html
├── geojson/
│   ├── s1a_king_abdulaziz.geojson
│   └── s1b_king_abdulaziz.geojson
├── summaries/
│   ├── s1a_oneway_summary.csv
│   ├── s1b_oneway_summary.csv
│   ├── baseline_summary.csv
│   └── run_output.txt
└── configs/
    ├── city_madina_abha_s0.yaml
    ├── city_madina_abha_s1a.yaml
    ├── city_madina_abha_s1b.yaml
    └── city_madina_abha_s2.yaml
```

## Excluded Experiments

### Previous King Abdulaziz One-Way Experiment

- S1A: King Abdulaziz One-Way NE
- S1B: King Abdulaziz One-Way SW

Associated maps, GeoJSON files, summaries, and configurations are archived here.

### Previous S2 Experiment

The previous S2 configuration represented a hypothetical Green Road bypass from Khamis Mushait toward Sali. It was not based on a confirmed alignment and is archived here.

### Previous S0 Setup

The previous S0 setup used:

- Center: `(18.2264426, 42.5053914)`
- Radius: `1500 m`
- Network type: `drive`
- Total directed road segments: `4,586`
- Origins: `315`
- Destinations: `56`
- Cleaned study corridor: `44 segments`
- Cleaned study corridor length: `7.81 km`

This baseline is retained only as historical reference for the previous scenario setup.

## Usage Rule

Files in this folder are excluded from the active Abha scenario analysis. Do not use them as current simulation inputs or report their outputs as current scenario results.
