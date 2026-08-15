"""
TRAFFIC PROJECT — FULL PIPELINE
Study / Development Entry Point

Current Abha workflow in one place for study and subsystem integration.
Production implementation remains in src/snrl, scripts, configs, and data.

FLOW
====
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

Reward trains the RL agent. Evaluation metrics independently judge whether a
traffic scenario improved or degraded system performance.
"""

from pathlib import Path
import sys

# Repository uses a src/ layout. This makes `python traffic_full_pipeline.py`
# work from the repository root without requiring PYTHONPATH to be set first.
REPO_ROOT = Path(__file__).resolve().parent
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from snrl.config import EnvConfig, load_config
from snrl.env import StreetNetworkEnv
from snrl.metrics import summarize
from snrl.backends import FlowBackend, SimulationResult, build_backend


# =============================================================================
# 1. MAP / STUDY AREA VALIDATION
# =============================================================================
# Validate the physical network before simulation: King Abdulaziz Belt, major
# roads inside the belt, Route 10 and Route 2120 from Khamis Mushait, Al Soudah
# Road / Route 214, and their connections. Check OSM geometry against reference
# imagery and verify intersections, roundabouts, bridges and access points.

ABHA_VALIDATION_MAP = Path("data/abha_baseline/abha_belt_soudah_khamis_map.html")


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
# Descriptive names are primary. S-codes remain only for compatibility.

ABHA_SCENARIOS = {
    "baseline_network": {
        "name": "Baseline Network",
        "legacy_code": "S0",
        "description": "Existing Abha road network without the proposed intervention.",
        "config": Path("configs/city_madina_abha_s0.yaml"),
        "builder": Path("scripts/build_abha_s0_env_data.py"),
    },
    "king_abdulaziz_oneway_ne": {
        "name": "King Abdulaziz One-Way — Northeast Direction",
        "legacy_code": "S1A",
        "description": "King Abdulaziz Road configured one-way toward the northeast.",
        "config": Path("configs/city_madina_abha_s1a.yaml"),
        "builder": Path("scripts/build_abha_s1_env_data.py"),
    },
    "king_abdulaziz_oneway_sw": {
        "name": "King Abdulaziz One-Way — Southwest Direction",
        "legacy_code": "S1B",
        "description": "King Abdulaziz Road configured one-way toward the southwest.",
        "config": Path("configs/city_madina_abha_s1b.yaml"),
        "builder": Path("scripts/build_abha_s1_env_data.py"),
    },
    "green_road_bypass": {
        "name": "Green Road / Bypass Alternative",
        "legacy_code": "S2",
        "description": "Alternative bypass / Green Road scenario.",
        "config": Path("configs/city_madina_abha_s2.yaml"),
        "builder": Path("scripts/build_abha_s2_env_data.py"),
        "status": "Hypothetical until authoritative geometry is provided.",
    },
}

BASELINE_SCENARIO = "baseline_network"


def repo_path(path: Path | str) -> Path:
    """Resolve a repository-relative path regardless of current working dir."""
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def get_scenario(scenario_key: str) -> dict:
    """Return one scenario definition."""
    if scenario_key not in ABHA_SCENARIOS:
        valid = ", ".join(ABHA_SCENARIOS)
        raise ValueError(f"Unknown scenario: {scenario_key}. Choose one of: {valid}")
    return ABHA_SCENARIOS[scenario_key]


def load_abha_config(scenario_key: str = BASELINE_SCENARIO) -> EnvConfig:
    """Load the YAML configuration associated with one Abha scenario."""
    return load_config(repo_path(get_scenario(scenario_key)["config"]))


# =============================================================================
# 4. PREFLIGHT CHECKS
# =============================================================================
def preflight_check(scenario_key: str = BASELINE_SCENARIO) -> dict:
    """Check map, config and generated network inputs before simulation.

    data/raw is intentionally gitignored, so a fresh clone may need the
    scenario builder before the environment can run.
    """
    scenario = get_scenario(scenario_key)
    config_path = repo_path(scenario["config"])
    builder_path = repo_path(scenario["builder"])
    validation_map = repo_path(ABHA_VALIDATION_MAP)

    report = {
        "scenario": scenario["name"],
        "config": config_path.exists(),
        "builder": builder_path.exists(),
        "validation_map": validation_map.exists(),
        "network_inputs": {},
        "ready": False,
    }

    if not config_path.exists():
        report["message"] = f"Missing config: {config_path}"
        return report

    cfg = load_config(config_path)
    network_paths = {
        "streets": repo_path(cfg.network.streets_path),
        "origins": repo_path(cfg.network.origins_path),
        "destinations": repo_path(cfg.network.destinations_path),
    }
    report["network_inputs"] = {
        name: path.exists() for name, path in network_paths.items()
    }

    missing = [name for name, exists in report["network_inputs"].items() if not exists]
    report["ready"] = not missing
    if missing:
        report["message"] = (
            f"Missing generated network inputs: {', '.join(missing)}. "
            f"Run: python {scenario['builder']}"
        )
    else:
        report["message"] = "Preflight passed. Scenario inputs are ready."
    return report


def require_preflight(scenario_key: str = BASELINE_SCENARIO) -> None:
    """Raise a clear error instead of failing later inside the backend."""
    report = preflight_check(scenario_key)
    if not report["ready"]:
        raise FileNotFoundError(report["message"])


