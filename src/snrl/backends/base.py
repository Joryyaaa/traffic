"""Backend interface shared by the stub and Madina implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np


@dataclass
class SimulationResult:
    """Output of one flow simulation on a given network state."""

    segment_flow: np.ndarray          # (n_segments,) betweenness flow per segment
    origin_access: np.ndarray         # (n_origins,)  accessibility score per origin
    mean_trip_distance: float         # average O-D network distance
    n_components: int                 # connected components of the open network
    unreachable_fraction: float       # share of origins with zero reachable destinations
    extra: dict = field(default_factory=dict)


class FlowBackend(ABC):
    """Simulates pedestrian/bicycle flow for a given open/closed segment mask."""

    def __init__(self, cfg):
        self.cfg = cfg

    # --- static properties of the study area -------------------------------
    @property
    @abstractmethod
    def n_segments(self) -> int:
        """Number of street segments the agent can open/close."""

    @property
    @abstractmethod
    def segment_lengths(self) -> np.ndarray:
        """(n_segments,) segment length in CRS units (meters)."""

    @abstractmethod
    def segment_adjacency(self) -> np.ndarray:
        """(n_segments, n_segments) sparse-ish boolean adjacency between segments.

        Used for graph-based policies (GNN) later on.
        """

    # --- the expensive bit --------------------------------------------------
    @abstractmethod
    def simulate(self, closed_mask: np.ndarray) -> SimulationResult:
        """Run one flow simulation.

        :param closed_mask: (n_segments,) boolean; True = segment is closed.
        """

    # --- helpers ------------------------------------------------------------
    @abstractmethod
    def is_connected(self, closed_mask: np.ndarray) -> bool:
        """True if the open network is still one connected component."""

    def reseed(self, seed: int) -> bool:
        """Redraw any stochastic demand for a new episode.

        Returns True if anything changed, so the caller knows the baseline has
        to be recomputed. Deterministic backends return False.
        """
        return False

    def close(self) -> None:  # pragma: no cover - optional cleanup hook
        pass
