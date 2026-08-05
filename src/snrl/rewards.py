"""Multi-objective reward for street-segment open/close decisions.

The reward combines planning objectives that are usually in tension:

    1. Accessibility    — can people still reach the destinations they need?
    2. Flow quality     — is pedestrian/bicycle flow concentrated on the
                          segments we want to be lively (or away from hazards)?
    3. Equity           — are accessibility gains spread across origins, or
                          captured by a few?
    4. Pedestrian zones — do the closures form coherent walkable areas rather
                          than scattered dead ends?
    5. Parsimony        — fewer, cheaper interventions are preferred.

Every term is expressed relative to the *baseline* (fully open) network so the
weights in `RewardConfig` are on a comparable scale.

Term 4 is what makes the problem worth solving with RL rather than a greedy
heuristic — see `metrics.zone_score`.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .metrics import gini, normalized_entropy, zone_score


@dataclass
class RewardBreakdown:
    """Per-term contributions — logged for diagnostics and mentor review."""

    accessibility: float = 0.0
    flow_concentration: float = 0.0
    equity: float = 0.0
    pedestrian_zone: float = 0.0
    detour: float = 0.0
    intervention: float = 0.0
    disconnection: float = 0.0

    @property
    def total(self) -> float:
        return (
            self.accessibility
            + self.flow_concentration
            + self.equity
            + self.pedestrian_zone
            + self.detour
            + self.intervention
            + self.disconnection
        )

    def as_dict(self) -> dict[str, float]:
        d = self.__dict__.copy()
        d["total"] = self.total
        return d


def simulation_stats(sim) -> dict[str, float]:
    """Scalar summary of one simulation run, independent of the action taken."""
    return {
        "mean_access": float(np.mean(sim.origin_access)) if sim.origin_access.size else 0.0,
        "access_gini": gini(sim.origin_access),
        "flow_entropy": normalized_entropy(sim.segment_flow),
        "total_flow": float(np.sum(sim.segment_flow)),
        "mean_trip_distance": float(sim.mean_trip_distance),
        "n_components": float(sim.n_components),
        "zone_score": 0.0,
        "n_closed_frac": 0.0,
    }


class RewardFunction:
    def __init__(
        self,
        cfg,
        baseline_stats: dict[str, float],
        adjacency: np.ndarray,
        baseline_flow: np.ndarray | None = None,
    ):
        self.cfg = cfg.reward
        self.action_cfg = cfg.action
        self.baseline = baseline_stats
        self.adjacency = adjacency
        # A single zone spending the whole budget — the natural normalizer.
        self._zone_scale = float(max(self.action_cfg.max_closures, 1)) ** self.cfg.zone_exponent
        self.set_baseline_flow(baseline_flow)

    def set_baseline_flow(self, baseline_flow: np.ndarray | None) -> None:
        """(Re)compute which segments count toward zone_score's size, based on
        the current baseline (fully-open) flow. Call this again if the
        baseline changes (e.g. on env.reset() with a new network)."""
        if baseline_flow is None or self.cfg.zone_min_flow_fraction <= 0:
            self._qualifying_mask = None  # zone_score treats this as "everything qualifies"
            return
        baseline_flow = np.asarray(baseline_flow, dtype=float)
        mean_flow = float(np.mean(baseline_flow)) if baseline_flow.size else 0.0
        threshold = self.cfg.zone_min_flow_fraction * mean_flow
        self._qualifying_mask = baseline_flow >= threshold

    # ------------------------------------------------------------------
    def stats(self, sim, closed_mask: np.ndarray) -> dict[str, float]:
        """Simulation summary plus the action-dependent zone score."""
        out = simulation_stats(sim)
        out["n_closed_frac"] = float(np.sum(closed_mask)) / max(
            self.action_cfg.max_closures, 1
        )
        if self.cfg.w_pedestrian_zone:
            out["zone_score"] = (
                zone_score(
                    closed_mask,
                    self.adjacency,
                    min_size=self.cfg.min_zone_size,
                    exponent=self.cfg.zone_exponent,
                    qualifying_mask=self._qualifying_mask,
                )
                / self._zone_scale
            )
        return out

    # ------------------------------------------------------------------
    def __call__(
        self, sim, prev_stats: dict[str, float], closed_mask: np.ndarray
    ) -> RewardBreakdown:
        cur = self.stats(sim, closed_mask)
        ref = prev_stats if self.cfg.reward_mode == "delta" else self.baseline
        b = self.baseline
        n_closed = int(np.sum(closed_mask))

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

        # zone_score has no meaningful baseline (it is 0 when nothing is closed),
        # so it is compared against the reference directly rather than via rel().
        if self.cfg.w_pedestrian_zone:
            out.pedestrian_zone = self.cfg.w_pedestrian_zone * (
                cur["zone_score"] - ref.get("zone_score", 0.0)
            )

        detour = rel("mean_trip_distance")
        out.detour = -self.cfg.w_detour * (0.0 if not np.isfinite(detour) else detour)

        # Charged when a segment is closed, not re-charged every step it stays
        # closed — otherwise simply holding a closure bleeds reward forever and
        # doing nothing becomes the optimal policy.
        out.intervention = -self.cfg.w_intervention * (
            cur["n_closed_frac"] - ref.get("n_closed_frac", 0.0)
        )

        if sim.n_components > b.get("n_components", 1.0):
            out.disconnection = -self.cfg.disconnection_penalty

        return out
