#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record one validated reconstruction timing event as NDJSON.

This recorder accepts a duration measured by the invoking runtime.  It does
not benchmark a synthetic pipeline or invent thresholds; callers must provide
their actual stage duration and then aggregate matched corpus samples.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.performance import TimingEvent  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", required=True)
    parser.add_argument("--temperature", required=True, choices=("cold", "warm"))
    parser.add_argument("--duration-ms", required=True, type=float)
    parser.add_argument("--profile")
    parser.add_argument("--hardware-id")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        event = TimingEvent(
            stage=args.stage,
            duration_ms=args.duration_ms,
            temperature=args.temperature,
            profile=args.profile,
            hardware_id=args.hardware_id,
        ).as_json()
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
    print("RECONSTRUCTION_TIMING_EVENT=RECORDED stage=" + args.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
