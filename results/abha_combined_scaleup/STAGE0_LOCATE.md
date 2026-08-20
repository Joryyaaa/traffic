# Stage 0: locating the Abha named-site data and the COMBINED GAT infra

## Branch: `abha-combined-scaleup` (new, created from this worktree's starting
HEAD, commit `60c72ca` "Merge pull request #3 from Joryyaaa/makkah-ibrahim-baseline",
which is a descendant of `main` at `6e0e7d4`).

## Where the Abha named-site scenario data and configs live

Already present on `main` (and therefore already on this worktree's starting
HEAD) via `codex/abha-hotspot-scenarios`, merged into `main` at commit `668a848`
/ `300c254`. No separate branch checkout or merge was needed for the data --
confirmed present at HEAD before any merge:

- `configs/city_madina_abha_art_street_baseline.yaml`
- `configs/city_madina_abha_central_market.yaml`
- `configs/city_madina_abha_asir_central_hospital.yaml`
- `configs/city_madina_abha_king_abdulaziz_grand_mosque.yaml`
- `configs/city_madina_abha_school_cluster.yaml` (data-blocked)
- `configs/city_madina_abha_abu_kheyal_park.yaml` (data-blocked)
- `data/raw/abha_hotspots/<scenario>/{streets,residential,amenities,road_metadata,intervention_targets}.geojson`
  + `qa.json` per scenario, `build_summary.json` at the root -- all already
  git-tracked (not gitignored; `.gitignore` already carries an
  `abha_hotspots` exception from commit `c149487`), so no new `.gitignore`
  edit or data commit was needed for these 6 scenarios.
- `ABHA_HOTSPOT_SCENARIOS.md` -- the scenario-name/status table the task's
  known-status list matches almost exactly.

## The 2,048-step smoke test (must not be cited as a finding)

Commit `a6960b0` "run the named-site package on Ibex: pipeline works, 2,048
steps does not learn" (also an ancestor of `main`/HEAD) is the smoke test
referenced in the task. It ran 2,048 timesteps (~136 episodes) on Central
Market and King Abdulaziz Grand Mosque; both trained agents lost to the
zone_builder heuristic. Per the task's own framing and this commit's message,
this is a pipeline-passes result, not a training result, and is not treated
as a finding anywhere in this study.

## Where the COMBINED GAT infra lives

NOT present on `main`/HEAD before this stage -- `src/snrl/gnn.py` only had
`GCNFeaturesExtractor`, no `GATFeaturesExtractor`/`GATLayer`, and
`scripts/seed_sweep_gat.py` did not exist. The real COMBINED lineage
(`GATFeaturesExtractor`, `GATLayer`, `seed_sweep_gat.py`, and
`configs/city_madina_ablation_r400_gat_mzs1.yaml`, the r400 min_zone_size=1 +
167k-step reference) lives on branch `combined-gat-credit-long`, which
diverged from `main` at `6e0e7d4` (the same commit this worktree's starting
HEAD descends from, confirmed via `git merge-base combined-gat-credit-long
HEAD` == `6e0e7d4`). `gat-scaleup-riyadh` also descends from
`combined-gat-credit-long` (confirmed via `git merge-base --is-ancestor
combined-gat-credit-long gat-scaleup-riyadh` == true) but is used here only
as a read-only structural/methodology template per instruction, never merged.

## Action taken

`git merge combined-gat-credit-long --no-edit` on top of the new
`abha-combined-scaleup` branch. Clean merge, zero conflicts (confirmed:
`git diff --stat` between the merge-base and HEAD touched none of
`src/snrl/env.py`, `src/snrl/config.py`, or `src/snrl/gnn.py` on the Abha
side, so the merge is a pure union of the two lines of history). This is a
real merge with full ancestry to both `main` (Abha data) and
`combined-gat-credit-long` (COMBINED GAT infra), not a cherry-pick of
individual files -- following the explicit precedent/requirement from the
task and from `combined-gat-credit-long`'s own commit `7226338` (which had to
redo an earlier cherry-pick as a real merge for the same reason).

Post-merge, confirmed present and working:
- `src/snrl/gnn.py`: `GATLayer`, `GATFeaturesExtractor` classes.
- `scripts/seed_sweep_gat.py`.
- `configs/city_madina_ablation_r400_gat_mzs1.yaml` (the COMBINED reference:
  `min_zone_size: 1`, `include_adjacency_state: true`, 89 segments,
  `--gat-hidden-dim 32 --n-heads 4 --global-embed-dim 16 --features-dim 64`
  wired in by `seed_sweep_gat.py`).
