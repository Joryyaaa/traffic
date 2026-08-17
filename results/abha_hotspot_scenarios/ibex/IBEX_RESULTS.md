# Abha named-site Ibex results

Successful jobs:

- cheap baseline array `50634291`: all four tasks completed in 14--17 seconds;
- 2,048-step training array `50634292`: Central Market completed in 1:51 and
  King Abdulaziz Grand Mosque in 1:30;
- trained-agent evaluation array `50634633`: both tasks completed in 22--26
  seconds.

## Fully open network measurements

| Scenario | Segments | Mean accessibility | Accessibility Gini | Flow entropy | Total flow | Mean trip distance (m) |
|---|---:|---:|---:|---:|---:|---:|
| Art Street and Al-Muftaha baseline | 57 | 2.337 | 0.070 | 0.536 | 5.3 | 296.1 |
| Asir Central Hospital | 96 | 0.187 | 0.043 | 0.522 | 3.9 | 560.4 |
| Central Market | 82 | 1.357 | 0.211 | 0.650 | 11.8 | 554.4 |
| King Abdulaziz Grand Mosque | 87 | 0.868 | 0.130 | 0.706 | 52.3 | 550.9 |

## Policy return comparison

One deterministic episode per policy, using the repository's unchanged
reward and `scripts/evaluate.py`.

| Scenario | Random | Highest flow | Lowest flow | Zone builder | RL agent (2,048 steps) |
|---|---:|---:|---:|---:|---:|
| Art Street and Al-Muftaha baseline | 0.0000 | 0.0000 | 0.0000 | 0.0000 | not trained |
| Asir Central Hospital | -0.0500 | -0.4173 | -0.0500 | -0.4173 | not trained |
| Central Market | -0.0500 | -0.4001 | -0.0500 | **0.8363** | -0.1188 |
| King Abdulaziz Grand Mosque | -0.1007 | **0.0503** | -0.0500 | **0.0503** | -0.0500 |

## Interpretation

- Central Market is the clearest positive intervention case: the deterministic
  zone builder reaches `+0.8363`.
- The mosque has only a small positive opportunity (`+0.0503`).
- The tested hospital interventions are harmful under the current reward.
- The 2,048-step agents are smoke tests, not converged policies. The market
  agent loses `-0.0383` from accessibility-related reward terms and `-0.0500`
  from intervention cost; the mosque agent gains no network benefit and pays
  `-0.0500` intervention cost.
- School Cluster remains blocked because the valid OSM crop has no residential
  origins. Abu Kheyal Park remains blocked because every valid directed crop
  has zero baseline accessibility. Neither was silently trained.

Raw reports and reward-breakdown charts are stored beside this file. VKT in
the visualization pipeline remains explicitly labelled as a Madina
flow-distance simulation proxy, not observed traffic counts.
