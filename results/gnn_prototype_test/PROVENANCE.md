# GNN-prototype single-seed test -- prep only, not run

**Date:** 2026-08-10
**Status:** config + Slurm job ready. **No training run anywhere yet** (not locally, not on
Ibex). This is prep for the mentor to pick up when free -- not urgent for tomorrow.

## Why 89 segments

The completed 5-point network-size sweep (`results/README.md`, "Network-size sweep" section)
found three regimes, not a smooth decay:

| segments | mean | std | max | planner | >= planner |
|---|---|---|---|---|---|
| 26 | +0.2595 | 0.0636 | +0.3323 | +0.2661 | 2/3 |
| **89** | **+0.2631** | **0.3886** | **+0.8125** | **+0.6863** | **1/3** |
| 186 | -0.0470 | 0.0025 | -0.0437 | +0.6190 | 0/3 |
| 226 | +0.0044 | 0.0245 | +0.0238 | +0.3297 | 0/3 |
| 386 | -0.0280 | 0.0213 | +0.0018 | +0.2878 | 0/3 |

89 segments is the last size where the MLP policy *can* reach planner-class performance --
one of three seeds got there (+0.8125 vs the +0.6863 planner bar) -- but does so unreliably (std
6x the 26-segment size, at a nearly identical mean). Above 89, the MLP result is flat and
uniformly negative regardless of seed. That makes 89 the size where an architecture change
(GNN's inductive bias over the segment-adjacency graph, instead of a flat per-segment MLP) has
the most obvious null-hypothesis-breaking signal to find: does it turn the bimodal 1-of-3 into a
reliable win, or does it land in the same place the MLP already does?

This is explicitly a smoke-scale test, not a claim: **n=1 seed**, no GNN baseline run at any
other size yet, and no comparison against the MLP's *specific* winning seed's actual closure
pattern (only its return). Treat a single number here as "worth a real sweep or not", nothing
stronger.

## What's confirmed, and what isn't

Confirmed locally (2026-08-08/2026-08-10, this is real, not assumed):

- `src/snrl/gnn.py` + `scripts/train_gnn.py` train, save, and `scripts/evaluate.py` loads the
  saved model back and runs it, without error, on `configs/hard.yaml` (stub backend) and
  `configs/city_madina_ablation.yaml` (26-segment, madina backend).
- **Not** run at 89 segments for a real (30k+) step count anywhere. A 2048-step calibration
  probe on `configs/city_madina_ablation_r400.yaml`, isolated (no other process competing for
  CPU), measured **1.35s/step**. That puts a 30,000-step run at ~11.3 hours and 50,000 at ~18.8
  hours on this machine -- not a "quick local test" by any reasonable reading, so nothing longer
  than the 2048-step calibration was run locally. Compare to the mentor's own 89-segment *MLP*
  run: 2.02h for 167,000 steps (~0.0436s/step) on Ibex, ~30x faster per step. Almost certainly
  the `mp.Manager()`-per-`simulate()`-call cost flagged as a TODO in
  `src/snrl/backends/madina_backend.py` (Windows spawn overhead, not present the same way under
  Linux fork) -- this has nothing to do with the GNN extractor itself, the same ~30x gap showed
  up on the plain-MLP 386-segment scenario prep too (`results/scale_sweep_prep/PROVENANCE.md`).

## To run

```bash
cd /home/shiekhmf/Student_Projects/Jory/traffic
sbatch slurm/gnn_prototype_test.sbatch
```

Defaults: `configs/city_madina_ablation_r400.yaml`, 30,000 steps, seed 1. Override with
`--export=ALL,TIMESTEPS=50000` for the longer end of the requested 30k-50k range, or
`--export=ALL,SEED=<n>` for a different seed. Expected wall-clock: roughly 15-25 minutes at
30k steps, extrapolating from the mentor's own 89-segment MLP rate -- the GNN forward pass adds
negligible overhead (`notes/2026-08-06-street-duplication.md` section 8 measured the policy
network at 1.2-0.18% of per-step runtime for the plain MLP; the GCN extractor is a similarly
small network, two graph-conv layers over an 89x89 adjacency, so the same order of overhead is
expected, not verified).

## What to read off the result

The job prints an `evaluate.py` table ending in an `rl_agent` row. Compare that single number
against:

- `zone_builder = +0.6863` (the planner bar for this size)
- the MLP seed-sweep distribution at 89 segments: mean +0.2631, best +0.8125, 1/3 seeds >=
  planner (`results/README.md`)

A GNN result clearly above +0.8125 (the MLP's best seed) on the *first* seed tried would be
worth a real multi-seed GNN sweep at this size. A result in the MLP's usual range (near 0, or
matching the +0.8125-class outcome by chance) is not evidence either way with n=1 -- it would
say "run more seeds," not "GNN doesn't help."
