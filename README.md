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

- [x] **Skeleton code — environment**
- [x] **Harder environment where planning is required** (`configs/hard.yaml`)
- [x] **PPO training + baseline comparison** (on the stub network)
- [x] **Non-uniform demand** (`configs/hard_demand.yaml`)
- [x] **Larger networks** (`configs/hard_large.yaml`) — greedy becomes unaffordable
- [x] **Stochastic demand** (`configs/hard_stochastic.yaml`)
- [ ] Real city data pipeline (OSM → streets / origins / destinations layers)
- [ ] Madina backend validated against a hand-checked simulation
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
├── default.yaml              # easy: greedy solves it. Sanity-check baseline
├── hard.yaml                 # planning required: zones + irreversible closures
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

## Does this problem actually need RL?

The first version of the environment was solved optimally by a one-step-lookahead
greedy policy. If greedy wins, the problem has no long-horizon structure and a
heuristic would do — so `configs/hard.yaml` adds two mechanisms that make
planning necessary.

**1. Pedestrian zones (`w_pedestrian_zone`).** Scattered closures create dead
ends and help nobody. A *contiguous* group of closed segments creates a walkable
plaza. So closures only pay off once at least `min_zone_size` of them form a
connected group, and the bonus is superlinear in group size.

This is a real planning constraint, and it produces exactly the structure RL is
for: **the first two closures of a plaza earn nothing while already costing
accessibility.** Greedy evaluates one move at a time, sees a loss, and refuses to
ever start. Only an agent willing to absorb an early loss reaches the payoff.

**2. Irreversible closures (`allow_reopen: false`).** A wasted move is
permanently wasted, so the agent must commit to a plan rather than explore
by trial and error within the episode.

### Baseline comparison (6×6 lattice, 60 segments, 3 episodes)

| policy | easy (`default.yaml`) | hard (`hard.yaml`) |
|---|---|---|
| random | −0.088 | −0.184 |
| **greedy** (1-step lookahead) | **+0.006** | +0.006 |
| highest_flow | −0.032 | +0.301 |
| lowest_flow | −0.017 | +0.067 |
| zone_builder (told to plan contiguity) | −0.132 | +0.619 |
| **MaskablePPO** (30k steps) | — | **+0.872** |

Read the two columns together:

- **Easy:** greedy is the best policy. Nothing rewards planning, so looking one
  move ahead is sufficient — and RL would have nothing to contribute.
- **Hard:** greedy is stuck at +0.006, i.e. it does essentially nothing, while a
  policy that plans contiguity reaches +0.619. Greedy leaves ~99% of the
  available return on the table because the payoff is three moves away.

`zone_builder` is a hand-coded planner that is *told* contiguity matters. It is
included as a headroom measure, not as a competitor: it marks the return that is
reachable when you plan ahead.

### The agent learns the structure on its own

MaskablePPO trained for 30k steps on `hard.yaml` reaches **+0.872** — it beats
the hand-coded planner by 41%, and greedy by two orders of magnitude. Nothing in
the observation or the network architecture mentions contiguity; the agent
recovers it from the reward alone.

Episode return during training:

| timesteps | 2k | 8k | 14k | 18k | 22k | 26k | 30k |
|---|---|---|---|---|---|---|---|
| `ep_rew_mean` | −0.060 | −0.044 | −0.009 | +0.078 | +0.152 | +0.335 | +0.617 |

Two things worth noting in the curve:

- The first ~14k steps sit near zero. The agent is paying the cost of the first
  closures without any zone bonus yet — exactly the trap greedy never escapes.
  It has to explore through that flat region before the payoff appears.
- Return was **still rising at the end** (+0.487 → +0.617 over the last 2k
  steps) and policy entropy was still falling, so 30k steps is undertrained.
  A longer run should improve on +0.872.

Reproduce:

```bash
python scripts/train.py --config configs/hard.yaml --timesteps 30000 --run-name ppo_hard
python scripts/evaluate.py --config configs/hard.yaml --model runs/ppo_hard/model
```

### Non-uniform demand (`configs/hard_demand.yaml`)

Uniform demand is the other way the stub was still theoretical: with origins and
destinations scattered evenly and weighted equally, every part of the network is
interchangeable. The agent only has to decide *how many* segments to close and
whether they touch — never *where*.

