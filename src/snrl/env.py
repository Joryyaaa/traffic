"""Gymnasium environment: open/close street segments to optimize
pedestrian & bicycle flow and accessibility.

MDP formulation
---------------
State   s_t : which segments are currently closed + the flow/accessibility
              pattern that results from that configuration.
Action  a_t : toggle one segment (open <-> closed), or no-op.
Reward  r_t : change in the multi-objective planning score (see rewards.py).
Episode     : `episode_length` interventions, subject to a budget of
              `max_closures` simultaneously closed segments.

Observation layout (per segment, `N_FEATURES` channels):
    0  is_closed          {0,1}
    1  normalized flow    betweenness / baseline max
    2  normalized length  length / max length
    3  flow delta         (current flow - baseline flow) / baseline max
    4  degree centrality  of the segment in the segment-adjacency graph
plus a small global vector appended as a final row:
    [budget_used, step_fraction, mean_access_ratio, access_gini, 0]
"""

from __future__ import annotations

from typing import Any

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .backends import build_backend
from .config import EnvConfig
from .rewards import RewardFunction, simulation_stats

N_FEATURES = 5


class StreetNetworkEnv(gym.Env):
    metadata = {"render_modes": ["human", "ansi"], "render_fps": 1}

    def __init__(self, config: EnvConfig | None = None, render_mode: str | None = None):
        super().__init__()
        self.cfg = config or EnvConfig()
        self.render_mode = render_mode

        self.backend = build_backend(self.cfg)
        self.n_segments = self.backend.n_segments

        # --- baseline: the fully-open network, our reference point ---------
        self._adjacency = self.backend.segment_adjacency()
        self._baseline_sim = self.backend.simulate(np.zeros(self.n_segments, dtype=bool))
        self._baseline_stats = simulation_stats(self._baseline_sim)
        self._flow_scale = float(np.max(self._baseline_sim.segment_flow)) or 1.0
        self._length_scale = float(np.max(self.backend.segment_lengths)) or 1.0
        self._seg_degree = self._segment_degree()

        self.reward_fn = RewardFunction(
            self.cfg, self._baseline_stats, self._adjacency, self._baseline_sim.segment_flow
        )

        # --- spaces ---------------------------------------------------------
        if self.cfg.action.action_type == "toggle":
            n = self.n_segments + (1 if self.cfg.action.allow_noop else 0)
            self.action_space = spaces.Discrete(n)
        else:  # "multi": choose a whole configuration at once
            self.action_space = spaces.MultiBinary(self.n_segments)

        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(self.n_segments + 1, N_FEATURES),
            dtype=np.float32,
        )

        # --- episode state ---------------------------------------------------
        self.closed_mask = np.zeros(self.n_segments, dtype=bool)
        self._step_count = 0
        self._last_sim = self._baseline_sim
        self._prev_stats = dict(self._baseline_stats)
        self._last_breakdown = None

    # ==================================================================
    # Gymnasium API
    # ==================================================================
    def reset(self, *, seed: int | None = None, options: dict | None = None):
        episode_seed = seed if seed is not None else self.cfg.seed
        super().reset(seed=episode_seed)

        # Stochastic demand: this episode is a different day, so the fully-open
        # network scores differently too and the baseline must be redrawn with
        # it. Without this the reward would measure the weather, not the policy.
        if self.backend.reseed(episode_seed):
            self._baseline_sim = self.backend.simulate(
                np.zeros(self.n_segments, dtype=bool)
            )
            self._baseline_stats = simulation_stats(self._baseline_sim)
            self._flow_scale = float(np.max(self._baseline_sim.segment_flow)) or 1.0
            self.reward_fn.baseline = self._baseline_stats
            self.reward_fn.set_baseline_flow(self._baseline_sim.segment_flow)

        self.closed_mask = np.zeros(self.n_segments, dtype=bool)
        # TODO: support randomized starts (a few random pre-existing closures)
        # to improve generalization — controlled via `options`.
        self._step_count = 0
        self._last_sim = self._baseline_sim
        self._prev_stats = dict(self._baseline_stats)
        self._last_breakdown = None
        return self._observation(), self._info()

    def step(self, action):
        self._apply_action(action)
        self._step_count += 1

        self._last_sim = self.backend.simulate(self.closed_mask)
        breakdown = self.reward_fn(self._last_sim, self._prev_stats, self.closed_mask)
        self._last_breakdown = breakdown
        self._prev_stats = self.reward_fn.stats(self._last_sim, self.closed_mask)

        terminated = bool(self._last_sim.n_components > self._baseline_sim.n_components) \
            and self.cfg.action.forbid_disconnection
        truncated = self._step_count >= self.cfg.action.episode_length

        return self._observation(), float(breakdown.total), terminated, truncated, self._info()

    def render(self):
        if self.render_mode == "ansi":
            return self._text_summary()
        print(self._text_summary())

    def close(self):
        self.backend.close()

    # ==================================================================
    # Internals
    # ==================================================================
    def _apply_action(self, action) -> None:
        cfg = self.cfg.action
        if cfg.action_type == "multi":
            proposed = np.asarray(action, dtype=bool)
            if proposed.sum() > cfg.max_closures:
                # Keep only the `max_closures` highest-index proposals.
                # TODO: a smarter tie-break (e.g. by predicted value) may help.
                keep = np.flatnonzero(proposed)[: cfg.max_closures]
                proposed = np.zeros_like(proposed)
                proposed[keep] = True
            self.closed_mask = proposed
            return

        action = int(action)
        if cfg.allow_noop and action == self.n_segments:
            return
        if self.closed_mask[action]:
            if cfg.allow_reopen:
                self.closed_mask[action] = False
            return
        if self.closed_mask.sum() >= cfg.max_closures:
            return  # over budget: treated as a no-op
        if cfg.forbid_disconnection:
            trial = self.closed_mask.copy()
            trial[action] = True
            if not self.backend.is_connected(trial):
                return  # illegal: would fragment the network
        self.closed_mask[action] = True

    def action_masks(self) -> np.ndarray:
        """Valid-action mask, for MaskablePPO (sb3-contrib).

        Cheap connectivity pre-check; the expensive flow simulation never runs
        on an invalid configuration.
        """
        cfg = self.cfg.action
        size = self.n_segments + (1 if cfg.allow_noop else 0)
        mask = np.ones(size, dtype=bool)
        at_budget = self.closed_mask.sum() >= cfg.max_closures
        for i in range(self.n_segments):
            if self.closed_mask[i]:
                mask[i] = cfg.allow_reopen
            elif at_budget:
                mask[i] = False
            elif cfg.forbid_disconnection:
                trial = self.closed_mask.copy()
                trial[i] = True
                mask[i] = self.backend.is_connected(trial)
        return mask

    def _segment_degree(self) -> np.ndarray:
        deg = self._adjacency.sum(axis=1).astype(float)
        return deg / (deg.max() or 1.0)

    def _observation(self) -> np.ndarray:
        sim = self._last_sim
        obs = np.zeros((self.n_segments + 1, N_FEATURES), dtype=np.float32)
        obs[: self.n_segments, 0] = self.closed_mask.astype(np.float32)
        obs[: self.n_segments, 1] = sim.segment_flow / self._flow_scale
        obs[: self.n_segments, 2] = self.backend.segment_lengths / self._length_scale
        obs[: self.n_segments, 3] = (
            sim.segment_flow - self._baseline_sim.segment_flow
        ) / self._flow_scale
        obs[: self.n_segments, 4] = self._seg_degree

        base_access = self._baseline_stats["mean_access"] or 1.0
        obs[self.n_segments] = np.array(
            [
                self.closed_mask.sum() / max(self.cfg.action.max_closures, 1),
                self._step_count / max(self.cfg.action.episode_length, 1),
                self._prev_stats["mean_access"] / base_access,
                self._prev_stats["access_gini"],
                0.0,
            ],
            dtype=np.float32,
        )
        return np.nan_to_num(obs, nan=0.0, posinf=0.0, neginf=0.0)

    def _info(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "closed_segments": np.flatnonzero(self.closed_mask).tolist(),
            "n_closed": int(self.closed_mask.sum()),
            "step": self._step_count,
            **{f"stat/{k}": v for k, v in self._prev_stats.items()},
        }
        if self._last_breakdown is not None:
            info.update({f"reward/{k}": v for k, v in self._last_breakdown.as_dict().items()})
        return info

    def _text_summary(self) -> str:
        s = self._prev_stats
        b = self._baseline_stats
        return (
            f"step {self._step_count:>3} | closed {int(self.closed_mask.sum()):>2}"
            f"/{self.cfg.action.max_closures} | "
            f"access {s['mean_access']:.3f} (base {b['mean_access']:.3f}) | "
            f"gini {s['access_gini']:.3f} | components {int(s['n_components'])}"
        )
