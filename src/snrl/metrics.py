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
