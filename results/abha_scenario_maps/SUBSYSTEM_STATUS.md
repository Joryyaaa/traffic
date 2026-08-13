# Road Segment / Green Road subsystem status

This project intentionally develops one subsystem independently: **Road Segment /
Green Road**. It does not attempt to add information-spread, financial, emissions,
waiting-time, or other subsystems in the same experiment.

## Workflow completion

| Required step | Status | Evidence |
|---|---|---|
| 1. Choose one subsystem | Complete | Road Segment / Green Road |
| 2. Define scenarios | Complete | S0 baseline, S1A/S1B one-way alternatives, S2 new-road alternative |
| 3. Collect required data | Partial | Real OSM roads/origins/destinations are prepared; authoritative ASDA S2 alignment is still missing |
| 4. Test on a small area (~2 km) | Complete at intervention scale | S2 placeholder alignment is 1.973 km inside the Abha study network |
| 5. Compare with baseline | Complete for no-intervention Madina metrics; policy evaluation pending | `scenario_metrics.json` and comparison table are complete; only S0 random policy completed locally |
| 6. Integrate into main system | Complete | Four Madina configs, reproducible builders, RL environment compatibility, and Ibex job are present |

## Expected outputs

- **Working subsystem:** yes — all four networks load and simulate through Madina.
- **Prepared data:** yes for OSM-based S0/S1A/S1B; S2 is reproducible but hypothetical.
- **Simulation scenario:** four scenarios completed.
- **Evaluation against baseline:** network metrics completed; full policy baselines deferred to Ibex.
- **Ready to merge:** integrated and committed on `main`.
- **Visualizations:** physical scenario renderings, Madina heatmaps, flow-difference
  maps, impact chart, CSV table, and text table completed.

## Remaining work

1. Replace `GREEN_ROAD_WAYPOINTS` with ASDA's authoritative route geometry.
2. Run `slurm/abha_s0_baselines.sbatch` on Ibex for S0/S1A/S1B/S2 to obtain
   `highest_flow`, `lowest_flow`, `zone_builder`, `greedy`, and
   `zone_builder_best` results (and a consistent rerun of `random`).
3. Rebuild S2 maps and tables after authoritative geometry or Ibex results arrive.

## Interpretation guardrails

- S2 currently demonstrates the subsystem and integration pipeline, not the
  performance of ASDA's actual proposal.
- `vkt_proxy_km` is a Madina network-load proxy, not observed vehicle-kilometres.
- S1A's observed accessibility improvement is small (+0.10% vs S0) and should
  not be overstated before policy runs and authoritative traffic data are added.
