# Design: optional zone-size restriction for zone_builder

## What "restricting zone size" means here (and what it does NOT mean)

Per the mentor's question, restricted here means: **cap how large a connected group of
qualifying segments `zone_builder` is allowed to grow to**, using the exact same "zone
size" definition the reward itself uses (`src/snrl/metrics.py::zone_score`'s
`effective_size`: count of *qualifying* segments in a connected component of closed
segments).

This is explicitly **not** `min_zone_size` (reward-activation threshold, unaffected by
this change) and **not** `max_closures` (global per-episode closure budget shared by every
policy — this ablation does not touch it or any config file).

## Implementation

Added directly to `scripts/evaluate.py` (the file that already owns `zone_builder_policy`
and produced the +0.6863 reference — no new module, no duplication):

```python
def _closed_group_size(closed_mask, adjacency, qualifying_mask):
    """Effective (qualifying) size of the connected group of closed segments.
    zone_builder only ever grows one cluster, so any closed segment identifies it."""
    ...  # BFS/flood-fill over `adjacency`, restricted to closed_mask; counts
         # qualifying members exactly like metrics.zone_score does


def zone_builder_policy(env, max_zone_size: int | None = None):
    """... unchanged docstring, plus:

    max_zone_size (optional): caps the connected group's qualifying size (same
    definition as metrics.zone_score) this policy will grow to. Once the current
    group reaches max_zone_size, returns no-op for the rest of the episode instead
    of extending further -- independent of env.action_masks()/max_closures. This is
    a POLICY-level restriction, not an environment one: no config file, no env.py,
    no reward code is touched.

    None (default) is byte-for-byte the original behavior -- this parameter is
    additive only.
    """
    def choose(env, obs):
        qualifying_mask = env.reward_fn._qualifying_mask
        closed = np.flatnonzero(env.closed_mask)

        if max_zone_size is not None and closed.size > 0:
            current_size = _closed_group_size(env.closed_mask, env._adjacency, qualifying_mask)
            if current_size >= max_zone_size:
                return env.n_segments  # restriction reached -- no-op, stop extending

        # ... rest of the function body IS THE ORIGINAL, UNCHANGED CODE ...
    return choose
```

The restriction check sits *before* the original selection logic and only ever early-returns
a no-op; when `max_zone_size is None` it never triggers, so the function's existing code path
is reached exactly as before, unmodified. `zone_builder_best_policy` is **not** touched — the
mentor's question is about `zone_builder` (the +0.6863 producer) specifically, and touching
the exhaustive-seed variant too would multiply runtime for a question that wasn't asked in
this round.

## Why the size check happens on the CURRENT group (before choosing the next action), not on a hypothetical "next" group

Simpler and exactly matches the intended semantics: once the group has reached
`max_zone_size`, stop — the *final* group size is then exactly `max_zone_size` (assuming
the network lets zone_builder reach it at all, i.e. `max_zone_size <= max_closures` and
enough adjacent qualifying segments exist — both true here, see INSPECTION.md). The very
first closure (seeding, when nothing is closed yet) is never blocked by this check
(`closed.size > 0` guards it) — a `max_zone_size >= 1` always gets to place its first
segment, which is the only sensible floor (there is no such thing as a zero-segment zone).

## Tested sizes: 1 through 9, no gaps

Derived from INSPECTION.md's empirical finding, not chosen arbitrarily: **unrestricted
zone_builder on this exact config closes exactly 9 segments** (`max_closures=9`, and the
network has enough adjacent qualifying segments to reach that budget — confirmed, not
assumed). So:

- `max_zone_size=9` is mechanically identical to unrestricted (the budget was already the
  binding constraint) — included as the built-in cross-check that the restriction code path
  reduces to the original behavior at the boundary.
- Sizes above 9 are unreachable under this config regardless of the restriction value —
  testing e.g. 10 (the prompt's own illustrative example) would return byte-identical
  results to size 9 and add nothing.
- 1-9 with no gaps requires only 9 evaluation calls (cheap — `zone_builder` alone took 24s
  per call in Stage 1, not the ~728s `zone_builder_best` did), so there is no cost reason to
  skip any value in between, and no gap needs justifying.

This range already includes every category the brief asked for: very small (1, 2), the
`min_zone_size=4` vicinity (3, 4, 5), moderate (6, 7, 8), and the unrestricted reference (9,
plus explicit `max_zone_size=None` run as a direct check against Stage 1's +0.6863).

## Two reward settings: min_zone_size=4 AND min_zone_size=1 — both valid, both run

Both `configs/city_madina_ablation_r400_gat.yaml` (mzs=4) and
`configs/city_madina_ablation_r400_gat_mzs1.yaml` (mzs=1) exist already, are byte-identical
to each other except `reward.min_zone_size` (confirmed in
`results/combined_gat_credit_long/PARITY_INSPECTION.md`, re-confirmed here), and both
already carry `include_adjacency_state`/network/action settings identical to each other.
`zone_builder_policy`'s restriction argument is completely orthogonal to which config it
runs against — no reason not to run both curves, exactly as the mentor's original results
(CREDIT vs. the original control) differ only in this same field. This gives two curves:
`min_zone_size=4` (fair reference for the original GAT control and GAT-LONG, both mzs=4) and
`min_zone_size=1` (fair reference for CREDIT and the in-progress COMBINED experiment, both
mzs=1) — resolving exactly the stale-threshold problem the brief flagged.
