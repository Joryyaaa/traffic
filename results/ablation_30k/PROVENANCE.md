# Provenance

**Scenario:** Al Nakheel, north Riyadh, r=250m (`configs/city_madina_ablation.yaml`)
**Data:** `data/raw/riyadh_ablation`, fetched 2026-08-06, **deduplicated** street layer
(26 real centerlines; the pre-fix layer had 52 rows because osmnx returns each street
in both directions). See `notes/2026-08-06-street-duplication.md`.

## Read these numbers with the following caveat

The street-duplication fix landed *before* this sweep, so closures are physically
effective here. But the **reward weights have not been re-tuned since**, and they were
originally chosen while four of the six reward terms were structurally ~0 (because
closures were inert). Measured baselines on this exact data:

| policy | return |
|---|---|
| greedy (does nothing) | **0.0000** |
| lowest_flow | -0.0167 |
| highest_flow | -0.3565 |
| zone_builder | -0.4586 |
| random | -0.8977 |

Doing nothing is the best available baseline. The cause is in `rewards.py:rel()`,
which divides a delta by the *baseline* level: baseline `access_gini` here is 0.0576,
so a Gini change is amplified ~17x. Closing 3 qualifying streets moves Gini
0.0576 -> 0.6240, giving an equity term of -2.95 against a maximum zone bonus of +1.00.

**So this sweep characterizes the seed-to-seed distribution of MaskablePPO under a
reward that currently prefers inaction.** The interesting question it answers is
whether PPO converges to ~0.0 (learns to do nothing, matching greedy) or finds
something positive. It is NOT a measurement of the intended
"greedy fails / planning wins" claim, which cannot hold while zone_builder is negative.

Success threshold for `scripts/aggregate_sweep.py` should therefore be **0.0**
(beat doing nothing), not the 0.9 default and not zone_builder's return.

## Collect with

    python scripts/aggregate_sweep.py --root <this dir> --expect <seed range> --success-threshold 0.0
