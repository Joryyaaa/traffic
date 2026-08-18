# Credit-Assignment Ablation (min_zone_size)

## Hypothesis

The GAT agent's poor performance at 30k steps may be caused by delayed
credit assignment rather than model capacity. With `min_zone_size=4`, the
first 3 closures of a pedestrian zone earn zero `zone_score` reward while
already paying accessibility and detour costs. The agent must take 3
unrewarded actions before any payoff appears — a severe exploration
challenge at a 30k-step budget. If this delayed-reward cliff is the
bottleneck, lowering `min_zone_size` to 1 (immediate reward for every
closure) should substantially improve learning.

## Design

| | Control (completed) | Treatment (this experiment) |
|---|---|---|
| **Config** | `r400_gat.yaml` | `r400_gat_mzs1.yaml` |
| **min_zone_size** | **4** | **1** |
| **Observation** | 7 features (adjacency-aware) | same |
| **Extractor** | GATFeaturesExtractor (4 heads, 32-dim) | same |
| **Algorithm** | MaskablePPO | same |
| **Network** | Al Nakheel r=400m, 89 segments | same |
| **max_closures** | 9 | same |
| **episode_length** | 22 | same |
| **All reward weights** | unchanged | same |
| **zone_exponent** | 2.0 | same |
| **zone_min_flow_fraction** | 0.1 | same |
| **Training** | 30,000 timesteps | same |
| **Seeds** | 1, 2, 3, 4, 5 | same |
| **Eval** | 1 deterministic episode | same |

The ONLY difference is `min_zone_size`: 4 → 1.

## What min_zone_size controls

`zone_score` (in `src/snrl/metrics.py`) finds connected components of closed
segments. A component contributes `effective_size ** zone_exponent` to the
reward — but ONLY if `effective_size >= min_zone_size`. With `min_zone_size=4`,
a group of 3 closed segments scores 0. With `min_zone_size=1`, every closed
segment immediately scores `1 ** 2.0 = 1.0` (growing superlinearly as the
group expands: 2→4, 3→9, 4→16, ...).

This changes when the agent receives its first non-zero pedestrian_zone
reward signal, not how large the signal eventually becomes for big zones.

## Completed results (control)

GAT, min_zone_size=4:
- Mean: -0.0322, Std: 0.0060

MLP + adjacency, min_zone_size=4:
- Mean: -0.0529, Std: 0.0154

MLP baseline, min_zone_size=4:
- Mean: -0.0733, Std: 0.0151

zone_builder, min_zone_size=4:
- +0.6863

## Important note on zone_builder reference

The zone_builder reference of +0.6863 was measured with min_zone_size=4.
The zone_builder return with min_zone_size=1 will be DIFFERENT (likely higher,
since every closure immediately contributes). To properly evaluate the
treatment arm, re-run zone_builder with min_zone_size=1 on Ibex.

## Slurm submission

```bash
cd /home/alblueja/traffic
git checkout credit-assignment-ablation
git pull

sbatch --array=1-5 slurm/credit_assignment_ablation.sbatch
```

## Aggregation

```bash
python scripts/aggregate_sweep.py --root runs/r400_gat_mzs1_30k \
    --success-threshold 0.6863 --expect 1-5
```

## Interpretation

- If mzs=1 GAT substantially outperforms mzs=4 GAT: the credit-assignment
  cliff was a primary bottleneck at 30k steps. The model has capacity to
  learn; it just couldn't discover the delayed payoff in time.

- If mzs=1 GAT performs similarly: credit assignment was not the bottleneck.
  The problem may be training budget, exploration, or a different reward
  design issue.

- If mzs=1 GAT performs worse: immediate rewards may have removed the
  incentive to build large contiguous zones (zone_exponent=2.0 still
  superlinearly rewards size, but the threshold effect that forces
  commitment is gone).

**No outcome is claimed before results exist.**
