# SPDX-License-Identifier: MIT
"""Fail-closed journal, immutable checkpoints, and exact rollback boundaries."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import copy
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePath, PurePosixPath
from typing import Any

from .contracts import ContractError, validate_run_contract
from .runtime_roots import RUNTIME_PARENT as _RUNTIME_PARENT
from .runtime_roots import runtime_root as _canonical_runtime_root

PROJECT_ROOT = Path(__file__).resolve().parents[3]
JOURNAL_SCHEMA = "design-lab/reconstruction-journal/v1"
CHECKPOINT_SCHEMA = "design-lab/reconstruction-checkpoint/v1"
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_JOURNAL_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_JOURNAL_ENTRIES = 8
MAX_CHECKPOINT_ARTIFACTS = 5
MAX_CREATED_ARTIFACTS = 14
PIPELINE_STATES = (
    "CREATED",
    "ANALYZED",
    "RECONSTRUCTED_LOCAL",
    "PIXEL_VERIFIED_DETERMINISTIC",
    "PARTIAL",
    "FAILED",
    "CANCELLED",
)


class PipelineStateError(RuntimeError):
    """Journal/checkpoint integrity or state-machine violation."""


class PipelineBlockedError(PipelineStateError):
    """A bounded pipeline cannot append another authorized checkpoint."""


class RollbackBoundaryError(PipelineStateError):
    """A rollback target is not one exact run-created artifact."""


class RollbackBlockedError(PipelineStateError):
    """An exact rollback could not prove filesystem absence."""


@dataclass(frozen=True)
class LoadedState:
    contract: dict[str, Any]
    contract_sha256: str
    run_root: Path
    journal_path: Path
    journal: dict[str, Any]
    checkpoint: dict[str, Any]
    resume_checkpoint: dict[str, Any]
    contract_authority: ContractAuthority | None = None
    journal_observation: ArtifactObservation | None = None
    checkpoint_observations: tuple[ArtifactObservation, ...] = ()
    artifact_observations: tuple[ArtifactObservation, ...] = ()
    registry_observation: ArtifactObservation | None = None


@dataclass(frozen=True)
class ContractAuthority:
    path: Path
    payload: bytes
    canonical_sha256: str
    device: int
    inode: int
    size: int
    mtime_ns: int


@dataclass(frozen=True)
class ArtifactObservation:
    path: Path
    device: int
    inode: int
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class RollbackSummary:
    state: str
    removed: tuple[str, ...]
    blocked: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "removed": list(self.removed),
            "blocked": list(self.blocked),
            "passed": self.passed,
        }


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r}")


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _json_depth(value: Any) -> int:
    maximum = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
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


def decode_json(
    payload: bytes, *, label: str, max_bytes: int = MAX_JSON_BYTES
) -> dict[str, Any]:
    if len(payload) > max_bytes:
        raise PipelineStateError(f"{label} exceeds the bounded JSON byte limit")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_object_no_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise PipelineStateError(f"{label} is not strict JSON: {exc}") from None
    if not isinstance(value, dict):
        raise PipelineStateError(f"{label} must be a JSON object")
    if _json_depth(value) > MAX_JSON_DEPTH:
        raise PipelineStateError(f"{label} exceeds the bounded JSON nesting depth")
    return value


def canonical_json_bytes(value: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise PipelineStateError(f"value is not canonical JSON: {exc}") from None


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise PipelineStateError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def read_bounded(path: Path, *, label: str, max_bytes: int = MAX_JSON_BYTES) -> bytes:
    try:
        metadata = path.stat()
        if metadata.st_size > max_bytes:
            raise PipelineStateError(f"{label} exceeds the bounded file-size limit")
        with path.open("rb") as stream:
            payload = stream.read(max_bytes + 1)
    except PipelineStateError:
        raise
    except OSError as exc:
        raise PipelineStateError(f"cannot read {label}: {exc}") from exc
    if len(payload) > max_bytes:
        raise PipelineStateError(f"{label} exceeds the bounded file-size limit")
    return payload


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_utc_timestamp(value: Any, *, prior: datetime | None) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PipelineStateError("journal timestamp must be explicit UTC")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise PipelineStateError("journal timestamp is not RFC 3339 UTC") from None
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PipelineStateError("journal timestamp must use UTC")
    if prior is not None and parsed < prior:
        raise PipelineStateError("journal timestamps regress")
    return parsed


def _validate_hash_map(value: Any, *, label: str, max_items: int = 32) -> None:
    if not isinstance(value, dict) or len(value) > max_items:
        raise PipelineStateError(f"{label} must be a hash map")
    for key, digest in value.items():
        if not isinstance(key, str) or not key:
            raise PipelineStateError(f"{label} contains an invalid key")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise PipelineStateError(f"{label} contains a malformed sha256")


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    reparse_flag = int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & reparse_flag)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def assert_plain_path(path: Path, root: Path, *, may_be_missing: bool) -> Path:
    lexical = Path(os.path.abspath(os.fspath(path)))
    lexical_root = Path(os.path.abspath(os.fspath(root)))
    if not _within(lexical, lexical_root):
        raise PipelineStateError(f"path escapes exact run root: {lexical}")
    current = lexical_root
    if current.exists() and _is_reparse(current):
        raise PipelineStateError(f"run root is a symlink/reparse point: {current}")
    for part in lexical.relative_to(lexical_root).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _is_reparse(current):
                raise PipelineStateError(f"path contains a symlink/reparse point: {current}")
        elif not may_be_missing:
            raise PipelineStateError(f"required path is absent: {current}")
    return lexical


def snapshot_artifact(path: Path, run_root: Path, *, expected_sha256: str | None = None) -> ArtifactObservation:
    lexical = assert_plain_path(path, run_root, may_be_missing=False)
    try:
        metadata = lexical.stat()
    except OSError as exc:
        raise PipelineStateError(f"cannot inspect exact artifact {lexical}: {exc}") from exc
    if not lexical.is_file() or int(getattr(metadata, "st_nlink", 1)) != 1:
        raise PipelineStateError(
            f"artifact must be one regular non-hardlinked file: {lexical}"
        )
    digest = sha256_file(lexical)
    if expected_sha256 is not None and digest != expected_sha256:
        raise PipelineStateError(f"artifact hash changed or is stale: {lexical}")
    return ArtifactObservation(
        path=lexical,
        device=int(metadata.st_dev),
        inode=int(metadata.st_ino),
        size=int(metadata.st_size),
        mtime_ns=int(metadata.st_mtime_ns),
        sha256=digest,
    )


def verify_artifact_snapshot(observation: ArtifactObservation, run_root: Path) -> None:
    current = snapshot_artifact(
        observation.path, run_root, expected_sha256=observation.sha256
    )
    if current != observation:
        raise PipelineStateError(f"artifact identity changed during commit: {observation.path}")


def revalidate_loaded_state(loaded: LoadedState) -> None:
    verify_contract_authority(loaded.contract_authority, loaded.contract)
    if loaded.journal_observation is None:
        raise PipelineStateError("loaded state lacks a journal identity snapshot")
    verify_artifact_snapshot(loaded.journal_observation, loaded.run_root)
    for observation in loaded.checkpoint_observations:
        verify_artifact_snapshot(observation, loaded.run_root)
    for observation in loaded.artifact_observations:
        verify_artifact_snapshot(observation, loaded.run_root)
    if loaded.registry_observation is None:
        raise PipelineStateError("loaded state lacks a C4 registry snapshot")
    verify_artifact_snapshot(loaded.registry_observation, PROJECT_ROOT)
    verify_contract_authority(loaded.contract_authority, loaded.contract)


def contract_path(contract: dict[str, Any], project_path: str) -> Path:
    pure = PurePosixPath(project_path)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise PipelineStateError(f"unsafe project path: {project_path!r}")
    return PROJECT_ROOT.joinpath(*pure.parts)


def artifact_for_role(
    contract: dict[str, Any], role: str, *, allow_many: bool = False
) -> dict[str, Any] | list[dict[str, Any]]:
    matches = [item for item in contract["artifacts"] if item.get("role") == role]
    if allow_many:
        if not matches:
            raise PipelineStateError(f"run contract omits required artifact role {role!r}")
        return matches
    if len(matches) != 1:
        raise PipelineStateError(f"run contract requires exactly one artifact role {role!r}")
    return matches[0]


def load_contract(contract_file: Path) -> tuple[dict[str, Any], bytes, str]:
    path = Path(os.path.abspath(os.fspath(contract_file)))
    try:
        payload = read_bounded(path, label="run contract")
    except (OSError, PipelineStateError) as exc:
        raise PipelineStateError(f"cannot read run contract: {exc}") from exc
    value = decode_json(payload, label="run contract")
    try:
        validate_run_contract(value)
    except (ContractError, TypeError, ValueError) as exc:
        raise PipelineStateError(f"invalid run contract: {exc}") from None
    canonical = canonical_json_bytes(value)
    return value, payload, sha256_bytes(canonical)


def _prepare_parent(path: Path, run_root: Path) -> None:
    assert_plain_path(path.parent, run_root, may_be_missing=True)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise PipelineStateError(f"cannot create exact artifact parent {path.parent}: {exc}") from exc
    assert_plain_path(path.parent, run_root, may_be_missing=False)


def _after_atomic_replace(_target: Path) -> None:
    """Test seam after namespace commit but before authoritative readback."""


def _remove_failed_atomic_target(target: Path) -> None:
    target.unlink()


def _restore_journal_bytes(target: Path, payload: bytes, run_root: Path) -> None:
    descriptor = -1
    temporary: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".restore", dir=target.parent
        )
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        assert_plain_path(target, run_root, may_be_missing=False)
        os.replace(temporary, target)
        temporary = None
        restored = snapshot_artifact(
            target, run_root, expected_sha256=sha256_bytes(payload)
        )
        if restored.size != len(payload) or read_bounded(
            target, label="restored pipeline journal", max_bytes=max(1, len(payload))
        ) != payload:
            raise PipelineStateError("pipeline journal byte restoration failed")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None and (temporary.exists() or temporary.is_symlink()):
            temporary.unlink()


def atomic_write(path: Path, payload: bytes, run_root: Path, *, immutable: bool = False) -> str:
    target = assert_plain_path(path, run_root, may_be_missing=True)
    _prepare_parent(target, run_root)
    expected_hash = sha256_bytes(payload)
    target_existed = target.exists() or target.is_symlink()
    prior_payload: bytes | None = None
    prior_observation: ArtifactObservation | None = None
    if target_existed:
        assert_plain_path(target, run_root, may_be_missing=False)
        try:
            metadata = target.stat()
        except OSError as exc:
            raise PipelineStateError(f"cannot inspect existing artifact target: {exc}") from exc
        if not target.is_file() or int(getattr(metadata, "st_nlink", 1)) != 1:
            raise PipelineStateError(
                f"artifact target must be one regular non-hardlinked file: {target}"
            )
        if immutable:
            if metadata.st_size != len(payload):
                raise PipelineStateError(
                    f"immutable artifact already exists with different bytes: {target}"
                )
            if sha256_file(target) == expected_hash and read_bounded(
                target,
                label="immutable artifact",
                max_bytes=max(1, len(payload)),
            ) == payload:
                return expected_hash
            raise PipelineStateError(f"immutable artifact already exists with different bytes: {target}")
        if target != run_root / "journal.json":
            raise PipelineStateError(
                f"atomic overwrite is forbidden outside the pipeline journal: {target}"
            )
        prior_observation = snapshot_artifact(target, run_root)
        prior_payload = read_bounded(
            target,
            label="existing pipeline journal",
            max_bytes=max(1, prior_observation.size),
        )
        verify_artifact_snapshot(prior_observation, run_root)
    temporary: Path | None = None
    descriptor = -1
    replaced = False
    try:
        descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        temporary = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        assert_plain_path(target, run_root, may_be_missing=True)
        if prior_observation is not None:
            verify_artifact_snapshot(prior_observation, run_root)
        elif target.exists() or target.is_symlink():
            raise PipelineStateError(
                f"previously-missing atomic target appeared before replace: {target}"
            )
        os.replace(temporary, target)
        replaced = True
        temporary = None
        _after_atomic_replace(target)
        committed = snapshot_artifact(
            target, run_root, expected_sha256=expected_hash
        )
        verify_artifact_snapshot(committed, run_root)
    except Exception as primary:
        cleanup_failures: list[BaseException] = []
        if replaced:
            try:
                if prior_payload is None:
                    _remove_failed_atomic_target(target)
                    if target.exists() or target.is_symlink():
                        raise PipelineStateError(
                            f"failed atomic target residue remains: {target}"
                        )
                else:
                    _restore_journal_bytes(target, prior_payload, run_root)
            except Exception as cleanup:
                cleanup_failures.append(cleanup)
        if cleanup_failures:
            raise PipelineBlockedError(
                f"atomic commit compensation BLOCKED; residue path: {target}"
            ) from ExceptionGroup(
                "atomic commit primary and compensation failures",
                [primary, *cleanup_failures],
            )
        if isinstance(primary, PipelineStateError):
            raise PipelineStateError(
                f"atomic commit failed and exact target compensation succeeded: {target}: {primary}"
            ) from primary
        raise PipelineStateError(
            f"cannot write exact artifact {target}: {primary}"
        ) from primary
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary is not None and (temporary.exists() or temporary.is_symlink()):
            try:
                temporary.unlink()
            except OSError as exc:
                raise PipelineStateError(f"temporary artifact residue remains at {temporary}: {exc}") from exc
    return expected_hash


def _artifact_rel(path: Path) -> str:
    return Path(os.path.abspath(os.fspath(path))).relative_to(PROJECT_ROOT).as_posix()


def _checkpoint_artifact(contract: dict[str, Any], sequence: int) -> dict[str, Any]:
    if sequence < 1 or sequence > MAX_JOURNAL_ENTRIES:
        raise PipelineStateError("pipeline checkpoint slot is exhausted")
    expected = contract["roots"]["runtime"] + f"checkpoints/{sequence:04d}.json"
    matches = [
        item
        for item in artifact_for_role(contract, "pipeline-checkpoint", allow_many=True)
        if item["path"] == expected
    ]
    if len(matches) != 1:
        raise PipelineStateError(f"contract must predeclare exact checkpoint slot {sequence:04d}")
    return matches[0]


def capture_contract_authority(
    contract_file: Path,
    contract: dict[str, Any],
    payload: bytes,
    canonical_sha256: str,
) -> ContractAuthority:
    path = Path(os.path.abspath(os.fspath(contract_file)))
    if _is_reparse(path):
        raise PipelineStateError("run contract must not be a symlink/reparse point")
    try:
        metadata = path.stat()
    except OSError as exc:
        raise PipelineStateError(f"cannot inspect run contract authority: {exc}") from exc
    if not path.is_file() or int(getattr(metadata, "st_nlink", 1)) != 1:
        raise PipelineStateError("run contract authority must be one regular non-hardlinked file")
    current = read_bounded(path, label="run contract")
    if current != payload:
        raise PipelineStateError("run contract changed during authoritative load")
    try:
        validate_run_contract(contract)
    except (ContractError, TypeError, ValueError) as exc:
        raise PipelineStateError(f"run authorization is no longer valid: {exc}") from None
    if sha256_bytes(canonical_json_bytes(contract)) != canonical_sha256:
        raise PipelineStateError("run contract canonical hash changed during load")
    return ContractAuthority(
        path=path,
        payload=payload,
        canonical_sha256=canonical_sha256,
        device=int(metadata.st_dev),
        inode=int(metadata.st_ino),
        size=int(metadata.st_size),
        mtime_ns=int(metadata.st_mtime_ns),
    )


def verify_contract_authority(
    authority: ContractAuthority | None, contract: dict[str, Any]
) -> None:
    try:
        validate_run_contract(contract)
    except (ContractError, TypeError, ValueError) as exc:
        raise PipelineStateError(f"run authorization is no longer valid: {exc}") from None
    if authority is None:
        return
    if _is_reparse(authority.path):
        raise PipelineStateError("run contract authority became a symlink/reparse point")
    try:
        metadata = authority.path.stat()
    except OSError as exc:
        raise PipelineStateError(f"cannot re-read run contract authority: {exc}") from exc
    identity = (
        int(metadata.st_dev),
        int(metadata.st_ino),
        int(metadata.st_size),
        int(metadata.st_mtime_ns),
    )
    expected_identity = (
        authority.device,
        authority.inode,
        authority.size,
        authority.mtime_ns,
    )
    payload = read_bounded(authority.path, label="run contract")
    if identity != expected_identity or payload != authority.payload:
        raise PipelineStateError("run contract disk authority changed during execution")
    decoded = decode_json(payload, label="run contract")
    try:
        validate_run_contract(decoded)
    except (ContractError, TypeError, ValueError) as exc:
        raise PipelineStateError(f"run authorization is no longer valid: {exc}") from None
    if canonical_json_bytes(decoded) != canonical_json_bytes(contract):
        raise PipelineStateError("run contract disk authority no longer matches loaded contract")
    if sha256_bytes(canonical_json_bytes(decoded)) != authority.canonical_sha256:
        raise PipelineStateError("run contract canonical authority hash changed")


def _pipeline_output_paths(runtime_root: str) -> dict[str, str]:
    return {
        "normalized-reference": runtime_root + "reference.normalized.png",
        "sanitized-svg": runtime_root + "master.svg",
        "render-preview": runtime_root + "preview.png",
        "diff-evidence": runtime_root + "diff.png",
        "pipeline-metrics": runtime_root + "metrics.json",
    }


def _required_outputs(runtime_root: str, completed_phases: list[str]) -> set[str]:
    outputs = _pipeline_output_paths(runtime_root)
    required: set[str] = set()
    if "analyze" in completed_phases:
        required.add(outputs["normalized-reference"])
    if "reconstruct" in completed_phases:
        required.update(
            {outputs["sanitized-svg"], outputs["render-preview"]}
        )
    if "verify" in completed_phases:
        required.update({outputs["diff-evidence"], outputs["pipeline-metrics"]})
    return required


def expected_input_hashes(
    contract: dict[str, Any],
    contract_sha256: str,
    phase: str,
    artifacts: dict[str, str],
    *,
    result_state: str | None = None,
) -> dict[str, str]:
    outputs = _pipeline_output_paths(contract["roots"]["runtime"])
    rir_artifact = artifact_for_role(contract, "reconstruction-rir")
    assert isinstance(rir_artifact, dict)
    rir_hash = rir_artifact.get("sha256")
    if not isinstance(rir_hash, str):
        raise PipelineStateError("explicit RIR contract hash is absent")
    if phase in {"create", "analyze"}:
        return {"contract": contract_sha256, "explicitRir": rir_hash}
    if phase == "cancel":
        result = {"contract": contract_sha256, "explicitRir": rir_hash}
        optional = {
            "normalizedReference": outputs["normalized-reference"],
            "sanitizedSvg": outputs["sanitized-svg"],
            "renderPreview": outputs["render-preview"],
        }
        for key, relative in optional.items():
            if relative in artifacts:
                result[key] = artifacts[relative]
        return result
    if phase == "reconstruct":
        normalized = artifacts.get(outputs["normalized-reference"])
        sanitized = artifacts.get(outputs["sanitized-svg"])
        if normalized is None:
            raise PipelineStateError("reconstruct inputs lack normalized-reference hash")
        result = {
            "contract": contract_sha256,
            "explicitRir": rir_hash,
            "normalizedReference": normalized,
        }
        if result_state not in {"FAILED", "CANCELLED"}:
            if sanitized is None:
                raise PipelineStateError("successful reconstruct input lacks sanitized SVG")
            result["sanitizedSvg"] = sanitized
        return result
    if phase == "verify":
        required = {
            "normalizedReference": artifacts.get(outputs["normalized-reference"]),
            "renderPreview": artifacts.get(outputs["render-preview"]),
        }
        if any(value is None for value in required.values()):
            raise PipelineStateError("verify input lacks an authoritative artifact hash")
        return {"contract": contract_sha256, **required}  # type: ignore[dict-item]
    raise PipelineStateError(f"unknown journal phase {phase!r}")


def _validate_metrics_payload_claims(
    contract: dict[str, Any],
    checkpoint: dict[str, Any],
    run_root: Path,
    *,
    allow_missing: bool = False,
) -> None:
    if checkpoint["state"] not in {"PIXEL_VERIFIED_DETERMINISTIC", "PARTIAL"}:
        return
    roles = {
        role: artifact_for_role(contract, role)
        for role in (
            "normalized-reference",
            "render-preview",
            "diff-evidence",
            "pipeline-metrics",
        )
    }
    if not all(isinstance(value, dict) for value in roles.values()):
        raise PipelineStateError("metrics roles are not singleton artifacts")
    paths = {role: value["path"] for role, value in roles.items()}  # type: ignore[index]
    artifact_hashes = checkpoint["artifacts"]
    metrics_path = contract_path(contract, paths["pipeline-metrics"])
    if allow_missing and not metrics_path.exists() and not metrics_path.is_symlink():
        return
    metrics_payload = read_bounded(metrics_path, label="pipeline metrics")
    metrics = decode_json(metrics_payload, label="pipeline metrics")
    required_shape = {
        "schemaVersion", "profileId", "pixelmatchVersion", "pixelThreshold",
        "antiAliasDetection", "matchMinimum", "ssimMinimum", "maeLimitVersion",
        "maeLimit", "edgeMetric", "width", "height", "matchRatio",
        "mismatchCount", "excludedAaCount", "ssim", "meanRgbaError",
        "alphaMeanError", "edgeError", "maxDiffWindow", "components",
        "denseRegions", "failureReasons", "passed", "lifecycleStatus",
        "registryDigest", "metricMaxPixels", "metricMaxBytes",
        "metricBudgetVersion", "referenceSha256", "previewSha256",
        "diffSha256", "mismatchMaskSha256", "excludedAaMaskSha256",
        "inputAuthority", "inputBindings", "referenceIcc", "actualIcc",
    }
    if set(metrics) != required_shape:
        raise PipelineStateError("pipeline metrics have an open or incomplete shape")
    registry_path = PROJECT_ROOT / "design-lab" / "config" / "reconstruction-tools.json"
    registry_payload = read_bounded(registry_path, label="reconstruction tool registry")
    registry = decode_json(registry_payload, label="reconstruction tool registry")
    profile = registry.get("renderProfile")
    pixelmatch = registry.get("metrics", {}).get("pixelmatch")
    if not isinstance(profile, dict) or not isinstance(pixelmatch, dict):
        raise PipelineStateError("reconstruction tool registry profile is malformed")
    exact_values = {
        "schemaVersion": "design-lab/reconstruction-metrics/v1",
        "profileId": profile.get("id"),
        "pixelmatchVersion": pixelmatch.get("version"),
        "pixelThreshold": profile.get("pixelThreshold"),
        "antiAliasDetection": profile.get("antiAliasDetection"),
        "matchMinimum": profile.get("matchMinimum"),
        "ssimMinimum": profile.get("ssimMinimum"),
        "maeLimitVersion": profile.get("maeLimit", {}).get("version"),
        "maeLimit": profile.get("maeLimit", {}).get("value"),
        "edgeMetric": profile.get("edgeMetric", {}).get("id"),
        "width": contract["canvasPolicy"]["width"],
        "height": contract["canvasPolicy"]["height"],
        "registryDigest": sha256_bytes(registry_payload),
        "metricMaxPixels": profile.get("metricMaxPixels"),
        "metricMaxBytes": profile.get("metricMaxBytes"),
        "metricBudgetVersion": profile.get("metricBudgetVersion"),
        "referenceSha256": artifact_hashes.get(paths["normalized-reference"]),
        "previewSha256": artifact_hashes.get(paths["render-preview"]),
        "diffSha256": artifact_hashes.get(paths["diff-evidence"]),
        "inputAuthority": "CONTRACT_BOUND_AUTHORITATIVE",
    }
    for key, value in exact_values.items():
        if metrics.get(key) != value:
            raise PipelineStateError(f"pipeline metrics {key} is not C4/contract-bound")
    numeric_fields = (
        "matchRatio", "ssim", "meanRgbaError", "alphaMeanError", "edgeError"
    )
    integer_fields = ("mismatchCount", "excludedAaCount")
    if any(
        isinstance(metrics.get(key), bool)
        or not isinstance(metrics.get(key), (int, float))
        for key in numeric_fields
    ) or any(
        isinstance(metrics.get(key), bool) or not isinstance(metrics.get(key), int)
        for key in integer_fields
    ):
        raise PipelineStateError("pipeline metrics contain invalid scalar result types")
    if not isinstance(metrics.get("components"), list) or not isinstance(
        metrics.get("denseRegions"), list
    ):
        raise PipelineStateError("pipeline metrics region evidence must be bounded arrays")
    if len(metrics["components"]) > 4096 or len(metrics["denseRegions"]) > 4096:
        raise PipelineStateError("pipeline metrics region evidence exceeds fixed bounds")
    for key in (
        "diffSha256", "mismatchMaskSha256", "excludedAaMaskSha256", "registryDigest"
    ):
        digest = metrics.get(key)
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise PipelineStateError(f"pipeline metrics {key} is not a sha256")
    approved_profiles = registry.get("approvedIccProfiles")
    if not isinstance(approved_profiles, list) or len(approved_profiles) != 1:
        raise PipelineStateError("C4 registry must bind one approved ICC profile")
    approved_icc = approved_profiles[0]
    icc_shape = {
        "profileId", "profileSha256", "rawSha256", "canonicalSha256", "canonicalization"
    }
    reference_icc = metrics.get("referenceIcc")
    actual_icc = metrics.get("actualIcc")
    if (
        not isinstance(reference_icc, dict)
        or set(reference_icc) != icc_shape
        or not isinstance(actual_icc, dict)
        or set(actual_icc) != icc_shape
    ):
        raise PipelineStateError("pipeline metrics ICC evidence shape is invalid")
    if (
        reference_icc.get("profileId") != approved_icc.get("id")
        or reference_icc.get("profileSha256") != approved_icc.get("sha256")
        or reference_icc.get("canonicalSha256") != approved_icc.get("sha256")
        or reference_icc.get("canonicalization") != approved_icc.get("canonicalization")
    ):
        raise PipelineStateError("pipeline metrics referenceIcc is not registry-bound")
    raw_digest = reference_icc.get("rawSha256")
    if (
        not isinstance(raw_digest, str)
        or len(raw_digest) != 64
        or any(character not in "0123456789abcdef" for character in raw_digest)
    ):
        raise PipelineStateError("pipeline metrics referenceIcc raw digest is invalid")
    if actual_icc != {
        "profileId": "implicit-sRGB-none",
        "profileSha256": None,
        "rawSha256": None,
        "canonicalSha256": None,
        "canonicalization": "none",
    }:
        raise PipelineStateError("pipeline metrics actualIcc is not the C4 resvg binding")
    expected_bindings = [
        {
            "path": paths["normalized-reference"],
            "role": "normalized-reference",
            "producer": "intake-normalizer-v1",
            "sha256": artifact_hashes[paths["normalized-reference"]],
        },
        {
            "path": paths["render-preview"],
            "role": "render-preview",
            "producer": "resvg-v0.47.0",
            "sha256": artifact_hashes[paths["render-preview"]],
        },
    ]
    if metrics.get("inputBindings") != expected_bindings:
        raise PipelineStateError("pipeline metrics input bindings are not exact")
    metrics_hash = sha256_bytes(metrics_payload)
    if artifact_hashes.get(paths["pipeline-metrics"]) != metrics_hash:
        raise PipelineStateError("pipeline metrics bytes do not bind checkpoint hash")
    state = checkpoint["state"]
    failures = metrics.get("failureReasons")
    if state == "PIXEL_VERIFIED_DETERMINISTIC":
        if (
            metrics.get("passed") is not True
            or metrics.get("lifecycleStatus") != state
            or failures != []
        ):
            raise PipelineStateError("PIXEL checkpoint lacks authoritative passing metrics")
    else:
        if (
            metrics.get("passed") is not False
            or metrics.get("lifecycleStatus") != "MEASURED"
            or not isinstance(failures, list)
            or not failures
        ):
            raise PipelineStateError("PARTIAL checkpoint lacks measured failure evidence")
        if checkpoint.get("reason") != ",".join(failures):
            raise PipelineStateError("PARTIAL checkpoint reason does not bind metric failures")


def _validate_metrics_semantics(
    contract: dict[str, Any],
    checkpoint: dict[str, Any],
    run_root: Path,
    *,
    allow_missing: bool = False,
) -> None:
    """Independently recompute C4 evidence; payload pass fields are never authority."""

    if checkpoint["state"] not in {"PIXEL_VERIFIED_DETERMINISTIC", "PARTIAL"}:
        return
    roles: dict[str, dict[str, Any]] = {}
    for role in (
        "normalized-reference", "render-preview", "diff-evidence", "pipeline-metrics"
    ):
        artifact = artifact_for_role(contract, role)
        assert isinstance(artifact, dict)
        roles[role] = artifact
    role_paths = {
        role: contract_path(contract, artifact["path"])
        for role, artifact in roles.items()
    }
    if allow_missing and any(
        not path.exists() and not path.is_symlink() for path in role_paths.values()
    ):
        return
    _validate_metrics_payload_claims(
        contract, checkpoint, run_root, allow_missing=allow_missing
    )
    try:
        from .metrics import compare_images
        from .render import _TRUSTED_REGISTRY_SHA256, load_render_profile

        profile = load_render_profile(
            contract["canvasPolicy"]["width"],
            contract["canvasPolicy"]["height"],
        )
        if profile.registry_sha256 != _TRUSTED_REGISTRY_SHA256:
            raise PipelineStateError("C4 profile is not bound to the trusted registry anchor")
        bound_contract = copy.deepcopy(contract)
        bound_artifacts = {item["path"]: item for item in bound_contract["artifacts"]}
        for role in ("normalized-reference", "render-preview"):
            relative = roles[role]["path"]
            digest = checkpoint["artifacts"].get(relative)
            if not isinstance(digest, str):
                raise PipelineStateError(f"checkpoint lacks {role} for metric recomputation")
            bound_artifacts[relative]["sha256"] = digest
        recomputed = compare_images(
            role_paths["normalized-reference"],
            role_paths["render-preview"],
            profile=profile,
            run_contract=bound_contract,
        )
    except PipelineStateError:
        raise
    except Exception as exc:
        raise PipelineStateError(f"cannot independently recompute C4 metrics: {exc}") from None
    expected_payload = {
        "schemaVersion": "design-lab/reconstruction-metrics/v1",
        "profileId": recomputed.profile_id,
        "pixelmatchVersion": recomputed.pixelmatch_version,
        "pixelThreshold": recomputed.pixel_threshold,
        "antiAliasDetection": recomputed.anti_alias_detection,
        "matchMinimum": recomputed.match_minimum,
        "ssimMinimum": recomputed.ssim_minimum,
        "maeLimitVersion": recomputed.mae_limit_version,
        "maeLimit": recomputed.mae_limit,
        "edgeMetric": recomputed.edge_metric,
        "width": recomputed.width,
        "height": recomputed.height,
        "matchRatio": recomputed.match_ratio,
        "mismatchCount": recomputed.mismatch_count,
        "excludedAaCount": recomputed.excluded_aa_count,
        "ssim": recomputed.ssim,
        "meanRgbaError": recomputed.mean_rgba_error,
        "alphaMeanError": recomputed.alpha_mean_error,
        "edgeError": recomputed.edge_error,
        "maxDiffWindow": recomputed.max_diff_window,
        "components": [dataclasses.asdict(item) for item in recomputed.components],
        "denseRegions": [dataclasses.asdict(item) for item in recomputed.dense_regions],
        "failureReasons": list(recomputed.failure_reasons),
        "passed": recomputed.passed,
        "lifecycleStatus": recomputed.lifecycle_status,
        "registryDigest": recomputed.registry_digest,
        "metricMaxPixels": recomputed.metric_max_pixels,
        "metricMaxBytes": recomputed.metric_max_bytes,
        "metricBudgetVersion": recomputed.metric_budget_version,
        "referenceSha256": recomputed.input_bindings[0].sha256,
        "previewSha256": recomputed.input_bindings[1].sha256,
        "diffSha256": recomputed.diff_sha256,
        "mismatchMaskSha256": recomputed.mismatch_mask_sha256,
        "excludedAaMaskSha256": hashlib.sha256(recomputed.excluded_aa_mask).hexdigest(),
        "inputAuthority": recomputed.input_authority,
        "inputBindings": [
            {
                "path": binding.path.relative_to(PROJECT_ROOT).as_posix(),
                "role": binding.role,
                "producer": binding.producer,
                "sha256": binding.sha256,
            }
            for binding in recomputed.input_bindings
        ],
        "referenceIcc": {
            "profileId": recomputed.reference_icc_profile_id,
            "profileSha256": recomputed.reference_icc_profile_sha256,
            "rawSha256": recomputed.reference_raw_icc_sha256,
            "canonicalSha256": recomputed.reference_canonical_icc_sha256,
            "canonicalization": recomputed.reference_icc_canonicalization,
        },
        "actualIcc": {
            "profileId": recomputed.actual_icc_profile_id,
            "profileSha256": recomputed.actual_icc_profile_sha256,
            "rawSha256": recomputed.actual_raw_icc_sha256,
            "canonicalSha256": recomputed.actual_canonical_icc_sha256,
            "canonicalization": recomputed.actual_icc_canonicalization,
        },
    }
    expected_payload = decode_json(
        canonical_json_bytes(expected_payload), label="recomputed pipeline metrics"
    )
    metrics_path = role_paths["pipeline-metrics"]
    metrics = decode_json(read_bounded(metrics_path, label="pipeline metrics"), label="pipeline metrics")
    if metrics != expected_payload:
        differing = sorted(
            key
            for key in set(metrics) | set(expected_payload)
            if metrics.get(key) != expected_payload.get(key)
        )
        raise PipelineStateError(
            f"pipeline metrics do not equal independent C4 recomputation: {differing}"
        )
    diff_hash = checkpoint["artifacts"].get(roles["diff-evidence"]["path"])
    if diff_hash != recomputed.diff_sha256:
        raise PipelineStateError("checkpoint diff hash does not bind recomputed C4 evidence")
    expected_state = (
        "PIXEL_VERIFIED_DETERMINISTIC" if recomputed.passed else "PARTIAL"
    )
    if checkpoint["state"] != expected_state:
        raise PipelineStateError("checkpoint lifecycle does not match recomputed C4 gates")
    expected_reason = None if recomputed.passed else ",".join(recomputed.failure_reasons)
    if checkpoint.get("reason") != expected_reason:
        raise PipelineStateError("checkpoint reason does not match recomputed C4 failures")


def _validate_transition_semantics(
    *,
    contract: dict[str, Any],
    contract_sha256: str,
    prior_checkpoint: dict[str, Any] | None,
    new_state: str,
    phase: str,
    completed_phases: list[str],
    artifacts: dict[str, str],
    input_hashes: dict[str, str],
    reason: str | None,
    resume_from: str | None,
    runtime_root: str,
) -> None:
    canonical_phases = ["analyze", "reconstruct", "verify"]
    if (
        not isinstance(completed_phases, list)
        or completed_phases != canonical_phases[: len(completed_phases)]
        or len(completed_phases) > len(canonical_phases)
    ):
        raise PipelineStateError("checkpoint completed phases are not canonical")
    if not isinstance(artifacts, dict) or len(artifacts) > MAX_CHECKPOINT_ARTIFACTS:
        raise PipelineStateError("checkpoint artifact map exceeds its fixed bound")
    _validate_hash_map(
        artifacts,
        label="checkpoint artifacts",
        max_items=MAX_CHECKPOINT_ARTIFACTS,
    )
    known_outputs = set(_pipeline_output_paths(runtime_root).values())
    if not set(artifacts).issubset(known_outputs):
        raise PipelineStateError("checkpoint contains a non-pipeline or input artifact")
    expected_inputs = expected_input_hashes(
        contract,
        contract_sha256,
        phase,
        artifacts,
        result_state=new_state,
    )
    if input_hashes != expected_inputs:
        raise PipelineStateError("journal inputHashes do not exactly bind phase inputs")
    if prior_checkpoint is None:
        if (
            new_state != "CREATED"
            or phase != "create"
            or completed_phases
            or artifacts
            or reason is not None
            or resume_from is not None
        ):
            raise PipelineStateError("journal must begin with the empty CREATED checkpoint")
        return

    prior_state = prior_checkpoint["state"]
    prior_completed = prior_checkpoint["completedPhases"]
    if prior_state in {"PIXEL_VERIFIED_DETERMINISTIC", "PARTIAL"}:
        raise PipelineStateError("terminal fidelity state cannot transition")
    if new_state in {"FAILED", "CANCELLED"}:
        if completed_phases != prior_completed:
            raise PipelineStateError("failure/cancellation cannot claim an uncompleted phase")
        if not isinstance(reason, str) or not reason:
            raise PipelineStateError("failure/cancellation requires an exact reason")
        if resume_from != prior_state:
            raise PipelineStateError("failure/cancellation resumeFrom must bind the prior state")
        if new_state == "CANCELLED":
            if phase != "cancel":
                raise PipelineStateError("CANCELLED requires the cancel phase")
            allowed = _required_outputs(runtime_root, prior_completed)
        else:
            if len(prior_completed) >= len(canonical_phases):
                raise PipelineStateError("completed run cannot transition to FAILED")
            if phase != canonical_phases[len(prior_completed)]:
                raise PipelineStateError("FAILED phase does not match the next attempted phase")
            attempted = canonical_phases[: len(prior_completed) + 1]
            allowed = _required_outputs(runtime_root, attempted)
        required = _required_outputs(runtime_root, prior_completed)
        if not required.issubset(artifacts) or not set(artifacts).issubset(allowed):
            raise PipelineStateError("failure/cancellation artifact set is not phase-bounded")
        return

    expected_resume = prior_state if prior_state in {"FAILED", "CANCELLED"} else None
    if resume_from != expected_resume:
        raise PipelineStateError("resumed fidelity transition does not bind the prior terminal attempt")
    if new_state == "PARTIAL":
        if not isinstance(reason, str) or not reason:
            raise PipelineStateError("PARTIAL requires an exact metric-failure reason")
    elif reason is not None:
        raise PipelineStateError("successful transition cannot carry a failure reason")
    if len(prior_completed) >= len(canonical_phases):
        raise PipelineStateError("completed phase ledger cannot transition")
    expected_phase = canonical_phases[len(prior_completed)]
    expected_states = {
        "analyze": {"ANALYZED"},
        "reconstruct": {"RECONSTRUCTED_LOCAL"},
        "verify": {"PIXEL_VERIFIED_DETERMINISTIC", "PARTIAL"},
    }[expected_phase]
    if phase != expected_phase or new_state not in expected_states:
        raise PipelineStateError(f"invalid pipeline transition {prior_state!r} -> {new_state!r}")
    expected_completed = canonical_phases[: len(prior_completed) + 1]
    if completed_phases != expected_completed:
        raise PipelineStateError("successful transition phase ledger is discontinuous")
    if set(artifacts) != _required_outputs(runtime_root, expected_completed):
        raise PipelineStateError("successful checkpoint omits or adds phase artifacts")


def _checkpoint_payload(
    *,
    contract: dict[str, Any],
    contract_sha256: str,
    sequence: int,
    state: str,
    completed_phases: list[str],
    artifacts: dict[str, str],
    reason: str | None,
    resume_from: str | None,
) -> dict[str, Any]:
    return {
        "schemaVersion": CHECKPOINT_SCHEMA,
        "runId": contract["runId"],
        "contractSha256": contract_sha256,
        "sequence": sequence,
        "state": state,
        "completedPhases": list(completed_phases),
        "artifacts": dict(sorted(artifacts.items())),
        "reason": reason,
        "resumeFrom": resume_from,
    }


def initialize_state(
    contract: dict[str, Any],
    contract_sha256: str,
    contract_authority: ContractAuthority | None = None,
) -> LoadedState:
    verify_contract_authority(contract_authority, contract)
    run_root = contract_path(contract, contract["roots"]["runtime"].rstrip("/"))
    run_root.mkdir(parents=True, exist_ok=True)
    assert_plain_path(run_root, run_root, may_be_missing=False)
    journal_artifact = artifact_for_role(contract, "pipeline-journal")
    assert isinstance(journal_artifact, dict)
    journal_path = contract_path(contract, journal_artifact["path"])
    if journal_path.exists() or journal_path.is_symlink():
        return load_state(contract, contract_sha256, contract_authority)
    checkpoint_artifact = _checkpoint_artifact(contract, 1)
    checkpoint_path = contract_path(contract, checkpoint_artifact["path"])
    checkpoint = _checkpoint_payload(
        contract=contract,
        contract_sha256=contract_sha256,
        sequence=1,
        state="CREATED",
        completed_phases=[],
        artifacts={},
        reason=None,
        resume_from=None,
    )
    checkpoint_hash = atomic_write(
        checkpoint_path, canonical_json_bytes(checkpoint), run_root, immutable=True
    )
    checkpoint_rel = _artifact_rel(checkpoint_path)
    journal_rel = _artifact_rel(journal_path)
    journal = {
        "schemaVersion": JOURNAL_SCHEMA,
        "runId": contract["runId"],
        "contractSha256": contract_sha256,
        "entries": [
            {
                "sequence": 1,
                "timestampUtc": utc_now(),
                "priorState": None,
                "newState": "CREATED",
                "phase": "create",
                "accepted": True,
                "reason": None,
                "inputHashes": expected_input_hashes(
                    contract, contract_sha256, "create", {}
                ),
                "outputHashes": {checkpoint_rel: checkpoint_hash},
                "checkpoint": {"path": checkpoint_rel, "sha256": checkpoint_hash},
            }
        ],
        "createdArtifacts": [checkpoint_rel, journal_rel],
    }
    atomic_write(journal_path, canonical_json_bytes(journal), run_root)
    verify_contract_authority(contract_authority, contract)
    return load_state(contract, contract_sha256, contract_authority)


def _validate_checkpoint(
    checkpoint: dict[str, Any], entry: dict[str, Any], contract: dict[str, Any], contract_sha256: str
) -> None:
    expected = {
        "schemaVersion", "runId", "contractSha256", "sequence", "state",
        "completedPhases", "artifacts", "reason", "resumeFrom",
    }
    if set(checkpoint) != expected:
        raise PipelineStateError("checkpoint has an open or incomplete shape")
    if checkpoint["schemaVersion"] != CHECKPOINT_SCHEMA:
        raise PipelineStateError("checkpoint schema version mismatch")
    if checkpoint["runId"] != contract["runId"] or checkpoint["contractSha256"] != contract_sha256:
        raise PipelineStateError("checkpoint is stale for this run contract")
    if checkpoint["sequence"] != entry["sequence"] or checkpoint["state"] != entry["newState"]:
        raise PipelineStateError("checkpoint state/sequence does not bind its journal entry")
    if checkpoint["state"] not in PIPELINE_STATES:
        raise PipelineStateError("checkpoint contains an unknown pipeline state")
    if not isinstance(checkpoint["completedPhases"], list) or not isinstance(checkpoint["artifacts"], dict):
        raise PipelineStateError("checkpoint phase/artifact ledger is malformed")


def load_state(
    contract: dict[str, Any],
    contract_sha256: str,
    contract_authority: ContractAuthority | None = None,
) -> LoadedState:
    verify_contract_authority(contract_authority, contract)
    run_root = contract_path(contract, contract["roots"]["runtime"].rstrip("/"))
    journal_artifact = artifact_for_role(contract, "pipeline-journal")
    assert isinstance(journal_artifact, dict)
    journal_path = contract_path(contract, journal_artifact["path"])
    assert_plain_path(journal_path, run_root, may_be_missing=False)
    journal_payload = read_bounded(
        journal_path, label="pipeline journal", max_bytes=MAX_JOURNAL_BYTES
    )
    journal_observation = snapshot_artifact(journal_path, run_root)
    if journal_observation.sha256 != sha256_bytes(journal_payload):
        raise PipelineStateError("pipeline journal changed during bounded read")
    journal = decode_json(
        journal_payload,
        label="pipeline journal",
        max_bytes=MAX_JOURNAL_BYTES,
    )
    if set(journal) != {"schemaVersion", "runId", "contractSha256", "entries", "createdArtifacts"}:
        raise PipelineStateError("pipeline journal has an open or incomplete shape")
    if journal["schemaVersion"] != JOURNAL_SCHEMA or journal["runId"] != contract["runId"]:
        raise PipelineStateError("pipeline journal identity mismatch")
    if journal["contractSha256"] != contract_sha256:
        raise PipelineStateError("pipeline journal is stale for this run contract")
    entries = journal["entries"]
    if (
        not isinstance(entries, list)
        or not entries
        or len(entries) > MAX_JOURNAL_ENTRIES
    ):
        raise PipelineStateError("pipeline journal has no accepted checkpoint")
    allowed_paths = {item["path"] for item in contract["artifacts"]}
    if (
        not isinstance(journal["createdArtifacts"], list)
        or len(journal["createdArtifacts"]) > MAX_CREATED_ARTIFACTS
        or len(journal["createdArtifacts"]) != len(set(journal["createdArtifacts"]))
    ):
        raise PipelineStateError("pipeline artifact ledger is malformed")
    if not set(journal["createdArtifacts"]).issubset(allowed_paths):
        raise PipelineStateError("pipeline artifact ledger contains an unauthorized path")
    last_checkpoint: dict[str, Any] | None = None
    successful_checkpoint: dict[str, Any] | None = None
    checkpoint_observations: list[ArtifactObservation] = []
    legitimate_created = {
        journal_path.relative_to(PROJECT_ROOT).as_posix()
    }
    prior_timestamp: datetime | None = None
    for expected_sequence, entry in enumerate(entries, 1):
        required = {
            "sequence", "timestampUtc", "priorState", "newState", "phase", "accepted",
            "reason", "inputHashes", "outputHashes", "checkpoint",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise PipelineStateError("pipeline journal entry has an open or incomplete shape")
        if entry["sequence"] != expected_sequence or entry["accepted"] is not True:
            raise PipelineStateError("pipeline journal sequence/acceptance is invalid")
        prior_timestamp = _validate_utc_timestamp(
            entry["timestampUtc"], prior=prior_timestamp
        )
        _validate_hash_map(entry["inputHashes"], label="journal inputHashes")
        _validate_hash_map(entry["outputHashes"], label="journal outputHashes")
        if expected_sequence == 1:
            if entry["priorState"] is not None or entry["newState"] != "CREATED":
                raise PipelineStateError("pipeline journal must begin at CREATED")
        elif entry["priorState"] != entries[expected_sequence - 2]["newState"]:
            raise PipelineStateError("pipeline journal transition chain is discontinuous")
        checkpoint_ref = entry["checkpoint"]
        if not isinstance(checkpoint_ref, dict) or set(checkpoint_ref) != {"path", "sha256"}:
            raise PipelineStateError("journal checkpoint reference is malformed")
        if entry["outputHashes"].get(checkpoint_ref["path"]) != checkpoint_ref["sha256"]:
            raise PipelineStateError("journal output hashes do not bind the checkpoint")
        checkpoint_path = contract_path(contract, checkpoint_ref["path"])
        assert_plain_path(checkpoint_path, run_root, may_be_missing=False)
        expected_checkpoint_path = contract["roots"]["runtime"] + f"checkpoints/{expected_sequence:04d}.json"
        if checkpoint_ref["path"] != expected_checkpoint_path:
            raise PipelineStateError("journal checkpoint path does not bind its state")
        if _checkpoint_artifact(contract, expected_sequence)["path"] != checkpoint_ref["path"]:
            raise PipelineStateError("journal checkpoint is not a contract-authorized slot")
        payload = read_bounded(
            checkpoint_path,
            label="pipeline checkpoint",
            max_bytes=MAX_JOURNAL_BYTES,
        )
        checkpoint_observation = snapshot_artifact(
            checkpoint_path,
            run_root,
            expected_sha256=checkpoint_ref["sha256"],
        )
        if checkpoint_observation.sha256 != sha256_bytes(payload):
            raise PipelineStateError("pipeline checkpoint changed during bounded read")
        if sha256_bytes(payload) != checkpoint_ref["sha256"]:
            raise PipelineStateError("journal references a corrupt checkpoint")
        checkpoint = decode_json(payload, label="pipeline checkpoint")
        checkpoint_observations.append(checkpoint_observation)
        _validate_checkpoint(checkpoint, entry, contract, contract_sha256)
        _validate_transition_semantics(
            contract=contract,
            contract_sha256=contract_sha256,
            prior_checkpoint=last_checkpoint,
            new_state=checkpoint["state"],
            phase=entry["phase"],
            completed_phases=checkpoint["completedPhases"],
            artifacts=checkpoint["artifacts"],
            input_hashes=entry["inputHashes"],
            reason=checkpoint["reason"],
            resume_from=checkpoint["resumeFrom"],
            runtime_root=contract["roots"]["runtime"],
        )
        if entry["reason"] != checkpoint["reason"]:
            raise PipelineStateError("journal reason does not bind the checkpoint")
        expected_outputs = dict(checkpoint["artifacts"])
        expected_outputs[checkpoint_ref["path"]] = checkpoint_ref["sha256"]
        if entry["outputHashes"] != expected_outputs:
            raise PipelineStateError("journal output hashes do not exactly bind checkpoint artifacts")
        legitimate_created.update(checkpoint["artifacts"])
        legitimate_created.add(checkpoint_ref["path"])
        if checkpoint["state"] not in {"FAILED", "CANCELLED"}:
            successful_checkpoint = checkpoint
        last_checkpoint = checkpoint
    assert last_checkpoint is not None
    if set(journal["createdArtifacts"]) != legitimate_created:
        raise PipelineStateError("pipeline created-artifact ledger is not checkpoint-derived")
    assert successful_checkpoint is not None
    observed_hashes = dict(successful_checkpoint["artifacts"])
    observed_hashes.update(last_checkpoint["artifacts"])
    artifact_observations = tuple(
        snapshot_artifact(
            contract_path(contract, rel), run_root, expected_sha256=expected_hash
        )
        for rel, expected_hash in sorted(observed_hashes.items())
    )
    registry_path = PROJECT_ROOT / "design-lab" / "config" / "reconstruction-tools.json"
    registry_observation = snapshot_artifact(registry_path, PROJECT_ROOT)
    _validate_metrics_semantics(contract, last_checkpoint, run_root)
    _after_metrics_semantic_validation()
    verify_contract_authority(contract_authority, contract)
    loaded = LoadedState(
        contract,
        contract_sha256,
        run_root,
        journal_path,
        journal,
        last_checkpoint,
        successful_checkpoint,
        contract_authority,
        journal_observation,
        tuple(checkpoint_observations),
        artifact_observations,
        registry_observation,
    )
    revalidate_loaded_state(loaded)
    return loaded


def _after_metrics_semantic_validation() -> None:
    """Test seam immediately before the final loaded-state snapshot revalidation."""


def _after_journal_commit(
    _journal_path: Path, _checkpoint_path: Path, _new_state: str
) -> None:
    """Test seam at the exact post-journal/pre-readback boundary."""


def record_transition(
    loaded: LoadedState,
    *,
    new_state: str,
    phase: str,
    completed_phases: list[str],
    artifact_hashes: dict[str, str],
    input_hashes: dict[str, str],
    reason: str | None = None,
    resume_from: str | None = None,
) -> LoadedState:
    verify_contract_authority(loaded.contract_authority, loaded.contract)
    if new_state not in PIPELINE_STATES:
        raise PipelineStateError(f"unknown pipeline state {new_state!r}")
    prior_state = loaded.checkpoint["state"]
    if new_state == prior_state and new_state not in {"FAILED", "CANCELLED"}:
        raise PipelineStateError("duplicate state transition is forbidden")
    _validate_transition_semantics(
        contract=loaded.contract,
        contract_sha256=loaded.contract_sha256,
        prior_checkpoint=loaded.checkpoint,
        new_state=new_state,
        phase=phase,
        completed_phases=completed_phases,
        artifacts=artifact_hashes,
        input_hashes=input_hashes,
        reason=reason,
        resume_from=resume_from,
        runtime_root=loaded.contract["roots"]["runtime"],
    )
    sequence = len(loaded.journal["entries"]) + 1
    if sequence > MAX_JOURNAL_ENTRIES:
        raise PipelineBlockedError("pipeline journal checkpoint slots are exhausted")
    observations = {
        rel: snapshot_artifact(
            contract_path(loaded.contract, rel),
            loaded.run_root,
            expected_sha256=digest,
        )
        for rel, digest in artifact_hashes.items()
    }
    checkpoint_artifact = _checkpoint_artifact(loaded.contract, sequence)
    checkpoint_path = contract_path(loaded.contract, checkpoint_artifact["path"])
    checkpoint = _checkpoint_payload(
        contract=loaded.contract,
        contract_sha256=loaded.contract_sha256,
        sequence=sequence,
        state=new_state,
        completed_phases=completed_phases,
        artifacts=artifact_hashes,
        reason=reason,
        resume_from=resume_from,
    )
    checkpoint_payload = canonical_json_bytes(checkpoint)
    _validate_metrics_semantics(loaded.contract, checkpoint, loaded.run_root)
    verify_contract_authority(loaded.contract_authority, loaded.contract)
    checkpoint_hash = atomic_write(
        checkpoint_path, checkpoint_payload, loaded.run_root, immutable=True
    )
    for observation in observations.values():
        verify_artifact_snapshot(observation, loaded.run_root)
    verify_contract_authority(loaded.contract_authority, loaded.contract)
    checkpoint_rel = _artifact_rel(checkpoint_path)
    entry = {
        "sequence": sequence,
        "timestampUtc": utc_now(),
        "priorState": prior_state,
        "newState": new_state,
        "phase": phase,
        "accepted": True,
        "reason": reason,
        "inputHashes": dict(sorted(input_hashes.items())),
        "outputHashes": dict(sorted(artifact_hashes.items() | {checkpoint_rel: checkpoint_hash}.items())),
        "checkpoint": {"path": checkpoint_rel, "sha256": checkpoint_hash},
    }
    journal = dict(loaded.journal)
    journal["entries"] = [*loaded.journal["entries"], entry]
    created = list(loaded.journal["createdArtifacts"])
    for rel in [*artifact_hashes, checkpoint_rel]:
        if rel not in created:
            created.append(rel)
    journal["createdArtifacts"] = created
    previous_journal_payload = canonical_json_bytes(loaded.journal)
    atomic_write(loaded.journal_path, canonical_json_bytes(journal), loaded.run_root)
    accepted: LoadedState | None = None
    try:
        _after_journal_commit(loaded.journal_path, checkpoint_path, new_state)
        for observation in observations.values():
            verify_artifact_snapshot(observation, loaded.run_root)
        verify_contract_authority(loaded.contract_authority, loaded.contract)
        accepted = load_state(
            loaded.contract, loaded.contract_sha256, loaded.contract_authority
        )
    except PipelineStateError as primary:
        rollback_failures: list[BaseException] = []
        try:
            atomic_write(
                loaded.journal_path, previous_journal_payload, loaded.run_root
            )
        except PipelineStateError as exc:
            rollback_failures.append(exc)
        try:
            checkpoint_observation = snapshot_artifact(
                checkpoint_path,
                loaded.run_root,
                expected_sha256=checkpoint_hash,
            )
            verify_artifact_snapshot(checkpoint_observation, loaded.run_root)
            checkpoint_path.unlink()
            if checkpoint_path.exists() or checkpoint_path.is_symlink():
                raise PipelineStateError(
                    f"invalid transition checkpoint residue remains: {checkpoint_path}"
                )
        except (OSError, PipelineStateError) as exc:
            rollback_failures.append(exc)
        if rollback_failures:
            raise PipelineStateError(
                f"artifact changed after journal commit; rollback incomplete: {rollback_failures}"
            ) from ExceptionGroup(
                "post-journal validation and rollback failures",
                [primary, *rollback_failures],
            )
        raise PipelineStateError(
            f"artifact changed after journal commit; transition rolled back: {primary}"
        ) from primary
    assert accepted is not None
    return accepted


def rollback_run(run_dir: Path, target: Path | None = None) -> RollbackSummary:
    lexical_run = Path(os.path.abspath(os.fspath(run_dir)))
    expected_parent = _RUNTIME_PARENT
    if lexical_run.parent != expected_parent:
        raise RollbackBoundaryError("rollback run directory is not one canonical reconstruction run root")
    runtime_relative = _canonical_runtime_root(lexical_run.name)
    known_output_paths = set(_pipeline_output_paths(runtime_relative).values())
    known_checkpoint_paths = {
        runtime_relative + f"checkpoints/{sequence:04d}.json"
        for sequence in range(1, MAX_JOURNAL_ENTRIES + 1)
    }
    journal_rel = runtime_relative + "journal.json"
    known_deletable = known_output_paths | known_checkpoint_paths | {journal_rel}
    requested_rel: str | None = None
    if target is not None:
        raw = os.fspath(target)
        pure = PurePath(raw)
        if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
            raise RollbackBoundaryError("rollback target must be a plain run-relative path")
        requested_rel = (lexical_run.joinpath(*pure.parts)).relative_to(
            PROJECT_ROOT
        ).as_posix()
        if requested_rel not in known_output_paths:
            raise RollbackBoundaryError(
                "targeted rollback is limited to canonical pipeline data outputs"
            )
    if not lexical_run.exists() and not lexical_run.is_symlink():
        return RollbackSummary("ROLLED_BACK", (), (), True)
    def rollback_plain(path: Path, *, may_be_missing: bool) -> Path:
        try:
            return assert_plain_path(path, lexical_run, may_be_missing=may_be_missing)
        except PipelineStateError as exc:
            raise RollbackBoundaryError(str(exc)) from exc

    rollback_plain(lexical_run, may_be_missing=False)
    journal_path = lexical_run / "journal.json"
    if not journal_path.exists() and not journal_path.is_symlink():
        residue = [
            rel
            for rel in sorted(known_deletable)
            if PROJECT_ROOT.joinpath(*PurePosixPath(rel).parts).exists()
            or PROJECT_ROOT.joinpath(*PurePosixPath(rel).parts).is_symlink()
        ]
        if residue:
            raise RollbackBlockedError(
                f"rollback BLOCKED; journal absent with known output residue: {residue}"
            )
        return RollbackSummary("ROLLED_BACK", (), (), True)
    try:
        journal_payload = read_bounded(
            journal_path,
            label="pipeline journal",
            max_bytes=MAX_JOURNAL_BYTES,
        )
        journal_observation = snapshot_artifact(journal_path, lexical_run)
        if journal_observation.sha256 != sha256_bytes(journal_payload):
            raise PipelineStateError("pipeline journal changed during bounded read")
        journal = decode_json(
            journal_payload,
            label="pipeline journal",
            max_bytes=MAX_JOURNAL_BYTES,
        )
    except PipelineStateError as exc:
        raise RollbackBoundaryError(str(exc)) from exc
    if set(journal) != {"schemaVersion", "runId", "contractSha256", "entries", "createdArtifacts"}:
        raise RollbackBoundaryError("rollback journal has an open or incomplete shape")
    if journal["schemaVersion"] != JOURNAL_SCHEMA or journal["runId"] != lexical_run.name:
        raise RollbackBoundaryError("rollback journal identity does not bind the run directory")
    contract_sha = journal["contractSha256"]
    if not isinstance(contract_sha, str) or len(contract_sha) != 64 or any(
        character not in "0123456789abcdef" for character in contract_sha
    ):
        raise RollbackBoundaryError("rollback journal contract hash is malformed")
    contract_file = lexical_run.parent / f"{lexical_run.name}.contract.json"
    try:
        contract, contract_payload, loaded_contract_sha = load_contract(contract_file)
        authority = capture_contract_authority(
            contract_file, contract, contract_payload, loaded_contract_sha
        )
    except PipelineStateError as exc:
        raise RollbackBoundaryError(str(exc)) from exc
    if loaded_contract_sha != contract_sha or contract["runId"] != lexical_run.name:
        raise RollbackBoundaryError("rollback contract authority does not bind the journal")
    created = journal.get("createdArtifacts")
    if (
        not isinstance(created, list)
        or len(created) > MAX_CREATED_ARTIFACTS
        or len(created) != len(set(created))
    ):
        raise RollbackBoundaryError("rollback artifact ledger is malformed")
    legitimate = {journal_rel}
    deletion_observations: dict[str, ArtifactObservation] = {
        journal_rel: journal_observation
    }
    entries = journal.get("entries")
    if (
        not isinstance(entries, list)
        or not entries
        or len(entries) > MAX_JOURNAL_ENTRIES
    ):
        raise RollbackBoundaryError("rollback journal has no checkpoint chain")
    prior_state: str | None = None
    prior_checkpoint: dict[str, Any] | None = None
    latest_artifact_hashes: dict[str, str] = {}
    prior_timestamp: datetime | None = None
    for expected_sequence, entry in enumerate(entries, 1):
        required = {
            "sequence", "timestampUtc", "priorState", "newState", "phase", "accepted",
            "reason", "inputHashes", "outputHashes", "checkpoint",
        }
        if not isinstance(entry, dict) or set(entry) != required:
            raise RollbackBoundaryError("rollback journal entry is malformed")
        if entry["sequence"] != expected_sequence or entry["accepted"] is not True:
            raise RollbackBoundaryError("rollback journal sequence/acceptance is invalid")
        try:
            prior_timestamp = _validate_utc_timestamp(
                entry["timestampUtc"], prior=prior_timestamp
            )
            _validate_hash_map(entry["inputHashes"], label="journal inputHashes")
            _validate_hash_map(entry["outputHashes"], label="journal outputHashes")
        except PipelineStateError as exc:
            raise RollbackBoundaryError(str(exc)) from exc
        if entry["priorState"] != prior_state:
            raise RollbackBoundaryError("rollback journal transition chain is discontinuous")
        prior_state = entry["newState"]
        reference = entry["checkpoint"]
        if not isinstance(reference, dict) or set(reference) != {"path", "sha256"}:
            raise RollbackBoundaryError("rollback checkpoint reference is malformed")
        checkpoint_path = PROJECT_ROOT.joinpath(*PurePosixPath(reference["path"]).parts)
        if not _within(checkpoint_path, lexical_run):
            raise RollbackBoundaryError("rollback checkpoint escapes the run root")
        expected_checkpoint_path = runtime_relative + f"checkpoints/{expected_sequence:04d}.json"
        if reference["path"] != expected_checkpoint_path:
            raise RollbackBoundaryError("rollback checkpoint path does not bind its state")
        legitimate.add(reference["path"])
        if checkpoint_path.exists() or checkpoint_path.is_symlink():
            try:
                checkpoint_observation = snapshot_artifact(
                    checkpoint_path,
                    lexical_run,
                    expected_sha256=reference["sha256"],
                )
                payload = read_bounded(
                    checkpoint_path,
                    label="rollback checkpoint",
                    max_bytes=MAX_JOURNAL_BYTES,
                )
            except PipelineStateError as exc:
                raise RollbackBoundaryError(str(exc)) from exc
            if sha256_bytes(payload) != reference["sha256"]:
                raise RollbackBoundaryError("rollback checkpoint hash is corrupt")
            deletion_observations[reference["path"]] = checkpoint_observation
            try:
                checkpoint = decode_json(
                    payload,
                    label="rollback checkpoint",
                    max_bytes=MAX_JOURNAL_BYTES,
                )
            except PipelineStateError as exc:
                raise RollbackBoundaryError(str(exc)) from exc
            if (
                checkpoint.get("schemaVersion") != CHECKPOINT_SCHEMA
                or checkpoint.get("runId") != lexical_run.name
                or checkpoint.get("contractSha256") != contract_sha
                or checkpoint.get("sequence") != expected_sequence
                or checkpoint.get("state") != entry["newState"]
                or not isinstance(checkpoint.get("artifacts"), dict)
            ):
                raise RollbackBoundaryError("rollback checkpoint identity is invalid")
            try:
                _validate_transition_semantics(
                    contract=contract,
                    contract_sha256=contract_sha,
                    prior_checkpoint=prior_checkpoint,
                    new_state=checkpoint["state"],
                    phase=entry["phase"],
                    completed_phases=checkpoint.get("completedPhases"),
                    artifacts=checkpoint["artifacts"],
                    input_hashes=entry["inputHashes"],
                    reason=checkpoint.get("reason"),
                    resume_from=checkpoint.get("resumeFrom"),
                    runtime_root=runtime_relative,
                )
            except PipelineStateError as exc:
                raise RollbackBoundaryError(str(exc)) from exc
            if entry["reason"] != checkpoint.get("reason"):
                raise RollbackBoundaryError("rollback journal reason mismatch")
            expected_outputs = dict(checkpoint["artifacts"])
            expected_outputs[reference["path"]] = reference["sha256"]
            if entry["outputHashes"] != expected_outputs:
                raise RollbackBoundaryError("rollback output hashes do not bind checkpoint")
            try:
                _validate_metrics_semantics(
                    contract, checkpoint, lexical_run, allow_missing=True
                )
            except PipelineStateError as exc:
                raise RollbackBoundaryError(str(exc)) from exc
            for artifact_rel, expected_hash in checkpoint["artifacts"].items():
                artifact_path = PROJECT_ROOT.joinpath(*PurePosixPath(artifact_rel).parts)
                if not _within(artifact_path, lexical_run):
                    raise RollbackBoundaryError("rollback checkpoint artifact escapes the run root")
                if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                    raise RollbackBoundaryError("rollback checkpoint artifact hash is malformed")
                legitimate.add(artifact_rel)
                if artifact_rel not in known_output_paths:
                    raise RollbackBoundaryError(
                        "rollback checkpoint includes a non-deletable input artifact"
                    )
                latest_artifact_hashes[artifact_rel] = expected_hash
            prior_checkpoint = checkpoint
        else:
            raise RollbackBoundaryError("rollback checkpoint is absent before rollback begins")
    if set(created) != legitimate:
        raise RollbackBoundaryError("rollback artifact ledger is not exactly checkpoint-derived")
    if not set(created).issubset(known_deletable):
        raise RollbackBoundaryError("rollback artifact ledger includes a non-deletable path")
    for artifact_rel, expected_hash in latest_artifact_hashes.items():
        artifact_path = PROJECT_ROOT.joinpath(*PurePosixPath(artifact_rel).parts)
        if artifact_path.exists() or artifact_path.is_symlink():
            try:
                deletion_observations[artifact_rel] = snapshot_artifact(
                    artifact_path,
                    lexical_run,
                    expected_sha256=expected_hash,
                )
            except PipelineStateError as exc:
                raise RollbackBoundaryError(str(exc)) from exc
    try:
        verify_artifact_snapshot(journal_observation, lexical_run)
        verify_contract_authority(authority, contract)
    except PipelineStateError as exc:
        raise RollbackBoundaryError(str(exc)) from exc
    exact: dict[str, Path] = {}
    for rel in created:
        if not isinstance(rel, str):
            raise RollbackBoundaryError("rollback artifact ledger contains a non-path")
        path = PROJECT_ROOT.joinpath(*PurePosixPath(rel).parts)
        if not _within(path, lexical_run):
            raise RollbackBoundaryError("rollback ledger escapes the exact run root")
        exact[rel] = path
    if target is not None:
        assert requested_rel is not None
        if requested_rel not in exact:
            raise RollbackBoundaryError("rollback target is not one declared run-created artifact")
        exact = {requested_rel: PROJECT_ROOT.joinpath(*PurePosixPath(requested_rel).parts)}
    ordered = sorted(
        exact.items(),
        key=lambda item: (
            2 if item[0] == journal_rel else 1 if "/checkpoints/" in item[0] else 0,
            item[0],
        ),
    )
    removed: list[str] = []
    blocked: list[str] = []
    for rel, path in ordered:
        try:
            if path.exists() or path.is_symlink():
                try:
                    observation = deletion_observations.get(rel)
                    if observation is None:
                        raise PipelineStateError(
                            f"rollback lacks latest ownership snapshot: {rel}"
                        )
                    verify_artifact_snapshot(observation, lexical_run)
                except PipelineStateError as exc:
                    raise RollbackBoundaryError(str(exc)) from exc
                path.unlink()
            if path.exists() or path.is_symlink():
                blocked.append(rel)
            else:
                removed.append(rel)
        except RollbackBoundaryError:
            raise
        except OSError as exc:
            blocked.append(f"{rel}: {exc}")
        if blocked:
            break
    if blocked:
        raise RollbackBlockedError(f"rollback BLOCKED; exact absence not proven: {blocked}")
    return RollbackSummary("ROLLED_BACK", tuple(removed), (), True)
