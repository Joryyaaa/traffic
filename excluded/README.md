# Excluded Abha Files

This folder contains Abha files that are no longer part of the active scenario workflow.

The archived material is retained only for traceability and development history. Files under `excluded/` should not be used as current scenario inputs or reported as current scenario results.

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
├── configs/
│   ├── city_madina_abha_s0.yaml
│   ├── city_madina_abha_s1a.yaml
│   ├── city_madina_abha_s1b.yaml
│   └── city_madina_abha_s2.yaml
├── scripts/
│   ├── _probe_abha_s0_timing.py
│   ├── abha_network_baseline.py
│   ├── abha_s1_oneway_scenarios.py
│   ├── build_abha_s0_env_data.py
│   ├── build_abha_s1_env_data.py
│   ├── build_abha_s2_env_data.py
│   ├── extract_abha_html_layers.py
│   ├── plot_abha_scenarios.py
│   ├── plot_abha_flow_heatmaps.py
│   └── render_abha_scenarios.py
├── results/
│   ├── abha_s0_baselines/
│   ├── abha_s1a_baselines/
│   ├── abha_s1b_baselines/
│   ├── abha_s2_baselines/
│   ├── abha_baselines_ibex/
│   └── abha_scenario_maps/
└── slurm/
    └── abha_s0_baselines.sbatch
```

## Excluded Experiments

### Previous King Abdulaziz One-Way Experiment

The previous S1 definitions were:

- S1A: King Abdulaziz One-Way NE
- S1B: King Abdulaziz One-Way SW

The associated maps, GeoJSON files, configuration files, environment-building scripts, plots, heatmaps, rendered maps, and simulation outputs are archived here.

### Previous S2 Experiment

The previous S2 configuration represented a hypothetical Green Road bypass from Khamis Mushait toward Sali. The route was not based on a confirmed alignment. Its configuration, environment-building code, visualizations, and associated outputs are archived here.

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

The associated configuration, baseline-building scripts, timing probe, Ibex job, summaries, scenario maps, and baseline outputs are archived here as historical reference.

## Archived Results

The `results/` directory contains outputs produced using the previous scenario definitions and previous baseline setup, including:

- S0 baseline results
- S1A baseline results
- S1B baseline results
- S2 baseline results
- Ibex baseline outputs
- Previous scenario maps and visual comparisons

These outputs should not be directly compared with results produced by the active scenario workflow.

## Usage Rule

Do not use files in this folder as current simulation inputs, current scenario definitions, or current reported results. They are preserved only to document earlier development and experiments.
