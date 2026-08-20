# GAT r400 Longer Training — Completed 5-Seed Results

## Setup
- Architecture: GAT
- Timesteps: 167,000 per seed
- Seeds: 1–5
- Same r400 environment and reward as the completed 30k GAT control
- Zone-builder reference: +0.6863

## Results
- Mean return: +0.1618
- Std: 0.3511
- Min / Median / Max: -0.0262 / -0.0204 / +0.8633
- Per-seed:
  - Seed 1: -0.0262
  - Seed 2: -0.0204
  - Seed 3: -0.0261
  - Seed 4: +0.8633
  - Seed 5: +0.0183
- Success vs zone_builder: 1/5

## Interpretation
Longer GAT training improved the mean return relative to the completed 30k GAT control (-0.0322), but performance remained highly variable across seeds.

One seed reached +0.8633 and exceeded the zone-builder reference, while the other four remained near zero or negative. This suggests that longer training can discover a strong policy, but does not make learning consistently reliable across seeds.
