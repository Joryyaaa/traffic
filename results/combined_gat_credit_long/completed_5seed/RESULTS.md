# COMBINED GAT + Credit Assignment — Completed 5-Seed Results

## Setup
- Architecture: GAT
- Network: r400 (89 segments)
- min_zone_size: 1
- Training steps: 167,000 per seed
- Seeds: 1–5

## Results
- Mean return: +0.8528
- Std: 0.0210
- Min: +0.8108
- Median: +0.8633
- Max: +0.8633
- 5/5 seeds >= +0.6863
- Mean training time: 95.9 min/seed
- Max training time: 104.0 min

## Per-seed returns
- Seed 1: +0.8633
- Seed 2: +0.8633
- Seed 3: +0.8108
- Seed 4: +0.8633
- Seed 5: +0.8633

## Comparison
- GAT 30k mean: -0.0322
- CREDIT (min_zone_size=1, 30k) mean: +0.3816
- GAT-LONG (min_zone_size=4, 167k) mean: +0.1618
- COMBINED (min_zone_size=1, 167k) mean: +0.8528

The combined treatment produced both high performance and strong consistency across all five seeds.

Note: +0.6863 is the previously reported zone_builder reference under the original setup. A restricted-zone-size / min_zone_size-aware zone_builder experiment is being evaluated separately to establish the appropriate comparison reference.
