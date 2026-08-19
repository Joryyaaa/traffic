# COMBINED GAT — 30-Seed Results

## Experiment
- Model: GAT
- Credit-assignment fix: min_zone_size = 1
- Training: 167,000 timesteps
- Seeds: 1–30
- Benchmark: zone_builder = 0.6863

## Results
- N: 30
- Mean return: 0.8365
- Sample standard deviation: 0.0623
- Median: 0.8633
- Min / Max: 0.5909 / 0.8633
- 95% CI: [0.8132, 0.8598]

## Comparison with zone_builder
- Seeds >= 0.6863: 29/30 (96.7%)
- Seeds < 0.6863: 1/30 (3.3%)
- Mean margin over benchmark: +0.1502
- Worst-seed margin: -0.0954

## Statistical test
One-sample, one-sided t-test:

H0: population mean <= 0.6863  
H1: population mean > 0.6863

- t(29) = 13.2021
- p = 4.30547e-14

The null hypothesis is rejected at alpha=0.05. The 30-seed experiment provides strong evidence that the expected return of the combined GAT model exceeds the zone_builder benchmark.

Note: 29 of 30 individual seeds exceeded the benchmark; seed 7 (0.5909) was the only seed below it.
