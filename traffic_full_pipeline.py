"""
TRAFFIC PROJECT — FULL PIPELINE
Study / Development Entry Point

This file exposes the current Abha traffic-simulation workflow in one place
for study, development, and subsystem integration.

Production implementation remains in src/snrl, scripts, configs, and data.
This file does not replace those modules.

CURRENT FLOW
============
MAP / STUDY AREA VALIDATION
    -> BASELINE NETWORK
    -> CORRIDOR DEFINITION
    -> SCENARIO DEFINITION
    -> SCENARIO DATA BUILDERS
    -> MADINA SIMULATION
    -> PERFORMANCE METRICS
    -> RL ENVIRONMENT
    -> REWARD FUNCTION
    -> BASELINES / PPO
    -> SCENARIO COMPARISON
    -> MAP / IMAGE / VIDEO VALIDATION

IMPORTANT: reward and evaluation metrics are not the same thing.
Reward trains the RL agent; metrics judge whether a traffic scenario actually
improved or degraded system performance.
"""

from pathlib import Path

from snrl.config import EnvConfig, load_config
from snrl.env import StreetNetworkEnv
from snrl.metrics import gini, normalized_entropy, zone_score, summarize
from snrl.rewards import RewardFunction, RewardBreakdown, simulation_stats
from snrl.backends import FlowBackend, SimulationResult, build_backend


# =============================================================================
# 1. MAP / STUDY AREA VALIDATION
# =============================================================================
# Validate the physical study network before simulation. Current validation
# covers King Abdulaziz Belt, major roads inside the belt, Route 10 and Route
# 2120 from Khamis Mushait, Al Soudah Road / Route 214, and their connections.
# Check OSM geometry against reality/reference imagery, decide full belt versus
# a shorter corridor, and verify intersections, roundabouts, bridges and access.

ABHA_VALIDATION_MAP = Path(
    "data/abha_baseline/abha_belt_soudah_khamis_map.html"
)


# =============================================================================
# 2. CORRIDOR DEFINITIONS
# =============================================================================
ABHA_CORRIDORS = {
    "king_abdulaziz_belt": {
        "name": "King Abdulaziz Belt",
        "description": "Main Abha ring-road / belt corridor.",
    },
    "khamis_route_10": {
        "name": "King Fahd Road / Route 10",
        "description": "Main approach from Khamis Mushait toward Abha.",
    },
    "khamis_route_2120": {
        "name": "King Abdullah Road / Route 2120",
        "description": "Alternative approach from Khamis Mushait toward Abha.",
    },
    "al_soudah_route": {
        "name": "Al Soudah Road / Route 214",
        "description": "Main connection from Abha toward Al Soudah.",
    },
}


# =============================================================================
# 3. SCENARIO DICTIONARY
# =============================================================================
# Descriptive names are primary. Legacy S-codes are retained only for file and
# experiment compatibility.

ABHA_SCENARIOS = {
    "baseline_network": {
        "name": "Baseline Network",
        "legacy_code": "S0",
        "description": "Existing Abha road network without the proposed intervention.",
        "config": Path("configs/city_madina_abha_s0.yaml"),
    },
    "king_abdulaziz_oneway_ne": {
        "name": "King Abdulaziz One-Way — Northeast Direction",
        "legacy_code": "S1A",
        "description": (
            "King Abdulaziz Road configured as a one-way alternative "
            "toward the northeast direction."
        ),
        "config": Path("configs/city_madina_abha_s1a.yaml"),
    },
    "king_abdulaziz_oneway_sw": {
        "name": "King Abdulaziz One-Way — Southwest Direction",
        "legacy_code": "S1B",
        "description": (
            "King Abdulaziz Road configured as a one-way alternative "
            "toward the southwest direction."
        ),
        "config": Path("configs/city_madina_abha_s1b.yaml"),
    },
    "green_road_bypass": {
        "name": "Green Road / Bypass Alternative",
        "legacy_code": "S2",
        "description": "Alternative bypass / Green Road scenario.",
        "config": Path("configs/city_madina_abha_s2.yaml"),
        "status": (
            "Current route is hypothetical until authoritative geometry "
            "is provided."
        ),
    },
}

