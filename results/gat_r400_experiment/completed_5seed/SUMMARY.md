# GAT r400 — 5-Seed Results

## Experiment
- Network: Al Nakheel r=400m
- Segments: 89
- Algorithm: MaskablePPO + GATFeaturesExtractor
- Observation: 7 features
- Seeds: 1, 2, 3, 4, 5
- Training: 30,000 timesteps per seed
- Zone Builder reference: +0.6863

## GAT Results
- Mean return: -0.0322
- Std: 0.0060
- Min: -0.0396
- Median: -0.0299
- Max: -0.0261
- Success vs zone_builder: 0/5

## Comparison
- MLP baseline mean: -0.0733
- MLP + adjacency mean: -0.0529
- GAT mean: -0.0322
- zone_builder: +0.6863

## Interpretation
GAT improved mean return and substantially reduced seed-to-seed variance relative to both MLP conditions, but remained far below the zone_builder reference. Graph-aware architecture helped, but did not close the planner gap at 30,000 timesteps.
