"""Madina (MIT Urban Network Analysis) flow-simulation backend.

Maps the RL environment's open/close decisions onto Madina's Zonal/Network
objects and reads pedestrian/bicycle flow back out of the UNA betweenness tool.

Reference API (City-Form-Lab/madina):
    zonal = Zonal()
    zonal.load_layer(name="streets", source="streets.geojson")
    zonal.create_street_network(source_layer="streets", weight_attribute=...)
    zonal.load_layer(name="homes", source="homes.geojson")
    zonal.insert_node("homes", label="origin", weight_attribute="residents")
    zonal.insert_node("shops", label="destination", weight_attribute="jobs")
    zonal.create_graph()
    from madina.una.tools import betweenness, accessibility
    betweenness(zonal, search_radius=800, save_betweenness_as="flow", ...)
"""

from __future__ import annotations

import contextlib
from functools import lru_cache
from pathlib import Path

import numpy as np

from .base import FlowBackend, SimulationResult


class MadinaBackend(FlowBackend):
    """Wraps a Madina `Zonal` object.

    Two ways of representing a closed segment (see `ActionConfig.closure_mode`):

    * ``rebuild``  — drop the closed rows from the street layer and rebuild the
      routable network. Physically exact, but pays the network-construction cost
      on every step.
    * ``penalize`` — keep the geometry and multiply the segment's *perceived
      cost* by a large factor, using Madina's `weight_attribute`. Much cheaper
      and differentiable-ish, but pedestrians can still "squeeze through" at a
      high cost.
    """

    STREETS = "streets"
    ORIGINS = "origins"
    DESTINATIONS = "destinations"
    FLOW_COL = "rl_betweenness"
    ACCESS_COL = "rl_gravity"
    COST_COL = "rl_perceived_cost"

    def __init__(self, cfg):
        super().__init__(cfg)
        self._check_paths()

        import geopandas as gpd  # noqa: F401  (import check, heavy dep)

        self._base_streets = self._read_streets()
        self._lengths = self._base_streets.geometry.length.to_numpy(dtype=float)
        self._zonal = None            # rebuilt lazily per network state
        self._cache: dict[bytes, SimulationResult] = {}

        import os

        self._debug_enabled = os.environ.get("SNRL_DEBUG_MADINA") == "1"

    def _debug(self, msg: str) -> None:
        """Stage-by-stage progress print, off by default (noisy at RL-training
        scale, one simulate() call per env step). Turn on temporarily with:
            set SNRL_DEBUG_MADINA=1        (Windows)
            export SNRL_DEBUG_MADINA=1     (macOS/Linux)
        """
        if self._debug_enabled:
            print(f"[madina_backend] {msg}", flush=True)

    # --- setup --------------------------------------------------------------
    def _check_paths(self) -> None:
        nc = self.cfg.network
        for label, p in [
            ("streets_path", nc.streets_path),
            ("origins_path", nc.origins_path),
            ("destinations_path", nc.destinations_path),
        ]:
            if p is None:
                raise ValueError(f"network.{label} must be set for the madina backend")
            if not Path(p).exists():
                raise FileNotFoundError(f"network.{label}: {p} not found")

    def _read_streets(self):
        import geopandas as gpd

        gdf = gpd.read_file(self.cfg.network.streets_path)
        gdf = gdf.to_crs(self.cfg.network.crs)
        gdf = gdf.reset_index(drop=True)
        gdf["segment_id"] = np.arange(len(gdf))
        return gdf

    def _read_points(self, path):
        """Read an origins/destinations layer and reproject it to match the
        street network's CRS -- required for node snapping to work correctly.
        Without this, insert_node() compares projected street coordinates
        (meters) against whatever CRS the source file happens to be in
        (typically WGS84 degrees), which silently produces nonsense nearest-edge
        snaps instead of an error.
        """
        import geopandas as gpd

        gdf = gpd.read_file(path)
        return gdf.to_crs(self.cfg.network.crs)

    def _build_zonal(self, closed_mask: np.ndarray):
        """Construct a Zonal object for the given network state."""
        import time

        from madina.zonal import Zonal

        nc, sc = self.cfg.network, self.cfg.simulation
        streets = self._base_streets
        t0 = time.time()
        self._debug(f"_build_zonal: start ({len(streets)} streets before closure)")

        weight_attribute = nc.weight_attribute
        if self.cfg.action.closure_mode == "rebuild":
            streets = streets.loc[~closed_mask].copy()
        else:  # "penalize"
            streets = streets.copy()
            base_cost = (
                streets[nc.weight_attribute] if nc.weight_attribute else streets.geometry.length
            )
            streets[self.COST_COL] = np.where(
                closed_mask, base_cost * self.cfg.action.closure_penalty, base_cost
            )
            weight_attribute = self.COST_COL

        zonal = Zonal()
        zonal.load_layer(name=self.STREETS, source=streets)
        self._debug(f"  loaded streets layer [{time.time()-t0:.1f}s]")
        zonal.create_street_network(
            source_layer=self.STREETS,
            weight_attribute=weight_attribute,
            node_snapping_tolerance=nc.node_snapping_tolerance,
            turn_threshold_degree=sc.turn_threshold_degree,
            turn_penalty_amount=sc.turn_penalty_amount,
        )
        self._debug(f"  create_street_network done [{time.time()-t0:.1f}s]")
        zonal.load_layer(name=self.ORIGINS, source=self._read_points(nc.origins_path))
        self._debug(f"  loaded origins layer [{time.time()-t0:.1f}s]")
        zonal.insert_node(self.ORIGINS, label="origin", weight_attribute=nc.origin_weight)
        self._debug(f"  inserted origins [{time.time()-t0:.1f}s]")
        zonal.load_layer(name=self.DESTINATIONS, source=self._read_points(nc.destinations_path))
        self._debug(f"  loaded destinations layer [{time.time()-t0:.1f}s]")
        zonal.insert_node(
            self.DESTINATIONS, label="destination", weight_attribute=nc.destination_weight
        )
        self._debug(f"  inserted destinations [{time.time()-t0:.1f}s]")
        zonal.create_graph()
        return zonal

    # --- static properties --------------------------------------------------
    @property
    def n_segments(self) -> int:
        return len(self._base_streets)

    @property
    def segment_lengths(self) -> np.ndarray:
        return self._lengths

    def segment_adjacency(self) -> np.ndarray:
        """Segments are adjacent when their geometries touch."""
        import geopandas as gpd

        gdf = self._base_streets
        n = len(gdf)
        adj = np.zeros((n, n), dtype=bool)
        sindex = gdf.sindex
        for i, geom in enumerate(gdf.geometry):
            for j in sindex.query(geom, predicate="touches"):
                if i != j:
                    adj[i, j] = True
        return adj

    # --- simulation ---------------------------------------------------------
    def simulate(self, closed_mask: np.ndarray) -> SimulationResult:
        import time

        key = np.packbits(closed_mask.astype(bool)).tobytes()
        if key in self._cache:
            return self._cache[key]

        from madina.una.tools import betweenness

        sc = self.cfg.simulation
        t0 = time.time()
        zonal = self._build_zonal(closed_mask)
        self._debug(f"_build_zonal total [{time.time()-t0:.1f}s]")

        with self._force_single_process_betweenness():
            if self._debug_enabled:
                import faulthandler
                import sys

                # If this call hangs, dump every thread's exact stack trace
                # after 20s instead of leaving us guessing -- cancelled below
                # once it returns (normally or via exception).
                faulthandler.dump_traceback_later(20, exit=False, file=sys.stderr)
            try:
                self._debug("calling betweenness() (in-process)...")
                betweenness(
                    zonal,
                    search_radius=sc.search_radius,
                    detour_ratio=sc.detour_ratio,
                    decay=sc.decay,
                    decay_method=sc.decay_method,
                    beta=sc.beta,
                    # Madina's betweenness() always wraps its per-origin loop in a
                    # concurrent.futures.ProcessPoolExecutor, regardless of
                    # num_cores -- there's no genuine serial code path in the
                    # public API. On Windows this can hang indefinitely (every
                    # spawned worker has to re-import the whole scientific stack,
                    # and on at least one dev machine that re-import never
                    # completes). _force_single_process_betweenness() patches the
                    # executor to run in-process instead, so num_cores is pinned
                    # to 1 here on purpose -- sc.num_cores is intentionally
                    # ignored for now. Revisit if/when this moves to a Linux/HPC
                    # box for the full-scale run, where real multiprocessing may
                    # be safe and worth the speedup.
                    num_cores=1,
                    closest_destination=sc.closest_destination,
                    turn_penalty=sc.turn_penalty,
                    save_betweenness_as=self.FLOW_COL,
                    save_gravity_as=self.ACCESS_COL,
                )
                self._debug(f"betweenness() done [{time.time()-t0:.1f}s]")
            except KeyError:
                # Madina bug, confirmed with a hand-built test case: if *zero*
                # origins can reach *any* destination within search_radius (a
                # closure -- or in "penalize" mode, a cost high enough to price
                # everyone out of the search radius -- isolates the whole
                # network), the internal per-origin result frame never gets a
                # betweenness/gravity column created at all, and the library
                # raises a KeyError trying to fillna() a column that doesn't
                # exist, instead of just writing zeros like it does for a
                # *partially* unreachable network. "Nobody can get anywhere" is
                # a real state the RL agent can produce (especially on small
                # networks / early random exploration), so treat it as such:
                # the code below already falls back to all-zero flow/access
                # when FLOW_COL/ACCESS_COL are missing from the layers.
                self._debug(f"betweenness() hit the zero-reachability KeyError [{time.time()-t0:.1f}s]")
            finally:
                if self._debug_enabled:
                    faulthandler.cancel_dump_traceback_later()

        street_gdf = zonal[self.STREETS].gdf
        origin_gdf = zonal[self.ORIGINS].gdf

        # If every origin is priced/routed out of every destination (e.g. a
        # "penalize" closure that pushes the whole search radius over budget,
        # or a set of closures that isolates a district), Madina's betweenness()
        # never creates these columns at all rather than filling them with
        # zeros -- so we can't just index them, we have to check first.
        flow = np.zeros(self.n_segments, dtype=float)
        if self.FLOW_COL in street_gdf.columns:
            sim_flow = street_gdf[self.FLOW_COL].fillna(0.0).to_numpy(dtype=float)
            flow[street_gdf["segment_id"].to_numpy(dtype=int)] = sim_flow

        if self.ACCESS_COL in origin_gdf.columns:
            access = origin_gdf[self.ACCESS_COL].fillna(0.0).to_numpy(dtype=float)
        else:
            access = np.zeros(len(origin_gdf), dtype=float)

        self._debug(f"flow/access extracted [{time.time()-t0:.1f}s]")
        mean_dist = self._mean_trip_distance(zonal)
        self._debug(f"_mean_trip_distance done [{time.time()-t0:.1f}s]")
        n_comp = self._count_components(zonal)
        self._debug(f"_count_components done [{time.time()-t0:.1f}s]")

        result = SimulationResult(
            segment_flow=flow,
            origin_access=access,
            mean_trip_distance=mean_dist,
            n_components=n_comp,
            unreachable_fraction=float(np.mean(access <= 0.0)),
            extra={"zonal": zonal},
        )

        if len(self._cache) >= self.cfg.simulation.cache_size:
            self._cache.clear()
        self._cache[key] = result
        return result

    def _mean_trip_distance(self, zonal) -> float:
        """Average network distance over every reachable origin-destination pair.

        Madina's `betweenness()` never returns this directly — it computes it
        internally (see `una.betweenness.one_access` / `turn_o_scope`) and
        throws it away once flow is written to the layers. Rather than turn on
        `keep_diagnostics` (extra memory, and it's a path record, not a
        distance) or approximate it from the gravity/reach score (loses the
        raw distance under the exponential decay), we replay the *same* walk
        Madina does per origin: temporarily insert the origin into `d_graph`,
        scope out to every destination within `search_radius` respecting
        `detour_ratio` and `turn_penalty`, then remove it again. This keeps the
        number consistent with whatever `simulation.*` settings produced the
        flow/access numbers above, at the cost of one extra graph walk per
        origin (cheap next to the betweenness computation itself).

        Unweighted mean across O-D pairs, mirroring `StubBackend.simulate`.
        """
        from madina.una.paths import turn_o_scope

        network = zonal.network
        node_gdf = network.nodes
        origins = node_gdf[node_gdf["type"] == "origin"].index
        if len(origins) == 0:
            return float("nan")

        sc = self.cfg.simulation
        o_graph = network.d_graph

        distances: list[float] = []
        for o_idx in origins:
            network.add_node_to_graph(o_graph, o_idx)
            d_idxs, _, _ = turn_o_scope(
                network=network,
                o_idx=o_idx,
                search_radius=sc.search_radius,
                detour_ratio=sc.detour_ratio,
                turn_penalty=sc.turn_penalty,
                o_graph=o_graph,
                return_paths=False,
            )
            network.remove_node_to_graph(o_graph, o_idx)
            distances.extend(d_idxs.values())

        return float(np.mean(distances)) if distances else float("nan")

    @staticmethod
    @contextlib.contextmanager
    def _force_single_process_betweenness():
        """Two Windows-hang workarounds for Madina's betweenness(), scoped to
        just this call via monkeypatching:

        1. ProcessPoolExecutor -> runs submitted work immediately, in this
           process, instead of spawning a worker (see the comment at the
           call site in `simulate()` for why).
        2. psutil.virtual_memory() -> reports abundant free memory, so the
           per-chunk `while low_memory: time.sleep(30)` throttle in
           betweenness_exposure() never triggers (see the comment further
           down where it's patched, for why that guard no longer applies
           once we're single-process).
        """
        import concurrent.futures
        from madina.una import betweenness as _betweenness_module

        import concurrent.futures as _cf

        class _ImmediateFuture(_cf.Future):
            def __init__(self, fn, /, *args, **kwargs):
                super().__init__()
                try:
                    self.set_result(fn(*args, **kwargs))
                except Exception as exc:  # noqa: BLE001 - surfaced via Future.result()/.exception()
                    self.set_exception(exc)

        class _ImmediateExecutor:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def submit(self, fn, /, *args, **kwargs):
                return _ImmediateFuture(fn, *args, **kwargs)

        original_executor = _betweenness_module.concurrent.futures.ProcessPoolExecutor
        _betweenness_module.concurrent.futures.ProcessPoolExecutor = _ImmediateExecutor

        # Madina's per-origin worker loop also throttles itself: before each
        # destination chunk it checks psutil.virtual_memory() and sleeps in a
        # loop (no output at all -- looks exactly like a hang) until at least
        # 2.4GB and 15% of system RAM are free. That guard exists so several
        # parallel worker *processes* on a shared machine don't all pile up
        # and OOM it at once. We no longer have parallel workers (see above),
        # so it's just extra, unnecessary latency here -- confirmed via
        # faulthandler that this exact wait loop (betweenness.py's
        # `while ... time.sleep(30)`) was where a real run sat stuck on a
        # modest laptop. Report abundant memory so it never triggers.
        import collections

        _FakeVirtualMemory = collections.namedtuple(
            "_FakeVirtualMemory", ["total", "available", "percent", "used", "free"]
        )
        original_virtual_memory = _betweenness_module.psutil.virtual_memory
        _betweenness_module.psutil.virtual_memory = lambda: _FakeVirtualMemory(
            total=32 * 1024**3, available=32 * 1024**3, percent=1.0, used=0, free=32 * 1024**3
        )

        try:
            yield
        finally:
            _betweenness_module.concurrent.futures.ProcessPoolExecutor = original_executor
            _betweenness_module.psutil.virtual_memory = original_virtual_memory

    @staticmethod
    def _count_components(zonal) -> int:
        import networkx as nx

        graph = zonal.network.light_graph or zonal.network.d_graph
        return nx.number_connected_components(graph) if graph is not None else 1

    def is_connected(self, closed_mask: np.ndarray) -> bool:
        """Cheap connectivity check on the segment graph, without rebuilding Madina."""
        import networkx as nx

        if not hasattr(self, "_topology"):
            self._topology = self._build_topology()
        g = self._topology.copy()
        g.remove_edges_from(
            [(u, v) for (u, v, k) in self._edge_keys if closed_mask[k]]
        )
        g.remove_nodes_from(list(nx.isolates(g)))
        return g.number_of_nodes() > 0 and nx.is_connected(g)

    def _build_topology(self):
        """Node-and-edge graph derived from segment endpoints (rounded to the
        snapping tolerance) — used only for fast connectivity tests."""
        import networkx as nx
        from shapely.geometry import LineString, MultiLineString

        tol = max(self.cfg.network.node_snapping_tolerance, 1e-6)

        def snap(pt):
            return (round(pt[0] / tol) * tol, round(pt[1] / tol) * tol)

        g = nx.Graph()
        self._edge_keys = []
        for k, geom in enumerate(self._base_streets.geometry):
            if isinstance(geom, MultiLineString):
                geom = LineString([c for part in geom.geoms for c in part.coords])
            u, v = snap(geom.coords[0]), snap(geom.coords[-1])
            g.add_edge(u, v)
            self._edge_keys.append((u, v, k))
        return g
