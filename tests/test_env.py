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


def test_baseline_is_deterministic(env):
    a = env.backend.simulate(np.zeros(env.n_segments, dtype=bool))
    b = env.backend.simulate(np.zeros(env.n_segments, dtype=bool))
    assert np.allclose(a.segment_flow, b.segment_flow)
