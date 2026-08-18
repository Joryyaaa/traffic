# NEOM Baseline Discovery: Candidate Comparison

**Date**: 2026-08-18  
**Branch**: `neom-baseline-discovery`  
**Data source**: OpenStreetMap via Overpass API (mirror: maps.mail.ru)

---

## Candidates

| | Candidate A | Candidate B |
|---|---|---|
| **Label** | Sharma / Camp 26 | Trojena |
| **Center** | 28.0307 N, 35.2420 E | 28.6738 N, 35.3036 E |
| **Anchors** | Sharma village, Neom Residential Camp 26, Construction Camp W1 & W2 | Trojena construction site |
| **OSM place tags** | شرما (village), نيوم (city) | (unnamed hamlet at 5 km) |

---

## Network Metrics by Radius

| Metric | A 1 km | A 2 km | A 3 km | A 5 km | A mid-5 km | B 1 km | B 2 km | B 3 km | B 5 km |
|--------|-------:|-------:|-------:|-------:|----------:|-------:|-------:|-------:|-------:|
| Ways | 52 | 93 | 139 | 306 | 533 | 1 | 7 | 9 | 13 |
| Segments | 459 | 789 | 1,230 | 2,620 | 4,309 | 194 | 246 | 318 | 686 |
| Nodes | 441 | 748 | 1,175 | 2,450 | 4,037 | 195 | 248 | 319 | 686 |
| Components | 3 | 2 | 4 | 3 | 2 | 1 | 2 | 2 | 2 |
| Largest component | 222 | 450 | 818 | 1,910 | 3,739 | 195 | 195 | 195 | 491 |
| Highway classes | 7 | 7 | 7 | 9 | 10 | 1 | 3 | 4 | 4 |

### Highway Class Breakdown

**Candidate A (r5 km)**: service 182, residential 45, trunk 27, track 20, tertiary 7+1 link, trunk_link 12, unclassified 9, secondary 3

**Candidate B (r5 km)**: residential 5, service 4, secondary 3, unclassified 1

---

## Feature Metrics by Radius

| Metric | A 1 km | A 2 km | A 3 km | A 5 km | A mid-5 km | B 1 km | B 2 km | B 3 km | B 5 km |
|--------|-------:|-------:|-------:|-------:|----------:|-------:|-------:|-------:|-------:|
| Buildings | 132 | 176 | 247 | 370 | 556 | 0 | 4 | 4 | 25 |
| Residential bldgs | 0 | 0 | 0 | 29 | 65 | 0 | 0 | 0 | 0 |
| Amenities | 0 | 6 | 70 | 99 | 154 | 0 | 0 | 0 | 0 |
| Landuse areas | 2 | 12 | 14 | 47 | 119 | 1 | 6 | 6 | 8 |
| Construction zones | 1 | 4 | 5 | 16 | 16 | 1 | 1 | 1 | 2 |
| Named roads | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |

### Notable Features

**Candidate A (r5 km)**: hospital (5 bldgs + 2 amenities), fuel stations (2), parking (32), shelters (61), place of worship (1), dormitory (22 bldgs), warehouses, industrial zones (12 landuse)

**Candidate B (r5 km)**: bunkers (4 bldgs), military landuse (5 areas), 1 named road (طريق جبل اللوز), 21 generic buildings at outer radius

---

## Connectivity Summary

| | Candidate A (r3 km) | Candidate B (r5 km) |
|---|---|---|
| Total segments | 1,230 | 686 |
| Connected components | 4 | 2 |
| Largest component % | 66.5% (818/1,230) | 71.6% (491/686) |
| Best single-network extent | mid-5 km: 86.8% (3,739/4,309) | r1 km: 100% (195/195) |

---

## Key Differences

| Dimension | Candidate A (Sharma) | Candidate B (Trojena) |
|---|---|---|
| **Road density** | High -- 306 ways at 5 km | Very sparse -- 13 ways at 5 km |
| **Road diversity** | 9 highway classes (trunk to living_street) | 4 classes (no trunk, no track) |
| **Built environment** | 370 buildings, hospitals, fuel, parking | 25 buildings (mostly bunkers + generic) |
| **Demand proxies** | 154 amenities at mid-5 km (shelters, parking, hospital) | 0 amenities at any radius |
| **Active construction** | 16 construction zones at 5 km | 2 construction zones at 5 km |
| **Military presence** | 1 military landuse | 5 military landuse areas |
| **Network connectivity** | Best at mid-5 km (87% in largest component) | Best at r1 km (100% -- single road) |
| **Scale for RL training** | Large action/state space | Small action/state space |

---

## HTML Maps

| Map | Path |
|---|---|
| Candidate A -- Sharma r3 km | `results/neom_baseline_discovery/map_A_sharma_r3km.html` |
| Candidate B -- Trojena r5 km | `results/neom_baseline_discovery/map_B_trojena_r5km.html` |

---

## Raw Data

Full analysis JSON: `results/neom_baseline_discovery/discovery_combined.json`  
Analysis script: `scripts/neom_osm_discovery.py`
