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
from types import MethodType

import numpy as np

from .base import FlowBackend, SimulationResult

# Set on the parent just before a fork pool is created, so forked workers
# inherit the backend (and its topology) copy-on-write instead of pickling it.
# Module level because pool.map needs a picklable top-level callable.
_MASK_WORKER_BACKEND = None


def _connectivity_chunk_worker(args):
    closed_mask, chunk = args
    return _MASK_WORKER_BACKEND._connectivity_mask_serial(closed_mask, chunk)


def _connected_ignoring_isolates(g) -> bool:
    """Is the graph connected once isolated nodes are disregarded?

    Exactly the predicate MadinaBackend.is_connected() applies: it drops
    isolated nodes and then requires the remainder to be non-empty and
    connected. Phrased as an induced subgraph on the positive-degree nodes so
    it needs no mutation, which is what makes the batched path able to reuse
    one graph across candidates.
    """
    import networkx as nx

    live = [n for n, d in g.degree() if d > 0]
    if not live:
        return False
    return nx.is_connected(g.subgraph(live))


def _read_geojson(path):
    """Read a .geojson file into a GeoDataFrame.

    Prefers `geopandas.read_file` (pyogrio/GDAL). Falls back to a plain
    json+shapely reader when pyogrio's bundled GDAL binary can't load at all
    -- confirmed on at least one dev machine where an OS-level Application
    Control policy blocks that specific DLL (not a "pyogrio isn't installed"
    case, an "installed but the DLL won't load" case, which geopandas doesn't
    itself fall back from). GeoJSON is plain JSON, so OGR was never
    load-bearing for *this* format -- only reprojection/other formats
    actually need GDAL, and reprojection already happens separately via
    `.to_crs()` on the returned GeoDataFrame.
    """
    import geopandas as gpd

    try:
        return gpd.read_file(path)
    except ImportError:
        pass

    import json

    import pandas as pd
    from shapely.geometry import shape

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    features = data["features"]
    geoms = [shape(f["geometry"]) for f in features]
    props = pd.DataFrame([f.get("properties") or {} for f in features])
    crs = "EPSG:4326"
    crs_name = (data.get("crs") or {}).get("properties", {}).get("name", "")
    if crs_name and "CRS84" not in crs_name and "4326" not in crs_name:
        crs = crs_name
    return gpd.GeoDataFrame(props, geometry=geoms, crs=crs)


def _rebuild_directed_edge(network, graph, edge_id: int) -> None:
    """Rebuild one street chain while preserving its allowed directions."""
    edge_id = int(edge_id)
    edge = network.edges.loc[edge_id]
    start, end = int(edge["start"]), int(edge["end"])
    forward_cost, reverse_cost = network._snrl_direction_costs[edge_id]

    for u, v, data in list(graph.edges(data=True)):
        if data.get("id") == edge_id:
            graph.remove_edge(u, v)

    added = set(graph.graph.get("added_nodes", []))
    nodes = network.nodes
    inserted = [
        int(idx)
        for idx in added
        if int(nodes.at[idx, "nearest_edge_id"]) == edge_id
    ]
    total = max(float(edge["weight"]), 1e-12)
    positions = {idx: float(nodes.at[idx, "weight_to_start"]) / total for idx in inserted}
    inserted.sort(key=positions.__getitem__)
    chain = [start, *inserted, end]
    fractions = [0.0, *(positions[idx] for idx in inserted), 1.0]

    def add_chain(cost: float, reverse: bool) -> None:
        pairs = list(zip(chain[:-1], chain[1:], fractions[:-1], fractions[1:]))
        if reverse:
            pairs = [(v, u, left, right) for u, v, left, right in reversed(pairs)]
        for u, v, left, right in pairs:
            graph.add_edge(
                int(u), int(v), weight=max((right - left) * cost, 0.0), id=edge_id
            )

    if forward_cost is not None:
        add_chain(float(forward_cost), reverse=False)
    if reverse_cost is not None:
        add_chain(float(reverse_cost), reverse=True)


