"""Multi-objective reward for street-segment open/close decisions.

The reward combines four planning objectives that are usually in tension:

    1. Accessibility  — can people still reach the destinations they need?
    2. Flow quality   — is pedestrian/bicycle flow concentrated on the
                        segments we want to be lively (or away from hazards)?
    3. Equity         — are accessibility gains spread across origins, or
                        captured by a few?
    4. Parsimony      — fewer, cheaper interventions are preferred.

Every term is expressed relative to the *baseline* (fully open) network so the
weights in `RewardConfig` are on a comparable scale.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .metrics import gini, normalized_entropy


@dataclass
class RewardBreakdown:
    """Per-term contributions — logged for diagnostics and mentor review."""

    accessibility: float = 0.0
    flow_concentration: float = 0.0
    equity: float = 0.0
    detour: float = 0.0
    intervention: float = 0.0
    disconnection: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.accessibility
            + self.flow_concentration
            + self.equity
            + self.detour
            + self.intervention
            + self.disconnection
        )

    def as_dict(self) -> dict[str, float]:
        d = self.__dict__.copy()
        d["total"] = self.total
        return d


class RewardFunction:
    def __init__(self, cfg, baseline_stats: dict[str, float]):
        self.cfg = cfg.reward
        self.action_cfg = cfg.action
        self.baseline = baseline_stats

    # ------------------------------------------------------------------
    @staticmethod
    def stats_from(sim) -> dict[str, float]:
        return {
            "mean_access": float(np.mean(sim.origin_access)) if sim.origin_access.size else 0.0,
            "access_gini": gini(sim.origin_access),
            "flow_entropy": normalized_entropy(sim.segment_flow),
            "total_flow": float(np.sum(sim.segment_flow)),
            "mean_trip_distance": float(sim.mean_trip_distance),
            "n_components": float(sim.n_components),
        }

    # ------------------------------------------------------------------
    def __call__(self, sim, prev_stats: dict[str, float], n_closed: int) -> RewardBreakdown:
        cur = self.stats_from(sim)
        ref = prev_stats if self.cfg.reward_mode == "delta" else self.baseline
        b = self.baseline

        def rel(key: str) -> float:
            """Change in `key` vs. the reference, scaled by the baseline level."""
            scale = abs(b.get(key, 0.0)) or 1.0
            return (cur[key] - ref.get(key, 0.0)) / scale

        out = RewardBreakdown()
        out.accessibility = self.cfg.w_accessibility * rel("mean_access")

        # Lower entropy = flow concentrated on fewer corridors.
        # TODO: replace with a corridor-targeted term once the mentor confirms
        # which streets should attract flow (e.g. designated bike spines).
        out.flow_concentration = -self.cfg.w_flow_concentration * rel("flow_entropy")

        out.equity = -self.cfg.w_equity * rel("access_gini")

        detour = rel("mean_trip_distance")
        out.detour = -self.cfg.w_detour * (0.0 if not np.isfinite(detour) else detour)

        out.intervention = -self.cfg.w_intervention * (
            n_closed / max(self.action_cfg.max_closures, 1)
        )

        if sim.n_components > b.get("n_components", 1.0):
            out.disconnection = -self.cfg.disconnection_penalty

        return out
