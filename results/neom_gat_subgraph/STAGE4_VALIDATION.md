# Stage 4: validation results

Script: `scripts/validate_neom_gat_subgraph.py` (modeled on
`scripts/validate_gat_scaleup_datasets.py`'s structure from the Riyadh
scale-up study).

```
$ PYTHONPATH=src python scripts/validate_neom_gat_subgraph.py
=== NEOM GAT subgraph validation (Stage 4) ===

0. Exact segment count (direct feature count, not trusted from any label)
  [PASS] streets file exists  (data\neom_gat_subgraph\sharma_dorm_r750\streets.geojson)
  [PASS] feature count == 273  (got 273)

1. Config comparability vs. r400 COMBINED reference
  [PASS] simulation block matches reference
  [PASS] include_adjacency_state matches reference (both True)
  [PASS] reward fields (all, including min_zone_size=1) match reference exactly
  [PASS] action fields other than max_closures/episode_length match reference
  [PASS] network.crs == EPSG:32636 (NEOM UTM 36N, not Riyadh's 32638)
  [PASS] network.crs differs from r400 reference's EPSG:32638 (expected: different city, different UTM zone)

=== environment: configs/city_madina_neom_gat_subgraph_r750_mzs1.yaml ===
  [PASS] config file exists
  [PASS] no missing data paths / env constructs
  [PASS] n_segments == 273  (got 273)
  [PASS] action_space.n == n_segments + 1  (got 274, expected 274)
  [PASS] observation_space.shape == (n_segments+1, 7)  (got (274, 7))
  [PASS] obs.shape matches observation_space.shape
  [PASS] adjacency matrix shape == (n_segments, n_segments)  (got (273, 273))
  [PASS] adjacency matrix is symmetric (undirected segment graph)
  [PASS] adjacency matrix has at least one real edge  (sum=844)
  [PASS] connectivity: at least one valid closure action (not unreachable-everything)  (246/273 valid)
  [PASS] GAT forward pass shape == (1, 64)  (got (1, 64))

=======================================================
ALL CHECKS PASSED.
```

**15/15 checks PASS, 0 FAIL.**

Additionally ran `scripts/check_zone_feasibility.py` against this config as
a sanity check on the pedestrian-zone reward: 132 of 273 segments qualify
(>= 10% of mean baseline flow), forming one contiguous group of 132 -- with
`min_zone_size=1` the bonus is trivially reachable, and there is no
feasibility risk even at a stricter `min_zone_size`.

Environment: local `.venv` (Windows), `PYTHONPATH=src`,
`PYTHONIOENCODING=utf-8`. `geopandas.read_file` / pyogrio worked directly in
this venv (the DLL-block workaround noted elsewhere in project memory did
not reproduce here); `src/snrl/backends/madina_backend.py::_read_geojson`'s
plain-JSON fallback exists regardless for any environment where it does.
