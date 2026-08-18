"""Tests for the optional max_zone_size restriction on zone_builder_policy
(scripts/evaluate.py). Run with: pytest -q tests/test_zone_builder_size_restriction.py

Two tiers:
- Fast, stub-backend tests (no geopandas/madina needed) for the mechanical
  properties: size cap respected, connectivity respected, determinism.
- Real-data tests against the actual r400 GAT config, guarded with an explicit
  skip (not a failure) when data/raw/riyadh_r400 isn't present in this
  checkout -- it's gitignored, so a fresh clone/worktree won't have it. These
  are the tests that matter for "did we actually reproduce +0.6863" and
  "is reward evaluation identical to the unrestricted baseline at the natural
  boundary" -- a synthetic stub network can't stand in for that.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from snrl import EnvConfig, StreetNetworkEnv, load_config  # noqa: E402
from evaluate import _closed_group_size, run_policy, zone_builder_policy  # noqa: E402

R400_GAT_CONFIG = Path(__file__).resolve().parents[1] / "configs" / "city_madina_ablation_r400_gat.yaml"
R400_DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "riyadh_r400"
KNOWN_UNRESTRICTED_RETURN = 0.6863
KNOWN_UNRESTRICTED_SIZE = 9  # from Stage 1 INSPECTION.md, empirically confirmed


def _is_connected(segment_ids, adjacency) -> bool:
    """True if every segment in `segment_ids` is reachable from the first one
    using only edges within `segment_ids` itself."""
    segment_ids = list(segment_ids)
    if len(segment_ids) <= 1:
        return True
    remaining = set(segment_ids)
    start = segment_ids[0]
    seen = {start}
    stack = [start]
    remaining.discard(start)
    while stack:
        u = stack.pop()
        for v in list(remaining):
            if adjacency[u][v]:
                seen.add(v)
                stack.append(v)
                remaining.discard(v)
    return not remaining


@pytest.fixture
def stub_env():
    """A synthetic network big enough (8x8 lattice) that zone_builder can grow
    a group well past any of the small sizes tested below, with the
    pedestrian-zone bonus active so there's something for the restriction to
    meaningfully cut off."""
    cfg = EnvConfig()
    cfg.network.stub_grid_size = 8
    cfg.action.episode_length = 15
    cfg.action.max_closures = 12
    cfg.action.allow_reopen = False
    cfg.reward.w_pedestrian_zone = 1.0
    cfg.reward.min_zone_size = 1
    cfg.reward.zone_exponent = 2.0
    e = StreetNetworkEnv(cfg)
    yield e
    e.close()


class TestSizeCapRespected:
    """Property 2: size=N never selects more than N (qualifying) segments."""

    @pytest.mark.parametrize("n", [1, 2, 3, 5, 8])
    def test_final_group_never_exceeds_n(self, stub_env, n):
        choose = zone_builder_policy(stub_env, max_zone_size=n)
        run_policy(stub_env, choose, seed=1)
        qualifying_mask = stub_env.reward_fn._qualifying_mask
        final_size = _closed_group_size(stub_env.closed_mask, stub_env._adjacency, qualifying_mask)
        assert final_size <= n, f"max_zone_size={n} but final group size was {final_size}"

    def test_larger_cap_grows_at_least_as_big_as_smaller_cap(self, stub_env):
        # Not a strict inequality requirement in general (network topology could
        # make two caps coincide), but a smaller cap must never produce a
        # STRICTLY larger group than a larger cap on the same seed/env.
        sizes = {}
        for n in (1, 3, 6):
            env = StreetNetworkEnv(stub_env.cfg)
            choose = zone_builder_policy(env, max_zone_size=n)
            run_policy(env, choose, seed=1)
            qualifying_mask = env.reward_fn._qualifying_mask
            sizes[n] = _closed_group_size(env.closed_mask, env._adjacency, qualifying_mask)
            env.close()
        assert sizes[1] <= sizes[3] <= sizes[6]


class TestConnectivityRespected:
    """Property 3: the restriction never breaks zone_builder's single-cluster
    invariant -- the closed set stays one connected component."""

    @pytest.mark.parametrize("n", [1, 2, 4, 7])
    def test_closed_set_is_one_connected_component(self, stub_env, n):
        choose = zone_builder_policy(stub_env, max_zone_size=n)
        run_policy(stub_env, choose, seed=1)
        closed = np.flatnonzero(stub_env.closed_mask)
        assert _is_connected(closed, stub_env._adjacency)


class TestDeterminism:
    """Property 5: still deterministic (it was before -- no rng anywhere in
    zone_builder_policy or the added restriction code)."""

    def test_same_config_same_cap_same_result(self):
        results = []
        for _ in range(2):
            cfg = EnvConfig()
            cfg.network.stub_grid_size = 8
            cfg.action.episode_length = 15
            cfg.action.max_closures = 12
            cfg.reward.w_pedestrian_zone = 1.0
            cfg.reward.min_zone_size = 1
            env = StreetNetworkEnv(cfg)
            choose = zone_builder_policy(env, max_zone_size=4)
            total, _ = run_policy(env, choose, seed=7)
            results.append(total)
            env.close()
        assert results[0] == results[1]


class TestUnrestrictedUnchanged:
    """Property 1: max_zone_size=None (the default, and the only value every
    prior caller including zone_builder_best_policy ever passed) reproduces
    the original, pre-restriction behavior exactly."""

    def test_default_matches_explicit_none(self, stub_env):
        env_a, env_b = stub_env, StreetNetworkEnv(stub_env.cfg)
        choose_default = zone_builder_policy(env_a)          # no max_zone_size arg at all
        choose_explicit = zone_builder_policy(env_b, max_zone_size=None)
        total_a, _ = run_policy(env_a, choose_default, seed=3)
        total_b, _ = run_policy(env_b, choose_explicit, seed=3)
        env_b.close()
        assert total_a == total_b

    def test_unrestricted_never_stops_early_from_the_cap_check(self, stub_env):
        # With max_zone_size=None, the new "if max_zone_size is not None"
        # branch must never fire -- final group size should equal whatever
        # max_closures allows (12 here), same as pre-existing behavior.
        choose = zone_builder_policy(stub_env)  # unrestricted
        run_policy(stub_env, choose, seed=1)
        assert int(stub_env.closed_mask.sum()) == stub_env.cfg.action.max_closures


# ---------------------------------------------------------------------------
# Real-data tests: the actual r400 GAT config. Skipped, not failed, if the
# (gitignored) data isn't present in this checkout.
# ---------------------------------------------------------------------------

_r400_available = R400_DATA.exists() and all(
    (R400_DATA / f).exists() for f in ("streets.geojson", "residential.geojson", "amenities.geojson")
)
requires_r400 = pytest.mark.skipif(
    not _r400_available,
    reason="data/raw/riyadh_r400 not present in this checkout (gitignored) -- "
           "copy/symlink it from an existing checkout to run this test",
)


@requires_r400
class TestReproducesKnownReference:
    """Property 6: the original +0.6863 reference is still reproducible."""

    def test_reproduces_0_6863(self):
        pytest.importorskip("geopandas")
        pytest.importorskip("madina")
        cfg = load_config(R400_GAT_CONFIG)
        env = StreetNetworkEnv(cfg)
        choose = zone_builder_policy(env)  # unrestricted -- must match the historical run
        total, _ = run_policy(env, choose, seed=cfg.seed)
        env.close()
        assert abs(total - KNOWN_UNRESTRICTED_RETURN) < 1e-3, (
            f"expected ~{KNOWN_UNRESTRICTED_RETURN}, got {total}"
        )

    def test_unrestricted_closes_exactly_9_qualifying_segments(self):
        pytest.importorskip("geopandas")
        pytest.importorskip("madina")
        cfg = load_config(R400_GAT_CONFIG)
        env = StreetNetworkEnv(cfg)
        choose = zone_builder_policy(env)
        run_policy(env, choose, seed=cfg.seed)
        qualifying_mask = env.reward_fn._qualifying_mask
        size = _closed_group_size(env.closed_mask, env._adjacency, qualifying_mask)
        env.close()
        assert size == KNOWN_UNRESTRICTED_SIZE


@requires_r400
class TestRewardIdenticalExceptRestriction:
    """Property 4: reward evaluation is identical to the unrestricted baseline
    when the cap is set at the natural unrestricted boundary (9) -- proves the
    restriction mechanism itself changes nothing else about how the reward is
    computed."""

    def test_cap_at_natural_boundary_matches_unrestricted_exactly(self):
        pytest.importorskip("geopandas")
        pytest.importorskip("madina")
        cfg = load_config(R400_GAT_CONFIG)

        env_unrestricted = StreetNetworkEnv(cfg)
        total_unrestricted, _ = run_policy(
            env_unrestricted, zone_builder_policy(env_unrestricted), seed=cfg.seed
        )
        env_unrestricted.close()

        env_capped = StreetNetworkEnv(cfg)
        total_capped, _ = run_policy(
            env_capped, zone_builder_policy(env_capped, max_zone_size=KNOWN_UNRESTRICTED_SIZE),
            seed=cfg.seed,
        )
        env_capped.close()

        # Not exact equality: two separately-constructed StreetNetworkEnv/Madina
        # Zonal instances can differ at the last bit of float64 (~1e-16) from
        # summation-order noise across ~9 simulate() calls -- confirmed by hand
        # (0.6862726039007933 vs ...34) to be float noise, not a behavioral
        # difference. 1e-9 is far tighter than any real semantic gap could hide
        # within, while comfortably absorbing that noise.
        assert abs(total_capped - total_unrestricted) < 1e-9, (
            f"{total_capped} vs {total_unrestricted}"
        )