`hard_demand.yaml` puts housing on the west side of the grid and amenities on
the east, with heterogeneous weights on both. Trips now have a direction, a few
crossing corridors carry most of the flow, and location starts to matter:
closing a main corridor is expensive, while closing a quiet edge is nearly free
but creates a plaza that serves nobody.

| policy | uniform demand | clustered demand |
|---|---|---|
| random | −0.184 | −0.148 |
| greedy | +0.006 | +0.000 |
| highest_flow | +0.301 | **+0.083** |
| lowest_flow | +0.067 | **−0.017** |
| zone_builder | +0.619 | +0.636 |
| **MaskablePPO** | **+0.872** (30k) | **+0.941** (60k) |

The two flow-ranked heuristics are the interesting column. Under uniform demand
they scored respectably almost by accident — with no spatial structure, ranking
segments by flow is as good as anything. Once demand has a direction they
collapse, because they optimise a single quantity while the actual problem is a
trade-off between where flow is, where people live, and where a plaza can go.
Planning (`zone_builder`) is unaffected. The environment now discriminates
between policies that reason about location and policies that do not.

The margin RL holds over the hand-coded planner *widens* as the environment gets
more realistic — +41% under uniform demand, +48% under clustered demand. The
planner encodes one fixed rule (extend the cluster); the agent can trade that
rule off against where flow and residents actually are, and the more structure
the environment has, the more there is to trade off.

```bash
python scripts/train.py --config configs/hard_demand.yaml --timesteps 60000 --run-name ppo_demand
python scripts/evaluate.py --config configs/hard_demand.yaml --model runs/ppo_demand/model
```

### Stochastic demand (`configs/hard_stochastic.yaml`)

Origin and destination weights are redrawn every episode — each episode is a
different day. A closure plan tuned to one demand pattern stops scoring.

| policy | mean return | std |
|---|---|---|
| random | −0.134 | 0.075 |
| greedy | +0.398 | **0.483** |
| highest_flow | +0.015 | 0.044 |
| lowest_flow | −0.005 | 0.015 |
| zone_builder | +0.475 | 0.105 |
| **MaskablePPO** (60k) | **+0.941** | **0.023** |

Greedy recovers here, and that is worth being honest about: the zone trap
depends on the first closure being net-negative, which holds under fixed demand
but not for every random draw. On a lucky day the first closure pays and greedy
starts a zone by accident. Its standard deviation is 4.6× the planner's — it is
gambling, not planning. Mean return still favours planning, but the margin
between the two *heuristics* is much narrower than under deterministic demand.

The trained agent separates cleanly on both axes: it roughly doubles the
planner's return (+98%) while cutting variance to 0.023 — **21× more consistent
than greedy**. That combination is the result to take forward. Under demand it
cannot observe, greedy's occasional good day comes with an equally likely bad
one, whereas the agent has learned closures that hold up across draws. Robust
performance under uncertain demand is also the property a planning department
would actually need: an intervention has to work on a normal Tuesday, not only
on the day it was designed for.

### Larger networks (`configs/hard_large.yaml`)

A 10×10 lattice — 180 segments instead of 60, budget 12, episodes of 30 steps.
The point is not that the task gets harder to learn; it is that greedy stops
being affordable:

| | simulations per episode | wall-clock (stub) |
|---|---|---|
| greedy | 5,400 | ~132 s |
| trained policy | 30 | ~0.7 s |

Greedy costs `n_segments × episode_length` simulations because it re-evaluates
every candidate at every step; a trained policy costs `episode_length`. That is
190× here, and the ratio grows linearly with network size. On a real city
network — thousands of segments, with each Madina betweenness run taking
seconds rather than 24 ms — one-step lookahead is not merely worse, it is
not runnable. The amortisation argument for RL is this: training is paid once,
inference is paid per decision.

Returns are small in absolute terms because a uniform lattice with uniformly
distributed origins and destinations offers little to improve. Non-uniform
demand is the next mechanism to add.

## Open questions 

1. **Is the pedestrian-zone mechanism the right way to make this hard?** It
   creates genuine long-horizon structure and is defensible as urban planning,
   but it is one choice among several. Other candidates, roughly in order of how
   much they'd change the problem: non-uniform demand (dense housing on one
   side, amenities on the other), a liveliness threshold a street must exceed to
   "count", larger networks where greedy's per-step search becomes infeasible,
   and stochastic demand across times of day.
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
