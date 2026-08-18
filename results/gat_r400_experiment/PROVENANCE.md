# GAT r400 Experiment

## Hypothesis

The MLP with adjacency-aware observation improved mean return from -0.0733 to
-0.0529 but remained far below zone_builder (+0.6863). If the bottleneck is
the policy's inability to reason about multi-hop graph structure (not just
one-hop adjacency counts), a graph attention network should close more of the
gap by learning which neighbours matter via attention weights, rather than
treating all neighbours equally (GCN) or counting them (MLP + adjacency).

## Design

| | MLP baseline | MLP + adjacency | GAT (this experiment) |
|---|---|---|---|
| **Config** | `r400_mlp_baseline` | `r400_mlp_adjacency` | `r400_gat` |
| **Observation** | 5 features | 7 features | 7 features |
| **Extractor** | flatten+MLP (default) | flatten+MLP (default) | GATFeaturesExtractor |
| **Algorithm** | MaskablePPO | MaskablePPO | MaskablePPO |
| **Network** | Al Nakheel r=400m, 89 seg | same | same |
| **Budget** | max_closures=9, ep_len=22 | same | same |
| **Reward** | all weights identical | same | same |
| **Training** | 30,000 timesteps | same | same |
| **Seeds** | 1, 2, 3, 4, 5 | same | same |
| **Eval** | 1 deterministic episode | same | same |

## GAT architecture

- 2 GAT layers, each 32-dim, 4 attention heads (head_dim=8)
- Attention masked to neighbours + self (adjacency + identity)
- ELU activation after each layer
- Mean-pool node embeddings → 32-dim
- Global row (7 features) → 16-dim MLP
- Concatenate (32 + 16 = 48) → 64-dim output MLP → policy/value heads
- Total extractor parameters: ~4,640 (on 7-feature input)

## Completed MLP results (for comparison)

MLP baseline (5-feature):
- Mean: -0.0733, Std: 0.0151
- Seeds > 0: 0/5, Seeds >= 0.6863: 0/5

MLP + adjacency (7-feature):
- Mean: -0.0529, Std: 0.0154
- Seeds > 0: 0/5, Seeds >= 0.6863: 0/5

## Reference baselines

- **zone_builder**: +0.6863
- **Inaction**: 0.0

## Slurm submission

```bash
cd /home/alblueja/traffic
git checkout gat-r400-experiment
git pull

sbatch --array=1-5 slurm/gat_r400_experiment.sbatch
```

## Aggregation

```bash
python scripts/aggregate_sweep.py --root runs/r400_gat_30k \
    --success-threshold 0.6863 --expect 1-5
```

## Interpretation

- If GAT substantially outperforms MLP+adjacency: graph-aware message passing
  captures multi-hop structure that flat features cannot, justifying the added
  complexity.

- If GAT performs similarly to MLP+adjacency: the observation was already
  sufficient; the bottleneck is elsewhere (training budget, reward shaping,
  exploration, or the fundamental difficulty of the problem at 30k steps).

- If GAT underperforms MLP+adjacency: the added parameters hurt sample
  efficiency at this budget. Consider longer training or simpler graph models.

**No outcome is claimed before results exist.**

## Constants (not changed from MLP experiment)

- Environment: Al Nakheel r=400m, 89 segments
- Reward: all weights identical, min_zone_size=4
- Algorithm: MaskablePPO (sb3-contrib required)
- Action masking: forbid_disconnection=true, allow_noop=true
- Training: 30,000 timesteps per seed
- Evaluation: 1 deterministic episode
