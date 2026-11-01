#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify V3 visual-quality scoring and regression guard behavior."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ASSISTANCE_DIR = "design-lab"


@dataclass
class Result:
    label: str
    ok: bool
    detail: str = ""


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ASSISTANCE_DIR).is_dir() and (parent / ".git").exists():
            return parent
    raise SystemExit("Could not locate repository root")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def check(results: list[Result], label: str, ok: bool, detail: str = "") -> None:
    results.append(Result(label, ok, detail))


def report_for(rubric: dict[str, Any], score: float, *, evidence: bool = True, failed_gate: str | None = None) -> dict[str, Any]:
    axes: dict[str, Any] = {}
    for spec in rubric.get("axes", []):
        axis_id = str(spec["id"])
        axes[axis_id] = {"score": score, "evidence": [f"synthetic evidence for {axis_id}"] if evidence else []}
    hard_gates = []
    for gate_id in rubric.get("hard_gates", []):
        hard_gates.append({"id": gate_id, "pass": gate_id != failed_gate, "result": "fail" if gate_id == failed_gate else "pass", "evidence": "synthetic gate evidence"})
    return {"artifact": "synthetic", "axes": axes, "hard_gates": hard_gates}


def critique_for(score: float, *, blocker: bool = False, evidence: bool = True) -> dict[str, Any]:
    return {
        "artifact": "synthetic",
        "discipline": "visual-quality",
        "rubric_version": "v3-smoke",
        "scores": [
            {"axis": "concept", "score": score, "weight": 1.2, "evidence": ["concept evidence"] if evidence else []},
            {"axis": "craft", "score": score, "weight": 1.0, "evidence": ["craft evidence"] if evidence else []},
        ],
        "automated_checks": [
            {"id": "blocker-smoke", "result": "fail" if blocker else "pass", "severity": "blocker", "evidence": "synthetic"}
        ],
        "evidence": ["synthetic"],
        "decision": "accept" if score >= 8 and not blocker and evidence else "reject",
    }


def verify_visual_score(root: Path, results: list[Result], out: dict[str, Any]) -> None:
    module = load_module(root / ASSISTANCE_DIR / "scripts" / "score_visual_quality.py", "score_visual_quality_v3_under_test")
    rubric = load_json(root / ASSISTANCE_DIR / "evals" / "rubrics" / "visual-quality-core.rubric.json")
    accepted = module.score_report(report_for(rubric, 9.1), rubric)
    revised = module.score_report(report_for(rubric, 7.6), rubric)
    missing_evidence = module.score_report(report_for(rubric, 9.1, evidence=False), rubric)
    failed_gate = module.score_report(report_for(rubric, 9.1, failed_gate=str(rubric["hard_gates"][0])), rubric)
    out["visual_score"] = {"accepted": accepted, "revised": revised, "missing_evidence": missing_evidence, "failed_gate": failed_gate}
    check(results, "visual scorer accepts high-evidence report", accepted["decision"] == "accept", str(accepted))
    check(results, "visual scorer revises mid-score report", revised["decision"] == "revise", str(revised))
    check(results, "visual scorer rejects missing evidence", missing_evidence["decision"] == "reject" and bool(missing_evidence["missing_evidence"]), str(missing_evidence))
    check(results, "visual scorer rejects failed hard gate", failed_gate["decision"] == "reject" and bool(failed_gate["failed_gates"]), str(failed_gate))


def verify_critique_score(root: Path, results: list[Result], out: dict[str, Any]) -> None:
    module = load_module(root / ASSISTANCE_DIR / "scripts" / "score_design_critique.py", "score_design_critique_v3_under_test")
    accepted = module.score_critique(critique_for(8.7), threshold=8.0)
    blocker = module.score_critique(critique_for(9.1, blocker=True), threshold=8.0)
    missing_evidence = module.score_critique(critique_for(9.1, evidence=False), threshold=8.0)
    out["critique_score"] = {"accepted": accepted, "blocker": blocker, "missing_evidence": missing_evidence}
    check(results, "critique scorer accepts weighted high score", accepted["accept"] is True, str(accepted))
    check(results, "critique scorer rejects blocker", blocker["accept"] is False and bool(blocker["blockers"]), str(blocker))
    check(results, "critique scorer rejects missing evidence", missing_evidence["accept"] is False and bool(missing_evidence["missing_evidence"]), str(missing_evidence))


def verify_compare(root: Path, results: list[Result], out: dict[str, Any]) -> None:
    module = load_module(root / ASSISTANCE_DIR / "scripts" / "compare_visual_iterations.py", "compare_visual_iterations_v3_under_test")
    before = {"overall": 7.0, "axes": {"craft": {"score": 7.0}, "concept": {"score": 7.5}}}
    after = {"overall": 8.2, "axes": {"craft": {"score": 8.1}, "concept": {"score": 8.4}}}
    regressed = {"overall": 8.0, "axes": {"craft": {"score": 6.9}, "concept": {"score": 8.4}}}
    improvement = module.compare_reports(before, after)
    regression = module.compare_reports(after, regressed)
    out["iteration_compare"] = {"improvement": improvement, "regression": regression}
    check(results, "iteration compare reports positive overall delta", improvement["overall_delta"] > 0, str(improvement))
    check(results, "iteration compare has no regressions on improved sample", not improvement["regressions"], str(improvement))
    check(results, "iteration compare detects axis regression", "craft" in regression["regressions"], str(regression))


def print_results(results: list[Result]) -> int:
    failed = [result for result in results if not result.ok]
    for result in results:
        prefix = "PASS" if result.ok else "FAIL"
        print(f"{prefix} {result.label}")
        if result.detail:
            print(f"  {result.detail}")
    print(f"\nVERIFY_VISUAL_SCORING_V3={'OK' if not failed else 'FAIL'} total={len(results)} failed={len(failed)}")
    return 0 if not failed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify V3 visual scoring")
    parser.add_argument("--emit", type=Path, help="Optional ignored directory for score samples")
    args = parser.parse_args()
    root = repo_root()
    results: list[Result] = []
    out: dict[str, Any] = {}
    verify_visual_score(root, results, out)
    verify_critique_score(root, results, out)
    verify_compare(root, results, out)
    if args.emit:
        args.emit.mkdir(parents=True, exist_ok=True)
        (args.emit / "visual-scoring-v3.sample.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        check(results, "visual scoring evidence emitted", (args.emit / "visual-scoring-v3.sample.json").is_file(), str(args.emit))
    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
