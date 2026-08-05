"""Network-level metrics used to build observations and rewards."""

from __future__ import annotations

import numpy as np


def gini(x: np.ndarray) -> float:
    """Gini coefficient of a non-negative array. 0 = perfectly equal."""
    x = np.asarray(x, dtype=float).ravel()
    x = x[np.isfinite(x)]
    if x.size == 0:
        return 0.0
    x = np.clip(x, 0.0, None)
    if x.sum() == 0:
        return 0.0
    xs = np.sort(x)
    n = xs.size
    idx = np.arange(1, n + 1)
    return float((2.0 * (idx * xs).sum()) / (n * xs.sum()) - (n + 1.0) / n)


def normalized_entropy(x: np.ndarray) -> float:
    """Entropy of a flow distribution, normalized to [0, 1].

    High  -> flow is spread evenly over many segments.
    Low   -> flow is concentrated on a few corridors.
    """
    x = np.clip(np.asarray(x, dtype=float).ravel(), 0.0, None)
    total = x.sum()
    if total <= 0 or x.size <= 1:
        return 0.0
    p = x / total
    p = p[p > 0]
    return float(-(p * np.log(p)).sum() / np.log(x.size))


def zone_score(
    closed_mask: np.ndarray,
    adjacency: np.ndarray,
    min_size: int = 3,
    exponent: float = 2.0,
    qualifying_mask: np.ndarray | None = None,
) -> float:
    """Reward for closures that form a coherent *pedestrian zone*.

    Scattered closures create dead ends and help nobody. A contiguous group of
    closed segments creates a walkable plaza. So the bonus is:

        sum over connected groups of closed segments, of  size ** exponent
        — but only for groups of at least `min_size` segments.

    Two properties make this the interesting case for RL:

    * **Superlinear** (`exponent > 1`): one group of four beats four scattered
      singles, so the agent must commit to a location rather than hedge.
    * **Threshold** (`min_size`): the first closures of a plaza earn *nothing*
      while already costing accessibility. A one-step-lookahead (greedy) agent
      therefore refuses to ever start one, while an agent that plans ahead can
      absorb the early loss to reach the payoff.

    `qualifying_mask` (optional): marks which segments carry enough baseline
    flow to count toward a group's *size*. A segment outside this mask can
    still sit inside a contiguous closed group (e.g. a quiet connector alley
    linking two busy streets), but doesn't contribute to the size used for
    `min_size`/`exponent`. Without this, the agent can farm the full bonus by
    closing a zone made entirely of already-unused streets -- a real finding
    from a trained run (see reward_breakdown.py output + the mentor's
    question: shouldn't the agent only close streets that see real
    congestion?). Defaults to everything qualifying (old behavior).
    """
    closed_mask = np.asarray(closed_mask, dtype=bool)
    closed = np.flatnonzero(closed_mask)
    if closed.size == 0:
        return 0.0
    if qualifying_mask is None:
        qualifying_mask = np.ones_like(closed_mask, dtype=bool)
    else:
        qualifying_mask = np.asarray(qualifying_mask, dtype=bool)

    seen: set[int] = set()
    total = 0.0
    for start in closed:
        start = int(start)
        if start in seen:
            continue
        seen.add(start)
        stack, group = [start], [start]
        while stack:
            u = stack.pop()
            for v in np.flatnonzero(adjacency[u]):
                v = int(v)
                if v in seen or not closed_mask[v]:
                    continue
                seen.add(v)
                stack.append(v)
                group.append(v)
        effective_size = sum(1 for seg in group if qualifying_mask[seg])
        if effective_size >= min_size:
            total += float(effective_size) ** exponent
    return total


def safe_normalize(x: np.ndarray, ref: float | None = None) -> np.ndarray:
    """Scale an array by a reference value (defaults to its own max)."""
    x = np.asarray(x, dtype=float)
    denom = ref if ref is not None else np.nanmax(np.abs(x))
    if denom is None or not np.isfinite(denom) or denom == 0:
        return np.zeros_like(x)
    return x / denom


def summarize(sim: "SimulationResult") -> dict[str, float]:  # noqa: F821
    """Scalar summary of one simulation run — the raw material for the reward."""
    return {
        "mean_access": float(np.mean(sim.origin_access)) if sim.origin_access.size else 0.0,
        "access_gini": gini(sim.origin_access),
        "total_flow": float(np.sum(sim.segment_flow)),
        "flow_entropy": normalized_entropy(sim.segment_flow),
        "mean_trip_distance": float(sim.mean_trip_distance),
        "n_components": float(sim.n_components),
        "unreachable_fraction": float(sim.unreachable_fraction),
    }
