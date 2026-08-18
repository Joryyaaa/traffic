# Credit-Assignment Ablation — Completed 5-Seed Results

## Setup
- Architecture: GAT
- Timesteps: 30,000 per seed
- Seeds: 1–5
- Treatment: min_zone_size = 1
- Control: GAT 30k with min_zone_size = 4

## Results
- Mean return: +0.3816
- Std: 0.1834
- Min / Median / Max: +0.2046 / +0.3210 / +0.7341
- Per-seed:
  - Seed 1: +0.2895
  - Seed 2: +0.3210
  - Seed 3: +0.3587
  - Seed 4: +0.2046
  - Seed 5: +0.7341

## Interpretation
Reducing min_zone_size from 4 to 1 produced a large and consistent improvement over the original 30k GAT result (mean -0.0322).

This supports the credit-assignment hypothesis: with min_zone_size=4, early closures receive no pedestrian-zone reward, making learning substantially harder.

The previous zone-builder reference (+0.6863) was measured with min_zone_size=4, so it is not a strictly comparable success threshold for this treatment. A new zone-builder reference with min_zone_size=1 is required for a fair planner comparison.
