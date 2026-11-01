#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Machine-readable deterministic reconstruction lifecycle CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(DESIGN_LAB) not in sys.path:
    sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.pipeline import (  # noqa: E402
    PipelineError,
    PipelineBlockedError,
    RollbackBlockedError,
    RollbackBoundaryError,
    rollback_run,
    run_reconstruction,
)
from reconstruction.state import PipelineStateError, load_contract  # noqa: E402


class CLIUsageError(ValueError):
    """A machine-readable command-line contract violation."""


class MachineArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CLIUsageError(message)


def _parser() -> argparse.ArgumentParser:
    parser = MachineArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("analyze", "reconstruct", "verify", "resume"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("contract", type=Path)
        subparser.add_argument(
            "--stop-after",
            choices=("CREATED", "ANALYZED", "RECONSTRUCTED_LOCAL", "PIXEL_VERIFIED_DETERMINISTIC", "PARTIAL"),
        )
        subparser.add_argument(
            "--cancel-after", choices=("CREATED", "ANALYZED", "RECONSTRUCTED_LOCAL")
        )
    rollback = subparsers.add_parser("rollback")
    rollback.add_argument("contract", type=Path)
    rollback.add_argument("--target", type=Path)
    return parser


def _emit(value: dict) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "rollback":
            contract, _, _ = load_contract(args.contract)
            repo_root = DESIGN_LAB.parent
            run_dir = repo_root.joinpath(*contract["roots"]["runtime"].rstrip("/").split("/"))
            summary = rollback_run(run_dir, args.target)
            _emit(summary.to_dict())
            return 0
        target = {
            "analyze": "analyze",
            "reconstruct": "reconstruct",
            "verify": "verify",
            "resume": "verify",
        }[args.command]
        summary = run_reconstruction(
            args.contract,
            target=target,
            stop_after=args.stop_after,
            cancel_after=args.cancel_after,
        )
        _emit(summary.to_dict())
        required_phase = {
            "analyze": "analyze",
            "reconstruct": "reconstruct",
            "verify": "verify",
            "resume": "verify",
        }[args.command]
        phase_complete = required_phase in summary.completed_phases
        fidelity_ok = args.command not in {"verify", "resume"} or summary.passed
        lifecycle_ok = summary.state not in {"FAILED", "CANCELLED", "PARTIAL"}
        return 0 if phase_complete and fidelity_ok and lifecycle_ok else 1
    except RollbackBoundaryError as exc:
        _emit({"state": "REJECTED", "passed": False, "error": str(exc)})
        return 2
    except RollbackBlockedError as exc:
        _emit({"state": "BLOCKED", "passed": False, "error": str(exc)})
        return 3
    except PipelineBlockedError as exc:
        _emit({"state": "BLOCKED", "passed": False, "error": str(exc)})
        return 3
    except (PipelineError, PipelineStateError, CLIUsageError, OSError, ValueError) as exc:
        _emit({"state": "FAILED", "passed": False, "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
