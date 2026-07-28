# AI-Driven Street Network Optimization for Pedestrian and Bicycle Flow

A reinforcement learning agent that decides **which street segments to open or close**
in order to optimize pedestrian and bicycle flow and accessibility across an urban
network. Flows are simulated with [**Madina**](https://github.com/City-Form-Lab/madina)
(MIT City Form Lab's Python implementation of the Urban Network Analysis toolbox).

**Case study:** a Saudi / Gulf city network.

## Positioning

| | DeCoR (2026) | This work |
|---|---|---|
| Decision variable | crosswalk placement + signal timing | street segment open/close |
| Spatial scope | a single corridor | a network of segments |
| Flow model | corridor simulation | Madina betweenness-based flow simulation |
| Objective | corridor throughput / delay | accessibility + flow quality + equity |

## Status

- [x] **Skeleton code — environment** (this repo)
- [ ] Real city data pipeline (OSM → streets / origins / destinations layers)
- [ ] Madina backend validated against a hand-checked simulation
- [ ] Reward function tuned with mentor
- [ ] PPO training + baseline comparison
- [ ] Ablations & case-study writeup

## Repository layout

```
src/snrl/
├── config.py                 # dataclass configs, loaded from YAML
├── env.py                    # StreetNetworkEnv (Gymnasium)
├── rewards.py                # multi-objective reward + per-term breakdown
├── metrics.py                # Gini, flow entropy, helpers
└── backends/
    ├── base.py               # FlowBackend interface + SimulationResult
    ├── stub.py               # synthetic lattice (no geopandas needed)
    └── madina_backend.py     # real Madina Zonal + UNA betweenness
configs/
├── default.yaml              # runs out of the box on the stub network
└── city_madina.yaml          # template for the real case study
scripts/
├── smoke_test.py             # random episode, sanity check
├── train.py                  # PPO / MaskablePPO training
└── evaluate.py               # agent vs. random / greedy / flow-ranked baselines
tests/test_env.py             # environment contract tests
```

## Problem formulation

|  |  |
|---|---|
| **State** | which segments are currently closed, plus the resulting flow and accessibility pattern |
| **Action** | toggle one segment open ↔ closed, or no-op (`Discrete(N+1)`); a `MultiBinary(N)` variant selects a whole configuration at once |
| **Reward** | change in a multi-objective planning score (below) |
| **Episode** | `episode_length` interventions under a budget of `max_closures` simultaneously closed segments |

### Observation

`(N+1, 5)` float array — one row per segment plus a global row:

| channel | meaning |
|---|---|
| 0 | `is_closed` ∈ {0,1} |
| 1 | betweenness flow / baseline max |
| 2 | segment length / max length |
| 3 | flow change vs. baseline |
| 4 | segment degree in the segment-adjacency graph |

Global row: `[budget_used, step_fraction, mean_access_ratio, access_gini, 0]`

### Reward

```
r = w_access · Δ(mean accessibility)
  − w_flow   · Δ(flow entropy)          # reward concentrating flow on corridors
  − w_equity · Δ(Gini of accessibility)
  − w_detour · Δ(mean trip distance)
  − w_interv · (closed segments / budget)
  − disconnection_penalty  if the network fragments
```

All terms are normalized by the **baseline** (fully open) network, so the weights
in `configs/*.yaml` are on a comparable scale. `RewardBreakdown` logs every term
separately into `info["reward/*"]` for diagnostics.

### Constraint handling

Closures that would fragment the network are **masked out** before the expensive
flow simulation runs (`env.action_masks()`, compatible with `MaskablePPO`).

## Two backends

The environment talks to a `FlowBackend`, not to Madina directly:

- **`stub`** — a synthetic `k×k` lattice, pure NetworkX. Runs in ~1 s, no geopandas,
  works in CI. Use it to develop the reward, the policy and the training loop.
- **`madina`** — real Madina `Zonal` + `una.tools.betweenness`. Same array shapes,
  so switching is one line of YAML.

A closed segment can be represented two ways (`action.closure_mode`):

- `rebuild` — drop the segment and rebuild the routable network (physically exact)
- `penalize` — multiply its *perceived cost* by a large factor via Madina's
  `weight_attribute` (much cheaper; pedestrians can still squeeze through)

## Quick start

```bash
# 1. environment (geopandas needs conda)
conda env create -f environment.yml
conda activate snrl

# ...or, stub backend only, no geospatial stack:
pip install gymnasium networkx numpy pyyaml pytest

# 2. sanity check
python scripts/smoke_test.py --config configs/default.yaml

# 3. tests
pytest -q

# 4. baselines
python scripts/evaluate.py --config configs/default.yaml

# 5. train
python scripts/train.py --config configs/default.yaml --timesteps 50000
```

Installing Madina itself (it is published on TestPyPI):

```bash
conda create -n snrl -c conda-forge --strict-channel-priority geopandas
conda activate snrl
pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple madina
```

## Current results (stub network, 6×6 lattice, 60 segments)

| policy | mean return |
|---|---|
| lowest_flow | −5.05 |
| random | −0.84 |
| highest_flow | −0.46 |
| **greedy (1-step lookahead)** | **−0.30** |

Returns are negative because on a uniform lattice with uniformly distributed
origins and destinations, *any* closure reduces accessibility — there is nothing
for the agent to improve. This is expected for the stub and is a useful
sanity check: greedy > random > naive rules, so the reward is not degenerate.
The real case study needs a network where closures can genuinely help
(pedestrianization, redirecting flow away from arterials, safety).

## Open questions for the mentor

1. **What makes a closure *good*?** Right now the reward rewards concentrating
   flow (lower entropy). Should we instead target *specific* corridors — a bike
   spine, a retail street — and reward flow on those?
2. **Mean trip distance from Madina.** `una.tools.betweenness` does not return it
   directly. Options: `keep_diagnostics=True` and read the path record, derive it
   from reach/gravity, or compute it separately on `zonal.network.d_graph`.
3. **Closure semantics.** `rebuild` (true closure) vs. `penalize` (soft) — the
   second is far faster; is it defensible for the paper?
4. **Action space.** Sequential toggling vs. one-shot configuration selection.
   Sequential gives credit assignment; one-shot matches how planners think.
5. **Generalization.** Train on one city and test on another, or one network only?
   This determines whether we need a GNN policy over segments instead of an MLP.
6. **Case-study city and scale** — how many segments is realistic given that each
   Madina betweenness run is expensive?

## References

- Alhassan, A. & Sevtsuk, A. (2024). *Madina Python Package: Scalable Urban Network
  Analysis for Modeling Pedestrian and Bicycle Trips in Cities.* SSRN 4748255.
- Urban Network Analysis Toolbox — https://cityform.mit.edu/projects/una-rhino-toolbox
- DeCoR (2026) — crosswalk placement + signal optimization on a single corridor.
