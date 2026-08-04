"""Break the reward down into its components (accessibility, flow
concentration, equity, pedestrian-zone bonus, detour penalty, intervention
cost, disconnection penalty) at every step of an episode, instead of just the
scalar total -- so it's clear *why* a policy is scoring the way it is, per
the mentor's "reward function breakdown" request.

`info["reward/<term>"]` is already populated by env.step() (see
src/snrl/env.py); this script just collects it across a full episode and
reports it as a table + stacked bar chart.

Usage (a trained agent):
    python scripts/reward_breakdown.py --config configs/city_madina_ablation.yaml \\
        --model runs/ablation_riyadh_seed1/model.zip

Usage (no model -- defaults to the zone_builder baseline, useful without
training anything first):
    python scripts/reward_breakdown.py --config configs/city_madina_ablation.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from snrl.config import load_config  # noqa: E402
from snrl.env import StreetNetworkEnv  # noqa: E402

TERMS = [
    "accessibility",
    "flow_concentration",
    "equity",
    "pedestrian_zone",
    "detour",
    "intervention",
    "disconnection",
]


def zone_builder_choose(env):
    mask = env.action_masks()
    closed = np.flatnonzero(env.closed_mask)
    valid = np.flatnonzero(mask[: env.n_segments])
    if valid.size == 0:
        return env.n_segments
    if closed.size == 0:
        return int(valid[np.argmax(env._seg_degree[valid])])
    touching = [a for a in valid if env._adjacency[a][closed].any()]
    return int(touching[0]) if touching else env.n_segments


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--model", default=None, help="Trained model path (omit to use zone_builder instead)")
    ap.add_argument("--out", default="reward_breakdown.png")
    args = ap.parse_args()

    cfg = load_config(args.config)
    env = StreetNetworkEnv(cfg)

    if args.model:
        from sb3_contrib import MaskablePPO

        model_path = args.model[:-4] if args.model.endswith(".zip") else args.model
        model = MaskablePPO.load(model_path)

        def choose(obs):
            a, _ = model.predict(obs, action_masks=env.action_masks(), deterministic=True)
            return int(a)
    else:
        print("No --model given, using the zone_builder baseline.")

        def choose(obs):
            return zone_builder_choose(env)

    obs, _ = env.reset()
    rows = []
    step = 0
    while True:
        action = choose(obs)
        obs, reward, terminated, truncated, info = env.step(action)
        rows.append({t: info[f"reward/{t}"] for t in TERMS})
        rows[-1]["total"] = info["reward/total"]
        step += 1
        if terminated or truncated:
            break

    # --- per-step table ---
    header = "step  " + "".join(f"{t[:10]:>12}" for t in TERMS) + f"{'total':>10}"
    print(header)
    for i, row in enumerate(rows):
        print(f"{i:>4}  " + "".join(f"{row[t]:>12.4f}" for t in TERMS) + f"{row['total']:>10.4f}")

    cum_total = sum(row["total"] for row in rows)
    print(f"\ncumulative return: {cum_total:.4f}")
    print("\ncontribution of each term to the cumulative return:")
    for t in TERMS:
        term_sum = sum(row[t] for row in rows)
        pct = 100 * term_sum / cum_total if cum_total else float("nan")
        print(f"  {t:<20}{term_sum:>10.4f}   ({pct:5.1f}% of total)")

    # --- stacked bar chart across steps ---
    fig, ax = plt.subplots(figsize=(11, 6))
    bottoms_pos = np.zeros(len(rows))
    bottoms_neg = np.zeros(len(rows))
    x = np.arange(len(rows))
    for t in TERMS:
        vals = np.array([row[t] for row in rows])
        pos, neg = np.clip(vals, 0, None), np.clip(vals, None, 0)
        ax.bar(x, pos, bottom=bottoms_pos, label=t)
        ax.bar(x, neg, bottom=bottoms_neg, color=ax.patches[-1].get_facecolor())
        bottoms_pos += pos
        bottoms_neg += neg
    ax.plot(x, [row["total"] for row in rows], color="black", marker="o", label="total", linewidth=2)
    ax.axhline(0, color="gray", linewidth=0.8)
    ax.set_xlabel("step")
    ax.set_ylabel("reward contribution")
    ax.set_title("Reward breakdown per step")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"\nSaved chart -> {args.out}")


if __name__ == "__main__":
    main()
