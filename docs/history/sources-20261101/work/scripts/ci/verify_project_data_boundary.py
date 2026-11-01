#!/usr/bin/env python3
"""Verify the single project-local runtime/evidence path policy."""
from __future__ import annotations

import json
from pathlib import Path

EXPECTED = {
    "runtimeRoot": ".project-local/runs",
    "taskArtifactsRoot": ".project-local/artifacts",
    "canonicalEvidenceRoot": ".project-local/artifacts",
}


def verify(root: Path) -> list[str]:
    errors: list[str] = []
    contract_path = root / ".project/governance" / "project-data-boundary.json"
    projects_path = root / ".project/governance" / "projects.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        projects = json.loads(projects_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"unreadable: {exc}"]
    spill = contract.get("spillGovernance") or {}
    ledger = spill.get("ledger")
    if not isinstance(ledger, dict):
        errors.append(
            "spillGovernance declares four verbs (trace/locate/clean/migrate) but names no "
            "machine-readable ledger, so a spill can only be described in prose"
        )
    else:
        path = str(ledger.get("path", ""))
        if not path.startswith(".project-local/"):
            errors.append(f"spillGovernance.ledger.path must live inside the project root, got {path!r}")
        if not str(ledger.get("schema", "")):
            errors.append("spillGovernance.ledger.schema is required")
        fields = ledger.get("requiredFields")
        if not isinstance(fields, list) or not fields:
            errors.append("spillGovernance.ledger.requiredFields must be a non-empty list")
        else:
            for verb in ("trace", "locate", "clean", "migrate"):
                if verb not in fields:
                    errors.append(f"spillGovernance.ledger.requiredFields drops the {verb} verb")
    for key, value in EXPECTED.items():
        if contract.get(key) != value:
            errors.append(f"contract {key} must be {value}")
    if contract.get("platformNeutral") is not True:
        errors.append("platformNeutral must be true")
    if ".work-lab" not in contract.get("legacyAliases", []):
        errors.append("legacy .work-lab alias must be explicitly input-only")
    if not any(line.strip() == ".project-local/" for line in (root / ".gitignore").read_text(encoding="utf-8").splitlines()):
        errors.append(".project-local/ must be ignored")
    if projects.get("generatedData", {}).get("evidencePath") != ".project-local/artifacts":
        errors.append("projects generatedData.evidencePath must use .project-local/artifacts")
    if projects.get("generatedData", {}).get("runtimeRoot") != EXPECTED["runtimeRoot"]:
        errors.append("projects generatedData.runtimeRoot must use .project-local/runs")
    if projects.get("generatedData", {}).get("taskArtifactsPath") != EXPECTED["taskArtifactsRoot"]:
        errors.append("projects generatedData.taskArtifactsPath must use .project-local/artifacts")
    if projects.get("forbiddenRoots") != ["E:\\", "F:\\"]:
        errors.append("projects forbiddenRoots must preserve E:/F: protection")
    return errors


def main() -> int:
    errors = verify(Path(__file__).resolve().parents[2])
    if errors:
        for error in errors:
            print(f"PROJECT_DATA_BOUNDARY_FAIL {error}")
        return 1
    print("PROJECT_DATA_BOUNDARY_PASS runtime=.project-local/runs evidence=.project-local/artifacts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
