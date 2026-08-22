"""Measure candidate action budgets on one scale-up network with zone_builder.

The reward, observation, architecture, and simulation settings come directly
from the supplied config. Only max_closures and episode_length are varied. One
deterministic episode per candidate matches the existing Riyadh scale-up budget
measurement methodology in results/gat_scaleup_riyadh/STAGE2_DATASETS.md.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from evaluate import run_policy, zone_builder_policy  # noqa: E402
from snrl import StreetNetworkEnv, load_config  # noqa: E402


def parse_candidates(value: str) -> list[tuple[int, int]]:
    candidates = []
    for item in value.split(","):
        try:
            max_closures, episode_length = item.strip().split(":", maxsplit=1)
            candidate = (int(max_closures), int(episode_length))
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"invalid candidate {item!r}; expected MAX_CLOSURES:EPISODE_LENGTH"
            ) from exc
        if candidate[0] < 1 or candidate[1] < candidate[0]:
            raise argparse.ArgumentTypeError(
                f"invalid candidate {item!r}; require 1 <= max_closures <= episode_length"
            )
        candidates.append(candidate)
    if not candidates:
        raise argparse.ArgumentTypeError("at least one candidate is required")
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--candidates",
        type=parse_candidates,
        default=parse_candidates("8:20,9:22,10:25,11:28,12:30,14:35"),
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    base_cfg = load_config(args.config)
    measurements = []
    expected_segments = None

    for max_closures, episode_length in args.candidates:
        cfg = copy.deepcopy(base_cfg)
        cfg.action.max_closures = max_closures
        cfg.action.episode_length = episode_length
        env = StreetNetworkEnv(cfg)
        if expected_segments is None:
            expected_segments = env.n_segments
        elif env.n_segments != expected_segments:
            raise RuntimeError("segment count changed during the budget measurement")

        started = time.perf_counter()
        total_return, _ = run_policy(env, zone_builder_policy(env), cfg.seed)
        wall_seconds = time.perf_counter() - started
        env.close()

        row = {
            "max_closures": max_closures,
            "episode_length": episode_length,
            "zone_builder_return": round(float(total_return), 10),
            "wall_seconds": round(wall_seconds, 3),
        }
        measurements.append(row)
        print(
            f"mc={max_closures:>2} ep={episode_length:>2} "
            f"zone_builder={total_return:+.6f} wall={wall_seconds:.1f}s",
            flush=True,
        )

    payload = {
        "config": Path(args.config).as_posix(),
        "segments": expected_segments,
        "policy": "zone_builder (scripts/evaluate.py), one deterministic episode",
        "seed": base_cfg.seed,
        "method": (
            "Current config held constant; only action.max_closures and "
            "action.episode_length varied per candidate."
        ),
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "measurements": measurements,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"saved -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