BASELINE_SCENARIO = "baseline_network"


def get_scenario(scenario_key: str) -> dict:
    """Return one scenario definition."""
    if scenario_key not in ABHA_SCENARIOS:
        valid = ", ".join(ABHA_SCENARIOS)
        raise ValueError(
            f"Unknown scenario: {scenario_key}. Choose one of: {valid}"
        )
    return ABHA_SCENARIOS[scenario_key]


def load_abha_config(scenario_key: str = BASELINE_SCENARIO) -> EnvConfig:
    """Load the YAML configuration associated with one Abha scenario."""
    return load_config(get_scenario(scenario_key)["config"])


def build_abha_environment(
    scenario_key: str = BASELINE_SCENARIO,
) -> StreetNetworkEnv:
    """Build the RL environment for one Abha traffic scenario."""
    return StreetNetworkEnv(load_abha_config(scenario_key))


# =============================================================================
# 4. BASELINE + SCENARIO DATA BUILDERS
# =============================================================================
# Baseline: scripts/build_abha_s0_env_data.py -> data/raw/abha_s0/
# One-way alternatives: scripts/build_abha_s1_env_data.py -> abha_s1a / abha_s1b
# Green Road: scripts/build_abha_s2_env_data.py -> data/raw/abha_s2/
# Scenario builders should change only the intended physical intervention while
# demand assumptions and evaluation settings remain consistent where possible.


# =============================================================================
# 5. FLOW BACKEND / SIMULATION
# =============================================================================
def build_abha_backend(scenario_key: str = BASELINE_SCENARIO) -> FlowBackend:
    """Build the backend selected by the scenario configuration."""
    return build_backend(load_abha_config(scenario_key))


# SimulationResult provides segment_flow, origin_access, mean_trip_distance,
# n_components, unreachable_fraction, and backend-specific extra diagnostics.


# =============================================================================
# 6. PERFORMANCE METRICS — SEPARATE FROM REWARD
# =============================================================================
# Current evaluation metrics include mean_access, access_gini, flow_entropy,
# total_flow, mean_trip_distance, n_components and unreachable_fraction.
# Future validated traffic metrics may include traffic volume, travel time,
# congestion, VKT, emissions, speed and queue length.


def extract_evaluation_metrics(sim: SimulationResult) -> dict:
    """Extract evaluation metrics independently from the RL reward."""
    return summarize(sim)


# =============================================================================
# 7. REWARD FUNCTION
# =============================================================================
# Reward is for RL training. Current components include accessibility, flow
# concentration, equity, pedestrian-zone score, detour, intervention cost and
# disconnection penalty. A higher reward does not imply every traffic metric
# improved, so final scenario evaluation must report metrics separately.


# =============================================================================
# 8. RL ENVIRONMENT / OBSERVATION / ACTION
# =============================================================================
# StreetNetworkEnv connects config, backend, baseline simulation, observation,
# action space, reward and connectivity constraints.
#
# Current observation shape: (n_segments + 1, 5)
# Per segment: is_closed, normalized flow, normalized length, flow delta from
# baseline, normalized segment degree.
# Global row: budget_used, step_fraction, mean_access_ratio, access_gini, 0.
# Measured vehicle volume, speed, lane capacity, congestion, queue length and
# signal state are not yet part of the observation.
#
# Current Abha scenarios use toggle actions and closure_mode=penalize. With
# allow_noop=True, actions 0..N-1 address segments and N is no-op.


# =============================================================================
# 9. CONNECTIVITY / ACTION MASK
# =============================================================================
# MaskablePPO uses env.action_masks() to prevent invalid actions before an
# expensive simulation. Checks include closure budget, reopening rules and
# network disconnection. SNRL_MASK_WORKERS can parallelize connectivity-mask
# computation for large Ibex jobs.


# =============================================================================
# 10. SCENARIO COMPARISON
# =============================================================================
# Compare every intervention with Baseline Network using the SAME metrics and
# demand assumptions. Recommended table columns: Baseline, Scenario, Difference.
# Report mean accessibility, Gini, flow entropy, total flow, trip distance,
# unreachable fraction and network components independently from reward.


