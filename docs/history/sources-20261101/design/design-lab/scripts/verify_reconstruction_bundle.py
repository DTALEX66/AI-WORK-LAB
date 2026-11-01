#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute one real C5 -> C6 fixture and validate its exact evidence bundle."""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import uuid
from pathlib import Path

DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DESIGN_LAB.parent
TESTS = DESIGN_LAB / "tests"
sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.evidence import package_evidence, seal_bundle, check_sealed, validate_bundle  # noqa: E402
from reconstruction.pipeline import run_reconstruction  # noqa: E402
from reconstruction.state import canonical_json_bytes  # noqa: E402
from test_reconstruction_pipeline import _create_contract  # noqa: E402


def _package_artifact(artifact_id: str, path: str) -> dict:
    return {"id": artifact_id, "kind": "package", "path": path}


def _remove_exact(path: Path, parent: Path) -> None:
    lexical = Path(os.path.abspath(os.fspath(path)))
    boundary = Path(os.path.abspath(os.fspath(parent)))
    try:
        lexical.relative_to(boundary)
    except ValueError:
        raise RuntimeError(f"cleanup target escapes fixture boundary: {lexical}") from None
    if not (lexical.exists() or lexical.is_symlink()):
        return
    def is_reparse(member: Path) -> bool:
        metadata = member.lstat()
        attributes = int(getattr(metadata, "st_file_attributes", 0))
        flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
        return member.is_symlink() or bool(attributes & flag)

    if is_reparse(lexical):
        raise RuntimeError(f"refusing fixture cleanup through reparse target: {lexical}")
    if lexical.is_file():
        lexical.unlink()
    else:
        for current_raw, dirs, names in os.walk(lexical, topdown=False, followlinks=False):
            current = Path(current_raw)
            for name in names:
                member = current / name
                if is_reparse(member):
                    raise RuntimeError(f"fixture cleanup found reparse residue: {member}")
                member.unlink()
            for name in dirs:
                member = current / name
                if is_reparse(member):
                    raise RuntimeError(f"fixture cleanup found reparse residue: {member}")
                member.rmdir()
        lexical.rmdir()
    if lexical.exists() or lexical.is_symlink():
        raise RuntimeError(f"fixture cleanup residue remains: {lexical}")


def _fixture() -> tuple[Path, Path, Path]:
    contract_path, run_dir, contract = _create_contract(
        "bundle-verifier-" + uuid.uuid4().hex
    )
    evidence_rel = contract["roots"]["evidence"]
    evidence_dir = PROJECT_ROOT.joinpath(*Path(evidence_rel.rstrip("/")).parts)
    model_registry = run_dir / "models.json"
    model_registry.write_bytes(
        canonical_json_bytes(
            {"schemaVersion": "design-lab/reconstruction-models/v1", "models": []}
        )
    )
    model_rel = model_registry.relative_to(PROJECT_ROOT).as_posix()
    contract["registries"]["modelRegistry"] = model_rel
    contract["artifacts"].append(_package_artifact("model-registry", model_rel))
    names = (
        "manifest.json",
        "reference.normalized.png",
        "master.svg",
        "preview.png",
        "metrics.json",
        "diff.png",
        "journal.json",
        "run.contract.json",
        "structure-report.json",
        "provenance.json",
        "registries/tool-registry.json",
        "registries/model-registry.json",
    )
    for index, name in enumerate(names):
        contract["artifacts"].append(
            _package_artifact(f"bundle-{index:02d}", evidence_rel + name)
        )
    contract["writeAuthorization"]["targets"] = [
        item["path"] for item in contract["artifacts"]
    ]
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return contract_path, run_dir, evidence_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="run the real 64x64 deterministic pipeline before validating the bundle",
    )
    parser.parse_args()
    contract_path: Path | None = None
    run_dir: Path | None = None
    evidence_dir: Path | None = None
    exit_code = 1
    summary = "RECONSTRUCTION_BUNDLE=FAIL artifacts=0 state=BLOCKED reason=fixture-not-run"
    try:
        contract_path, run_dir, evidence_dir = _fixture()
        run = run_reconstruction(contract_path)
        if run.state != "PIXEL_VERIFIED_DETERMINISTIC" or not run.passed:
            raise RuntimeError(f"fixture pipeline did not pass: {run.state}")
        packaged = package_evidence(run_dir, evidence_dir)
        validated = validate_bundle(evidence_dir)
        if packaged != validated:
            raise RuntimeError("packager and independent validator summaries diverge")
        seal = seal_bundle(evidence_dir)
        missing = check_sealed(seal)
        if missing:
            raise RuntimeError("R0-004: promoted bundle is not sealed: " + "; ".join(missing))
        summary = (
            "RECONSTRUCTION_BUNDLE=PASS "
            f"artifacts={validated.artifact_count} state={validated.state} "
            f"seal={seal['bundle_sha256'][:12]}"
        )
        exit_code = 0
    except Exception as exc:
        summary = f"RECONSTRUCTION_BUNDLE=FAIL artifacts=0 state=BLOCKED reason={exc}"
        exit_code = 1
    finally:
        cleanup_errors: list[BaseException] = []
        for path, parent in (
            (evidence_dir, PROJECT_ROOT / ".project-local" / "task-artifacts" / "reconstruction"),
            (run_dir, PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction"),
            (contract_path, PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction"),
        ):
            if path is None:
                continue
            try:
                _remove_exact(path, parent)
            except BaseException as cleanup:
                cleanup_errors.append(cleanup)
        if cleanup_errors:
            summary = (
                "RECONSTRUCTION_BUNDLE=FAIL artifacts=0 state=BLOCKED "
                f"reason=fixture-cleanup-residue count={len(cleanup_errors)}"
            )
            exit_code = 1
    print(summary)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
