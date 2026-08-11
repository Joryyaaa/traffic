"""
TRAFFIC PROJECT — FULL PIPELINE (study / development entry point)

This standalone study file exposes the repository's main traffic-RL pipeline in
one place so it can be understood and extended subsystem-by-subsystem.

Flow:
    CONFIG -> OSM DATA -> BACKEND -> METRICS/REWARD -> ENV -> PPO/EVALUATION

The production implementation remains in src/snrl and scripts; this file does
not replace those modules. It is intentionally kept separate for Samaher's
Abha/subsystem development work.
"""

from pathlib import Path

from snrl.config import EnvConfig, load_config
from snrl.env import StreetNetworkEnv
from snrl.metrics import gini, normalized_entropy, zone_score
from snrl.rewards import RewardFunction, RewardBreakdown, simulation_stats
from snrl.backends.base import FlowBackend, SimulationResult
from snrl.backends.stub import StubBackend
from snrl.backends.madina_backend import MadinaBackend


# -----------------------------------------------------------------------------
# CURRENT ABHA CONFIGURATION
# Mirrors configs/city_madina_abha.yaml and makes the intended city pipeline
# visible from this single development entry point.
# -----------------------------------------------------------------------------
ABHA_CONFIG_PATH = Path("configs/city_madina_abha.yaml")


def build_abha_environment() -> StreetNetworkEnv:
    """Load the current Abha configuration and build the RL environment."""
    cfg = load_config(ABHA_CONFIG_PATH)
    return StreetNetworkEnv(cfg)


# -----------------------------------------------------------------------------
# SUBSYSTEM A — OSM / OFFICIAL TRAFFIC DATA
# -----------------------------------------------------------------------------
# Existing OSM acquisition is implemented in scripts/fetch_osm_data.py.
# This is the clean extension boundary for authority traffic data such as:
# traffic_volume, speed, lanes, capacity, signal state, and congestion.
#
# def enrich_abha_network_with_authority_data(streets_gdf, traffic_df):
#     return enriched_streets_gdf


# -----------------------------------------------------------------------------
# SUBSYSTEM B — ABHA INTERVENTION SCENARIOS
# -----------------------------------------------------------------------------
# Candidate scenario functions can be added here first, then moved into their
# own production module after the design is stable.
#
# def apply_ring_road_one_way(network): ...
# def apply_green_ring_bypass(network): ...
# def open_blocked_roads(network): ...
# def modify_intersections(network): ...
# def modify_traffic_signals(network): ...


# -----------------------------------------------------------------------------
# SUBSYSTEM C — VEHICULAR STATE / OBSERVATION FEATURES
# -----------------------------------------------------------------------------
# Extend StreetNetworkEnv._observation() with features such as:
# traffic_volume, speed, capacity, lanes, congestion, queue length, etc.


# -----------------------------------------------------------------------------
# SUBSYSTEM D — VEHICULAR REWARD
# -----------------------------------------------------------------------------
# Extend RewardFunction with traffic objectives such as:
# travel_time, congestion, VKT, emissions, feasibility and intervention cost.


# -----------------------------------------------------------------------------
# SUBSYSTEM E — SCENARIO COMPARISON
# -----------------------------------------------------------------------------
# Run baseline Abha and every intervention under the same demand assumptions,
# then compare accessibility, travel time, congestion, VKT and emissions.


if __name__ == "__main__":
    env = build_abha_environment()
    obs, info = env.reset()
    print("Abha traffic environment loaded")
    print(f"Segments: {env.n_segments}")
    print(f"Observation shape: {obs.shape}")
    print(f"Initial info: {info}")