# =============================================================================
# 11. VISUAL / REALITY VALIDATION
# =============================================================================
# Each scenario should have a map, baseline-vs-scenario map, flow heatmap,
# flow-difference map, screenshot, optional short video and numerical table.
# Use clear scenario names, a common basemap, legend, consistent visual encoding,
# major-road labels and an intervention description.
#
# Validation sequence:
# OSM network -> interactive validation map -> satellite/reference comparison ->
# identify geometry errors -> correct network -> rerun simulation.


# =============================================================================
# 12. FUTURE AUTHORITY TRAFFIC DATA
# =============================================================================
# Future validated authority data may add traffic_volume, average_speed, lanes,
# capacity, congestion_index, travel_time, queue_length, signal state/cycle and
# population/demand. Do not silently reinterpret current Madina metrics as
# measured vehicular traffic.
#
# def enrich_abha_network_with_authority_data(streets_gdf, authority_traffic_df):
#     ...


# =============================================================================
# 13. TRAINING / EVALUATION / IBEX
# =============================================================================
# Production PPO training: scripts/train.py
# Production policy evaluation: scripts/evaluate.py
# Baselines include random, greedy, highest_flow, lowest_flow, zone_builder and
# zone_builder_best. Large experiments run on Ibex through Slurm jobs.


# =============================================================================
# 14. DEVELOPMENT WORKFLOW
# =============================================================================
# one change -> local test -> separate Git branch -> scenario/tests -> save
# numerical and visual evidence -> review -> merge after validation.


def inspect_abha_scenario(scenario_key: str = BASELINE_SCENARIO) -> dict:
    """Build one Abha scenario and inspect its initial environment state."""
    scenario = get_scenario(scenario_key)
    env = build_abha_environment(scenario_key)
    obs, info = env.reset()
    result = {
        "scenario_key": scenario_key,
        "scenario_name": scenario["name"],
        "legacy_code": scenario.get("legacy_code"),
        "segments": env.n_segments,
        "backend": env.cfg.network.backend,
        "observation_shape": obs.shape,
        "initial_info": info,
    }
    env.close()
    return result


def inspect_all_abha_scenarios() -> list[dict]:
    """Inspect all currently configured Abha scenarios."""
    return [inspect_abha_scenario(key) for key in ABHA_SCENARIOS]


if __name__ == "__main__":
    scenario_key = BASELINE_SCENARIO
    scenario = get_scenario(scenario_key)
    env = build_abha_environment(scenario_key)
    obs, info = env.reset()

    print("=" * 75)
    print("TRAFFIC PROJECT — ABHA STUDY PIPELINE")
    print("=" * 75)
    print(f"Scenario: {scenario['name']}")
    print(f"Legacy code: {scenario.get('legacy_code')}")
    print(f"Backend: {env.cfg.network.backend}")
    print(f"Segments: {env.n_segments}")
    print(f"Observation shape: {obs.shape}")
    print()
    print("Network data:")
    print(f"  Streets: {env.cfg.network.streets_path}")
    print(f"  Origins: {env.cfg.network.origins_path}")
    print(f"  Destinations: {env.cfg.network.destinations_path}")
    print()
    print("Action configuration:")
    print(f"  Action type: {env.cfg.action.action_type}")
    print(f"  Closure mode: {env.cfg.action.closure_mode}")
    print(f"  Maximum closures: {env.cfg.action.max_closures}")
    print(f"  Episode length: {env.cfg.action.episode_length}")
    print()
    print("Baseline metrics:")
    print(f"  Mean accessibility: {info['stat/mean_access']:.6f}")
    print(f"  Accessibility Gini: {info['stat/access_gini']:.6f}")
    print(f"  Flow entropy: {info['stat/flow_entropy']:.6f}")
    print(f"  Total flow: {info['stat/total_flow']:.6f}")
    print(f"  Mean trip distance: {info['stat/mean_trip_distance']:.6f}")
    print(f"  Network components: {int(info['stat/n_components'])}")
    print()
    print("Environment successfully loaded.")
    env.close()
