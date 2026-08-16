"""One-off: how long does a single Madina simulate() call take on Abha S0
(4,586 segments) -- before committing to evaluate.py's baseline suite, which
calls simulate() once per candidate action per step for greedy/zone_builder_best.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from snrl import StreetNetworkEnv, load_config  # noqa: E402

if __name__ == "__main__":
    cfg = load_config("configs/city_madina_abha_s0.yaml")
    t0 = time.time()
    env = StreetNetworkEnv(cfg)
    print(f"env construction: {time.time()-t0:.1f}s, n_segments={env.n_segments}")

    t0 = time.time()
    closed = np.zeros(env.n_segments, dtype=bool)
    sim = env.backend.simulate(closed)
    dt = time.time() - t0
    print(f"simulate() [fully open]: {dt:.2f}s  mean_access={np.mean(sim.origin_access):.3f}  "
          f"total_flow={np.sum(sim.segment_flow):.1f}")

    t0 = time.time()
    closed2 = closed.copy()
    closed2[0] = True
    sim2 = env.backend.simulate(closed2)
    dt2 = time.time() - t0
    print(f"simulate() [1 closure, new combo]: {dt2:.2f}s")

    n_valid_actions = int(env.action_masks().sum())
    print(f"\nvalid actions at reset: {n_valid_actions}")
    print(f"estimated cost of ONE greedy step (one-step lookahead over all valid actions): "
          f"{n_valid_actions * dt2:.1f}s (~{n_valid_actions * dt2/60:.1f} min)")
    print(f"estimated cost of a {cfg.action.episode_length}-step greedy episode: "
          f"{cfg.action.episode_length * n_valid_actions * dt2/60:.1f} min "
          f"(~{cfg.action.episode_length * n_valid_actions * dt2/3600:.1f} hr)")
