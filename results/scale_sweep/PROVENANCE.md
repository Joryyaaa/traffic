# Provenance: 5-point network-size sweep

The experiment Jory prepared in `results/scale_sweep_prep/PROVENANCE.md` (commit
`3ef29f2`), run to completion on Ibex, plus the r=460 fifth point she could not
fetch.

**Design:** one neighborhood (Al Nakheel, north Riyadh, center 24.7412/46.6335) at
five radii, so network size varies and city, demand pattern and street morphology
do not. All five run the current reward (Jory's `b138dba` + `de90953`).

**Run:** 3 seeds per size, Slurm arrays `50215597`, `50215667`, `50215668`,
`50215669`, `50215600`. All 15 tasks COMPLETED, no failures, no timeouts.
Source rows: `results_all.csv` (one row per size and seed, with the training
seconds and the planner bar each number is judged against).

Every figure below re-derives from that CSV. `std` is the population std, matching
`scripts/aggregate_sweep.py`:

    python scripts/aggregate_sweep.py --root runs/scale_<r> --expect 1-3 \
        --success-threshold <planner_zone_builder for that size>

## Result

| segments | radius | steps | mean | std | min / median / max | planner | >= planner | > 0 | h/seed |
|---|---|---|---|---|---|---|---|---|---|
| 26 | 250m | 100k | **+0.2595** | 0.0636 | +0.1773 / +0.2689 / +0.3323 | +0.2661 | **2/3** | 3/3 | 0.24 |
| 89 | 400m | 167k | **+0.2631** | 0.3886 | -0.0249 / +0.0016 / **+0.8125** | +0.6863 | **1/3** | 2/3 | 2.02 |
| 186 | 460m | 214k | -0.0470 | 0.0025 | -0.0499 / -0.0475 / -0.0437 | +0.6190 | 0/3 | **0/3** | 5.34 |
| 226 | 500m | 233k | +0.0044 | 0.0245 | -0.0302 / +0.0195 / +0.0238 | +0.3297 | 0/3 | 2/3 | 14.81 |
| 386 | 700m | 300k | -0.0280 | 0.0213 | -0.0465 / -0.0395 / +0.0018 | +0.2878 | 0/3 | 1/3 | 18.79 |

Three regimes, not a smooth decay:

- **26 segments: works.** All three seeds positive in a tight band, two of three at
  or above the planner. The best seed (+0.3323) is the same value the 100-seed 30k
  sweep found as its maximum, which suggests the policy is converging on the best
  reachable closure set rather than still improving.
- **89 segments: bimodal.** One seed reaches +0.8125, clearly above the planner's
  +0.6863. The other two sit at zero (+0.0016, -0.0249). The mean (+0.2631) is
  almost identical to the 26-segment mean (+0.2595) while the std is 6x larger, so
  a mean-versus-size curve would show a flat line and hide that the outcome
  distribution changed character completely.
- **186 segments and above: collapsed.** No seed at any of the three largest sizes
  matches the planner. At 186 the failure is total and uniform: std 0.0025, every
  seed on the -0.05 floor, which is exactly the `w_intervention` cost of spending
  the closure budget while earning zero zone bonus. The agent closes streets and
  never assembles a qualifying zone.

The transition is between 89 and 186 segments.

## This settles the open question from `results/large_30k_fixed`

That run (386 segments, 30k steps, 10 seeds, mean -0.0489) ended with an explicit
caveat: 30k was short for the action space, longer training clearly helped at 26
segments, and "a 200k-300k run on 2-3 seeds would separate *does not scale* from
*undertrained*". That is exactly the run in the last row above.

At 10x the training (300k steps, up to 23.5 hours per seed) the 386-segment result
is still negative: mean -0.0280 against -0.0489 at 30k, best seed +0.0018, which is
zero to three decimal places. Training longer moves it off the floor and no
further.

So **undertraining is ruled out as the sole cause** and the weaker claim can be
dropped. The MLP-over-flat-observation policy does not scale past roughly 100
segments. `zone_builder` reaches +0.2878 on this exact network, so the return is
there to be had and PPO cannot find it. That is direct evidence for the GNN-policy
question (README open question 5) and makes Jory's `src/snrl/gnn.py` prototype the
right next step.

## What would change the conclusion

Three confounds, all real, none of which I can remove from these runs:

1. **n = 3.** At 89 segments the spread between seeds is 0.84. Three seeds cannot
   distinguish "this size fails" from "these three seeds were unlucky", and the
   89-segment row is the proof: had seed 1 not run, that size would read as a clean
   failure. The 186-segment row is the one I would defend on n=3, because its std
   is 0.0025 and it reproduces the independent 10-seed 386-segment run almost
   exactly (-0.0470 vs -0.0489). The others need more seeds.
2. **Budget varies with size, and not monotonically.** Each size uses its own
   measured `max_closures`/`min_zone_size`/`episode_length`, because a flat
   percentage rule produces a planner that loses to doing nothing (see the r460 and
   large config headers). So "size" is confounded with "budget". Notably 12/6/30 is
   the measured-good budget at both 186 and 386 segments, so workable budget does
   not track network size in any simple way.
3. **Timesteps vary with size** (100k to 300k, interpolated), so the sizes are not
   trained equally. The 386-segment point is the only one where that confound has
   been probed directly, via the 30k-versus-300k comparison above.

**The planner bar also moves with size** (+0.2661 to +0.6863), so "match/beat
planner" is not comparable across rows. Comparison against inaction (0.0) is the
one fixed bar, and on that measure the ordering is 3/3, 2/3, 0/3, 2/3, 1/3.

The cleanest follow-up is 20+ seeds at 89 and 186 segments on a matched budget and
matched timesteps. That would turn the bimodal-versus-collapsed boundary from a
3-seed observation into a measurement.

## Note on the r=460 point

`results/scale_sweep_prep/PROVENANCE.md` records this point as unfetchable, with
the amenities query timing out on every attempt. It fetched on the first try on
2026-08-08 (186 segments, 66 residential, 18 amenities, matching the predicted
~186) once two osmnx/Overpass quirks were worked around: `overpass-api.de`
round-robins over two backends of which 65.109.112.52 refuses connections outright,
and osmnx resolves the host itself over DNS-over-HTTPS and re-pins via
`socket.gethostbyname`, so ordinary DNS overrides are ignored. Pin the healthy IP
and disable DoH (`ox.settings.doh_url_template = None`) and it is reliable. The
failure was infrastructure, not the query.
