"""Synthetic lattice backend.

Purpose: let the environment, reward function and training loop be developed
and unit-tested before the real geospatial data pipeline exists. The API and
the shape of every returned array match `MadinaBackend` exactly, so swapping
backends is a one-line config change.
"""

from __future__ import annotations

import networkx as nx
import numpy as np

from .base import FlowBackend, SimulationResult


class StubBackend(FlowBackend):
    def __init__(self, cfg):
        super().__init__(cfg)
        n = cfg.network.stub_grid_size
        rng = np.random.default_rng(cfg.network.stub_seed)

        # A k x k lattice standing in for a gridded street network.
        self._graph = nx.convert_node_labels_to_integers(nx.grid_2d_graph(n, n))
        self._edges = list(self._graph.edges())
        for u, v in self._edges:
            # ~100 m blocks with some jitter
            self._graph[u][v]["length"] = float(rng.uniform(80, 120))

        self._lengths = np.array(
            [self._graph[u][v]["length"] for u, v in self._edges], dtype=float
        )

        nodes = list(self._graph.nodes())
        n_od = max(2, len(nodes) // 6)
        self._origins = list(rng.choice(nodes, size=n_od, replace=False))
        self._destinations = list(rng.choice(nodes, size=n_od, replace=False))

    # --- static properties --------------------------------------------------
    @property
    def n_segments(self) -> int:
        return len(self._edges)

    @property
    def segment_lengths(self) -> np.ndarray:
        return self._lengths

    def segment_adjacency(self) -> np.ndarray:
        n = self.n_segments
        adj = np.zeros((n, n), dtype=bool)
        for i, (a, b) in enumerate(self._edges):
            for j, (c, d) in enumerate(self._edges):
                if i != j and {a, b} & {c, d}:
                    adj[i, j] = True
        return adj

    # --- simulation ---------------------------------------------------------
    def _open_graph(self, closed_mask: np.ndarray) -> nx.Graph:
        g = self._graph.copy()
        g.remove_edges_from([e for e, closed in zip(self._edges, closed_mask) if closed])
        return g

    def is_connected(self, closed_mask: np.ndarray) -> bool:
        g = self._open_graph(closed_mask)
        g.remove_nodes_from(list(nx.isolates(g)))
        return g.number_of_nodes() > 0 and nx.is_connected(g)

    def simulate(self, closed_mask: np.ndarray) -> SimulationResult:
        g = self._open_graph(closed_mask)
        radius = self.cfg.simulation.search_radius
        beta = self.cfg.simulation.beta

        flow = np.zeros(self.n_segments, dtype=float)
        edge_index = {frozenset(e): i for i, e in enumerate(self._edges)}

        access, trip_lengths = [], []
        for o in self._origins:
            if o not in g:
                access.append(0.0)
                continue
            dist, paths = nx.single_source_dijkstra(g, o, cutoff=radius, weight="length")
            score = 0.0
            for d in self._destinations:
                if d == o or d not in dist:
                    continue
                # gravity-style decay, mirroring Madina's exponential decay
                w = float(np.exp(-beta * dist[d]))
                score += w
                trip_lengths.append(dist[d])
                path = paths[d]
                for u, v in zip(path[:-1], path[1:]):
                    flow[edge_index[frozenset((u, v))]] += w
            access.append(score)

        access_arr = np.asarray(access, dtype=float)
        return SimulationResult(
            segment_flow=flow,
            origin_access=access_arr,
            mean_trip_distance=float(np.mean(trip_lengths)) if trip_lengths else 0.0,
            n_components=nx.number_connected_components(g) if g.number_of_nodes() else 0,
            unreachable_fraction=float(np.mean(access_arr <= 0.0)),
        )
