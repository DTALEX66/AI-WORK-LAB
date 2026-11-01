# SPDX-License-Identifier: MIT
"""Validation and canonicalization for reconstruction contracts."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from jsonschema.exceptions import best_match

RIR_SCHEMA_ID = "design-lab/reconstruction-ir/v1"
RUN_SCHEMA_ID = "design-lab/reconstruction-run/v1"

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_DIR = _PROJECT_ROOT / "design-lab" / "schemas" / "reconstruction"


class ContractError(ValueError):
    """A schema or cross-field reconstruction contract violation."""


def _load_schema(name: str) -> dict[str, Any]:
    source_checkout = Path(__file__).resolve().parent == _PROJECT_ROOT / 'packages' / 'capabilities' / 'reconstruction'
    if __package__.startswith('design_lab.') and not source_checkout:
        from importlib.resources import files
        source = files('design_lab').joinpath('resources', 'reconstruction', name)
    else:
        source = _SCHEMA_DIR / name
    with source.open("r", encoding="utf-8") as stream:
        schema = json.load(stream)
    Draft202012Validator.check_schema(schema)
    return schema


_RIR_VALIDATOR = Draft202012Validator(
    _load_schema("reconstruction-ir.schema.json"), format_checker=FormatChecker()
)
_RUN_VALIDATOR = Draft202012Validator(
    _load_schema("reconstruction-run.schema.json"), format_checker=FormatChecker()
)


def _error_path(error: ValidationError) -> str:
    path = "$"
    for part in error.absolute_path:
        path += f"[{part}]" if isinstance(part, int) else f".{part}"
    return path


def _validate_schema(validator: Draft202012Validator, value: Any) -> None:
    error = best_match(validator.iter_errors(value))
    if error is not None:
        raise ContractError(f"{_error_path(error)}: {error.message}") from None


def _walk_nodes(nodes: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    for node in nodes:
        yield node
        if node.get("type") == "group":
            yield from _walk_nodes(node["children"])


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _require_project_relative(path: str, field: str, project_root=None) -> Path:
    root = Path(project_root) if project_root is not None else _PROJECT_ROOT
    if not isinstance(path, str) or not path:
        raise ContractError(f"{field}: expected a non-empty project-relative path")
    if "\\" in path or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
        raise ContractError(f"{field}: URLs, URI schemes, and backslash paths are forbidden")
    pure = PurePosixPath(path)
    if pure.is_absolute() or (pure.parts and pure.parts[0].endswith(":")):
        raise ContractError(f"{field}: absolute paths are forbidden")
    if any(part in {"", ".", ".."} for part in pure.parts):
        raise ContractError(f"{field}: parent traversal and dot segments are forbidden")
    try:
        resolved = root.joinpath(*pure.parts).resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise ContractError(f"{field}: cannot resolve path safely: {exc}") from None
    if not _path_is_within(resolved, root):
        raise ContractError(f"{field}: reparse resolution escapes outside the project")
    return resolved


def _parse_timestamp(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise ContractError(f"{field}: invalid RFC 3339 timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError(f"{field}: timestamp must include an offset")
    return parsed.astimezone(timezone.utc)


def _reject_non_finite_numbers(value: Any, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError(f"{path}: non-finite numbers are not valid JSON")
    if isinstance(value, dict):
        for key, child in value.items():
            _reject_non_finite_numbers(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_non_finite_numbers(child, f"{path}[{index}]")


def validate_rir(value: dict, *, project_root=None) -> None:
    """Validate a version-one reconstruction intermediate representation."""

    if __package__.startswith('design_lab.') and project_root is None:
        raise ContractError('installed RIR validation requires an explicit project root')
    _reject_non_finite_numbers(value)
    _validate_schema(_RIR_VALIDATOR, value)
    seen: set[str] = set()
    for node in _walk_nodes(value["layers"]):
        node_id = node["id"]
        if node_id in seen:
            raise ContractError(f"$.layers: duplicate node id {node_id!r}")
        seen.add(node_id)
        if node["type"] == "raster":
            _require_project_relative(node["raster"]["path"], f"node {node_id!r} raster.path", project_root)


def validate_run_contract(value: dict) -> None:
    """Validate a run contract, including identity and authorization bindings."""

    if __package__.startswith('design_lab.'):
        raise ContractError('legacy run-contract validation is source-checkout only; use the installed service task contract')
    from .runtime_roots import runtime_root as _canonical_runtime_root
    from .runtime_roots import evidence_root as _canonical_evidence_root

    _validate_schema(_RUN_VALIDATOR, value)
    run_id = value["runId"]
    job_id = value["jobId"]
    try:
        runtime_root = _canonical_runtime_root(run_id)
        evidence_root = _canonical_evidence_root(run_id)
    except ValueError as exc:
        raise ContractError(f'$.roots: unsafe path or reparse point: {exc}') from exc
    if value["roots"] != {"runtime": runtime_root, "evidence": evidence_root}:
        raise ContractError("$.roots: roots must be the exact declared run runtime/evidence roots")

    resolved_runtime_root = _require_project_relative(runtime_root, "$.roots.runtime")
    resolved_evidence_root = _require_project_relative(evidence_root, "$.roots.evidence")
    lexical_runtime_root = _PROJECT_ROOT.joinpath(*PurePosixPath(runtime_root).parts)
    lexical_evidence_root = _PROJECT_ROOT.joinpath(*PurePosixPath(evidence_root).parts)
    if resolved_runtime_root != lexical_runtime_root:
        raise ContractError("$.roots.runtime: declared root must not resolve through a reparse point")
    if resolved_evidence_root != lexical_evidence_root:
        raise ContractError("$.roots.evidence: declared root must not resolve through a reparse point")

    path_fields = [
        (value["source"]["path"], "$.source.path"),
        (value["source"]["normalizedReferenceTarget"], "$.source.normalizedReferenceTarget"),
        (value["registries"]["toolRegistry"], "$.registries.toolRegistry"),
        (value["registries"]["modelRegistry"], "$.registries.modelRegistry"),
        (value["cancellationPolicy"]["checkpointPath"], "$.cancellationPolicy.checkpointPath"),
    ]
    path_fields.extend(
        (consent["path"], f"$.providerPolicy.remoteConsents[{index}].path")
        for index, consent in enumerate(value["providerPolicy"]["remoteConsents"])
    )
    for path, field in path_fields:
        _require_project_relative(path, field)

    resolved_checkpoint = _require_project_relative(
        value["cancellationPolicy"]["checkpointPath"], "$.cancellationPolicy.checkpointPath"
    )
    if not _path_is_within(resolved_checkpoint, resolved_runtime_root):
        raise ContractError("$.cancellationPolicy.checkpointPath: must be inside the runtime root")

    artifacts = value["artifacts"]
    artifact_ids = [artifact["id"] for artifact in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ContractError("$.artifacts: duplicate artifact id")
    artifact_paths = [artifact["path"] for artifact in artifacts]
    if len(artifact_paths) != len(set(artifact_paths)):
        raise ContractError("$.artifacts: duplicate artifact path")
    for index, path in enumerate(artifact_paths):
        resolved = _require_project_relative(path, f"$.artifacts[{index}].path")
        if not (
            _path_is_within(resolved, resolved_runtime_root)
            or _path_is_within(resolved, resolved_evidence_root)
        ):
            raise ContractError(f"$.artifacts[{index}].path: target is outside declared roots")

    role_contract = {
        "normalized-reference": ("normalized-source", "intake-normalizer-v1"),
        "sanitized-svg": ("vector-output", "rir-svg-serializer-v1"),
        "render-preview": ("evidence", "resvg-v0.47.0"),
        "diff-evidence": ("evidence", "fidelity-metrics-v1"),
        "reconstruction-rir": ("rir-input", "explicit-rir-v1"),
        "pipeline-journal": ("journal", "reconstruction-pipeline-v1"),
        "pipeline-checkpoint": ("checkpoint", "reconstruction-pipeline-v1"),
        "pipeline-metrics": ("metrics", "fidelity-metrics-v1"),
    }
    artifact_roles = [artifact.get("role") for artifact in artifacts if artifact.get("role")]
    singleton_roles = [
        role for role in artifact_roles if role != "pipeline-checkpoint"
    ]
    if len(singleton_roles) != len(set(singleton_roles)):
        raise ContractError("$.artifacts: duplicate artifact role")
    for index, artifact in enumerate(artifacts):
        role = artifact.get("role")
        producer = artifact.get("producer")
        if (role is None) != (producer is None):
            raise ContractError(
                f"$.artifacts[{index}]: role and producer must be declared together"
            )
        if role is not None:
            expected_kind, expected_producer = role_contract[role]
            if artifact["kind"] != expected_kind or producer != expected_producer:
                raise ContractError(
                    f"$.artifacts[{index}]: role/kind/producer binding is inconsistent"
                )

    policy = value["providerPolicy"]
    if policy["selectedProvider"] not in policy["providerAllowlist"]:
        raise ContractError("$.providerPolicy.selectedProvider: provider is not allowlisted")
    selected_provider = policy["selectedProvider"]
    consent_entries = policy["remoteConsents"]
    if selected_provider == "local":
        if consent_entries:
            raise ContractError("$.providerPolicy.remoteConsents: local selection requires no remote consent")
    else:
        required_consent = {
            "path": value["source"]["path"],
            "sha256": value["source"]["sha256"].lower(),
            "provider": selected_provider,
            "consented": True,
        }
        normalized_consents = [
            {
                "path": entry["path"],
                "sha256": entry["sha256"].lower(),
                "provider": entry["provider"],
                "consented": entry["consented"],
            }
            for entry in consent_entries
        ]
        if normalized_consents != [required_consent]:
            raise ContractError(
                "$.providerPolicy.remoteConsents: consent must exactly bind the single source hash/provider"
            )

    authorization = value["writeAuthorization"]
    for index, target in enumerate(authorization["targets"]):
        resolved = _require_project_relative(target, f"$.writeAuthorization.targets[{index}]")
        if not (
            _path_is_within(resolved, resolved_runtime_root)
            or _path_is_within(resolved, resolved_evidence_root)
        ):
            raise ContractError(
                f"$.writeAuthorization.targets[{index}]: target is outside declared roots"
            )

    if authorization["runId"] != run_id or authorization["jobId"] != job_id:
        raise ContractError("$.writeAuthorization: authorization identity does not match job/run")
    if set(authorization["targets"]) != set(artifact_paths) or len(authorization["targets"]) != len(artifact_paths):
        raise ContractError("$.writeAuthorization.targets: targets must exactly match declared artifacts")
    issued_at = _parse_timestamp(authorization["issuedAt"], "$.writeAuthorization.issuedAt")
    expires_at = _parse_timestamp(authorization["expiresAt"], "$.writeAuthorization.expiresAt")
    now = datetime.now(timezone.utc)
    if issued_at > now:
        raise ContractError("$.writeAuthorization.issuedAt: authorization is not active yet")
    if expires_at <= issued_at:
        raise ContractError("$.writeAuthorization.expiresAt: must be later than issuedAt")
    if expires_at <= now:
        raise ContractError("$.writeAuthorization.expiresAt: authorization is expired")

    lifecycle = value["lifecycle"]
    transitions = {
        "created": {"authorized", "cancelled", "failed"},
        "authorized": {"running", "cancelled", "failed"},
        "running": {"completed", "cancelled", "failed"},
        "cancelled": {"authorized"},
        "failed": {"authorized"},
        "completed": {"packaged"},
        "packaged": {"readback-verified"},
        "readback-verified": set(),
    }
    history = lifecycle["history"]
    if history and history[0]["from"] != "created":
        raise ContractError("$.lifecycle.history[0]: lifecycle history must start at created")
    prior_to: str | None = None
    prior_at: datetime | None = None
    for index, entry in enumerate(history):
        if entry["to"] not in transitions[entry["from"]]:
            raise ContractError(f"$.lifecycle.history[{index}]: invalid lifecycle promotion")
        if prior_to is not None and entry["from"] != prior_to:
            raise ContractError(f"$.lifecycle.history[{index}]: discontinuous lifecycle history")
        at = _parse_timestamp(entry["at"], f"$.lifecycle.history[{index}].at")
        if prior_at is not None and at < prior_at:
            raise ContractError(f"$.lifecycle.history[{index}].at: lifecycle timestamps regress")
        prior_to, prior_at = entry["to"], at
    expected_state = prior_to if prior_to is not None else "created"
    if lifecycle["state"] != expected_state:
        raise ContractError("$.lifecycle.state: state does not match lifecycle history")


def canonical_rir_bytes(value: dict, *, project_root=None) -> bytes:
    """Return the validated RIR as canonical compact UTF-8 JSON."""

    validate_rir(value, project_root=project_root)
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ContractError(f"$: cannot canonicalize RIR: {exc}") from None
    return text.encode("utf-8")


def canonical_rir_hash(value: dict, *, project_root=None) -> str:
    """Return SHA-256 of the exact canonical RIR byte sequence."""

    return hashlib.sha256(canonical_rir_bytes(value, project_root=project_root)).hexdigest()
