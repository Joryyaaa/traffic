# Excluded and Legacy Abha Experiments

## Purpose

This document records previous Abha traffic-network experiments that were created before the latest mentor review and are no longer part of the current validated scenario workflow.

The purpose is to preserve development history and reproducibility while preventing outdated scenario definitions, configurations, maps, and results from being confused with the current scenarios.

No files listed here should be deleted solely because they are documented as excluded or legacy.

---

## 1. Current Workflow — KEEP

The following work represents the current direction after the mentor review and must NOT be treated as excluded.

### Current Validation Map

- `data/abha_baseline/abha_belt_soudah_khamis_map.html`

This map represents the current Abha full-belt and approach-corridor study area used for geometry validation.

### Current Scenario Definitions

- **Full-Belt Baseline** — current reference network before applying an intervention.
- **Preferred Existing Corridor** — existing corridor selected as the preferred route.
- **Network-Resilient Backup Corridor** — alternative existing route intended to provide a network-resilient backup.
- **New Connector Alternatives** — conceptual new-connector candidates requiring further validation before traffic-simulation conclusions are made.

These current scenario definitions supersede the previous scenario meanings that used similar S0/S1A/S1B/S2 identifiers.

---

## 2. Excluded Pre-Mentor Experiments

### 2.1 Old Corridor Validation Map

**File:** `data/abha_baseline/abha_corridor_validation_map.html`

**Status:** EXCLUDED / SUPERSEDED

**Reason:** This map belongs to the earlier corridor-development stage and predates the current full-belt, Khamis Mushait, and Al Soudah validation map.

**Current replacement:** `data/abha_baseline/abha_belt_soudah_khamis_map.html`

### 2.2 Previous King Abdulaziz One-Way Experiment

**Files:**

- `data/abha_baseline/abha_s1_oneway_comparison_map_fixed.html`
- `data/abha_baseline/s1a_king_abdulaziz.geojson`
- `data/abha_baseline/s1b_king_abdulaziz.geojson`
- `data/abha_baseline/s1a_oneway_summary.csv`
- `data/abha_baseline/s1b_oneway_summary.csv`

**Status:** EXCLUDED

**Reason:** These files belong to the previous King Abdulaziz one-way experiment.

The old definitions were:

- S1A: King Abdulaziz One-Way NE
- S1B: King Abdulaziz One-Way SW

These definitions are NOT the same as the current corridor-based S1A/S1B geometry scenarios and must not be used in the current scenario comparison.

---

## 3. Legacy Configuration Files

### 3.1 Old S1A Configuration

**File:** `configs/city_madina_abha_s1a.yaml`

**Previous definition:** King Abdulaziz One-Way NE. The configuration removes 16 SW-bearing segments from the previous S0 network.

**Status:** LEGACY / DO NOT USE FOR CURRENT S1A

### 3.2 Old S1B Configuration

**File:** `configs/city_madina_abha_s1b.yaml`

**Previous definition:** King Abdulaziz One-Way SW. The configuration removes 13 NE-bearing segments from the previous S0 network.

**Status:** LEGACY / DO NOT USE FOR CURRENT S1B

### 3.3 Old S2 Configuration

**File:** `configs/city_madina_abha_s2.yaml`

**Previous definition:** Hypothetical Green Road bypass from Khamis Mushait toward Sali.

The configuration explicitly describes the route as hypothetical and requiring replacement when an official alignment becomes available.

**Status:** LEGACY / DO NOT USE FOR CURRENT S2

The current New Connector Alternatives scenario must therefore not be confused with this previous hypothetical Green Road configuration.

---

## 4. Legacy Baseline Reference

The following files are not necessarily incorrect, but they belong to the previous Abha study setup and should currently be treated as reference material rather than the final full-belt baseline.

**Files:**

- `configs/city_madina_abha_s0.yaml`
- `data/abha_baseline/baseline_summary.csv`
- `data/abha_baseline/run_output.txt`

### Previous Study Setup

- Center: `(18.2264426, 42.5053914)`
- Radius: `1500 m`
- Network type: `drive`
- Total directed road segments: `4,586`
- Origins: `315`
- Destinations: `56`
- Cleaned study corridor: `44 segments`
- Cleaned study corridor length: `7.81 km`

This setup was the baseline used for the previous King Abdulaziz one-way experiments.

**Status:** LEGACY REFERENCE

It should not automatically be treated as the current Full-Belt Baseline.

---

## 5. Results Produced from Excluded Experiments

Any results generated from the excluded one-way, hypothetical Green Road, or previous corridor experiments must not be presented as results for the current scenarios.

Old results should not be directly compared with future results unless the following are identical:

1. Study network
2. Traffic demand
3. Origin and destination definitions
4. Simulation parameters
5. Evaluation metrics
6. Scenario intervention definition

If these conditions are not satisfied, the previous result is retained only as development history.

---

## 6. Current Scenario Evaluation Rule

Geometry validation and traffic simulation are separate stages. A visually validated scenario is NOT automatically a validated traffic intervention.

Current workflow:

```text
Current Validated Study Area
        |
        v
Full-Belt Baseline
        |
        v
Scenario Geometry Validation
        |
        +--> Preferred Existing Corridor
        |
        +--> Network-Resilient Backup Corridor
        |
        +--> New Connector Alternatives
        |
        v
Common Traffic Demand
        |
        v
Traffic Simulation
        |
        v
Common Evaluation Metrics
        |
        v
Scenario Comparison
        |
        v
Reward / RL / PPO
        (later stage)
```

---

## 7. Evaluation Principle

Scenario performance should be evaluated using common quantitative metrics.

The RL reward is a training objective and should not be treated as the sole measure of scenario performance.

All scenarios should therefore be evaluated using the same demand, simulation assumptions, and evaluation metrics.

---

## 8. Important Naming Note

The identifiers S0, S1A, S1B, and S2 have been used for more than one scenario definition during development.

Future files should preferably use descriptive scenario names instead of relying only on these identifiers, for example:

- `abha_full_belt_baseline`
- `abha_preferred_existing_corridor`
- `abha_network_resilient_backup`
- `abha_new_connector_alternatives`

This prevents current scenarios from being confused with the previous one-way and hypothetical-road experiments.

---

## Summary

### CURRENT / KEEP

- `abha_belt_soudah_khamis_map.html`
- Full-Belt Baseline geometry
- Preferred Existing Corridor geometry
- Network-Resilient Backup Corridor geometry
- New Connector Alternatives geometry

### EXCLUDED

- Old corridor validation map
- King Abdulaziz one-way comparison map
- Old S1A/S1B one-way GeoJSON files
- Old S1A/S1B one-way summaries
- Old S1A/S1B one-way configurations
- Old hypothetical Green Road S2 configuration

### LEGACY REFERENCE

- Previous 1500 m S0 configuration
- Previous baseline summary
- Previous baseline run output

These files are retained for traceability but should remain separate from the current validated Abha scenario workflow.
