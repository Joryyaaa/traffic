# Abha Khamis-Jabal Soudah Viewpoint Madina results

| Scenario | Method | Demand scope | Access | Access Gini | VKT proxy (km) | Trip distance (m) | Major-road flow | Protected-local flow | Unreachable | Runtime (s) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| combined_peak_1_5 | exact_linear_derivation | khamis_to_jabal_soudah_viewpoint | 0.209416 | 0.0446 | 32.8 | 52247.5 | 85.8% | 0.0% | 0.0% | 0.0 |
| combined_peak_2_0 | exact_linear_derivation | khamis_to_jabal_soudah_viewpoint | 0.209416 | 0.0446 | 43.8 | 52247.5 | 85.8% | 0.0% | 0.0% | 0.0 |
| current_full_belt | madina_simulation | city_accessibility | 1.080261 | 0.4799 | 143.2 | 795.6 | 1.7% | 78.5% | 9.6% | 5.0 |
| khamis_viewpoint_baseline | exact_linear_derivation | khamis_to_jabal_soudah_viewpoint | 0.209416 | 0.0446 | 21.9 | 52247.5 | 85.8% | 0.0% | 0.0% | 0.0 |
| route10_reference | madina_simulation | khamis_to_jabal_soudah_viewpoint | 0.190740 | 0.0000 | 10.6 | 55228.2 | 78.5% | 0.0% | 0.0% | 1.5 |
| route2120_reference | madina_simulation | khamis_to_jabal_soudah_viewpoint | 0.228092 | 0.0000 | 11.3 | 49266.9 | 96.4% | 0.0% | 0.0% | 0.8 |

Demand multipliers are sensitivity weights, not measured traffic counts. 
VKT is a Madina flow-distance proxy. Peak-load cases do not model queues or capacity-dependent congestion.
The city-accessibility row is context only and must not be compared numerically with the Khamis-to-viewpoint demand rows.