# Abha Scenario Metrics Review

## Objective

This review compares the current Abha intervention scenarios against the S0 baseline using the available Madina network metrics.

The scenarios evaluated are:

- S0: Baseline network
- S1A: King Abdulaziz Road one-way — NE direction
- S1B: King Abdulaziz Road one-way — SW direction
- S2: Green Road scenario — current hypothetical placeholder

The purpose of this review is to identify the changes produced by each scenario without modifying the simulation or RL code.

---

## Scenario Comparison

| Scenario | Segments | Accessibility | Gini | VKT Proxy (km) | Total Flow | Mean Trip Distance (m) |
|----------|---------:|--------------:|-----:|---------------:|-----------:|-----------------------:|
| S0  | 4586 | 1.3013 | 0.3516 | 2232.8 | 22232.5 | 774.9 |
| S1A | 4570 | 1.3026 | 0.3503 | 2231.2 | 22257.0 | 774.9 |
| S1B | 4573 | 1.3008 | 0.3520 | 2232.8 | 22232.5 | 774.9 |
| S2  | 4602 | 1.2921 | 0.3554 | 2216.7 | 22092.5 | 775.1 |

## Change Relative to S0

| Scenario | Accessibility | VKT Proxy | Total Flow | Mean Trip Distance |
|----------|--------------:|----------:|-----------:|-------------------:|
| S1A | +0.10% | -0.07% | +0.11% | ~0.0 m |
| S1B | -0.04% | 0.00% | 0.00% | ~0.0 m |
| S2 | -0.71% | -0.72% | -0.63% | +0.2 m |

---

## Findings

### S1A — King Abdulaziz One-Way NE

S1A currently shows the most favorable overall change relative to S0.

Accessibility increases by approximately 0.10%, while total flow increases by approximately 0.11%. The VKT proxy decreases slightly by approximately 0.07%.

The Gini value also decreases from 0.3516 in S0 to 0.3503 in S1A.

However, these changes are small and should not yet be interpreted as evidence that S1A is the preferred real-world traffic intervention.

### S1B — King Abdulaziz One-Way SW

S1B remains very close to the S0 baseline.

Accessibility decreases by approximately 0.04%, while the VKT proxy and total flow remain effectively unchanged.

Based on the current Madina metrics, S1B does not demonstrate a clear improvement over S0.

### S2 — Green Road

S2 produces the largest reduction in the VKT proxy, approximately 0.72% relative to S0.

However, accessibility decreases by approximately 0.71% and total flow decreases by approximately 0.63%.

The mean trip distance remains almost unchanged.

The current S2 alignment is a hypothetical approximately 2 km placeholder used to demonstrate and validate the Green Road subsystem. It does not represent the authoritative ASDA Green Road alignment.

Therefore, these results must not be interpreted as an evaluation of the actual proposed Green Road.

---

## Overall Interpretation

Among the currently available no-intervention Madina metrics, S1A shows the most favorable overall change relative to S0, although the magnitude of the improvement is small.

S1B behaves almost identically to the baseline.

S2 reduces the modeled VKT proxy but also reduces accessibility and total flow, indicating a trade-off in the current placeholder configuration.

Mean trip distance remains essentially unchanged across all four scenarios.

---

## Limitations

- The VKT value is a modeled Madina network-load proxy and is not observed vehicle-kilometers traveled.
- The current results should not be treated as observed traffic performance.
- Authoritative traffic demand and OD data are not yet integrated.
- Detailed lane-count data are incomplete in the available OSM data.
- The S2 Green Road alignment is hypothetical and must be replaced with the official ASDA geometry.
- The observed differences between S0, S1A, and S1B are small.
- Final recommendations should consider the completed policy evaluation and authoritative traffic data.

---

## Conclusion

The current scenario comparison validates that S0, S1A, S1B, and S2 can be evaluated consistently within the same Abha/Madina pipeline.

At this stage, S1A provides a small improvement in accessibility and total flow relative to S0, while S1B remains approximately equivalent to the baseline.

S2 demonstrates the Green Road subsystem successfully but cannot yet be used to evaluate the actual ASDA proposal because its current alignment is hypothetical.

These results should therefore be treated as preliminary scenario-level evidence rather than final traffic recommendations.
