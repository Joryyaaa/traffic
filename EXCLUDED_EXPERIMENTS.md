# Excluded Abha Experiments

## Purpose

This file documents Abha traffic-network experiments, maps, configurations, and outputs that are no longer used in the active workflow.

They are retained only for traceability and development history and should not be used as inputs or results for the current scenario analysis.

---

## 1. Old Corridor Validation Map

**File:**
`data/abha_baseline/abha_corridor_validation_map.html`

**Status:** EXCLUDED / SUPERSEDED

**Reason:**
This file belongs to an earlier corridor-development stage and is no longer used as the active study-area map.

---

## 2. Previous King Abdulaziz One-Way Experiment

**Files:**

- `data/abha_baseline/abha_s1_oneway_comparison_map_fixed.html`
- `data/abha_baseline/s1a_king_abdulaziz.geojson`
- `data/abha_baseline/s1b_king_abdulaziz.geojson`
- `data/abha_baseline/s1a_oneway_summary.csv`
- `data/abha_baseline/s1b_oneway_summary.csv`

**Status:** EXCLUDED

**Reason:**
These files belong to the previous King Abdulaziz one-way experiment.

The old definitions were:

- S1A: King Abdulaziz One-Way NE
- S1B: King Abdulaziz One-Way SW

These scenario definitions are no longer used.

---

## 3. Old Scenario Configuration Files

### Old S1A Configuration

**File:**
`configs/city_madina_abha_s1a.yaml`

**Previous definition:**
King Abdulaziz One-Way NE. The configuration removes 16 SW-bearing segments from the previous S0 network.

**Status:** EXCLUDED / DO NOT USE

### Old S1B Configuration

**File:**
`configs/city_madina_abha_s1b.yaml`

**Previous definition:**
King Abdulaziz One-Way SW. The configuration removes 13 NE-bearing segments from the previous S0 network.

**Status:** EXCLUDED / DO NOT USE

### Old S2 Configuration

**File:**
`configs/city_madina_abha_s2.yaml`

**Previous definition:**
Hypothetical Green Road bypass from Khamis Mushait toward Sali.

The route was explicitly defined as hypothetical and was not based on a confirmed alignment.

**Status:** EXCLUDED / DO NOT USE

---

## 4. Previous Baseline Setup

**Files:**

- `configs/city_madina_abha_s0.yaml`
- `data/abha_baseline/baseline_summary.csv`
- `data/abha_baseline/run_output.txt`

**Status:** EXCLUDED FROM CURRENT ANALYSIS / REFERENCE ONLY

**Previous setup:**

- Center: `(18.2264426, 42.5053914)`
- Radius: `1500 m`
- Network type: `drive`
- Total directed road segments: `4,586`
- Origins: `315`
- Destinations: `56`
- Cleaned study corridor: `44 segments`
- Cleaned study corridor length: `7.81 km`

This setup was used for the previous one-way experiments and should not be reused automatically for current scenario results.

---

## 5. Results from Excluded Experiments

Any results generated from the following should be treated as excluded from the current scenario comparison:

- Previous King Abdulaziz one-way scenarios
- Previous corridor-validation setup
- Previous hypothetical Green Road scenario
- Previous 1500 m baseline setup when used with the old scenario definitions

These outputs may be retained for reference but should not be reported as current scenario results.

---

## Excluded File Summary

### Data / Maps

- `data/abha_baseline/abha_corridor_validation_map.html`
- `data/abha_baseline/abha_s1_oneway_comparison_map_fixed.html`
- `data/abha_baseline/s1a_king_abdulaziz.geojson`
- `data/abha_baseline/s1b_king_abdulaziz.geojson`
- `data/abha_baseline/s1a_oneway_summary.csv`
- `data/abha_baseline/s1b_oneway_summary.csv`

### Configurations

- `configs/city_madina_abha_s1a.yaml`
- `configs/city_madina_abha_s1b.yaml`
- `configs/city_madina_abha_s2.yaml`

### Reference-Only Previous Baseline

- `configs/city_madina_abha_s0.yaml`
- `data/abha_baseline/baseline_summary.csv`
- `data/abha_baseline/run_output.txt`

These files are preserved for traceability only and are not part of the active scenario analysis.
