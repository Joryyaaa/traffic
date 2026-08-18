# MLP Adjacency Observation — 5-Seed Results

## Experiment
- Network: Al Nakheel r=400m
- Segments: 89
- Algorithm: MaskablePPO + MlpPolicy
- Seeds: 1, 2, 3, 4, 5
- Training: 30,000 timesteps per seed
- Zone Builder reference: +0.6863

## MLP Baseline — 5 features
- Mean return: -0.0733
- Std: 0.0151
- Min: -0.0993
- Median: -0.0699
- Max: -0.0541
- Success vs zone_builder: 0/5

## MLP + Adjacency — 7 features
- Mean return: -0.0529
- Std: 0.0154
- Min: -0.0774
- Median: -0.0540
- Max: -0.0290
- Success vs zone_builder: 0/5

## Reference validation
zone_builder was re-evaluated on the same current r400 dataset:
- Segments: 89
- Mean return: +0.6863
- Episodes: 1

## Interpretation
Adding local adjacency state improved the MLP mean return from -0.0733 to -0.0529, but did not close the large gap to zone_builder (+0.6863). This supports moving to the next planned graph-aware architecture experiment rather than increasing MLP training time or changing the reward.
