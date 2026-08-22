"""Configuration objects for the street-network RL environment."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

import yaml


@dataclass
class NetworkConfig:
    """Where the street network and the origin/destination layers come from."""

    # Backend used to simulate flows: "madina" (real) or "stub" (synthetic grid, no deps)
    backend: Literal["madina", "stub"] = "stub"

    # --- madina backend ---
    streets_path: str | None = None        # .geojson / .shp of street centerlines
    origins_path: str | None = None        # e.g. residential buildings
    destinations_path: str | None = None   # e.g. shops, schools, transit stops
    origin_weight: str | None = None       # column name, e.g. "residents"
    destination_weight: str | None = None  # column name, e.g. "jobs"
    weight_attribute: str | None = None    # perceived cost column; None -> geometric length
    crs: str = "EPSG:3857"                 # projected CRS, units = meters
    node_snapping_tolerance: float = 0.0
    # Preserve allowed travel directions for drive-network scenarios.
    respect_oneway: bool = False

    # --- stub backend (for smoke tests / CI, no geopandas needed) ---
    stub_grid_size: int = 6                # 6x6 lattice -> 60 segments
    stub_seed: int = 0

    # Demand pattern.
    #   "uniform"   - origins and destinations scattered evenly, equal weights.
    #                 Every part of the network matters equally, so there is no
    #                 reason to prefer one location over another.
    #   "clustered" - origins on one side, destinations on the other, with
    #                 heterogeneous weights. Trips acquire a direction, some
    #                 corridors carry most of the flow, and *where* a closure
    #                 goes starts to matter as much as how many there are.
    stub_demand: Literal["uniform", "clustered"] = "uniform"
    stub_demand_skew: float = 4.0          # spread of origin/destination weights

    # If True, origin/destination weights are redrawn at every reset, so each
    # episode is a different day. A closure plan that only works for one demand
    # pattern stops scoring; the agent has to find something robust. This is
    # also the setting where a hand-coded planner has no advantage left, since
    # it cannot see the draw either.
    stub_demand_stochastic: bool = False


@dataclass
class SimulationConfig:
    """Parameters passed to Madina's UNA betweenness / accessibility tools."""

    search_radius: float = 800.0     # meters
    detour_ratio: float = 1.0        # 1.0 = shortest path only
    decay: bool = True
    decay_method: Literal["exponent", "power"] = "exponent"
    beta: float = 0.003              # walking-distance sensitivity
    closest_destination: bool = True
    turn_penalty: bool = False
    turn_threshold_degree: float = 45.0
    turn_penalty_amount: float = 30.0
    num_cores: int = 1

    # Simulation is expensive -> cache results keyed by the set of closed segments
    cache_size: int = 4096


@dataclass
class ActionConfig:
    """How the agent is allowed to modify the network."""

    # "toggle": one segment per step; "multi": a binary vector over all segments
    action_type: Literal["toggle", "multi"] = "toggle"

    # How a "closed" segment is represented in the flow model:
    #   "rebuild"  -> drop the segment and rebuild the routable network (true closure)
    #   "penalize" -> multiply its perceived cost by `closure_penalty` (soft closure)
    closure_mode: Literal["rebuild", "penalize"] = "rebuild"
    closure_penalty: float = 1000.0

    max_closures: int = 10           # budget: max simultaneously closed segments
    episode_length: int = 20         # steps per episode
    allow_reopen: bool = True        # agent may re-open a segment it closed
    allow_noop: bool = True          # include an explicit "do nothing" action
    forbid_disconnection: bool = True  # mask actions that would disconnect the network


@dataclass
class RewardConfig:
    """Weights of the multi-objective reward. All terms are computed on
    normalized (baseline-relative) quantities so the weights are comparable."""

    w_accessibility: float = 1.0     # + mean gravity/reach access across origins
    w_flow_concentration: float = 0.5  # + concentrate flow on designated corridors
    w_equity: float = 0.3            # - inequality (Gini) of access across origins
    w_detour: float = 0.2            # - added travel distance from closures
    w_intervention: float = 0.05     # - cost per closed segment (parsimony)
    disconnection_penalty: float = 5.0  # - if the closure fragments the network

    # --- pedestrian-zone bonus (see metrics.zone_score) --------------------
    # Rewards *contiguous* closures that form a walkable plaza. Setting
    # w_pedestrian_zone > 0 gives the problem long-horizon structure: the first
    # closures of a zone earn nothing while already costing accessibility, so a
    # one-step-lookahead (greedy) agent never starts one.
    w_pedestrian_zone: float = 0.0
    min_zone_size: int = 3           # segments needed before a zone counts at all
    zone_exponent: float = 2.0       # >1 makes one big zone beat several small ones
    zone_min_flow_fraction: float = 0.0
    # A segment must carry at least this fraction of the network's mean
    # *baseline* flow to count toward a zone's size. 0.0 = disabled (any
    # segment counts, including ones nobody ever walks on -- the original
    # behavior). Without this, the agent can farm the full pedestrian_zone
    # bonus by closing a corridor that already carried zero flow, since
    # zone_score only ever looked at contiguity, never at whether closing
    # the segment costs (or helps) anyone. Try e.g. 0.1 so a segment needs
    # >=10% of mean baseline flow to count.

    # "delta" -> reward = change vs. previous step; "absolute" -> vs. baseline
    reward_mode: Literal["delta", "absolute"] = "delta"


@dataclass
class EnvConfig:
    network: NetworkConfig = field(default_factory=NetworkConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    action: ActionConfig = field(default_factory=ActionConfig)
    reward: RewardConfig = field(default_factory=RewardConfig)
    seed: int = 42
    include_adjacency_state: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path) -> EnvConfig:
    """Load an EnvConfig from a YAML file."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    return EnvConfig(
        network=NetworkConfig(**raw.get("network", {})),
        simulation=SimulationConfig(**raw.get("simulation", {})),
        action=ActionConfig(**raw.get("action", {})),
        reward=RewardConfig(**raw.get("reward", {})),
        seed=raw.get("seed", 42),
        include_adjacency_state=raw.get("include_adjacency_state", False),
    )
