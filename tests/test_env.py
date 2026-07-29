"""Unit tests for the environment contract. Run with: pytest -q"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pytest

from snrl import EnvConfig, StreetNetworkEnv


@pytest.fixture
def env():
    cfg = EnvConfig()
    cfg.network.stub_grid_size = 4
    cfg.action.episode_length = 5
    cfg.action.max_closures = 3
    e = StreetNetworkEnv(cfg)
    yield e
    e.close()


def test_reset_returns_valid_observation(env):
    obs, info = env.reset()
    assert env.observation_space.contains(obs)
    assert info["n_closed"] == 0


def test_step_shapes_and_types(env):
    env.reset()
    obs, reward, terminated, truncated, info = env.step(0)
    assert env.observation_space.contains(obs)
    assert isinstance(reward, float)
    assert isinstance(terminated, bool) and isinstance(truncated, bool)


def test_episode_terminates(env):
    env.reset()
    for _ in range(env.cfg.action.episode_length):
        _, _, terminated, truncated, _ = env.step(env.action_space.sample())
        if terminated or truncated:
            break
    assert terminated or truncated


def test_closure_budget_is_respected(env):
    env.reset()
    rng = np.random.default_rng(0)
    for _ in range(50):
        valid = np.flatnonzero(env.action_masks())
        env.step(int(rng.choice(valid)))
        assert env.closed_mask.sum() <= env.cfg.action.max_closures


def test_network_stays_connected(env):
    env.reset()
    rng = np.random.default_rng(1)
    for _ in range(30):
        valid = np.flatnonzero(env.action_masks())
        env.step(int(rng.choice(valid)))
        assert env.backend.is_connected(env.closed_mask)


def test_zone_score_rewards_contiguity():
    """Four connected closures must beat four scattered ones."""
    from snrl.metrics import zone_score

    # path graph over 5 segments: 0-1-2-3-4
    adj = np.zeros((5, 5), dtype=bool)
    for i in range(4):
        adj[i, i + 1] = adj[i + 1, i] = True

    lone = np.array([1, 0, 0, 0, 0], dtype=bool)
    pair = np.array([1, 1, 0, 0, 0], dtype=bool)
    trio = np.array([1, 1, 1, 0, 0], dtype=bool)
    split = np.array([1, 1, 0, 1, 1], dtype=bool)

    # below min_size a group is worth nothing — this is what stalls greedy
    assert zone_score(lone, adj, min_size=3) == 0.0
    assert zone_score(pair, adj, min_size=3) == 0.0
    assert zone_score(trio, adj, min_size=3) == 9.0
    # superlinear: one group of 3 beats two groups of 2
    assert zone_score(trio, adj, min_size=3) > zone_score(split, adj, min_size=3)


def test_hard_config_gives_greedy_no_first_move():
    """On the hard config the first closure must be net-negative, otherwise the
    environment has no long-horizon structure and RL has nothing to learn."""
    from snrl import load_config

    cfg = load_config("configs/hard.yaml")
    cfg.network.stub_grid_size = 4
    e = StreetNetworkEnv(cfg)
    try:
        e.reset()
        first = np.zeros(e.n_segments, dtype=bool)
        first[0] = True
        r = e.reward_fn(e.backend.simulate(first), e._prev_stats, first)
        assert r.pedestrian_zone == 0.0
        assert r.total < 0.0
    finally:
        e.close()


def test_baseline_is_deterministic(env):
    a = env.backend.simulate(np.zeros(env.n_segments, dtype=bool))
    b = env.backend.simulate(np.zeros(env.n_segments, dtype=bool))
    assert np.allclose(a.segment_flow, b.segment_flow)
