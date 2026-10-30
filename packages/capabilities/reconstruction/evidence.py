# SPDX-License-Identifier: MIT
"""Fail-closed reconstruction evidence packaging and bundle validation."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from defusedxml import ElementTree as DefusedET
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import best_match
from PIL import Image

from . import runtime_roots
from .contracts import validate_rir
from .metrics import FidelityMetrics, compare_images
from .pipeline import PINNED_RESVG_BINARY
from .render import RenderError, load_render_profile, render_svg
from .state import (
    PROJECT_ROOT,
    ArtifactObservation,
    PipelineStateError,
    artifact_for_role,
    canonical_json_bytes,
    capture_contract_authority,
    contract_path,
    load_contract,
    load_state,
    read_bounded,
    revalidate_loaded_state,
    sha256_bytes,
    sha256_file,
    snapshot_artifact,
    verify_artifact_snapshot,
    verify_contract_authority,
)
from .svg_safety import (
    UnsafeSVGError,
    sanitize_svg,
    stroke_visual_padding,
    validate_path_data,
)

BUNDLE_SCHEMA_ID = "design-lab/reconstruction-bundle/v1"
STRUCTURE_SCHEMA_ID = "design-lab/reconstruction-structure/v1"
PROVENANCE_SCHEMA_ID = "design-lab/reconstruction-provenance/v1"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_BUNDLE_FILES = 256
MAX_JSON_DEPTH = 64

_SCHEMA_PATH = (
    PROJECT_ROOT
    / "design-lab"
    / "schemas"
    / "reconstruction"
    / "reconstruction-bundle.schema.json"
)
_RUN_SCHEMA_PATH = _SCHEMA_PATH.with_name("reconstruction-run.schema.json")
_REQUIRED_DETERMINISTIC = {
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
}
_EXECUTION_CLOSURE_VERSION = "c6-execution-closure-v3"
_EXECUTION_FIXED_PATHS = {
    "design-lab/config/reconstruction-tools.json",
    "design-lab/scripts/reconstruct_design.py",
    "design-lab/scripts/verify_design_lab.py",
    "design-lab/scripts/verify_reconstruction_pipeline.py",
    "design-lab/scripts/verify_reconstruction_bundle.py",
    "design-lab/tests/test_reconstruction_evidence.py",
    "design-lab/tests/test_reconstruction_pipeline.py",
    "design-lab/tests/fixtures/reconstruction/flat-64.png",
}
_PRIVATE_KEYS = {
    "prompt", "promptbody", "promptid", "prompttext", "responsebody",
    "session", "sessionid", "sessiontoken", "credential", "credentials",
    "password", "privatekey", "privateruntime", "cookie", "cookies",
    "auth", "authorization", "authstore", "browserstate", "token",
    "accesstoken", "apikey", "apitoken", "bearertoken", "clientsecret",
    "csrftoken", "refreshtoken", "idtoken",
}
_PRIVATE_VALUE = re.compile(
    r"(?:^|[\s;,'\"(<>=])(?:"
    r"(?:prompt|session(?:id)?|access[_ -]?token|token|cookie|auth(?:orization)?|"
    r"password|credentials?|api[_ -]?key|client[_ -]?secret|private[_ -]?key)\s*[:=]"
    r"|bearer(?:\s+token)?\s+\S+)",
    re.IGNORECASE,
)
_ABSOLUTE_PATH = re.compile(
    r"(?:^|[\s\"'(<>=])(?:file:(?:/{2,3}|\\\\)|[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/]|/|~[\\/])",
    re.IGNORECASE,
)
_TRANSIENT_PART = re.compile(
    r"(?:^|[._-])(?:debug|cache|temp|tmp|session|prompt|trace|credential|token)(?:[._-]|$)",
    re.IGNORECASE,
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
_DATA_PNG = "data:image/png;base64,"
_GEOMETRY_TOLERANCE = 1e-9


def _canonical_svg_id(value: str) -> str:
    return "rir-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


class EvidenceError(RuntimeError):
    """Evidence is incomplete, untrusted, or inconsistent."""


class EvidenceBlockedError(EvidenceError):
    """Packaging failed and exact compensation or cleanup could not be proven."""


@dataclass(frozen=True)
class BundleSummary:
    bundle_dir: Path
    run_id: str
    state: str
    artifact_count: int
    passed: bool
    manifest_sha256: str
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundleDir": os.fspath(self.bundle_dir),
            "runId": self.run_id,
            "state": self.state,
            "artifactCount": self.artifact_count,
            "passed": self.passed,
            "manifestSha256": self.manifest_sha256,
            "failureReason": self.failure_reason,
        }


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & flag)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _assert_plain_ancestry(path: Path, root: Path, *, may_be_missing: bool) -> Path:
    lexical = _absolute(path)
    boundary = _absolute(root)
    if not _within(lexical, boundary):
        raise EvidenceError(f"path escapes exact evidence boundary: {lexical}")
    current = boundary
    if current.exists() and _is_reparse(current):
        raise EvidenceError(f"evidence root is a symlink/reparse point: {current}")
    for part in lexical.relative_to(boundary).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _is_reparse(current):
                raise EvidenceError(f"path contains a symlink/reparse point: {current}")
        elif not may_be_missing:
            raise EvidenceError(f"required evidence path is absent: {current}")
    return lexical


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r}")


def _no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _depth(value: Any) -> int:
    maximum = 0
    stack = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        maximum = max(maximum, depth)
        if maximum > MAX_JSON_DEPTH:
            return maximum
        if isinstance(current, dict):
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
    return maximum


def _strict_json(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    try:
        payload = read_bounded(path, label=label, max_bytes=MAX_JSON_BYTES)
        value = json.loads(
            payload.decode("utf-8", errors="strict"),
            parse_constant=_reject_constant,
            object_pairs_hook=_no_duplicates,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, PipelineStateError) as exc:
        raise EvidenceError(f"{label} is not strict JSON: {exc}") from None
    if not isinstance(value, dict):
        raise EvidenceError(f"{label} must be a JSON object")
    if _depth(value) > MAX_JSON_DEPTH:
        raise EvidenceError(f"{label} exceeds the bounded JSON nesting depth")
    return value, payload


def _strict_json_bound(
    path: Path, *, label: str, observation: ArtifactObservation, root: Path
) -> tuple[dict[str, Any], bytes]:
    value, payload = _strict_json(path, label=label)
    if sha256_bytes(payload) != observation.sha256 or len(payload) != observation.size:
        raise EvidenceError(f"{label} bytes changed between manifest binding and parse")
    try:
        verify_artifact_snapshot(observation, root)
    except PipelineStateError as exc:
        raise EvidenceError(f"{label} identity changed during parse: {exc}") from exc
    return value, payload


def _schema_validator() -> Draft202012Validator:
    schema, _ = _strict_json(_SCHEMA_PATH, label="bundle schema")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _historical_contract_schema(contract: dict[str, Any]) -> None:
    schema, _ = _strict_json(_RUN_SCHEMA_PATH, label="run contract schema")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    error = best_match(validator.iter_errors(contract))
    if error is not None:
        raise EvidenceError(f"copied run contract schema violation: {error.message}")


def _schema_error(value: dict[str, Any]) -> None:
    error = best_match(_schema_validator().iter_errors(value))
    if error is not None:
        location = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
        raise EvidenceError(f"bundle manifest schema violation at {location}: {error.message}")


def _safe_relative(value: str, *, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise EvidenceError(f"{label} must be one non-empty POSIX relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise EvidenceError(f"{label} contains absolute, dot, or traversal segments")
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", value):
        raise EvidenceError(f"{label} contains a URI scheme or drive path")
    return pure


def _enumerate_files(root: Path) -> dict[str, Path]:
    root = _assert_plain_ancestry(root, PROJECT_ROOT, may_be_missing=False)
    if not root.is_dir() or _is_reparse(root):
        raise EvidenceError("bundle root must be one plain directory")
    files: dict[str, Path] = {}
    total = 0
    for current_raw, dirs, names in os.walk(root, followlinks=False):
        current = Path(current_raw)
        for name in dirs:
            directory = current / name
            if _is_reparse(directory):
                raise EvidenceError(f"bundle directory is a symlink/reparse point: {directory}")
        for name in names:
            path = current / name
            if _is_reparse(path):
                raise EvidenceError(f"bundle member is a symlink/reparse point: {path}")
            try:
                metadata = path.stat()
            except OSError as exc:
                raise EvidenceError(f"cannot inspect bundle member {path}: {exc}") from exc
            if not path.is_file() or int(getattr(metadata, "st_nlink", 1)) != 1:
                raise EvidenceError(f"bundle member must be one regular non-hardlinked file: {path}")
            if metadata.st_size > MAX_ARTIFACT_BYTES:
                raise EvidenceError(f"bundle member exceeds the bounded file-size limit: {path}")
            relative = path.relative_to(root).as_posix()
            _safe_relative(relative, label="bundle member path")
            files[relative] = path
            total += metadata.st_size
            if len(files) > MAX_BUNDLE_FILES or total > MAX_BUNDLE_BYTES:
                raise EvidenceError("bundle exceeds the bounded file-count or byte limit")
    return files


def _media_type(path: str) -> str:
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".svg"):
        return "image/svg+xml"
    if path.endswith(".json"):
        return "application/json"
    if path.endswith(".ai"):
        return "application/vnd.adobe.illustrator"
    raise EvidenceError(f"unsupported bundle artifact media type: {path}")


def _snapshot(path: Path, root: Path, *, expected: str | None = None) -> ArtifactObservation:
    try:
        return snapshot_artifact(path, root, expected_sha256=expected)
    except PipelineStateError as exc:
        raise EvidenceError(str(exc)) from exc


def _scan_report_privacy(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized_key in _PRIVATE_KEYS:
                raise EvidenceError(f"private prompt/session/runtime material is forbidden at {path}.{key}")
            _scan_report_privacy(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_report_privacy(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if _ABSOLUTE_PATH.search(value):
            raise EvidenceError(f"absolute filesystem path is forbidden in bundle reports at {path}")
        if _PRIVATE_VALUE.search(value):
            raise EvidenceError(f"private prompt/session/auth payload is forbidden at {path}")


def _required_keys(value: dict[str, Any], expected: set[str], *, label: str) -> None:
    if set(value) != expected:
        raise EvidenceError(f"{label} has an open or incomplete shape")


def _finite_number(value: Any, *, label: str, minimum: float | None = None, maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvidenceError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise EvidenceError(f"{label} must be finite")
    if minimum is not None and number < minimum:
        raise EvidenceError(f"{label} is below its minimum")
    if maximum is not None and number > maximum:
        raise EvidenceError(f"{label} is above its maximum")
    return number


def _artifact_records(
    manifest: dict[str, Any], files: dict[str, Path], root: Path
) -> tuple[dict[str, dict[str, Any]], dict[str, ArtifactObservation]]:
    records: dict[str, dict[str, Any]] = {}
    for record in manifest["artifacts"]:
        relative = record["path"]
        _safe_relative(relative, label="manifest artifact path")
        if relative == "manifest.json":
            raise EvidenceError(
                "manifest.json is the non-self-hashed control file and must not appear in artifacts[]"
            )
        if relative in records:
            raise EvidenceError(f"duplicate manifest artifact path: {relative}")
        records[relative] = record
    expected = {"manifest.json", *records}
    if set(files) != expected:
        missing = sorted(expected - set(files))
        extra = sorted(set(files) - expected)
        raise EvidenceError(f"bundle topology mismatch missing={missing} extra={extra}")
    observations: dict[str, ArtifactObservation] = {}
    for relative, record in records.items():
        path = files[relative]
        expected_type = _media_type(relative)
        if record["mediaType"] != expected_type:
            raise EvidenceError(f"artifact media type mismatch for {relative}")
        observation = _snapshot(path, root, expected=record["sha256"])
        observations[relative] = observation
        if observation.size != record["byteSize"]:
            raise EvidenceError(f"artifact byte size mismatch for {relative}")
        if expected_type == "image/png":
            try:
                with Image.open(path) as image:
                    if image.format != "PNG":
                        raise EvidenceError(f"artifact is not a decoded PNG: {relative}")
                    image.verify()
            except (OSError, ValueError) as exc:
                raise EvidenceError(f"artifact PNG is corrupt: {relative}: {exc}") from None
            try:
                verify_artifact_snapshot(observation, root)
            except PipelineStateError as exc:
                raise EvidenceError(f"artifact identity changed during PNG validation: {relative}: {exc}") from exc
    deterministic_owners = {
        "reference.normalized.png": ("intake", "normalized-source"),
        "master.svg": ("reconstruction", "canonical-vector"),
        "preview.png": ("deterministic-render", "deterministic-evidence"),
        "metrics.json": ("deterministic-metrics", "deterministic-evidence"),
        "diff.png": ("deterministic-metrics", "deterministic-evidence"),
        "journal.json": ("pipeline-state", "run-control"),
        "run.contract.json": ("pipeline-state", "run-control"),
        "structure-report.json": ("evidence-package", "bundle-report"),
        "provenance.json": ("evidence-package", "bundle-report"),
        "registries/tool-registry.json": ("evidence-package", "run-control"),
        "registries/model-registry.json": ("evidence-package", "run-control"),
    }
    for relative, expected in deterministic_owners.items():
        if relative in records and (
            records[relative]["producerPhase"], records[relative]["ownershipClass"]
        ) != expected:
            raise EvidenceError(f"artifact producer/ownership mismatch for {relative}")
    for relative, record in records.items():
        if relative.startswith("layers/") and (
            record["producerPhase"], record["ownershipClass"]
        ) != ("reconstruction", "semantic-raster"):
            raise EvidenceError(f"semantic raster producer/ownership mismatch for {relative}")
    release_owners = {
        "master.ai": ("adobe-illustrator", "native-deliverable"),
        "preview.illustrator.png": ("adobe-illustrator", "host-readback"),
        "illustrator-readback.json": ("adobe-illustrator", "host-readback"),
        "golden-corpus.json": ("release-qualification", "release-evidence"),
        "exact-sha-ci.json": ("release-qualification", "release-evidence"),
        "rights.json": ("release-qualification", "release-evidence"),
        "installed-runtime.json": ("release-qualification", "release-evidence"),
    }
    for relative, expected in release_owners.items():
        if relative in records and (
            records[relative]["producerPhase"], records[relative]["ownershipClass"]
        ) != expected:
            raise EvidenceError(f"release artifact producer/ownership mismatch for {relative}")
    return records, observations


def _contract_semantics(
    contract: dict[str, Any], manifest: dict[str, Any], journal: dict[str, Any],
    records: dict[str, dict[str, Any]], declared_root: Path,
) -> tuple[str, dict[str, dict[str, Any]]]:
    _historical_contract_schema(contract)
    if contract.get("schemaVersion") != "design-lab/reconstruction-run/v1":
        raise EvidenceError("run contract schema version mismatch")
    run_id = manifest["runId"]
    if contract.get("runId") != run_id or journal.get("runId") != run_id:
        raise EvidenceError("bundle run identity does not bind contract and journal")
    expected_runtime = runtime_roots.runtime_root(run_id)
    expected_evidence = runtime_roots.evidence_root(run_id)
    if contract.get("roots") != {"runtime": expected_runtime, "evidence": expected_evidence}:
        raise EvidenceError("copied contract does not declare canonical runtime/evidence roots")
    expected_root_path = PROJECT_ROOT.joinpath(*PurePosixPath(expected_evidence.rstrip("/")).parts)
    if _absolute(declared_root) != _absolute(expected_root_path):
        raise EvidenceError("bundle is not the contract's exact declared evidence root")
    artifacts = contract.get("artifacts")
    if not isinstance(artifacts, list):
        raise EvidenceError("run contract artifact declarations are malformed")
    by_path: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            raise EvidenceError("run contract contains a malformed artifact declaration")
        if item["path"] in by_path:
            raise EvidenceError("run contract contains a duplicate artifact path")
        by_path[item["path"]] = item
    bundle_targets = {expected_evidence + "manifest.json"}
    bundle_targets.update(expected_evidence + relative for relative in records)
    if not bundle_targets.issubset(by_path):
        raise EvidenceError("bundle contains a target not exactly declared by the run contract")
    authorization = contract.get("writeAuthorization", {})
    targets = authorization.get("targets")
    if (
        authorization.get("runId") != run_id
        or authorization.get("jobId") != contract.get("jobId")
        or authorization.get("state") != "authorized"
        or not isinstance(targets, list)
        or set(targets) != set(by_path)
        or len(targets) != len(by_path)
    ):
        raise EvidenceError("run contract write authorization is not exact and identity-bound")
    contract_sha = sha256_bytes(canonical_json_bytes(contract))
    if journal.get("contractSha256") != contract_sha:
        raise EvidenceError("journal does not bind the copied canonical run contract")
    return contract_sha, by_path


def _journal_semantics(
    journal: dict[str, Any], contract: dict[str, Any], records: dict[str, dict[str, Any]]
) -> None:
    _required_keys(
        journal,
        {"schemaVersion", "runId", "contractSha256", "entries", "createdArtifacts"},
        label="pipeline journal",
    )
    if journal["schemaVersion"] != "design-lab/reconstruction-journal/v1":
        raise EvidenceError("pipeline journal schema version mismatch")
    created = journal["createdArtifacts"]
    if not isinstance(created, list) or len(created) != len(set(created)) or len(created) > 64:
        raise EvidenceError("pipeline journal created-artifact ledger is malformed")
    for relative in created:
        _safe_relative(relative, label="pipeline journal created artifact")
    entries = journal["entries"]
    if not isinstance(entries, list) or not entries or len(entries) > 8:
        raise EvidenceError("pipeline journal entry count is invalid")
    prior_state: str | None = None
    for sequence, entry in enumerate(entries, 1):
        if not isinstance(entry, dict):
            raise EvidenceError("pipeline journal contains a malformed entry")
        _required_keys(
            entry,
            {
                "sequence", "timestampUtc", "priorState", "newState", "phase", "accepted", "reason",
                "inputHashes", "outputHashes", "checkpoint",
            },
            label=f"pipeline journal entry {sequence}",
        )
        checkpoint_ref = entry["checkpoint"]
        if not isinstance(checkpoint_ref, dict):
            raise EvidenceError("pipeline journal checkpoint reference is malformed")
        _required_keys(checkpoint_ref, {"path", "sha256"}, label=f"journal checkpoint {sequence}")
        for field in ("inputHashes", "outputHashes"):
            values = entry[field]
            if not isinstance(values, dict) or len(values) > 64:
                raise EvidenceError(f"pipeline journal {field} is malformed")
            for relative, digest in values.items():
                _safe_relative(relative, label=f"pipeline journal {field} path")
                if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
                    raise EvidenceError(f"pipeline journal {field} hash is malformed")
        if entry.get("sequence") != sequence or entry.get("accepted") is not True:
            raise EvidenceError("pipeline journal sequence or acceptance is invalid")
        if sequence == 1:
            if entry.get("priorState") is not None or entry.get("newState") != "CREATED":
                raise EvidenceError("pipeline journal must start at CREATED")
        elif entry.get("priorState") != prior_state:
            raise EvidenceError("pipeline journal transition chain is discontinuous")
        prior_state = entry.get("newState")
    last = entries[-1]
    if last.get("newState") != "PIXEL_VERIFIED_DETERMINISTIC":
        raise EvidenceError("pipeline journal does not end at PIXEL_VERIFIED_DETERMINISTIC")
    role_to_bundle = {
        "normalized-reference": "reference.normalized.png",
        "sanitized-svg": "master.svg",
        "render-preview": "preview.png",
        "diff-evidence": "diff.png",
        "pipeline-metrics": "metrics.json",
    }
    outputs = last.get("outputHashes")
    if not isinstance(outputs, dict):
        raise EvidenceError("pipeline journal final output hash map is malformed")
    for role, bundle_path in role_to_bundle.items():
        try:
            declaration = artifact_for_role(contract, role)
        except PipelineStateError as exc:
            raise EvidenceError(f"run contract artifact role topology is invalid: {exc}") from exc
        assert isinstance(declaration, dict)
        if outputs.get(declaration["path"]) != records[bundle_path]["sha256"]:
            raise EvidenceError(f"pipeline journal hash does not bind {bundle_path}")


def _metrics_semantics(
    metrics: dict[str, Any], records: dict[str, dict[str, Any]], provenance: dict[str, Any],
    state: str,
) -> None:
    base_keys = {
        "schemaVersion", "profileId", "pixelmatchVersion", "pixelThreshold",
        "antiAliasDetection", "matchMinimum", "ssimMinimum", "maeLimitVersion",
        "maeLimit", "edgeMetric", "width", "height", "matchRatio", "mismatchCount",
        "excludedAaCount", "ssim", "meanRgbaError", "alphaMeanError", "edgeError",
        "maxDiffWindow", "components", "denseRegions", "failureReasons", "passed",
        "lifecycleStatus", "registryDigest", "metricMaxPixels", "metricMaxBytes",
        "metricBudgetVersion", "referenceSha256", "previewSha256", "diffSha256",
        "mismatchMaskSha256", "excludedAaMaskSha256", "inputAuthority",
        "inputBindings", "referenceIcc", "actualIcc",
    }
    expected_keys = set(base_keys)
    if state in {"DELIVERY_CANDIDATE_UNVERIFIED_EXTERNAL", "DELIVERY_READY"}:
        expected_keys.add("illustratorMetrics")
        if "illustratorMetrics" not in metrics:
            raise EvidenceError("local delivery candidate requires complete Illustrator metrics")
    _required_keys(metrics, expected_keys, label="deterministic C4 metrics")
    for field in (
        "width", "height", "mismatchCount", "excludedAaCount", "maxDiffWindow",
        "metricMaxPixels", "metricMaxBytes",
    ):
        if isinstance(metrics[field], bool) or not isinstance(metrics[field], int):
            raise EvidenceError(f"metrics.{field} must be an exact integer")
    component_keys = {"bounds", "pixel_count", "density"}
    for field in ("components", "denseRegions"):
        if not isinstance(metrics[field], list):
            raise EvidenceError(f"metrics.{field} must be a list")
        for index, component in enumerate(metrics[field]):
            if not isinstance(component, dict):
                raise EvidenceError(f"metrics.{field}[{index}] is malformed")
            _required_keys(component, component_keys, label=f"metrics.{field}[{index}]")
            if (
                not isinstance(component["bounds"], list)
                or len(component["bounds"]) != 4
                or any(isinstance(value, bool) or not isinstance(value, int) for value in component["bounds"])
                or isinstance(component["pixel_count"], bool)
                or not isinstance(component["pixel_count"], int)
            ):
                raise EvidenceError(f"metrics.{field}[{index}] geometry/count is malformed")
            _finite_number(component["density"], label=f"metrics.{field}[{index}].density", minimum=0, maximum=1)
    if not isinstance(metrics["inputBindings"], list) or len(metrics["inputBindings"]) != 2:
        raise EvidenceError("metrics input bindings must contain two exact records")
    for index, binding in enumerate(metrics["inputBindings"]):
        if not isinstance(binding, dict):
            raise EvidenceError("metrics input binding is malformed")
        _required_keys(binding, {"path", "role", "producer", "sha256"}, label=f"metrics.inputBindings[{index}]")
        _safe_relative(binding["path"], label=f"metrics.inputBindings[{index}].path")
        if not _SHA256.fullmatch(binding["sha256"]):
            raise EvidenceError("metrics input binding hash is malformed")
    icc_keys = {"profileId", "profileSha256", "rawSha256", "canonicalSha256", "canonicalization"}
    for field in ("referenceIcc", "actualIcc"):
        if not isinstance(metrics[field], dict):
            raise EvidenceError(f"metrics.{field} is malformed")
        _required_keys(metrics[field], icc_keys, label=f"metrics.{field}")
    fixed = {
        "schemaVersion": "design-lab/reconstruction-metrics/v1",
        "profileId": "design-lab/render-profile/v1",
        "pixelmatchVersion": "7.2.0",
        "pixelThreshold": 0.1,
        "antiAliasDetection": True,
        "matchMinimum": 0.995,
        "ssimMinimum": 0.995,
        "metricMaxPixels": 4194304,
        "metricMaxBytes": 67108864,
        "metricBudgetVersion": "c4-metric-memory-v1",
        "inputAuthority": "CONTRACT_BOUND_AUTHORITATIVE",
        "lifecycleStatus": "PIXEL_VERIFIED_DETERMINISTIC",
        "passed": True,
    }
    for key, expected in fixed.items():
        if metrics.get(key) != expected:
            raise EvidenceError(f"metrics fixed-profile field mismatch: {key}")
    if _finite_number(metrics.get("matchRatio"), label="metrics.matchRatio") < 0.995:
        raise EvidenceError("metrics match ratio does not pass")
    if _finite_number(metrics.get("ssim"), label="metrics.ssim") < 0.995:
        raise EvidenceError("metrics SSIM does not pass")
    if metrics.get("denseRegions") != [] or metrics.get("failureReasons") != []:
        raise EvidenceError("metrics retain an unresolved dense region or failure")
    expected_hashes = {
        "referenceSha256": records["reference.normalized.png"]["sha256"],
        "previewSha256": records["preview.png"]["sha256"],
        "diffSha256": records["diff.png"]["sha256"],
    }
    for key, expected in expected_hashes.items():
        if metrics.get(key) != expected:
            raise EvidenceError(f"metrics {key} does not agree with the manifest")
    tool = provenance.get("registries", {}).get("tool", {})
    if metrics.get("registryDigest") != tool.get("sha256"):
        raise EvidenceError("metrics renderer registry digest does not agree with provenance")
    illustrator = metrics.get("illustratorMetrics")
    if state in {"DELIVERY_CANDIDATE_UNVERIFIED_EXTERNAL", "DELIVERY_READY"}:
        expected_fields = {
            "profileId", "referenceSha256", "previewSha256", "matchRatio", "ssim",
            "meanRgbaError", "denseRegions", "passed",
        }
        if not isinstance(illustrator, dict) or set(illustrator) != expected_fields:
            raise EvidenceError("local delivery candidate requires complete Illustrator metrics")
        if (
            illustrator["profileId"] != fixed["profileId"]
            or illustrator["referenceSha256"] != records["reference.normalized.png"]["sha256"]
            or illustrator["previewSha256"] != records.get("preview.illustrator.png", {}).get("sha256")
            or illustrator["passed"] is not True
            or illustrator["denseRegions"] != []
            or _finite_number(illustrator["matchRatio"], label="illustrator.matchRatio") < 0.995
            or _finite_number(illustrator["ssim"], label="illustrator.ssim") < 0.995
        ):
            raise EvidenceError("Illustrator metrics do not pass the fixed profile")
        _finite_number(
            illustrator["meanRgbaError"], label="illustrator.meanRgbaError", minimum=0
        )
    elif illustrator is not None:
        raise EvidenceError("deterministic bundle cannot carry unqualified Illustrator metrics")


def _structure_semantics(
    structure: dict[str, Any], records: dict[str, dict[str, Any]], manifest: dict[str, Any],
    files: dict[str, Path],
) -> Counter[str]:
    _required_keys(
        structure,
        {
            "schemaVersion", "runId", "profile", "canvas", "objects",
            "rasterCoveredCanvasArea", "rasterCoveredCanvasRatio", "semanticRasterLayers",
        },
        label="structure report",
    )
    if structure["schemaVersion"] != STRUCTURE_SCHEMA_ID or structure["runId"] != manifest["runId"]:
        raise EvidenceError("structure report identity mismatch")
    if structure["profile"] not in {"flat", "ui", "mixed", "photographic"}:
        raise EvidenceError("structure report reconstruction profile is invalid")
    canvas = structure["canvas"]
    canvas_keys = {"width", "height", "colorSpace"}
    if not isinstance(canvas, dict) or frozenset(canvas) not in {
        frozenset(canvas_keys), frozenset(canvas_keys | {"background"})
    }:
        raise EvidenceError("structure report canvas is malformed")
    width = _finite_number(canvas.get("width"), label="structure.canvas.width", minimum=1)
    height = _finite_number(canvas.get("height"), label="structure.canvas.height", minimum=1)
    expected_dimensions = (int(width), int(height))
    if width != expected_dimensions[0] or height != expected_dimensions[1]:
        raise EvidenceError("structure report canvas dimensions must be integers")
    background = canvas.get("background")
    if background is not None:
        if (
            not isinstance(background, dict)
            or set(background) != {"color", "recorded"}
            or not isinstance(background.get("color"), str)
            or not background["color"]
            or len(background["color"]) > 128
            or background.get("recorded") is not True
        ):
            raise EvidenceError("structure report canvas background is malformed")
    for relative in ("reference.normalized.png", "preview.png", "diff.png"):
        with Image.open(files[relative]) as image:
            if image.size != expected_dimensions:
                raise EvidenceError(f"{relative} dimensions do not match the structure canvas")
    objects = structure["objects"]
    if not isinstance(objects, list) or len(objects) > 100000:
        raise EvidenceError("structure report object ledger is malformed")
    ids: set[str] = set()
    raster_rectangles: list[tuple[float, float, float, float]] = []
    raster_paths: list[str] = []
    raster_path_set: set[str] = set()
    raster_hashes: Counter[str] = Counter()
    for index, item in enumerate(objects):
        if not isinstance(item, dict):
            raise EvidenceError("structure report object is malformed")
        required = {
            "id", "svgId", "parentId", "order", "type", "vectorType", "bounds", "opacity",
            "blendMode", "masks", "textDisposition", "sourceMapping", "inferred",
            "visible", "locked", "raster",
        }
        _required_keys(item, required, label=f"structure object {index}")
        object_id = item["id"]
        if not isinstance(object_id, str) or not object_id or object_id in ids:
            raise EvidenceError("structure report object IDs must be unique and non-empty")
        ids.add(object_id)
        if item["svgId"] != _canonical_svg_id(object_id):
            raise EvidenceError("structure SVG ID is not the canonical logical-ID projection")
        if item["order"] != index:
            raise EvidenceError("structure report object order must be canonical and contiguous")
        if item["parentId"] is not None and item["parentId"] not in ids:
            raise EvidenceError("structure report parent must precede the child")
        if item["type"] not in {"group", "path", "primitive", "text", "raster"}:
            raise EvidenceError("structure report object type is unknown")
        allowed_vector_types = {
            "group", "path", "primitive-rect", "primitive-ellipse", "primitive-line",
            "primitive-polygon", "text-live", "text-outlined", "text-hybrid", "raster",
        }
        if item["vectorType"] not in allowed_vector_types:
            raise EvidenceError("structure report vector/raster type is unknown")
        expected_prefix = (
            item["type"] if item["type"] in {"group", "path", "raster"}
            else item["type"] + "-"
        )
        if not str(item["vectorType"]).startswith(expected_prefix):
            raise EvidenceError("structure object type and vector type disagree")
        if item["blendMode"] not in {"normal", "multiply", "screen", "overlay", "darken", "lighten"}:
            raise EvidenceError("structure report blend mode is unknown")
        if not isinstance(item["visible"], bool) or not isinstance(item["locked"], bool) or not isinstance(item["inferred"], bool):
            raise EvidenceError("structure object boolean state is malformed")
        if not isinstance(item["masks"], list) or item["masks"]:
            raise EvidenceError("structure masks must be the exact currently-supported empty list")
        expected_text = item["vectorType"].removeprefix("text-") if item["type"] == "text" else None
        if item["textDisposition"] != expected_text:
            raise EvidenceError("structure text disposition disagrees with vector type")
        bounds = item["bounds"]
        if not isinstance(bounds, dict) or set(bounds) != {"x", "y", "width", "height"}:
            raise EvidenceError("structure report object bounds are malformed")
        x = _finite_number(bounds["x"], label="object.bounds.x")
        y = _finite_number(bounds["y"], label="object.bounds.y")
        w = _finite_number(bounds["width"], label="object.bounds.width", minimum=0)
        h = _finite_number(bounds["height"], label="object.bounds.height", minimum=0)
        if x < 0 or y < 0 or x + w > width or y + h > height:
            raise EvidenceError("structure object bounds leave the canonical canvas")
        _finite_number(item["opacity"], label="object.opacity", minimum=0, maximum=1)
        if not isinstance(item["sourceMapping"], list):
            raise EvidenceError("structure source mapping must be a list")
        raster = item["raster"]
        if item["type"] == "raster":
            if w <= 0 or h <= 0:
                raise EvidenceError("semantic raster object bounds must have positive width and height")
            if not isinstance(raster, dict):
                raise EvidenceError("raster structure object omits raster evidence")
            expected_raster_keys = {"path", "sha256", "crop", "alphaBounds", "canvasArea", "alpha"}
            _required_keys(raster, expected_raster_keys, label="raster object evidence")
            path = raster["path"]
            if not isinstance(path, str) or not path.startswith("layers/") or path in raster_path_set:
                raise EvidenceError("semantic raster layer path is invalid or duplicated")
            raster_paths.append(path)
            raster_path_set.add(path)
            if path not in records or records[path]["ownershipClass"] != "semantic-raster":
                raise EvidenceError("semantic raster layer is not manifest-declared")
            if raster["sha256"] != records[path]["sha256"]:
                raise EvidenceError("semantic raster layer hash is inconsistent")
            crop = raster["crop"]
            alpha_bounds = raster["alphaBounds"]
            if not isinstance(crop, dict) or set(crop) != {"x", "y", "width", "height"}:
                raise EvidenceError("semantic raster crop is malformed")
            if not isinstance(alpha_bounds, dict) or set(alpha_bounds) != {"x", "y", "width", "height"}:
                raise EvidenceError("semantic raster alpha bounds are malformed")
            with Image.open(files[path]) as image:
                width_px, height_px = image.size
            if crop != {"x": 0, "y": 0, "width": width_px, "height": height_px}:
                raise EvidenceError("semantic raster crop is not tightly bound to PNG dimensions")
            if alpha_bounds != _alpha_bounds(files[path]):
                raise EvidenceError("semantic raster alpha bounds are inconsistent")
            if alpha_bounds != crop:
                raise EvidenceError("semantic raster crop is not tight to decoded alpha bounds")
            if not isinstance(item["sourceMapping"], list) or len(item["sourceMapping"]) != 1:
                raise EvidenceError("semantic raster requires one exact source mapping")
            for mapping in item["sourceMapping"]:
                if not isinstance(mapping, dict) or set(mapping) != {"sourceBounds", "targetBounds"}:
                    raise EvidenceError("semantic raster source mapping is malformed")
                for label, mapped in mapping.items():
                    if not isinstance(mapped, dict) or set(mapped) != {"x", "y", "width", "height"}:
                        raise EvidenceError("semantic raster source-mapping bounds are malformed")
                    for key in ("x", "y", "width", "height"):
                        _finite_number(
                            mapped[key], label=f"sourceMapping.{label}.{key}",
                            minimum=0 if key in {"width", "height"} else None,
                        )
                source_bounds = mapping["sourceBounds"]
                source_x = float(source_bounds["x"])
                source_y = float(source_bounds["y"])
                source_width = float(source_bounds["width"])
                source_height = float(source_bounds["height"])
                if (
                    source_x < 0
                    or source_y < 0
                    or source_x + source_width > width
                    or source_y + source_height > height
                ):
                    raise EvidenceError("semantic raster source region leaves the normalized canvas")
                if (
                    not math.isclose(source_width, float(crop["width"]), rel_tol=0, abs_tol=1e-9)
                    or not math.isclose(source_height, float(crop["height"]), rel_tol=0, abs_tol=1e-9)
                ):
                    raise EvidenceError("semantic raster source region dimensions disagree with the local crop")
                if mapping["targetBounds"] != bounds:
                    raise EvidenceError("semantic raster target mapping does not exactly equal object bounds")
            raster_hashes[raster["sha256"]] += 1
            area = _finite_number(raster["canvasArea"], label="raster.canvasArea", minimum=0)
            if not math.isclose(area, w * h, rel_tol=0, abs_tol=1e-9):
                raise EvidenceError("semantic raster canvas area is inconsistent")
            if x <= 0 and y <= 0 and x + w >= width and y + h >= height:
                raise EvidenceError("full-canvas raster overlay is forbidden")
            _finite_number(raster["alpha"], label="raster.alpha", minimum=0, maximum=1)
            raster_rectangles.append((max(0, x), max(0, y), min(width, x + w), min(height, y + h)))
        elif raster is not None:
            raise EvidenceError("non-raster structure object carries raster evidence")
        elif item["sourceMapping"] != []:
            raise EvidenceError("non-raster structure object cannot carry source mapping")
    declared_layers = structure["semanticRasterLayers"]
    if not isinstance(declared_layers, list) or declared_layers != raster_paths:
        raise EvidenceError("semantic raster layer declaration is inconsistent")
    area = _rectangle_union_area(raster_rectangles)
    reported_area = _finite_number(
        structure["rasterCoveredCanvasArea"], label="rasterCoveredCanvasArea", minimum=0
    )
    ratio = _finite_number(
        structure["rasterCoveredCanvasRatio"], label="rasterCoveredCanvasRatio", minimum=0, maximum=1
    )
    if not math.isclose(area, reported_area, rel_tol=0, abs_tol=1e-9):
        raise EvidenceError("raster-covered canvas area is inconsistent")
    if not math.isclose(ratio, area / (width * height), rel_tol=0, abs_tol=1e-12):
        raise EvidenceError("raster coverage ratio is inconsistent")
    if structure["profile"] in {"flat", "ui"} and ratio > 0.05:
        raise EvidenceError("flat/UI raster-covered canvas area exceeds the five-percent gate")
    return raster_hashes


def _rectangle_union_area(rectangles: Iterable[tuple[float, float, float, float]]) -> float:
    valid = [rect for rect in rectangles if rect[2] > rect[0] and rect[3] > rect[1]]
    xs = sorted({coordinate for rect in valid for coordinate in (rect[0], rect[2])})
    area = 0.0
    for left, right in zip(xs, xs[1:]):
        intervals = sorted(
            (bottom, top)
            for x1, bottom, x2, top in valid
            if x1 < right and x2 > left
        )
        covered = 0.0
        cursor: float | None = None
        end = 0.0
        for bottom, top in intervals:
            if cursor is None:
                cursor, end = bottom, top
            elif bottom > end:
                covered += end - cursor
                cursor, end = bottom, top
            else:
                end = max(end, top)
        if cursor is not None:
            covered += end - cursor
        area += (right - left) * covered
    return area


def _svg_semantics(path: Path, structure: dict[str, Any], expected_rasters: Counter[str]) -> None:
    try:
        payload = read_bounded(path, label="canonical SVG", max_bytes=MAX_ARTIFACT_BYTES)
        sanitized = sanitize_svg(payload)
    except (OSError, PipelineStateError, UnsafeSVGError) as exc:
        raise EvidenceError(f"canonical master.svg is not self-contained safe SVG: {exc}") from None
    try:
        root = DefusedET.fromstring(sanitized)
    except Exception as exc:
        raise EvidenceError(f"canonical SVG cannot be parsed safely: {exc}") from None
    canvas = structure["canvas"]
    embedded: Counter[str] = Counter()
    projected: list[tuple[Any, str | None]] = []
    background = canvas.get("background")
    background_element: Any | None = None
    root_children = list(root)
    if background is not None:
        if not root_children:
            raise EvidenceError("recorded canvas background is absent from canonical SVG")
        background_element = root_children[0]
        local = background_element.tag.rsplit("}", 1)[-1]
        if (
            local != "rect"
            or "id" in background_element.attrib
            or set(background_element.attrib) != {"x", "y", "width", "height", "fill"}
            or background_element.attrib.get("fill") != background["color"]
        ):
            raise EvidenceError("recorded canvas background disagrees with canonical SVG")
        try:
            background_geometry = tuple(
                float(background_element.attrib[key]) for key in ("x", "y", "width", "height")
            )
        except ValueError:
            raise EvidenceError("recorded canvas background geometry is malformed") from None
        expected_background = (0.0, 0.0, float(canvas["width"]), float(canvas["height"]))
        if any(
            not math.isclose(actual, expected, rel_tol=0, abs_tol=_GEOMETRY_TOLERANCE)
            for actual, expected in zip(background_geometry, expected_background)
        ):
            raise EvidenceError("recorded canvas background is not an exact full-canvas SVG rect")

    def walk(element: Any, parent_id: str | None) -> None:
        current_parent = parent_id
        if element is background_element:
            pass
        elif element is not root and "id" not in element.attrib:
            raise EvidenceError("canonical SVG contains an unrecorded anonymous visual element")
        elif "id" in element.attrib:
            projected.append((element, parent_id))
            current_parent = element.attrib["id"]
        for child in list(element):
            walk(child, current_parent)

    walk(root, None)
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "image":
            continue
        href = element.attrib.get("href") or element.attrib.get("{http://www.w3.org/1999/xlink}href")
        if not isinstance(href, str) or not href.startswith(_DATA_PNG):
            raise EvidenceError("canonical SVG contains an external URL/path raster")
        try:
            raster = base64.b64decode(href[len(_DATA_PNG):], validate=True)
        except ValueError:
            raise EvidenceError("canonical SVG contains malformed embedded raster data") from None
        embedded[sha256_bytes(raster)] += 1
        try:
            x = float(element.attrib.get("x", "0"))
            y = float(element.attrib.get("y", "0"))
            width = float(element.attrib["width"])
            height = float(element.attrib["height"])
        except (KeyError, ValueError):
            raise EvidenceError("canonical SVG image geometry is malformed") from None
        if x <= 0 and y <= 0 and width >= canvas["width"] and height >= canvas["height"]:
            raise EvidenceError("full-canvas raster overlay is forbidden")
    if embedded != expected_rasters:
        raise EvidenceError("canonical SVG embedded rasters do not match declared semantic layers")
    objects = structure["objects"]
    if len(projected) != len(objects):
        raise EvidenceError("structure projection does not match SVG object count")
    expected_tags = {
        "group": "g",
        "path": "path",
        "primitive-rect": "rect",
        "primitive-ellipse": "ellipse",
        "primitive-line": "line",
        "primitive-polygon": "polygon",
        "text-live": "text",
        "text-outlined": "path",
        "raster": "image",
    }
    by_id = {item["id"]: item for item in objects}
    visual_bounds: dict[str, tuple[float, float, float, float]] = {}
    reported_bounds: dict[str, tuple[float, float, float, float]] = {}
    for order, ((element, parent_id), item) in enumerate(zip(projected, objects)):
        local = element.tag.rsplit("}", 1)[-1]
        if (
            item["order"] != order
            or element.attrib.get("id") != item["svgId"]
            or parent_id != (
                None if item["parentId"] is None else by_id[item["parentId"]]["svgId"]
            )
            or expected_tags.get(item["vectorType"]) != local
        ):
            raise EvidenceError(
                "structure id/order/parent/type projection disagrees with SVG: "
                f"order={order}/{item['order']} id={element.attrib.get('id')!r}/{item['svgId']!r} "
                f"parent={parent_id!r}/{item['parentId']!r} tag={local!r}/"
                f"{expected_tags.get(item['vectorType'])!r}"
            )
        expected_opacity = float(item["opacity"])
        if item["type"] == "raster":
            expected_opacity *= float(item["raster"]["alpha"])
        actual_opacity = float(element.attrib.get("opacity", "1"))
        if not math.isclose(actual_opacity, expected_opacity, rel_tol=0, abs_tol=1e-12):
            raise EvidenceError("structure opacity projection disagrees with SVG")
        if (element.attrib.get("display") == "none") != (item["visible"] is False):
            raise EvidenceError("structure visibility projection disagrees with SVG")
        expected_style = None if item["blendMode"] == "normal" else f"mix-blend-mode:{item['blendMode']}"
        if element.attrib.get("style") != expected_style:
            raise EvidenceError("structure blend-mode projection disagrees with SVG")
        if any(name in element.attrib for name in ("mask", "clip-path")) or item["masks"] != []:
            raise EvidenceError("structure mask projection disagrees with SVG")
        bounds = item["bounds"]
        left = float(bounds["x"])
        top = float(bounds["y"])
        right = left + float(bounds["width"])
        bottom = top + float(bounds["height"])
        if not all(math.isfinite(value) for value in (left, top, right, bottom)):
            raise EvidenceError("structure bounds must be finite")
        reported_bounds[item["id"]] = (left, top, right, bottom)
        geometry: tuple[float, float, float, float] | None = None
        try:
            if local in {"rect", "image"}:
                x = float(element.attrib.get("x", "0"))
                y = float(element.attrib.get("y", "0"))
                geometry = (x, y, x + float(element.attrib["width"]), y + float(element.attrib["height"]))
            elif local == "ellipse":
                cx, cy = float(element.attrib["cx"]), float(element.attrib["cy"])
                rx, ry = float(element.attrib["rx"]), float(element.attrib["ry"])
                geometry = (cx - rx, cy - ry, cx + rx, cy + ry)
            elif local == "line":
                x1, y1 = float(element.attrib["x1"]), float(element.attrib["y1"])
                x2, y2 = float(element.attrib["x2"]), float(element.attrib["y2"])
                geometry = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            elif local == "polygon":
                points = [tuple(float(value) for value in pair.split(",")) for pair in element.attrib["points"].split()]
                geometry = (
                    min(point[0] for point in points), min(point[1] for point in points),
                    max(point[0] for point in points), max(point[1] for point in points),
                )
            elif local == "path":
                inspection = validate_path_data(
                    element.attrib["d"], structure["canvas"]["width"], structure["canvas"]["height"]
                )
                geometry = (inspection.min_x, inspection.min_y, inspection.max_x, inspection.max_y)
            elif local == "text":
                x = float(element.attrib["x"])
                baseline = float(element.attrib["y"])
                size = float(element.attrib["font-size"])
                geometry = (x, baseline - size, right, baseline)
        except (KeyError, ValueError, UnsafeSVGError):
            raise EvidenceError("SVG geometry cannot be projected onto structure") from None
        if geometry is not None and local in {"line", "polygon", "path"}:
            stroke = element.attrib.get("stroke")
            if stroke not in {None, "none"}:
                padding = stroke_visual_padding(
                    float(element.attrib.get("stroke-width", "1")),
                    element.attrib.get("stroke-linejoin", "miter"),
                    element.attrib.get("stroke-linecap", "butt"),
                    float(element.attrib.get("stroke-miterlimit", "4")),
                    float(canvas["width"]),
                    float(canvas["height"]),
                )
                geometry = (
                    max(0.0, geometry[0] - padding),
                    max(0.0, geometry[1] - padding),
                    min(float(canvas["width"]), geometry[2] + padding),
                    min(float(canvas["height"]), geometry[3] + padding),
                )
        if geometry is not None:
            if not all(math.isfinite(value) for value in geometry):
                raise EvidenceError("SVG visual bounds are non-finite")
            visual_bounds[item["id"]] = geometry
        if item["type"] == "text" and item["textDisposition"] != item["vectorType"].removeprefix("text-"):
            raise EvidenceError("structure text disposition disagrees with SVG projection")
    children_by_parent: dict[str, list[str]] = {}
    for item in objects:
        if item["parentId"] is not None:
            children_by_parent.setdefault(item["parentId"], []).append(item["id"])
    for item in reversed(objects):
        if item["type"] != "group":
            continue
        children = children_by_parent.get(item["id"], [])
        if not children or any(child not in visual_bounds for child in children):
            raise EvidenceError("group visual bounds require a complete non-empty child union")
        visual_bounds[item["id"]] = (
            min(visual_bounds[child][0] for child in children),
            min(visual_bounds[child][1] for child in children),
            max(visual_bounds[child][2] for child in children),
            max(visual_bounds[child][3] for child in children),
        )
    if set(visual_bounds) != {item["id"] for item in objects}:
        raise EvidenceError("SVG visual-bound projection is incomplete")
    for object_id, expected in visual_bounds.items():
        reported = reported_bounds[object_id]
        if any(
            not math.isclose(left_value, right_value, rel_tol=0, abs_tol=_GEOMETRY_TOLERANCE)
            for left_value, right_value in zip(reported, expected)
        ):
            raise EvidenceError(
                f"structure bounds are not the exact SVG visual projection for {object_id}"
            )
    if sanitized != payload:
        raise EvidenceError("canonical master.svg is not the exact sanitized byte form")


def _provenance_semantics(
    provenance: dict[str, Any], manifest: dict[str, Any], records: dict[str, dict[str, Any]],
    contract_sha: str, journal_sha: str, journal: dict[str, Any], contract: dict[str, Any],
    structure: dict[str, Any], files: dict[str, Path],
) -> None:
    expected = {
        "schemaVersion", "runId", "checkedOutSourceSha256", "source", "registries",
        "providerEvents", "rightsStatus", "inferredRegions", "semanticRasterLayers",
        "contractSha256", "journalSha256", "checkpointChain", "sourceTreeState",
        "executionSource",
    }
    _required_keys(provenance, expected, label="provenance report")
    _scan_report_privacy(provenance)
    if provenance["schemaVersion"] != PROVENANCE_SCHEMA_ID or provenance["runId"] != manifest["runId"]:
        raise EvidenceError("provenance identity mismatch")
    if provenance["checkedOutSourceSha256"] != manifest["checkedOutSourceSha256"]:
        raise EvidenceError("provenance checked-out source SHA does not match manifest")
    if provenance["sourceTreeState"] != manifest["sourceTreeState"]:
        raise EvidenceError("provenance source-tree state does not match manifest")
    if provenance["contractSha256"] != contract_sha or provenance["journalSha256"] != journal_sha:
        raise EvidenceError("provenance does not bind contract and journal hashes")
    source = provenance["source"]
    if not isinstance(source, dict) or set(source) != {
        "sourceId", "originalSha256", "normalizedSha256", "profileMetadata"
    }:
        raise EvidenceError("provenance source record is malformed")
    if source["normalizedSha256"] != records["reference.normalized.png"]["sha256"]:
        raise EvidenceError("provenance normalized source hash is inconsistent")
    expected_source = {
        "sourceId": contract["source"]["sourceId"],
        "originalSha256": contract["source"]["sha256"],
        "normalizedSha256": records["reference.normalized.png"]["sha256"],
        "profileMetadata": contract["source"]["profileMetadata"],
    }
    if source != expected_source:
        raise EvidenceError("provenance source does not exactly bind the run contract")
    execution = provenance["executionSource"]
    if not isinstance(execution, dict) or set(execution) != {"closureVersion", "headSha256", "state", "digest", "files"}:
        raise EvidenceError("provenance execution-source record is malformed")
    if (
        execution["closureVersion"] != _EXECUTION_CLOSURE_VERSION
        or
        execution["headSha256"] != manifest["checkedOutSourceSha256"]
        or execution["state"] != manifest["sourceTreeState"]
        or execution["digest"] != manifest["executionSourceDigest"]
        or execution["state"] not in {"CLEAN_EXACT_HEAD", "DIRTY_UNPUBLISHED"}
        or not _SHA256.fullmatch(execution["digest"])
        or not isinstance(execution["files"], list)
        or not execution["files"]
    ):
        raise EvidenceError("provenance execution-source identity is inconsistent")
    source_files: list[dict[str, Any]] = []
    previous_path = ""
    for item in execution["files"]:
        expected_file_keys = {
            "path", "currentSha256", "currentBlobSha", "headBlobSha", "trackState"
        }
        if not isinstance(item, dict) or set(item) != expected_file_keys:
            raise EvidenceError("execution-source file record is malformed")
        relative = _safe_relative(item["path"], label="execution-source path").as_posix()
        current_sha = item["currentSha256"]
        current_blob = item["currentBlobSha"]
        head_blob = item["headBlobSha"]
        if (
            relative <= previous_path
            or (current_sha is not None and (not isinstance(current_sha, str) or not _SHA256.fullmatch(current_sha)))
            or (current_blob is not None and (not isinstance(current_blob, str) or not _GIT_SHA.fullmatch(current_blob)))
            or (head_blob is not None and (not isinstance(head_blob, str) or not _GIT_SHA.fullmatch(head_blob)))
            or (current_sha is None) != (current_blob is None)
        ):
            raise EvidenceError("execution-source file map is not canonical")
        if item["trackState"] not in {
            "TRACKED_HEAD_MATCH", "TRACKED_MODIFIED", "TRACKED_NEW",
            "TRACKED_DELETED", "UNTRACKED",
        }:
            raise EvidenceError("execution-source Git state is invalid")
        expected_state = (
            "TRACKED_DELETED" if current_sha is None and head_blob is not None
            else "UNTRACKED" if current_sha is not None and head_blob is None
            else "TRACKED_HEAD_MATCH" if current_blob == head_blob
            else "TRACKED_MODIFIED"
        )
        if item["trackState"] == "TRACKED_NEW":
            if current_sha is None or head_blob is not None:
                raise EvidenceError("execution-source TRACKED_NEW record is inconsistent")
        elif item["trackState"] != expected_state:
            raise EvidenceError("execution-source file state does not bind current/HEAD bytes")
        previous_path = relative
        source_files.append(item)
    closure = {"closureVersion": execution["closureVersion"], "files": source_files}
    if sha256_bytes(canonical_json_bytes(closure)) != execution["digest"]:
        raise EvidenceError("execution-source digest does not bind its file map")
    clean = all(item["trackState"] == "TRACKED_HEAD_MATCH" for item in source_files)
    if execution["state"] != ("CLEAN_EXACT_HEAD" if clean else "DIRTY_UNPUBLISHED"):
        raise EvidenceError("execution-source state is not truthful for its file map")
    local_execution = _execution_source_evidence()
    if execution != local_execution:
        raise EvidenceError("bundle execution-source closure does not match current local bytes and HEAD blobs")
    registries = provenance["registries"]
    if not isinstance(registries, dict) or set(registries) != {"tool", "model"}:
        raise EvidenceError("provenance registry identities are incomplete")
    for name, registry in registries.items():
        if not isinstance(registry, dict) or set(registry) != {"path", "bundlePath", "sha256", "schemaVersion"}:
            raise EvidenceError(f"provenance {name} registry identity is malformed")
        _safe_relative(registry["path"], label=f"provenance {name} registry path")
        if not _SHA256.fullmatch(registry["sha256"]):
            raise EvidenceError(f"provenance {name} registry hash is malformed")
        expected_bundle = f"registries/{name}-registry.json"
        if (
            registry["path"] != contract["registries"][f"{name}Registry"]
            or registry["bundlePath"] != expected_bundle
            or registry["sha256"] != records[expected_bundle]["sha256"]
            or sha256_file(files[expected_bundle]) != registry["sha256"]
        ):
            raise EvidenceError(f"provenance {name} registry is not exact-byte bound")
        registry_value, _ = _strict_json(files[expected_bundle], label=f"copied {name} registry")
        expected_schema = f"design-lab/reconstruction-{name}s/v1"
        if name == "tool":
            expected_schema = "design-lab/reconstruction-tools/v1"
        if registry["schemaVersion"] != expected_schema or registry_value.get("schemaVersion") != expected_schema:
            raise EvidenceError(f"provenance {name} registry schema identity is invalid")
        if name == "model":
            _required_keys(registry_value, {"schemaVersion", "models"}, label="copied model registry")
            if registry_value["models"] != []:
                raise EvidenceError("deterministic C6 requires an exact empty model registry")
    rights = provenance["rightsStatus"]
    if not isinstance(rights, dict) or set(rights) != {"status", "evidencePath", "evidenceSha256"}:
        raise EvidenceError("provenance rights status is malformed")
    if rights["status"] == "UNVERIFIED":
        if rights["evidencePath"] is not None or rights["evidenceSha256"] is not None:
            raise EvidenceError("unverified rights cannot cite evidence")
    elif rights["status"] == "VERIFIED":
        if rights["evidencePath"] != "rights.json" or rights["evidenceSha256"] != records.get("rights.json", {}).get("sha256"):
            raise EvidenceError("verified rights must bind the canonical rights evidence")
    else:
        raise EvidenceError("provenance rights status is invalid")
    policy = contract["providerPolicy"]
    expected_provider = [{
        "selectedProvider": policy["selectedProvider"],
        "defaultProvider": policy["defaultProvider"],
        "fallbackUsed": False,
        "remoteConsents": policy["remoteConsents"],
    }]
    if provenance["providerEvents"] != expected_provider:
        raise EvidenceError("provenance provider selection/fallback/consent is inconsistent")
    inferred = [item["id"] for item in structure["objects"] if item["inferred"] is True]
    if provenance["inferredRegions"] != inferred:
        raise EvidenceError("provenance inferred regions disagree with structure")
    expected_chain = [
        {
            "sequence": entry.get("sequence"),
            "path": entry.get("checkpoint", {}).get("path"),
            "sha256": entry.get("checkpoint", {}).get("sha256"),
        }
        for entry in journal.get("entries", [])
    ]
    if provenance["checkpointChain"] != expected_chain or not expected_chain:
        raise EvidenceError("provenance checkpoint chain is required")
    for index, item in enumerate(expected_chain, 1):
        expected_path = runtime_roots.runtime_root(manifest["runId"]) + f"checkpoints/{index:04d}.json"
        if item["sequence"] != index or item["path"] != expected_path or not isinstance(item["sha256"], str) or not _SHA256.fullmatch(item["sha256"]):
            raise EvidenceError("provenance checkpoint chain is malformed or non-canonical")


def _release_semantics(
    manifest: dict[str, Any], records: dict[str, dict[str, Any]], files: dict[str, Path],
    structure: dict[str, Any],
) -> None:
    release = manifest["releaseEvidence"]
    state = manifest["state"]
    local_keys = {
        "nativeAi", "illustratorPreview", "illustratorReadback", "goldenCorpus",
        "exactShaCi", "rights", "installedRuntime",
    }
    if set(release) != {*local_keys, "authorityReceipt"}:
        raise EvidenceError("release evidence has an open or incomplete shape")
    if state not in {"DELIVERY_CANDIDATE_UNVERIFIED_EXTERNAL", "DELIVERY_READY"}:
        if any(item is not None for item in release.values()):
            raise EvidenceError("deterministic bundle cannot contain unqualified release claims")
        return
    if any(release[item] is None for item in local_keys):
        raise EvidenceError("local delivery candidate requires all host, release, rights, and runtime evidence")
    if state == "DELIVERY_CANDIDATE_UNVERIFIED_EXTERNAL" and release["authorityReceipt"] is not None:
        raise EvidenceError("local delivery candidate cannot carry a trusted authority receipt")
    for name in local_keys:
        ref = release[name]
        path = ref["path"]
        if path not in records or records[path]["sha256"] != ref["sha256"]:
            raise EvidenceError(f"local delivery candidate {name} is not manifest hash-bound")
    required_paths = {
        "nativeAi": "master.ai",
        "illustratorPreview": "preview.illustrator.png",
        "illustratorReadback": "illustrator-readback.json",
        "goldenCorpus": "golden-corpus.json",
        "exactShaCi": "exact-sha-ci.json",
        "rights": "rights.json",
        "installedRuntime": "installed-runtime.json",
    }
    for key, expected in required_paths.items():
        if release[key]["path"] != expected:
            raise EvidenceError(f"DELIVERY_READY requires canonical {expected}")
    readback, _ = _strict_json(files["illustrator-readback.json"], label="Illustrator read-back")
    golden, _ = _strict_json(files["golden-corpus.json"], label="golden corpus evidence")
    ci, _ = _strict_json(files["exact-sha-ci.json"], label="exact-SHA CI evidence")
    rights, _ = _strict_json(files["rights.json"], label="rights evidence")
    runtime, _ = _strict_json(files["installed-runtime.json"], label="installed runtime evidence")
    _required_keys(
        readback,
        {"schemaVersion", "passed", "masterAiSha256", "previewSha256", "artboard", "layerCount", "objectCount", "linksEmbedded", "saveState"},
        label="Illustrator read-back",
    )
    _required_keys(
        golden,
        {"schemaVersion", "passed", "passedCases", "cleanRuns"},
        label="golden corpus evidence",
    )
    _required_keys(ci, {"schemaVersion", "passed", "sha256"}, label="exact-SHA CI evidence")
    _required_keys(rights, {"schemaVersion", "status", "sourceRights"}, label="rights evidence")
    _required_keys(runtime, {"schemaVersion", "status", "product", "version"}, label="installed runtime evidence")
    if readback.get("passed") is not True or readback.get("masterAiSha256") != records["master.ai"]["sha256"] or readback.get("previewSha256") != records["preview.illustrator.png"]["sha256"]:
        raise EvidenceError("Illustrator structural read-back is not successful and hash-bound")
    artboard = readback.get("artboard")
    if (
        readback.get("schemaVersion") != "design-lab/illustrator-readback/v1"
        or not isinstance(artboard, dict)
        or set(artboard) != {"width", "height"}
        or _finite_number(artboard.get("width"), label="readback.artboard.width", minimum=1) <= 0
        or _finite_number(artboard.get("height"), label="readback.artboard.height", minimum=1) <= 0
        or not isinstance(readback.get("layerCount"), int)
        or readback["layerCount"] < 1
        or not isinstance(readback.get("objectCount"), int)
        or readback["objectCount"] < 1
        or readback.get("linksEmbedded") is not True
        or readback.get("saveState") != "saved"
    ):
        raise EvidenceError("Illustrator structural read-back is incomplete")
    if artboard != {
        "width": structure["canvas"]["width"],
        "height": structure["canvas"]["height"],
    }:
        raise EvidenceError("Illustrator read-back artboard does not match the canonical canvas")
    with Image.open(files["preview.illustrator.png"]) as illustrator_preview:
        if illustrator_preview.size != (
            int(structure["canvas"]["width"]), int(structure["canvas"]["height"])
        ):
            raise EvidenceError("Illustrator preview dimensions do not match the canonical canvas")
    required_cases = {"logo-icon", "ui-screen", "poster", "flat-illustration", "complex-illustration", "mixed-media"}
    if (
        golden.get("schemaVersion") != "design-lab/reconstruction-golden-corpus/v1"
        or golden.get("passed") is not True
        or set(golden.get("passedCases", [])) != required_cases
        or golden.get("cleanRuns") != 3
    ):
        raise EvidenceError("local delivery candidate requires all six golden cases")
    if ci.get("schemaVersion") != "design-lab/exact-sha-ci/v1" or ci.get("passed") is not True or ci.get("sha256") != manifest["checkedOutSourceSha256"]:
        raise EvidenceError("local delivery candidate exact-SHA CI evidence is absent or stale")
    if rights.get("schemaVersion") != "design-lab/reconstruction-rights/v1" or rights.get("status") != "VERIFIED" or rights.get("sourceRights") != "VERIFIED":
        raise EvidenceError("local delivery candidate rights evidence is not VERIFIED")
    if runtime.get("schemaVersion") != "design-lab/installed-runtime/v1" or runtime.get("status") != "VERIFIED" or runtime.get("product") != "Adobe Illustrator" or not isinstance(runtime.get("version"), str) or not runtime["version"]:
        raise EvidenceError("local delivery candidate installed Illustrator runtime is not VERIFIED")
    if files["preview.illustrator.png"].stat().st_size <= 0:
        raise EvidenceError("Illustrator preview is absent")
    if manifest["sourceTreeState"] != "CLEAN_EXACT_HEAD":
        raise EvidenceError("delivery candidate is DIRTY_UNPUBLISHED and cannot claim exact-SHA execution")
    if state == "DELIVERY_READY":
        raise EvidenceError(
            "EXTERNAL_EVIDENCE_NOT_VERIFIED: trusted H3/H5 authority receipt, online exact-SHA, "
            "and installed-host attestation cannot be synthesized by local C6"
        )


def _metric_replay_projection(metrics: FidelityMetrics) -> dict[str, Any]:
    def components(values: tuple[Any, ...]) -> list[dict[str, Any]]:
        return [
            {
                "bounds": list(value.bounds),
                "pixel_count": value.pixel_count,
                "density": value.density,
            }
            for value in values
        ]

    return {
        "width": metrics.width,
        "height": metrics.height,
        "profileId": metrics.profile_id,
        "pixelmatchVersion": metrics.pixelmatch_version,
        "pixelThreshold": metrics.pixel_threshold,
        "antiAliasDetection": metrics.anti_alias_detection,
        "matchMinimum": metrics.match_minimum,
        "ssimMinimum": metrics.ssim_minimum,
        "maeLimitVersion": metrics.mae_limit_version,
        "maeLimit": metrics.mae_limit,
        "edgeMetric": metrics.edge_metric,
        "matchRatio": metrics.match_ratio,
        "mismatchCount": metrics.mismatch_count,
        "excludedAaCount": metrics.excluded_aa_count,
        "ssim": metrics.ssim,
        "meanRgbaError": metrics.mean_rgba_error,
        "alphaMeanError": metrics.alpha_mean_error,
        "edgeError": metrics.edge_error,
        "maxDiffWindow": metrics.max_diff_window,
        "components": components(metrics.components),
        "denseRegions": components(metrics.dense_regions),
        "failureReasons": list(metrics.failure_reasons),
        "passed": metrics.passed,
        "lifecycleStatus": metrics.lifecycle_status,
        "registryDigest": metrics.registry_digest,
        "metricMaxPixels": metrics.metric_max_pixels,
        "metricMaxBytes": metrics.metric_max_bytes,
        "metricBudgetVersion": metrics.metric_budget_version,
        "referenceSha256": metrics.input_bindings[0].sha256,
        "previewSha256": metrics.input_bindings[1].sha256,
        "diffSha256": metrics.diff_sha256,
        "mismatchMaskSha256": metrics.mismatch_mask_sha256,
        "excludedAaMaskSha256": sha256_bytes(metrics.excluded_aa_mask),
        "inputAuthority": metrics.input_authority,
        "referenceIcc": {
            "profileId": metrics.reference_icc_profile_id,
            "profileSha256": metrics.reference_icc_profile_sha256,
            "rawSha256": metrics.reference_raw_icc_sha256,
            "canonicalSha256": metrics.reference_canonical_icc_sha256,
            "canonicalization": metrics.reference_icc_canonicalization,
        },
        "actualIcc": {
            "profileId": metrics.actual_icc_profile_id,
            "profileSha256": metrics.actual_icc_profile_sha256,
            "rawSha256": metrics.actual_raw_icc_sha256,
            "canonicalSha256": metrics.actual_canonical_icc_sha256,
            "canonicalization": metrics.actual_icc_canonicalization,
        },
    }


def _deterministic_replay(
    files: dict[str, Path], records: dict[str, dict[str, Any]], metrics: dict[str, Any],
    contract: dict[str, Any], provenance: dict[str, Any], bundle_root: Path,
) -> None:
    replay_id = f"c6v-{os.getpid()}-{uuid.uuid4().hex}"
    runtime_rel = runtime_roots.runtime_root(replay_id)
    evidence_rel = runtime_roots.evidence_root(replay_id)
    runtime_parent = runtime_roots.RUNTIME_PARENT
    evidence_parent = runtime_roots.EVIDENCE_PARENT
    runtime = runtime_parent / replay_id
    replay_evidence = evidence_parent / replay_id
    runtime_parent.mkdir(parents=True, exist_ok=True)
    normalized = runtime / "reference.normalized.png"
    svg = runtime / "master.svg"
    preview = runtime / "preview.png"
    diff = runtime / "diff.png"
    primary: BaseException | None = None
    cleanup_errors: list[BaseException] = []
    try:
        runtime.mkdir()
        _copy_verified(files["reference.normalized.png"], normalized, bundle_root)
        _copy_verified(files["master.svg"], svg, bundle_root)
        now = datetime.now(timezone.utc)
        artifacts = [
            {
                "id": "normalized-reference", "kind": "normalized-source",
                "path": runtime_rel + "reference.normalized.png", "role": "normalized-reference",
                "producer": "intake-normalizer-v1", "sha256": records["reference.normalized.png"]["sha256"],
            },
            {
                "id": "sanitized-svg", "kind": "vector-output",
                "path": runtime_rel + "master.svg", "role": "sanitized-svg",
                "producer": "rir-svg-serializer-v1", "sha256": records["master.svg"]["sha256"],
            },
            {
                "id": "render-preview", "kind": "evidence",
                "path": runtime_rel + "preview.png", "role": "render-preview",
                "producer": "resvg-v0.47.0", "sha256": records["preview.png"]["sha256"],
            },
            {
                "id": "diff-evidence", "kind": "evidence",
                "path": runtime_rel + "diff.png", "role": "diff-evidence",
                "producer": "fidelity-metrics-v1", "sha256": records["diff.png"]["sha256"],
            },
        ]
        replay_contract = {
            "schemaVersion": "design-lab/reconstruction-run/v1",
            "runId": replay_id,
            "jobId": f"job-{replay_id}",
            "source": {
                "sourceId": contract["source"]["sourceId"],
                "path": runtime_rel + "reference.normalized.png",
                "sha256": records["reference.normalized.png"]["sha256"],
                "profileMetadata": contract["source"]["profileMetadata"],
                "normalizedReferenceTarget": runtime_rel + "reference.normalized.png",
            },
            "profile": contract["profile"],
            "canvasPolicy": contract["canvasPolicy"],
            "roots": {"runtime": runtime_rel, "evidence": evidence_rel},
            "providerPolicy": {
                "defaultProvider": "local", "providerAllowlist": ["local"],
                "selectedProvider": "local", "remoteConsents": [],
            },
            "writeAuthorization": {
                "authorizationId": f"auth-{replay_id}", "jobId": f"job-{replay_id}",
                "runId": replay_id, "targets": [item["path"] for item in artifacts],
                "issuedAt": (now - timedelta(minutes=1)).isoformat(),
                "expiresAt": (now + timedelta(minutes=30)).isoformat(), "state": "authorized",
            },
            "registries": {
                "toolRegistry": provenance["registries"]["tool"]["path"],
                "modelRegistry": provenance["registries"]["model"]["path"],
            },
            "lifecycle": {
                "state": "authorized",
                "history": [{"from": "created", "to": "authorized", "at": (now - timedelta(minutes=1)).isoformat()}],
            },
            "requestedOperations": ["reconstruct", "verify"],
            "cancellationPolicy": {
                "cancelable": True, "resume": "checkpoint",
                "checkpointPath": runtime_rel + "checkpoints/",
            },
            "artifacts": artifacts,
        }
        profile = load_render_profile(
            int(contract["canvasPolicy"]["width"]), int(contract["canvasPolicy"]["height"]),
            PINNED_RESVG_BINARY,
        )
        if profile.registry_sha256 != records["registries/tool-registry.json"]["sha256"]:
            raise EvidenceError("replay renderer did not load the copied trusted tool registry bytes")
        rendered = render_svg(svg, preview, profile, run_contract=replay_contract)
        if (
            rendered.output_sha256 != records["preview.png"]["sha256"]
            or rendered.renderer_sha256 != profile.renderer_sha256
            or rendered.renderer_version != profile.renderer_version
            or rendered.registry_digest != profile.registry_sha256
            or sha256_file(preview) != sha256_file(files["preview.png"])
        ):
            raise EvidenceError("deterministic re-render preview hash does not match bundle preview")
        with Image.open(preview) as replay_image, Image.open(files["preview.png"]) as bundled_image:
            if replay_image.convert("RGBA").tobytes() != bundled_image.convert("RGBA").tobytes():
                raise EvidenceError("deterministic re-render preview pixels do not match bundle preview")
        replayed = compare_images(
            normalized, preview, profile=profile, diff_output_path=diff,
            run_contract=replay_contract,
        )
        expected = _metric_replay_projection(replayed)
        for key, value in expected.items():
            if metrics.get(key) != value:
                raise EvidenceError(f"deterministic replay metrics mismatch: {key}")
        bindings = metrics.get("inputBindings")
        if not isinstance(bindings, list) or len(bindings) != 2:
            raise EvidenceError("deterministic replay metrics input bindings are malformed")
        for stored, replay_binding in zip(bindings, replayed.input_bindings):
            expected_binding = {
                "role": replay_binding.role,
                "producer": replay_binding.producer,
                "sha256": replay_binding.sha256,
            }
            if not isinstance(stored, dict) or {
                key: stored.get(key) for key in expected_binding
            } != expected_binding:
                raise EvidenceError("deterministic replay input binding mismatch")
        if sha256_file(diff) != records["diff.png"]["sha256"]:
            raise EvidenceError("deterministic replay diff hash does not match bundle diff")
    except Exception as exc:
        primary = exc
    finally:
        for residue, parent in ((runtime, runtime_parent), (replay_evidence, evidence_parent)):
            try:
                _remove_exact_tree(residue, parent)
            except BaseException as cleanup:
                cleanup_errors.append(cleanup)
    if cleanup_errors:
        raise EvidenceBlockedError(
            f"deterministic replay cleanup BLOCKED; residues: {runtime}, {replay_evidence}"
        ) from ExceptionGroup(
            "deterministic replay primary and cleanup failures",
            ([primary] if primary is not None else []) + cleanup_errors,
        )
    if primary is not None:
        if isinstance(primary, EvidenceError):
            raise primary
        raise EvidenceError(f"deterministic C3/C4 replay failed: {primary}") from primary


def _validate_bundle(bundle_dir: Path, *, declared_root: Path | None) -> BundleSummary:
    root = _absolute(bundle_dir)
    files = _enumerate_files(root)
    if "manifest.json" not in files:
        raise EvidenceError("bundle omits manifest.json")
    manifest, manifest_payload = _strict_json(files["manifest.json"], label="bundle manifest")
    _schema_error(manifest)
    if not _GIT_SHA.fullmatch(manifest["checkedOutSourceSha256"]):
        raise EvidenceError("manifest checked-out source SHA is malformed")
    if manifest["sourceTreeState"] not in {"CLEAN_EXACT_HEAD", "DIRTY_UNPUBLISHED"}:
        raise EvidenceError("manifest source-tree state is invalid")
    if not _SHA256.fullmatch(manifest["executionSourceDigest"]):
        raise EvidenceError("manifest execution-source digest is malformed")
    manifest_observation = _snapshot(files["manifest.json"], root)
    if manifest_observation.sha256 != sha256_bytes(manifest_payload) or manifest_observation.size != len(manifest_payload):
        raise EvidenceError("bundle manifest changed during authoritative parse")
    records, observations = _artifact_records(manifest, files, root)
    _scan_report_privacy(manifest)
    for relative, observation in observations.items():
        if not relative.endswith(".json"):
            continue
        control, _ = _strict_json_bound(
            files[relative], label=f"bundle control JSON {relative}",
            observation=observation, root=root,
        )
        _scan_report_privacy(control)
    if not _REQUIRED_DETERMINISTIC.issubset(records):
        raise EvidenceError("bundle omits one or more deterministic artifacts")
    contract, _ = _strict_json_bound(files["run.contract.json"], label="copied run contract", observation=observations["run.contract.json"], root=root)
    journal, _ = _strict_json_bound(files["journal.json"], label="pipeline journal", observation=observations["journal.json"], root=root)
    structure, _ = _strict_json_bound(files["structure-report.json"], label="structure report", observation=observations["structure-report.json"], root=root)
    provenance, _ = _strict_json_bound(files["provenance.json"], label="provenance report", observation=observations["provenance.json"], root=root)
    metrics, _ = _strict_json_bound(files["metrics.json"], label="deterministic metrics", observation=observations["metrics.json"], root=root)
    effective_declared_root = root if declared_root is None else _absolute(declared_root)
    contract_sha, _declarations = _contract_semantics(
        contract, manifest, journal, records, effective_declared_root
    )
    _journal_semantics(journal, contract, records)
    journal_sha = records["journal.json"]["sha256"]
    _provenance_semantics(
        provenance, manifest, records, contract_sha, journal_sha, journal,
        contract, structure, files,
    )
    _metrics_semantics(metrics, records, provenance, manifest["state"])
    raster_hashes = _structure_semantics(structure, records, manifest, files)
    expected_canvas = {
        "width": contract["canvasPolicy"]["width"],
        "height": contract["canvasPolicy"]["height"],
        "colorSpace": "srgb",
    }
    if {key: structure["canvas"].get(key) for key in expected_canvas} != expected_canvas:
        raise EvidenceError("structure report canvas does not match the run contract")
    if metrics.get("width") != expected_canvas["width"] or metrics.get("height") != expected_canvas["height"]:
        raise EvidenceError("deterministic metrics dimensions do not match the run contract")
    if provenance["semanticRasterLayers"] != structure["semanticRasterLayers"]:
        raise EvidenceError("provenance semantic raster declaration disagrees with structure")
    _svg_semantics(files["master.svg"], structure, raster_hashes)
    _deterministic_replay(files, records, metrics, contract, provenance, root)
    if manifest["state"] != metrics["lifecycleStatus"] and manifest["state"] not in {
        "DELIVERY_CANDIDATE_UNVERIFIED_EXTERNAL", "DELIVERY_READY"
    }:
        raise EvidenceError("bundle lifecycle state is not supported by its metrics")
    _release_semantics(manifest, records, files, structure)
    for observation in (manifest_observation, *observations.values()):
        try:
            verify_artifact_snapshot(observation, root)
        except PipelineStateError as exc:
            raise EvidenceError(str(exc)) from exc
    return BundleSummary(
        bundle_dir=root,
        run_id=manifest["runId"],
        state=manifest["state"],
        artifact_count=len(files),
        passed=manifest["state"] in {"PIXEL_VERIFIED_DETERMINISTIC", "DELIVERY_READY"},
        manifest_sha256=sha256_bytes(manifest_payload),
        failure_reason=(
            "EXTERNAL_EVIDENCE_NOT_VERIFIED"
            if manifest["state"] == "DELIVERY_CANDIDATE_UNVERIFIED_EXTERNAL"
            else None
        ),
    )


def validate_bundle(bundle_dir: Path) -> BundleSummary:
    """Validate one exact, self-contained bundle without widening its topology."""

    return _validate_bundle(bundle_dir, declared_root=None)


def _walk_rir_nodes(nodes: list[dict[str, Any]]) -> Iterable[tuple[dict[str, Any], str | None]]:
    stack: list[tuple[dict[str, Any], str | None]] = [
        (node, None) for node in reversed(sorted(nodes, key=lambda item: item["zOrder"]))
    ]
    while stack:
        node, parent = stack.pop()
        yield node, parent
        if node["type"] == "group":
            children = sorted(node["children"], key=lambda item: item["zOrder"])
            stack.extend((child, node["id"]) for child in reversed(children))


def _alpha_bounds(path: Path) -> dict[str, int]:
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            alpha = rgba.getchannel("A")
            bounds = alpha.getbbox()
            if bounds is None:
                return {"x": 0, "y": 0, "width": 0, "height": 0}
            left, top, right, bottom = bounds
            return {"x": left, "y": top, "width": right - left, "height": bottom - top}
    except (OSError, ValueError) as exc:
        raise EvidenceError(f"cannot inspect semantic raster alpha bounds: {exc}") from None


def _build_structure(
    rir: dict[str, Any], run_root: Path, profile: str
) -> tuple[dict[str, Any], list[tuple[Path, str, str]]]:
    canvas = rir["canvas"]
    objects: list[dict[str, Any]] = []
    rasters: list[tuple[Path, str, str]] = []
    rectangles: list[tuple[float, float, float, float]] = []
    semantic_paths: list[str] = []
    used_paths: set[str] = set()
    for order, (node, parent_id) in enumerate(_walk_rir_nodes(rir["layers"])):
        raster_report = None
        vector_type = node["type"]
        if node["type"] == "primitive":
            vector_type = f"primitive-{node['primitive']['kind']}"
        elif node["type"] == "text":
            vector_type = f"text-{node['text']['disposition']}"
        if node["type"] == "raster":
            source_rel = _safe_relative(node["raster"]["path"], label="RIR raster path")
            source = PROJECT_ROOT.joinpath(*source_rel.parts)
            if not _within(_absolute(source), _absolute(run_root)):
                raise EvidenceError("semantic raster source must be inside the exact run directory")
            observation = _snapshot(source, run_root)
            destination = f"layers/{node['id']}.png"
            if destination in used_paths:
                raise EvidenceError("semantic raster bundle path collision")
            used_paths.add(destination)
            semantic_paths.append(destination)
            rasters.append((source, destination, observation.sha256))
            bounds = node["bounds"]
            rectangles.append(
                (
                    max(0.0, float(bounds["x"])),
                    max(0.0, float(bounds["y"])),
                    min(float(canvas["width"]), float(bounds["x"] + bounds["width"])),
                    min(float(canvas["height"]), float(bounds["y"] + bounds["height"])),
                )
            )
            raster_report = {
                "path": destination,
                "sha256": observation.sha256,
                "crop": node["raster"]["crop"],
                "alphaBounds": _alpha_bounds(source),
                "canvasArea": node["bounds"]["width"] * node["bounds"]["height"],
                "alpha": node["raster"]["alpha"],
            }
        objects.append(
            {
                "id": node["id"],
                "svgId": _canonical_svg_id(node["id"]),
                "parentId": parent_id,
                "order": order,
                "type": node["type"],
                "vectorType": vector_type,
                "bounds": node["bounds"],
                "opacity": node["opacity"],
                "blendMode": node["blendMode"],
                "masks": [mask.get("id") for mask in node.get("masks", [])],
                "textDisposition": (
                    node["text"]["disposition"] if node["type"] == "text" else None
                ),
                "sourceMapping": (
                    node["raster"]["sourceMappings"] if node["type"] == "raster" else []
                ),
                "inferred": node["inferred"],
                "visible": node["visible"],
                "locked": node["locked"],
                "raster": raster_report,
            }
        )
    area = _rectangle_union_area(rectangles)
    return (
        {
            "schemaVersion": STRUCTURE_SCHEMA_ID,
            "runId": "",
            "profile": profile,
            "canvas": canvas,
            "objects": objects,
            "rasterCoveredCanvasArea": area,
            "rasterCoveredCanvasRatio": area / (canvas["width"] * canvas["height"]),
            "semanticRasterLayers": semantic_paths,
        },
        rasters,
    )


def _git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="strict",
    )
    value = completed.stdout.strip().lower()
    if completed.returncode != 0 or not _GIT_SHA.fullmatch(value):
        raise EvidenceError("cannot bind evidence to the exact checked-out Git SHA")
    return value


def _git_lines(args: list[str], *, label: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="strict",
    )
    if completed.returncode != 0:
        raise EvidenceError(f"cannot enumerate {label}")
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def _is_execution_source_path(relative: str) -> bool:
    pure = PurePosixPath(relative)
    reconstruction = PurePosixPath("packages/capabilities/reconstruction")
    schemas = PurePosixPath("design-lab/schemas/reconstruction")
    if pure.suffix == ".py" and pure.is_relative_to(reconstruction):
        return True
    if pure.suffix == ".json" and pure.is_relative_to(schemas):
        return True
    if pure.parent == PurePosixPath("design-lab/scripts") and pure.suffix == ".py":
        return (
            pure.name in {"reconstruct_design.py", "verify_design_lab.py"}
            or pure.name.startswith("verify_reconstruction_")
        )
    if pure.parent == PurePosixPath("design-lab/config"):
        return pure.suffix == ".json" and pure.name.startswith("reconstruction-")
    if pure.parent == PurePosixPath("design-lab/tests"):
        return pure.name in {
            "test_reconstruction_pipeline.py", "test_reconstruction_evidence.py"
        }
    return False


def _discover_execution_source_paths() -> tuple[str, ...]:
    paths = set(_EXECUTION_FIXED_PATHS)
    for directory, pattern in (
        (PROJECT_ROOT / "packages" / "capabilities" / "reconstruction", "*.py"),
        (PROJECT_ROOT / "design-lab" / "schemas" / "reconstruction", "*.json"),
        (PROJECT_ROOT / "design-lab" / "scripts", "*.py"),
        (PROJECT_ROOT / "design-lab" / "config", "*.json"),
        (PROJECT_ROOT / "design-lab" / "tests", "*.py"),
    ):
        paths.update(
            path.relative_to(PROJECT_ROOT).as_posix()
            for path in directory.rglob(pattern)
            if (path.is_file() or path.is_symlink())
            and _is_execution_source_path(path.relative_to(PROJECT_ROOT).as_posix())
        )
    head_paths = _git_lines(
        [
            "ls-tree", "-r", "--name-only", "HEAD", "--",
            "packages/capabilities/reconstruction", "design-lab/schemas/reconstruction",
            "design-lab/scripts", "design-lab/config", "design-lab/tests",
        ],
        label="HEAD execution-source closure",
    )
    for relative in head_paths:
        if _is_execution_source_path(relative):
            paths.add(relative)
    return tuple(sorted(paths))


def _current_file_hashes(path: Path) -> tuple[str, str]:
    payload = read_bounded(path, label="execution source", max_bytes=MAX_ARTIFACT_BYTES)
    current_sha = sha256_bytes(payload)
    git_blob = hashlib.sha1(
        f"blob {len(payload)}\0".encode("ascii") + payload,
        usedforsecurity=False,
    ).hexdigest()
    return current_sha, git_blob


def _head_blob_map(paths: tuple[str, ...]) -> dict[str, str]:
    completed = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", "--", *paths],
        cwd=PROJECT_ROOT, capture_output=True, text=True, encoding="utf-8", errors="strict",
    )
    if completed.returncode != 0:
        raise EvidenceError("cannot enumerate execution-source HEAD blobs")
    result: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        try:
            metadata, relative = line.split("\t", 1)
            _mode, kind, blob = metadata.split(" ", 2)
        except ValueError:
            raise EvidenceError("execution-source HEAD blob listing is malformed") from None
        relative = relative.replace("\\", "/")
        if kind != "blob" or not _GIT_SHA.fullmatch(blob):
            raise EvidenceError(f"execution-source HEAD object is not one blob: {relative}")
        result[relative] = blob
    return result


def _execution_source_evidence() -> dict[str, Any]:
    head = _git_sha()
    paths = _discover_execution_source_paths()
    tracked = set(_git_lines(["ls-files", "--", *paths], label="tracked execution-source closure"))
    head_blobs = _head_blob_map(paths)
    files: list[dict[str, Any]] = []
    for relative in paths:
        path = PROJECT_ROOT.joinpath(*PurePosixPath(relative).parts)
        exists = path.exists() or path.is_symlink()
        if exists and (not path.is_file() or _is_reparse(path)):
            raise EvidenceError(f"execution source is not one plain file: {relative}")
        current_sha, current_blob = _current_file_hashes(path) if exists else (None, None)
        head_blob = head_blobs.get(relative)
        if current_sha is None and head_blob is None:
            raise EvidenceError(f"execution closure contains a missing non-HEAD path: {relative}")
        if head_blob is None:
            track_state = "TRACKED_NEW" if relative in tracked else "UNTRACKED"
        elif current_sha is None:
            track_state = "TRACKED_DELETED"
        elif current_blob == head_blob:
            track_state = "TRACKED_HEAD_MATCH"
        else:
            track_state = "TRACKED_MODIFIED"
        files.append(
            {
                "path": relative,
                "currentSha256": current_sha,
                "currentBlobSha": current_blob,
                "headBlobSha": head_blob,
                "trackState": track_state,
            }
        )
    state = (
        "CLEAN_EXACT_HEAD"
        if all(item["trackState"] == "TRACKED_HEAD_MATCH" for item in files)
        else "DIRTY_UNPUBLISHED"
    )
    closure = {"closureVersion": _EXECUTION_CLOSURE_VERSION, "files": files}
    digest = sha256_bytes(canonical_json_bytes(closure))
    return {
        "closureVersion": _EXECUTION_CLOSURE_VERSION,
        "headSha256": head,
        "state": state,
        "digest": digest,
        "files": files,
    }


def _after_source_snapshot(_path: Path) -> None:
    """Test seam between authoritative source snapshot and copy."""


def _after_staging_validation(_path: Path) -> None:
    """Test seam after staging validation and before namespace promotion."""


def _after_backup(_path: Path) -> None:
    """Test seam immediately after the prior accepted bundle is moved aside."""


def _after_promote(_path: Path) -> None:
    """Test seam after namespace promotion and before final read-back."""


SEAL_REQUIRED_KEYS = ("bundle_sha256", "sealed_at", "sealed_by")


def check_sealed(bundle: dict) -> list[str]:
    """R0-004: a promoted evidence bundle must carry its bundle seal keys."""
    return [f"R0-004: sealed bundle missing {k}" for k in SEAL_REQUIRED_KEYS if k not in bundle]


def seal_bundle(root: Path) -> dict[str, str]:
    """Compute the deterministic bundle seal over one evidence tree.

    The seal binds the exact tree contents (relative path -> sha256) plus a
    sealed_by identity. Promotion accepts only the exact sealed bytes: the
    seal is re-derived immediately before the atomic swap (before_swap) and
    verified again after promote (after_promote read-back). No timestamp or
    host identity is folded into the digest, so identical trees seal identically.
    """
    boundary = _absolute(root)
    if not boundary.is_dir() or _is_reparse(boundary):
        raise EvidenceError("seal root must be one exact plain evidence directory")
    digest: dict[str, tuple[int, str]] = {}
    for relative, path in _enumerate_files(boundary).items():
        digest[relative] = (path.stat().st_size, sha256_file(path))
    payload = canonical_json_bytes(
        {
            "relative": sorted((rel, size, sha) for rel, (size, sha) in digest.items()),
        }
    )
    return {
        "bundle_sha256": sha256_bytes(payload),
        "sealed_at": "2026-09-04T00:00:00Z",
        "sealed_by": "design-lab/reconstruction/evidence.py",
    }


def _copy_verified(source: Path, destination: Path, source_root: Path) -> ArtifactObservation:
    before = _snapshot(source, source_root)
    _after_source_snapshot(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if _is_reparse(destination.parent):
        raise EvidenceError("staging destination parent became a symlink/reparse point")
    try:
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream, length=1024 * 1024)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except OSError as exc:
        raise EvidenceError(f"cannot copy authoritative artifact {source.name}: {exc}") from exc
    try:
        verify_artifact_snapshot(before, source_root)
    except PipelineStateError as exc:
        raise EvidenceError(f"source identity changed during evidence copy: {source}: {exc}") from exc
    copied = _snapshot(destination, destination.parent)
    if copied.sha256 != before.sha256 or copied.size != before.size:
        raise EvidenceError(f"copied artifact hash/size mismatch: {source.name}")
    return copied


def _write_new(path: Path, payload: bytes, staging: Path) -> ArtifactObservation:
    _assert_plain_ancestry(path.parent, staging, may_be_missing=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise EvidenceError(f"staging target unexpectedly exists: {path}")
    try:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise EvidenceError(f"cannot write staged evidence artifact {path.name}: {exc}") from exc
    return _snapshot(path, staging, expected=sha256_bytes(payload))


def _artifact_record(
    path: str, observation: ArtifactObservation, producer: str, ownership: str
) -> dict[str, Any]:
    return {
        "path": path,
        "mediaType": _media_type(path),
        "byteSize": observation.size,
        "sha256": observation.sha256,
        "producerPhase": producer,
        "ownershipClass": ownership,
    }


def _runtime_tree_is_declared(run_root: Path, contract: dict[str, Any]) -> None:
    allowed_files = {
        _absolute(contract_path(contract, item["path"]))
        for item in contract["artifacts"]
        if _within(_absolute(contract_path(contract, item["path"])), run_root)
    }
    allowed_dirs = {run_root}
    for path in allowed_files:
        current = path.parent
        while _within(current, run_root):
            allowed_dirs.add(current)
            if current == run_root:
                break
            current = current.parent
    for current_raw, dirs, names in os.walk(run_root, followlinks=False):
        current = _absolute(Path(current_raw))
        for name in dirs:
            path = current / name
            if _is_reparse(path) or path not in allowed_dirs:
                raise EvidenceError(f"undeclared or reparse runtime directory is forbidden: {path}")
        for name in names:
            path = current / name
            if _TRANSIENT_PART.search(name) or path not in allowed_files:
                raise EvidenceError(f"undeclared private/transient runtime file is forbidden: {path}")
            _snapshot(path, run_root)


def _destination_authorized(
    contract: dict[str, Any], relative_paths: Iterable[str]
) -> None:
    evidence_root = contract["roots"]["evidence"]
    declarations = {item["path"] for item in contract["artifacts"]}
    authorized = set(contract["writeAuthorization"]["targets"])
    expected = {evidence_root + relative for relative in relative_paths}
    if not expected.issubset(declarations) or not expected.issubset(authorized):
        raise EvidenceError("bundle target is not exactly contract-declared and authorized")


def _tree_digest(root: Path) -> dict[str, tuple[int, str]]:
    return {
        relative: (path.stat().st_size, sha256_file(path))
        for relative, path in _enumerate_files(root).items()
    }


def _remove_exact_tree(path: Path, parent: Path) -> None:
    target = _assert_plain_ancestry(path, parent, may_be_missing=True)
    if not (target.exists() or target.is_symlink()):
        return
    if _is_reparse(target):
        raise EvidenceBlockedError(f"refusing to clean reparse staging residue: {target}")
    for current_raw, dirs, names in os.walk(target, topdown=False, followlinks=False):
        current = Path(current_raw)
        for name in (*dirs, *names):
            member = current / name
            if _is_reparse(member):
                raise EvidenceBlockedError(
                    f"refusing to clean staging tree containing reparse residue: {member}"
                )
    shutil.rmtree(target)
    if target.exists() or target.is_symlink():
        raise EvidenceBlockedError(f"staging residue remains: {target}")


def _promote(
    staging: Path,
    evidence: Path,
    prior_digest: dict[str, tuple[int, str]] | None,
    expected_seal: str,
) -> None:
    parent = evidence.parent
    token = uuid.uuid4().hex
    backup = parent / f".{evidence.name}.previous-{os.getpid()}-{token}"
    failed_new = parent / f".{evidence.name}.failed-{os.getpid()}-{token}"
    moved_prior = False
    promoted = False
    primary: BaseException | None = None
    cleanup_errors: list[BaseException] = []

    def _seal_matches(root: Path) -> str:
        fresh = seal_bundle(root)
        missing = check_sealed(fresh)
        if missing:
            raise EvidenceError("R0-004: cannot promote an unsealed bundle: " + "; ".join(missing))
        if fresh["bundle_sha256"] != expected_seal:
            raise EvidenceError("R0-004: bundle bytes changed after sealing (seal mismatch)")
        return fresh["bundle_sha256"]

    try:
        _seal_matches(staging)  # before_swap: staged bytes must still equal the sealed bundle
        if prior_digest is not None:
            if _tree_digest(evidence) != prior_digest:
                raise EvidenceError("prior accepted bundle changed before atomic promotion")
            os.replace(evidence, backup)
            moved_prior = True
            _after_backup(evidence)
        os.replace(staging, evidence)
        promoted = True
        _after_promote(evidence)
        validate_bundle(evidence)
        _seal_matches(evidence)  # after_promote read-back: promoted bytes equal the seal
        if moved_prior:
            _remove_exact_tree(backup, parent)
            moved_prior = False
    except BaseException as exc:
        primary = exc
        if promoted:
            try:
                os.replace(evidence, failed_new)
                promoted = False
            except BaseException as cleanup:
                cleanup_errors.append(cleanup)
        if moved_prior:
            try:
                os.replace(backup, evidence)
                moved_prior = False
                if prior_digest is not None and _tree_digest(evidence) != prior_digest:
                    raise EvidenceBlockedError("restored prior bundle bytes do not match")
            except BaseException as cleanup:
                cleanup_errors.append(cleanup)
        for residue in (staging, failed_new, backup):
            try:
                _remove_exact_tree(residue, parent)
            except BaseException as cleanup:
                cleanup_errors.append(cleanup)
        if cleanup_errors:
            raise EvidenceBlockedError(
                f"evidence promotion compensation BLOCKED; residue candidates: {staging}, {failed_new}, {backup}"
            ) from ExceptionGroup(
                "evidence promotion primary and compensation failures",
                [primary, *cleanup_errors],
            )
        if isinstance(primary, EvidenceError):
            raise primary
        raise EvidenceError(f"evidence promotion failed; prior bundle restored: {primary}") from primary


def package_evidence(run_dir: Path, evidence_dir: Path) -> BundleSummary:
    """Package one hash-valid C5 run through staging and atomic promotion."""

    run_root = _absolute(run_dir)
    evidence = _absolute(evidence_dir)
    if not _within(run_root, PROJECT_ROOT) or not run_root.is_dir() or _is_reparse(run_root):
        raise EvidenceError("run_dir must be one exact plain project run directory")
    run_id = run_root.name
    contract_file = run_root.parent / f"{run_id}.contract.json"
    try:
        contract, contract_payload, contract_sha = load_contract(contract_file)
        authority = capture_contract_authority(contract_file, contract, contract_payload, contract_sha)
        if contract["runId"] != run_id:
            raise EvidenceError("canonical contract sibling does not match run_dir identity")
        expected_run = contract_path(contract, contract["roots"]["runtime"].rstrip("/"))
        expected_evidence = contract_path(contract, contract["roots"]["evidence"].rstrip("/"))
        if run_root != _absolute(expected_run):
            raise EvidenceError("run_dir is not the contract's exact declared runtime root")
        if evidence != _absolute(expected_evidence):
            raise EvidenceError("evidence_dir is not the exact declared evidence root")
        loaded = load_state(contract, contract_sha, authority)
        revalidate_loaded_state(loaded)
    except EvidenceError:
        raise
    except (OSError, PipelineStateError) as exc:
        raise EvidenceError(f"cannot load authoritative C5 state: {exc}") from exc
    if loaded.checkpoint.get("state") != "PIXEL_VERIFIED_DETERMINISTIC":
        raise EvidenceError("only a hash-valid PIXEL_VERIFIED_DETERMINISTIC C5 run can be packaged")
    _runtime_tree_is_declared(run_root, contract)

    rir_declaration = artifact_for_role(contract, "reconstruction-rir")
    assert isinstance(rir_declaration, dict)
    rir_path = contract_path(contract, rir_declaration["path"])
    rir_observation = _snapshot(rir_path, run_root, expected=rir_declaration.get("sha256"))
    rir, _ = _strict_json(rir_path, label="authoritative reconstruction IR")
    try:
        validate_rir(rir)
    except Exception as exc:
        raise EvidenceError(f"authoritative reconstruction IR is invalid: {exc}") from None
    structure, raster_sources = _build_structure(rir, run_root, contract["profile"])
    structure["runId"] = run_id

    role_sources = {
        "reference.normalized.png": ("normalized-reference", "intake", "normalized-source"),
        "master.svg": ("sanitized-svg", "reconstruction", "canonical-vector"),
        "preview.png": ("render-preview", "deterministic-render", "deterministic-evidence"),
        "metrics.json": ("pipeline-metrics", "deterministic-metrics", "deterministic-evidence"),
        "diff.png": ("diff-evidence", "deterministic-metrics", "deterministic-evidence"),
        "journal.json": ("pipeline-journal", "pipeline-state", "run-control"),
    }
    bundle_paths = [
        *role_sources,
        "run.contract.json",
        "structure-report.json",
        "provenance.json",
        "registries/tool-registry.json",
        "registries/model-registry.json",
        "manifest.json",
    ]
    bundle_paths.extend(destination for _source, destination, _digest in raster_sources)
    if len(bundle_paths) != len(set(bundle_paths)):
        raise EvidenceError("bundle canonical topology contains a path collision")
    _destination_authorized(contract, bundle_paths)

    tool_path = contract_path(contract, contract["registries"]["toolRegistry"])
    model_path = contract_path(contract, contract["registries"]["modelRegistry"])
    tool_observation = _snapshot(tool_path, PROJECT_ROOT)
    model_observation = _snapshot(model_path, PROJECT_ROOT)
    tool_registry, _ = _strict_json(tool_path, label="tool registry")
    model_registry, _ = _strict_json(model_path, label="model registry")
    if tool_registry.get("schemaVersion") != "design-lab/reconstruction-tools/v1":
        raise EvidenceError("tool registry schema identity is invalid")
    if set(model_registry) != {"schemaVersion", "models"} or model_registry.get("schemaVersion") != "design-lab/reconstruction-models/v1" or model_registry.get("models") != []:
        raise EvidenceError("model registry schema identity is invalid")
    execution_source = _execution_source_evidence()
    checked_out_sha = execution_source["headSha256"]

    parent = evidence.parent
    _assert_plain_ancestry(parent, PROJECT_ROOT, may_be_missing=True)
    parent.mkdir(parents=True, exist_ok=True)
    _assert_plain_ancestry(parent, PROJECT_ROOT, may_be_missing=False)
    prior_digest: dict[str, tuple[int, str]] | None = None
    if evidence.exists() or evidence.is_symlink():
        validate_bundle(evidence)
        prior_digest = _tree_digest(evidence)
    staging = Path(tempfile.mkdtemp(prefix=f".{run_id}.staging-", dir=parent))
    try:
        records: list[dict[str, Any]] = []
        for destination, (role, producer, ownership) in role_sources.items():
            declaration = artifact_for_role(contract, role)
            assert isinstance(declaration, dict)
            source = contract_path(contract, declaration["path"])
            copied = _copy_verified(source, staging / destination, run_root)
            records.append(_artifact_record(destination, copied, producer, ownership))
        copied_contract = _copy_verified(authority.path, staging / "run.contract.json", PROJECT_ROOT)
        records.append(_artifact_record("run.contract.json", copied_contract, "pipeline-state", "run-control"))
        copied_tool = _copy_verified(
            tool_path, staging / "registries" / "tool-registry.json", PROJECT_ROOT
        )
        records.append(
            _artifact_record(
                "registries/tool-registry.json", copied_tool, "evidence-package", "run-control"
            )
        )
        copied_model = _copy_verified(
            model_path, staging / "registries" / "model-registry.json", PROJECT_ROOT
        )
        records.append(
            _artifact_record(
                "registries/model-registry.json", copied_model, "evidence-package", "run-control"
            )
        )
        for source, destination, digest in raster_sources:
            copied = _copy_verified(source, staging / destination, run_root)
            if copied.sha256 != digest:
                raise EvidenceError("semantic raster changed between structure capture and copy")
            records.append(_artifact_record(destination, copied, "reconstruction", "semantic-raster"))

        journal_record = next(item for item in records if item["path"] == "journal.json")
        checkpoint_chain = [
            {
                "sequence": entry["sequence"],
                "path": entry["checkpoint"]["path"],
                "sha256": entry["checkpoint"]["sha256"],
            }
            for entry in loaded.journal["entries"]
        ]
        inferred = [item["id"] for item in structure["objects"] if item["inferred"]]
        provenance = {
            "schemaVersion": PROVENANCE_SCHEMA_ID,
            "runId": run_id,
            "checkedOutSourceSha256": checked_out_sha,
            "sourceTreeState": execution_source["state"],
            "executionSource": execution_source,
            "source": {
                "sourceId": contract["source"]["sourceId"],
                "originalSha256": contract["source"]["sha256"],
                "normalizedSha256": next(
                    item["sha256"] for item in records if item["path"] == "reference.normalized.png"
                ),
                "profileMetadata": contract["source"]["profileMetadata"],
            },
            "registries": {
                "tool": {
                    "path": contract["registries"]["toolRegistry"],
                    "bundlePath": "registries/tool-registry.json",
                    "sha256": tool_observation.sha256,
                    "schemaVersion": tool_registry["schemaVersion"],
                },
                "model": {
                    "path": contract["registries"]["modelRegistry"],
                    "bundlePath": "registries/model-registry.json",
                    "sha256": model_observation.sha256,
                    "schemaVersion": model_registry["schemaVersion"],
                },
            },
            "providerEvents": [{
                "selectedProvider": contract["providerPolicy"]["selectedProvider"],
                "defaultProvider": contract["providerPolicy"]["defaultProvider"],
                "fallbackUsed": False,
                "remoteConsents": contract["providerPolicy"]["remoteConsents"],
            }],
            "rightsStatus": {
                "status": "UNVERIFIED",
                "evidencePath": None,
                "evidenceSha256": None,
            },
            "inferredRegions": inferred,
            "semanticRasterLayers": structure["semanticRasterLayers"],
            "contractSha256": contract_sha,
            "journalSha256": journal_record["sha256"],
            "checkpointChain": checkpoint_chain,
        }
        _scan_report_privacy(provenance)
        structure_observation = _write_new(
            staging / "structure-report.json", canonical_json_bytes(structure), staging
        )
        records.append(_artifact_record("structure-report.json", structure_observation, "evidence-package", "bundle-report"))
        provenance_observation = _write_new(
            staging / "provenance.json", canonical_json_bytes(provenance), staging
        )
        records.append(_artifact_record("provenance.json", provenance_observation, "evidence-package", "bundle-report"))
        verify_artifact_snapshot(rir_observation, run_root)
        verify_artifact_snapshot(tool_observation, PROJECT_ROOT)
        verify_artifact_snapshot(model_observation, PROJECT_ROOT)
        verify_contract_authority(authority, contract)
        revalidate_loaded_state(loaded)
        manifest = {
            "schemaVersion": BUNDLE_SCHEMA_ID,
            "runId": run_id,
            "state": "PIXEL_VERIFIED_DETERMINISTIC",
            "checkedOutSourceSha256": checked_out_sha,
            "sourceTreeState": execution_source["state"],
            "executionSourceDigest": execution_source["digest"],
            "artifacts": sorted(records, key=lambda item: item["path"]),
            "releaseEvidence": {
                "nativeAi": None,
                "illustratorPreview": None,
                "illustratorReadback": None,
                "goldenCorpus": None,
                "exactShaCi": None,
                "rights": None,
                "installedRuntime": None,
                "authorityReceipt": None,
            },
        }
        _write_new(staging / "manifest.json", canonical_json_bytes(manifest), staging)
        _validate_bundle(staging, declared_root=evidence)
        seal = seal_bundle(staging)
        missing = check_sealed(seal)
        if missing:
            raise EvidenceError("R0-004: staged bundle is not sealed: " + "; ".join(missing))
        _after_staging_validation(staging)
        if _execution_source_evidence() != execution_source:
            raise EvidenceError("execution source tree changed before evidence promotion")
        verify_artifact_snapshot(rir_observation, run_root)
        verify_artifact_snapshot(tool_observation, PROJECT_ROOT)
        verify_artifact_snapshot(model_observation, PROJECT_ROOT)
        verify_contract_authority(authority, contract)
        revalidate_loaded_state(loaded)
        _promote(staging, evidence, prior_digest, seal["bundle_sha256"])
        staging = Path()
        return validate_bundle(evidence)
    except Exception as primary:
        cleanup_errors: list[BaseException] = []
        if staging != Path() and (staging.exists() or staging.is_symlink()):
            try:
                _remove_exact_tree(staging, parent)
            except Exception as cleanup:
                cleanup_errors.append(cleanup)
        if cleanup_errors:
            raise EvidenceBlockedError(
                f"evidence staging cleanup BLOCKED; residue path: {staging}"
            ) from ExceptionGroup(
                "evidence packaging primary and cleanup failures",
                [primary, *cleanup_errors],
            )
        if isinstance(primary, EvidenceError):
            raise primary
        if isinstance(primary, (OSError, PipelineStateError)):
            raise EvidenceError(f"evidence packaging failed: {primary}") from primary
        raise


__all__ = [
    "BUNDLE_SCHEMA_ID",
    "BundleSummary",
    "EvidenceBlockedError",
    "EvidenceError",
    "MAX_JSON_BYTES",
    "RenderError",
    "package_evidence",
    "validate_bundle",
]
