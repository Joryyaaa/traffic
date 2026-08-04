# Task tracker — mentor's latest requests (see commit 37a064a for the code)

Split into two lists: things that run in seconds-to-minutes on a laptop
(no GPU, no long wait -- we do these ourselves, today), and things that need
real compute time and/or many repeated training runs (mentor runs these on
APEX). Check items off as they're done, same convention as README's Status
list.

---

## 🟢 Local / fast — no GPU, minutes not hours (us)

- [ ] Fetch Al-Kharj OSM data and confirm it has real residential buildings
      (Al Olaya at 150-250m had zero — check before assuming Al-Kharj works):
      `python scripts/fetch_osm_data.py --radius 250 --out data/raw/alkharj --lat 24.1483 --lon 47.3050`
- [ ] `scripts/baseline_report.py` across all scenario configs we have data
      for (Al Nakheel + Al-Kharj once fetched) — one comparison table
- [ ] `scripts/plot_flow.py` on Al Nakheel — flow heatmap, no training needed
- [ ] `scripts/reward_breakdown.py` using an *already-trained* model from
      today (seed1/seed3/seed7/long) — no new training, just inference
- [ ] `scripts/record_episode.py` (the requested video) using an
      already-trained model from today — same, no new training
- [ ] Follow up on NEOM data request (sent to mentor's NEOM contact) —
      this unblocks `configs/city_madina_neom.yaml`, currently a placeholder
- [ ] Update `ملخص_عمل_اليوم.md` / README with whatever comes out of the
      above once run

## 🔴 Heavy / APEX — long training, many seeds, GPU (mentor)

- [ ] Large seed sweep, current scenario (Al Nakheel): e.g. 100 seeds x
      30,000 steps via `scripts/seed_sweep.py` — get a real mean ± std,
      not 4 hand-picked seeds
- [ ] Same seed sweep repeated on Al-Kharj once data is confirmed usable —
      does the greedy-fails/planning-wins pattern hold in a 2nd real
      neighborhood, not just Al Nakheel?
- [ ] Same again on NEOM, once real data exists
- [ ] Larger network size: re-fetch Al Nakheel (or a new area) at a bigger
      radius (e.g. 800m-1km, several hundred segments instead of 52) and
      re-run training — note: the `greedy` baseline itself becomes the
      bottleneck at this size (one simulate() call per candidate segment,
      per step -- see the smoketest slowdown from earlier today), so either
      budget real time for it or drop greedy from the comparison table at
      this scale and say why
- [ ] Longer training runs per seed (100,000+ timesteps) to check whether
      the ~25% of seeds that get stuck in a local optimum (like seed 42
      today) eventually escape given enough time, or genuinely need a
      different seed
- [ ] Once seed-sweep numbers exist: re-run `scripts/record_episode.py` /
      `scripts/plot_closures.py` on the *best* seed from the big sweep
      (today's plots used seed 1 from a 4-seed sample, not necessarily the
      true best)

---

*Add rows here as new requests come in — same format, same two buckets.*