def build_abha_environment(scenario_key: str = BASELINE_SCENARIO) -> StreetNetworkEnv:
    """Build the RL environment after checking required scenario inputs."""
    require_preflight(scenario_key)
    return StreetNetworkEnv(load_abha_config(scenario_key))


# =============================================================================
# 5. SCENARIO DATA BUILDERS
# =============================================================================
# Baseline: scripts/build_abha_s0_env_data.py -> data/raw/abha_s0/
# One-way alternatives: scripts/build_abha_s1_env_data.py -> abha_s1a / abha_s1b
# Green Road: scripts/build_abha_s2_env_data.py -> data/raw/abha_s2/
# Keep demand assumptions/evaluation settings consistent wherever possible.


# =============================================================================
# 6. FLOW BACKEND / SIMULATION
# =============================================================================
def build_abha_backend(scenario_key: str = BASELINE_SCENARIO) -> FlowBackend:
    """Build the backend selected by the scenario configuration."""
    require_preflight(scenario_key)
    return build_backend(load_abha_config(scenario_key))


# =============================================================================
# 7. PERFORMANCE METRICS — SEPARATE FROM REWARD
# =============================================================================
# Current metrics: mean_access, access_gini, flow_entropy, total_flow,
# mean_trip_distance, n_components and unreachable_fraction. Future validated
# traffic metrics may include volume, travel time, congestion, VKT, emissions,
# speed and queue length.

def extract_evaluation_metrics(sim: SimulationResult) -> dict:
    """Extract evaluation metrics independently from the RL reward."""
    return summarize(sim)


# =============================================================================
# 8. REWARD / RL ENVIRONMENT
# =============================================================================
# Reward is for training and currently combines accessibility, flow
# concentration, equity, pedestrian-zone score, detour, intervention cost and
# disconnection penalty. A higher reward does not mean every metric improved.
#
# Current observation shape: (n_segments + 1, 5)
# Segment features: closure state, normalized flow, normalized length, flow
# delta from baseline, normalized degree. Global row: budget, step fraction,
# mean-access ratio, access Gini, 0. Measured vehicle volume/speed/capacity,
# congestion, queues and signals are not yet part of the observation.


# =============================================================================
# 9. CONNECTIVITY / ACTION MASK
# =============================================================================
# MaskablePPO uses env.action_masks(). Checks include closure budget, reopening
# rules and disconnection. SNRL_MASK_WORKERS parallelizes large Ibex mask jobs.


# =============================================================================
# 10. SCENARIO COMPARISON
# =============================================================================
# Compare each intervention with Baseline Network using the SAME metrics and
# demand assumptions. Report each metric independently from reward.


# =============================================================================
# 11. VISUAL / REALITY VALIDATION
# =============================================================================
# Each scenario should have a map, baseline-vs-scenario map, flow heatmap,
# flow-difference map, screenshot, optional video and numerical table.
# OSM -> interactive validation map -> satellite/reference comparison -> fix
# geometry errors -> rerun simulation.


# =============================================================================
# 12. FUTURE AUTHORITY TRAFFIC DATA
# =============================================================================
# Future validated data may add traffic_volume, average_speed, lanes, capacity,
# congestion_index, travel_time, queue_length, signal state/cycle and demand.
# Do not reinterpret current Madina metrics as measured vehicular traffic.


# =============================================================================
# 13. TRAINING / EVALUATION / IBEX
# =============================================================================
# Production PPO training: scripts/train.py
# Production policy evaluation: scripts/evaluate.py
# Large experiments run on Ibex through Slurm jobs.


# =============================================================================
# 14. DEVELOPMENT WORKFLOW
# =============================================================================
# one change -> local test -> separate branch -> scenario/tests -> save numeric
# and visual evidence -> review -> merge after validation.


def inspect_abha_scenario(scenario_key: str = BASELINE_SCENARIO) -> dict:
    """Build one scenario and inspect its initial environment state."""
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
    check = preflight_check(scenario_key)

    print("=" * 75)
    print("TRAFFIC PROJECT — ABHA STUDY PIPELINE")
    print("=" * 75)
    print(f"Scenario: {scenario['name']}")
    print(f"Legacy code: {scenario.get('legacy_code')}")
    print(f"Validation map: {'OK' if check['validation_map'] else 'MISSING'}")
    print(f"Config: {'OK' if check['config'] else 'MISSING'}")
    print(f"Builder: {'OK' if check['builder'] else 'MISSING'}")
    print(f"Network inputs: {check['network_inputs']}")
    print(f"Preflight: {check['message']}")

    if check["ready"]:
        env = build_abha_environment(scenario_key)
        obs, info = env.reset()
        print(f"Backend: {env.cfg.network.backend}")
        print(f"Segments: {env.n_segments}")
        print(f"Observation shape: {obs.shape}")
        print("Baseline metrics:")
        print(f"  Mean accessibility: {info['stat/mean_access']:.6f}")
        print(f"  Accessibility Gini: {info['stat/access_gini']:.6f}")
        print(f"  Flow entropy: {info['stat/flow_entropy']:.6f}")
        print(f"  Total flow: {info['stat/total_flow']:.6f}")
        print(f"  Mean trip distance: {info['stat/mean_trip_distance']:.6f}")
        print(f"  Network components: {int(info['stat/n_components'])}")
        env.close()
        print("Environment successfully loaded.")
