"""Flow-simulation backends.

A backend hides *how* pedestrian/bicycle flow is simulated behind a small
interface, so the RL environment can be developed and unit-tested without a
full geospatial stack.

    StubBackend   - synthetic lattice, pure networkx. Fast, no geopandas.
    MadinaBackend - real Madina (MIT UNA) betweenness flow simulation.
"""

from .base import FlowBackend, SimulationResult
from .stub import StubBackend

__all__ = ["FlowBackend", "SimulationResult", "StubBackend", "build_backend"]


def build_backend(cfg) -> FlowBackend:
    """Factory: pick a backend from the config."""
    kind = cfg.network.backend
    if kind == "stub":
        return StubBackend(cfg)
    if kind == "madina":
        from .madina_backend import MadinaBackend  # imported lazily: heavy deps
        return MadinaBackend(cfg)
    raise ValueError(f"Unknown backend {kind!r}. Use 'stub' or 'madina'.")