def _directed_add_node_to_graph(network, graph, node_idx) -> None:
    node_idx = int(node_idx)
    added = graph.graph.setdefault("added_nodes", [])
    if node_idx in added:
        return
    added.append(node_idx)
    graph.add_node(node_idx)
    _rebuild_directed_edge(network, graph, int(network.nodes.at[node_idx, "nearest_edge_id"]))


def _directed_remove_node_to_graph(network, graph, node_idx) -> None:
    node_idx = int(node_idx)
    edge_id = int(network.nodes.at[node_idx, "nearest_edge_id"])
    added = graph.graph.setdefault("added_nodes", [])
    if node_idx in added:
        added.remove(node_idx)
    if node_idx in graph:
        graph.remove_node(node_idx)
    _rebuild_directed_edge(network, graph, edge_id)


def _directed_turn_o_scope(
    network,
    o_idx,
    search_radius: float,
    detour_ratio: float,
    turn_penalty=True,
    o_graph=None,
    return_paths=True,
):
    """Madina shortest-path scope without its undirected leaf shortcut."""
    from heapq import heappop, heappush

    from madina.una.paths import turn_penalty_value

    graph = o_graph if o_graph is not None else network.d_graph
    destinations = set(network.nodes[network.nodes["type"] == "destination"].index)
    scope = {o_idx: 0.0}
    destination_distances = {}
    scope_paths = {}
    queue = [(0.0, o_idx, [o_idx])]

    while queue:
        weight, node, visited = heappop(queue)
        if weight > scope.get(node, float("inf")):
            continue
        for neighbor in graph.neighbors(node):
            turn_cost = 0.0
            if turn_penalty and len(visited) >= 2:
                turn_cost = turn_penalty_value(network, visited[-2], node, neighbor)
            new_weight = weight + graph.edges[node, neighbor]["weight"] + turn_cost
            if new_weight > search_radius * detour_ratio:
                continue
            if new_weight >= scope.get(neighbor, float("inf")):
                continue
            scope[neighbor] = new_weight
            path = visited + [neighbor]
            if return_paths:
                scope_paths[neighbor] = path
            if neighbor in destinations and new_weight <= search_radius:
                destination_distances[neighbor] = new_weight
            heappush(queue, (new_weight, neighbor, path))

    return destination_distances, scope, scope_paths


