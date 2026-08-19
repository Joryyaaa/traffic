# zone_builder restricted zone-size ablation — results

**Question:** what return does `zone_builder` get when the zone it's allowed to build is
restricted to N segments, for N = 1..9, under both reward settings currently in use
(`min_zone_size=4`, the original control/GAT-LONG; and `min_zone_size=1`, CREDIT/COMBINED)?

**Validation:** the +0.6863 reference was reproduced exactly (0.0000 difference) before any
ablation was run — see `INSPECTION.md`. All 16 automated tests pass (`tests/test_zone_builder_size_restriction.py`).

## Results

| Allowed Zone Size | Return (mzs=4) | Return (mzs=1) |
|---|---|---|
| 1 | −0.0054 | +0.0069 |
| 2 | −0.0459 | +0.0035 |
| 3 | −0.1161 | −0.0050 |
| 4 | +0.0759 | +0.0759 |
| 5 | +0.1815 | +0.1815 |
| 6 | +0.3117 | +0.3117 |
| 7 | +0.4285 | +0.4285 |
| 8 | +0.6081 | +0.6081 |
| **9** | **+0.6863** | **+0.6863** |
| **unrestricted** | **+0.6863** | **+0.6863** |

(Full per-run data, including achieved zone size and wall-clock, in `results_mzs4.csv` /
`results_mzs1.csv`.)

## Key findings

**1. +0.6863 is reproduced exactly, at size 9, under both settings.** Confirms Stage 1's
independent reproduction and shows the unrestricted zone_builder result is identical
regardless of `min_zone_size` — because the zone it actually builds (size 9) is already well
above both thresholds.

**2. Unrestricted zone_builder selects size 9** — the full `max_closures` budget, not some
smaller sweet spot. The curve is monotonically increasing from size 4 upward under both
settings, so there is no restricted size that beats the unrestricted result: **best
restricted size = 9, tied with unrestricted, for both mzs=4 and mzs=1.** The hand-coded
planner's own optimum (within what it can search) is to use its whole budget.

**3. Sizes 4-9 are byte-identical between the two reward settings.** Once a zone reaches
size 4, it clears the `min_zone_size=4` threshold too, so the mzs=4 and mzs=1 rewards
compute the exact same `zone_score` from size 4 on — the two curves only diverge below the
mzs=4 threshold. This is a clean, direct illustration of what `min_zone_size` actually
controls (see INSPECTION.md's distinction from zone-size restriction).

**4. Sizes 1-3 show the "delayed-reward cliff" directly, and CREDIT's hypothesis confirmed
in isolation.** Under mzs=4, sizes 1-3 all score negative and get *more* negative as the
zone grows (−0.0054 → −0.0459 → **−0.1161** at size 3) — the agent is paying increasing
accessibility/detour cost for a zone that earns exactly zero pedestrian-zone bonus, because
it hasn't reached the threshold yet. Under mzs=1, the same sizes are roughly flat around
zero (+0.0069, +0.0035, −0.0050) — the zone bonus activates immediately, largely offsetting
the cost at every size. **This is CREDIT's exact hypothesis, demonstrated directly on the
deterministic planner, independent of any RL training or seed variance**: `min_zone_size=4`
manufactures a strictly worse-the-longer-you-commit region for the first 3 segments that
`min_zone_size=1` does not have.

## Fair zone_builder reference for each RL experiment

| RL experiment | min_zone_size | Fair zone_builder reference |
|---|---|---|
| Original GAT control (34f03c8) | 4 | **+0.6863** (unchanged — already the correct comparison) |
| GAT-LONG (25f968a) | 4 | **+0.6863** (unchanged) |
| CREDIT (115220e) | 1 | **+0.6863** (same value — confirmed here, not assumed) |
| COMBINED (in progress) | 1 | **+0.6863** (same value) |

**The +0.6863 bar turns out to already be the fair reference for both reward settings** —
this ablation doesn't produce a *different* number to re-quote CREDIT/COMBINED against, it
*confirms* the existing one is valid for both, because the unrestricted zone (size 9) sits
well clear of where the two curves diverge (sizes 1-3). The brief's concern (comparing a
mzs=1 treatment against a stale mzs=4 threshold) turns out not to bite at the unrestricted
comparison point — CREDIT's own `RESULTS.md` caveat about this can be resolved: **0/5 vs.
5/5 seeds beating +0.6863 is a valid, apples-to-apples comparison for both mzs=4 and mzs=1
runs.** It would only need revisiting if a future experiment reported returns evaluated at
a *restricted* zone size rather than the unrestricted budget every RL experiment in this
lineage actually uses.

## Files in this package

- `INSPECTION.md` — Stage 1: how zone_builder actually works, how +0.6863 was produced, why
  a restriction needed new code (not an existing parameter)
- `DESIGN.md` — Stage 2: exact implementation design and size-range justification
- `results_mzs4.csv`, `results_mzs1.csv` — Stage 5: raw per-size results (return, achieved
  zone size, segments closed, wall-clock)
- `SUMMARY.md` — this file
- `../../tests/test_zone_builder_size_restriction.py` — Stage 3: 16 tests, all passing
- `../../scripts/zone_builder_size_ablation.py` — Stage 4: the harness that produced the CSVs
- `../../scripts/plot_zone_builder_size_ablation.py` — plotting script (see note below)

## Note: plot not generated in this environment

`scripts/plot_zone_builder_size_ablation.py` is written and reads the two CSVs correctly,
but `matplotlib`'s `fig.savefig()` crashes (exit 127, no Python traceback — a native-level
crash, isolated by hand to specifically the save step, not import/figure-construction) in
this Windows conda environment, for both PNG and SVG output. This reproduces on a *minimal*
2-point matplotlib smoke test unrelated to this ablation's code, so it's an environment
issue (likely a native library conflict), not a bug in the plotting script. The full curve
data needed for a plot is in the table above and the two CSVs; regenerating the image on a
machine where matplotlib's Agg backend saves cleanly (e.g. Ibex) should work without changes.
