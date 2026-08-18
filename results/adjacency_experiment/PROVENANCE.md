# Adjacency-Observation Experiment

## Hypothesis

The current MLP may be bottlenecked by an impoverished observation: the reward
favours contiguous pedestrian zones while the policy does not directly observe
which neighbouring segments are already closed. Adding local adjacency state
to the observation may close the gap without requiring a graph neural network.

## Design

| | Control | Treatment |
|---|---|---|
| **Config** | `city_madina_ablation_r400_mlp_baseline.yaml` | `city_madina_ablation_r400_mlp_adjacency.yaml` |
| **Observation** | 5 features (is_closed, flow, length, flow_delta, degree) | 7 features (+closed_neighbour_count, +touches_closed) |
| **Algorithm** | MaskablePPO + MlpPolicy | MaskablePPO + MlpPolicy |
| **Network** | Al Nakheel r=400m, 89 segments | same |
| **Budget** | max_closures=9, episode_length=22 | same |
| **Reward** | w_ped_zone=1.0, min_zone_size=4, zone_exponent=2.0, zone_min_flow_fraction=0.1 | same |
| **Training** | 30,000 timesteps | same |
| **Seeds** | 1, 2, 3, 4, 5 | same |
| **Eval** | 1 deterministic episode per seed (Madina is deterministic) | same |

Seeds 1-3 overlap the historical MLP results for direct comparison:
- seed 1: +0.812453
- seed 2: -0.024868
- seed 3: +0.001617

## Added observation features

**Feature 5 — closed_neighbour_count:** For each segment, the number of
currently-closed adjacent segments. Computed as `adjacency @ closed_mask`.

**Feature 6 — touches_closed:** Binary {0,1} flag: does this segment have at
least one currently-closed neighbour? Computed as
`(closed_neighbour_count > 0)`.

The global summary row (final row of the observation) fills positions 5-6 with
zeros — no global adjacency statistic is invented.

## Reference baselines

- **zone_builder** on this config: **+0.6863** (the planner ceiling)
- **Inaction** (no closures): **0.0** (baseline-relative delta reward)

## Slurm submission

```bash
cd /home/shiekhmf/Student_Projects/Jory/traffic

# Baseline (5 seeds)
sbatch --array=1-5 \
       --export=ALL,CONFIG=configs/city_madina_ablation_r400_mlp_baseline.yaml,OUTROOT=runs/r400_mlp_baseline_30k \
       slurm/adjacency_experiment.sbatch

# Adjacency (5 seeds)
sbatch --array=1-5 \
       --export=ALL,CONFIG=configs/city_madina_ablation_r400_mlp_adjacency.yaml,OUTROOT=runs/r400_mlp_adjacency_30k \
       slurm/adjacency_experiment.sbatch
```

## Aggregation

```bash
python scripts/aggregate_sweep.py --root runs/r400_mlp_baseline_30k \
    --success-threshold 0.6863 --expect 1-5

python scripts/aggregate_sweep.py --root runs/r400_mlp_adjacency_30k \
    --success-threshold 0.6863 --expect 1-5
```

## Interpretation

- If adjacency-aware MLP closes most of the planner gap or becomes
  substantially more reliable across seeds: the primary limitation was
  impoverished observation, not architectural capacity. An MLP with the right
  input is sufficient.

- If adjacency-aware MLP remains weak/bimodal across seeds: local adjacency
  information was insufficient, providing stronger justification for a later
  graph-based feature extractor (GAT/GNN) experiment.

**No outcome is claimed before results exist.**

## Constants (not changed)

- Environment: Al Nakheel r=400m, 89 segments
- Reward: all weights identical, min_zone_size=4
- Algorithm: MaskablePPO + MlpPolicy (sb3-contrib required)
- Action masking: forbid_disconnection=true, allow_noop=true
- Training: 30,000 timesteps per seed
- Evaluation: 1 deterministic episode