def _directed_bfs_subgraph_generation(
    o_idx,
    detour_ratio=1.15,
    o_graph=None,
    d_idxs=None,
    o_scope=None,
    o_scope_paths=None,
):
    """Build destination distances by traversing a directed graph backwards."""
    import networkx as nx

    d_idxs = d_idxs or {}
    o_scope = o_scope or {}
    distance_matrix = {node: {} for node in o_scope}
    od_scope = set()
    reverse_graph = o_graph.reverse(copy=False)

    for destination, shortest in d_idxs.items():
        allowed = shortest * detour_ratio
        distances = nx.single_source_dijkstra_path_length(
            reverse_graph, destination, cutoff=allowed, weight="weight"
        )
        for node, distance in distances.items():
            if node not in o_scope:
                continue
            if o_scope[node] + distance <= allowed + 1e-7:
                distance_matrix[node][destination] = distance
                od_scope.add(node)

        shortest_path = (o_scope_paths or {}).get(destination, [])
        for node in shortest_path:
            if node in distance_matrix:
                distance_matrix[node][destination] = max(
                    float(shortest) - float(o_scope[node]), 0.0
                )
                od_scope.add(node)

    return od_scope, distance_matrix, d_idxs


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
        gdf = _read_geojson(self.cfg.network.streets_path)
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
        gdf = _read_geojson(path)
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
        if nc.respect_oneway:
            self._create_directed_graphs(zonal, streets, weight_attribute)
        else:
            zonal.create_graph()
        return zonal

    @staticmethod
    def _oneway_mode(value) -> str:
        """Normalize common OSM/GeoJSON one-way encodings."""
        if value is None:
            return "both"
        try:
            if np.isnan(value):
                return "both"
        except TypeError:
            pass
        text = str(value).strip().lower()
        if text in {"-1", "reverse", "backward"}:
            return "reverse"
        if text in {"1", "true", "yes", "y", "t"}:
            return "forward"
        return "both"

    @staticmethod
    def _physical_pair_key(row):
        """Identify opposite OSM rows belonging to one physical link."""
        if "u" in row.index and "v" in row.index:
            u, v = row["u"], row["v"]
            if not (np.isscalar(u) and np.isscalar(v)):
                u = v = None
            if u is not None and v is not None:
                try:
                    if not (np.isnan(u) or np.isnan(v)):
                        return ("osm", *sorted((int(u), int(v))))
                except TypeError:
                    return ("osm", *sorted((str(u), str(v))))
        geom = row.geometry
        a = tuple(round(float(x), 3) for x in geom.coords[0])
        b = tuple(round(float(x), 3) for x in geom.coords[-1])
        return ("geometry", *sorted((a, b)))

    @staticmethod
    def _same_orientation(row, parent) -> bool:
        if all(name in row.index for name in ("u", "v")):
            try:
                return int(row["u"]) == int(parent["u"]) and int(row["v"]) == int(parent["v"])
            except (TypeError, ValueError):
                pass
        row_start = np.asarray(row.geometry.coords[0], dtype=float)
        parent_start = np.asarray(parent.geometry.coords[0], dtype=float)
        return bool(np.linalg.norm(row_start - parent_start) <= 0.01)

    @staticmethod
    def _row_cost(row, weight_attribute: str | None) -> float:
        value = row.geometry.length if weight_attribute is None else row[weight_attribute]
        if value == 0:
            value = row.geometry.length
        return max(float(value), 0.01)

    def _direction_costs(self, network, streets, weight_attribute):
        """Recover allowed forward/reverse costs from the original OSM rows."""
        groups = {}
        for idx, row in streets.iterrows():
            groups.setdefault(self._physical_pair_key(row), []).append((idx, row))

        result = {}
        for edge_id, edge in network.edges.iterrows():
            parent = streets.loc[int(edge["parent_street_id"])]
            rows = groups[self._physical_pair_key(parent)]
            orientations = [self._same_orientation(row, parent) for _, row in rows]
            has_forward_row = any(orientations)
            has_reverse_row = any(not same for same in orientations)
            forward_costs, reverse_costs = [], []

            for (_, row), same in zip(rows, orientations):
                mode = self._oneway_mode(row.get("oneway", False))
                cost = self._row_cost(row, weight_attribute)
                if mode == "reverse":
                    same = not same
                    mode = "forward"

                both = mode == "both" and not (has_forward_row and has_reverse_row)
                if same or both:
                    forward_costs.append(cost)
                if (not same) or both:
                    reverse_costs.append(cost)

            result[int(edge_id)] = (
                min(forward_costs) if forward_costs else None,
                min(reverse_costs) if reverse_costs else None,
            )
        return result

    def _create_directed_graphs(self, zonal, streets, weight_attribute) -> None:
        """Create Madina-compatible directed graphs for drive networks."""
        import networkx as nx

        network = zonal.network
        network.street_node_ids = set(
            network.nodes[network.nodes["type"] == "street_node"].index
        )
        network._snrl_direction_costs = self._direction_costs(
            network, streets, weight_attribute
        )
        network.add_node_to_graph = MethodType(_directed_add_node_to_graph, network)
        network.remove_node_to_graph = MethodType(_directed_remove_node_to_graph, network)

        light = nx.DiGraph()
        light.graph["added_nodes"] = []
        for idx in network.street_node_ids:
            light.add_node(int(idx), type="street_node")
        network.light_graph = light
        for edge_id in network.edges.index:
            _rebuild_directed_edge(network, network.light_graph, int(edge_id))

        network.d_graph = network.light_graph.copy()
        network.d_graph.graph["added_nodes"] = []
        destinations = list(network.nodes[network.nodes["type"] == "destination"].index)
        for node_idx in destinations:
            network.add_node_to_graph(network.d_graph, int(node_idx))

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

        with self._force_single_process_betweenness(), self._directed_scope_patch():
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
        """Average network distance over every origin-destination pair,
        treating an unreachable pair as costing `search_radius` rather than
        vanishing from the average.

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

        IMPORTANT: an origin-destination pair that turn_o_scope doesn't reach
        within search_radius is NOT dropped from the average -- it's counted
        as `search_radius` (the worst distance the search still considers,
        i.e. "as bad as the edge of the search area"). Earlier this method
        just used the *reachable* pairs and silently ignored the rest, which
        meant closing streets could *lower* the reported mean_trip_distance by
        cutting a long/costly trip off entirely rather than making it longer
        -- i.e. it was possible to earn a *better* detour reward for making
        someone's destination completely unreachable, exactly the same shape
        of bug as the pedestrian_zone "free lunch" (see commit 15d2fa2).
        origin_access already correctly reflects this harm (unreachable
        origins get 0 access, pulling the mean down), but mean_trip_distance
        did not, so the two reward terms could disagree about whether cutting
        someone off was good or bad.
        """
        from madina.una.paths import turn_o_scope as undirected_turn_o_scope

        network = zonal.network
        node_gdf = network.nodes
        origins = node_gdf[node_gdf["type"] == "origin"].index
        n_destinations = int((node_gdf["type"] == "destination").sum())
        if len(origins) == 0 or n_destinations == 0:
            return float("nan")

        sc = self.cfg.simulation
        o_graph = network.d_graph
        turn_o_scope = (
            _directed_turn_o_scope if o_graph.is_directed() else undirected_turn_o_scope
        )

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
            n_missed = n_destinations - len(d_idxs)
            if n_missed > 0:
                distances.extend([float(sc.search_radius)] * n_missed)

        return float(np.mean(distances)) if distances else float("nan")

    @contextlib.contextmanager
    def _directed_scope_patch(self):
        """Use directed-compatible path helpers inside Madina betweenness."""
        if not self.cfg.network.respect_oneway:
            yield
            return

        from madina.una import betweenness as betweenness_module

        original_scope = betweenness_module.turn_o_scope
        original_subgraph = betweenness_module.bfs_subgraph_generation
        betweenness_module.turn_o_scope = _directed_turn_o_scope
        betweenness_module.bfs_subgraph_generation = _directed_bfs_subgraph_generation
        try:
            yield
        finally:
            betweenness_module.turn_o_scope = original_scope
            betweenness_module.bfs_subgraph_generation = original_subgraph

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

        # TODO(perf): this patch does NOT cover mp.Manager(), which
        # paralell_betweenness_exposure() still calls directly (for the
        # origin Queue) regardless of the ProcessPoolExecutor patch above.
        # On Windows (spawn, not fork) that still pays a real OS
        # process-spawn cost on every single simulate() call. Measured
        # 2026-08-08 on a 386-segment scenario: ~2-4s per genuinely new
        # closed-segment combination -- almost certainly dominated by this
        # spawn, not the actual betweenness computation. Also requires every
        # caller to guard top-level code with `if __name__ == "__main__":`
        # (scripts/*.py already do; ad-hoc one-off scripts easily don't, and
        # fail with a cryptic multiprocessing bootstrap RuntimeError, or hang
        # indefinitely with near-zero CPU use, if they skip that guard).
        # Worth patching mp.Manager() the same way _ImmediateExecutor patches
        # ProcessPoolExecutor above, if local Windows training throughput
        # matters again.

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
        if graph is None:
            return 1
        if graph.is_directed():
            return nx.number_weakly_connected_components(graph)
        return nx.number_connected_components(graph)

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

    # --- batched connectivity -------------------------------------------------
    #
    # env.action_masks() asks "would closing segment i disconnect the network?"
    # for every still-open segment, once per step. Answering that with
    # is_connected() per segment means one full _topology.copy() per segment:
    # measured on Abha S0 (4,586 segments, 1,729-node topology) the copies alone
    # were 18.3s of a 33.5s mask, and the whole mask was 95% of per-step cost.
    #
    # This does one copy for the whole batch and then mutates-and-restores a
    # single candidate's edges at a time, which is exactly equivalent. The
    # equivalence is not obvious and is worth spelling out, because _topology is
    # a plain nx.Graph and several segments can share one (u, v) edge:
    #
    #   * is_connected(closed | {i}) removes the edge (u, v) if ANY segment
    #     mapping to it is closed. So if candidate i shares its edge with an
    #     already-closed segment j, the edge is already absent from the base
    #     graph, `removed` comes out empty, and we test the base graph. That is
    #     the same graph is_connected() would have built.
    #   * restoring only the edges we actually removed cannot resurrect an edge
    #     that some closed segment was suppressing, for the same reason.
    #
    # That shared-edge collapse is also why single-pass bridge detection is NOT
    # a drop-in here: a bridge in _topology need not correspond to a unique
    # segment. Left as a follow-up rather than assumed equivalent.
    def _open_topology(self, closed_mask: np.ndarray):
        """`_topology` with every closed segment's edge removed. One copy."""
        if not hasattr(self, "_topology"):
            self._topology = self._build_topology()
        g = self._topology.copy()
        g.remove_edges_from(
            [(u, v) for (u, v, k) in self._edge_keys if closed_mask[k]]
        )
        return g

    def _edges_by_segment(self) -> dict:
        if not hasattr(self, "_edges_by_segment_cache"):
            if not hasattr(self, "_topology"):
                self._topology = self._build_topology()
            cache: dict = {}
            for (u, v, k) in self._edge_keys:
                cache.setdefault(k, []).append((u, v))
            self._edges_by_segment_cache = cache
        return self._edges_by_segment_cache

    def _connectivity_mask_serial(
        self, closed_mask: np.ndarray, candidates: np.ndarray
    ) -> np.ndarray:
        g = self._open_topology(closed_mask)
        by_seg = self._edges_by_segment()
        out = np.empty(len(candidates), dtype=bool)
        for i, c in enumerate(candidates):
            removed = [e for e in by_seg.get(int(c), []) if g.has_edge(*e)]
            g.remove_edges_from(removed)
            out[i] = _connected_ignoring_isolates(g)
            g.add_edges_from(removed)
        return out

    def connectivity_mask(
        self,
        closed_mask: np.ndarray,
        candidates: np.ndarray,
        n_workers: int = 1,
    ) -> np.ndarray:
        candidates = np.asarray(candidates, dtype=int)
        if candidates.size == 0:
            return np.zeros(0, dtype=bool)

        n_workers = int(n_workers or 1)
        if n_workers <= 1 or candidates.size < 2:
            return self._connectivity_mask_serial(closed_mask, candidates)

        # fork so the topology is shared copy-on-write instead of pickled per
        # worker. Each worker makes one base copy for its whole chunk.
        import multiprocessing as mp

        n_workers = min(n_workers, candidates.size)
        chunks = [c for c in np.array_split(candidates, n_workers) if c.size]
        global _MASK_WORKER_BACKEND
        _MASK_WORKER_BACKEND = self
        try:
            ctx = mp.get_context("fork")
            with ctx.Pool(len(chunks)) as pool:
                parts = pool.map(
                    _connectivity_chunk_worker,
                    [(closed_mask, c) for c in chunks],
                )
        except (OSError, ValueError, ImportError, RuntimeError):
            # no fork (or no process room): the serial path is equivalent, just
            # slower, so degrade rather than fail a multi-hour job.
            return self._connectivity_mask_serial(closed_mask, candidates)
        return np.concatenate(parts)

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
