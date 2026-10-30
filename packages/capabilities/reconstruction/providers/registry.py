# SPDX-License-Identifier: MIT
"""Closed model registry, provider preflight, and proposal path binding."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from reconstruction.contracts import ContractError, validate_run_contract
from reconstruction.state import canonical_json_bytes

from .base import (
    ALLOWED_EVENT_CODES,
    ALLOWED_TASKS,
    ALLOWED_WARNING_CODES,
    AuthorizedOutput,
    FallbackEvent,
    PreflightResult,
    ProposalBoundaryError,
    ProposalRequest,
    ProposalResult,
    ProviderDescriptor,
    ProviderError,
    ProviderRegistryError,
    RemoteProviderDenied,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "design-lab" / "config" / "reconstruction-models.json"
MAX_REGISTRY_BYTES = 1024 * 1024
MAX_REGISTRY_DEPTH = 16
MAX_REGISTRY_ENTRIES = 64
SHA256_LENGTH = 64
APPROVED_EXTERNAL_ROOTS = (
    Path(r"D:\All projects\Model library"),
    Path(r"D:\All projects\Design External Configuration"),
)
_TOP_LEVEL_KEYS = {"schemaVersion", "hardwarePolicy", "entries"}
_HARDWARE_KEYS = {"defaultDevice", "availableVramMiB", "gpu"}
_ENTRY_KEYS = {
    "artifactKind",
    "id",
    "providerId",
    "version",
    "revision",
    "source",
    "license",
    "commercialUse",
    "checksumSha256",
    "storageClass",
    "localPath",
    "remote",
    "device",
    "minimumVramMiB",
    "tasks",
    "defaultEnabled",
    "priority",
    "limitations",
    "qualification",
}
_COMMERCIAL_STATES = {"ALLOWED", "DENIED", "UNVERIFIED"}
_QUALIFICATION_STATES = {
    "QUALIFIED",
    "UNQUALIFIED_NOT_INSTALLED",
    "UNQUALIFIED_CHECKSUM",
    "DISABLED_LICENSE_CONFLICT",
    "DISABLED_UNMEASURED_VRAM",
}
_SENSITIVE_VALUE_MARKER = re.compile(
    r"(?:\b(?:bearer|cookie|password|secret|token)\b|\.env\b|private[ _-]+key)",
    re.IGNORECASE,
)
_WINDOWS_ABSOLUTE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")
_UNC_PATH = re.compile(r"(?<![A-Za-z0-9_])\\\\[^\\/\s]+[\\/]")
_POSIX_ABSOLUTE = re.compile(r"(?<![A-Za-z0-9_:/])/(?!/)[^\s)]*")
_ASSIGNMENT_KEY = re.compile(
    r"(?<![A-Za-z0-9_])([A-Za-z][A-Za-z0-9_.-]{0,63})\s*[:=]",
    re.IGNORECASE,
)
_SENSITIVE_ASSIGNMENT_KEYS = {
    "apikey",
    "apisecret",
    "apitoken",
    "auth",
    "authorization",
    "authtoken",
    "accesstoken",
    "clientsecret",
    "cookie",
    "credential",
    "credentials",
    "password",
    "passwd",
    "privatekey",
    "prompt",
    "refreshtoken",
    "secret",
    "session",
    "sessionid",
    "sessiontoken",
    "systemprompt",
    "token",
    "userprompt",
}
_ALLOWED_TELEMETRY_ASSIGNMENT_KEYS = {
    "sessioncount",
    "sessionduration",
    "sessiondurationms",
    "sessionelapsed",
    "sessionelapsedms",
}


def _is_sensitive_assignment_key(raw_key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", raw_key.lower())
    if normalized in _ALLOWED_TELEMETRY_ASSIGNMENT_KEYS:
        return False
    return (
        normalized in _SENSITIVE_ASSIGNMENT_KEYS
        or normalized.startswith(
            (
                "auth",
                "authorization",
                "credential",
                "authentication",
                "private",
                "prompt",
                "session",
            )
        )
        or normalized.endswith(
            ("apikey", "cookie", "password", "privatekey", "secret", "token")
        )
    )


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant {value!r}")


def _object_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON key {key!r}")
        value[key] = item
    return value


def _depth(value: Any) -> int:
    maximum = 0
    stack = [(value, 1)]
    while stack:
        item, depth = stack.pop()
        maximum = max(maximum, depth)
        if maximum > MAX_REGISTRY_DEPTH:
            return maximum
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return maximum


def _strict_object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ProviderRegistryError(f"{label} must contain exactly {sorted(keys)!r}")
    return value


def _bounded_text(value: Any, label: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ProviderRegistryError(f"{label} must be a non-empty bounded string")
    return value


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == SHA256_LENGTH
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _is_absolute_path(value: str) -> bool:
    """Accept both POSIX and Windows absolute paths.

    Model/toolchain ``localPath`` entries are pinned to Windows absolute paths
    (e.g. ``D:\\All projects\\Model library\\...``). On Linux these are not
    ``Path.is_absolute()``, but they are still explicit (non-relative) locations,
    so the registry must accept them cross-platform.
    """
    if Path(value).is_absolute():
        return True
    return bool(_WINDOWS_ABSOLUTE_RE.match(value))


def _validate_entry(value: Any, index: int) -> ProviderDescriptor:
    entry = _strict_object(value, _ENTRY_KEYS, f"entries[{index}]")
    for key in (
        "artifactKind",
        "id",
        "providerId",
        "version",
        "revision",
        "source",
        "license",
        "storageClass",
        "device",
        "qualification",
    ):
        _bounded_text(entry[key], f"entries[{index}].{key}")
    if entry["artifactKind"] not in {"model", "binary"}:
        raise ProviderRegistryError(f"entries[{index}].artifactKind is not allowed")
    if entry["commercialUse"] not in _COMMERCIAL_STATES:
        raise ProviderRegistryError(f"entries[{index}].commercialUse is not closed")
    if not _is_sha256(entry["checksumSha256"]):
        raise ProviderRegistryError(f"entries[{index}].checksumSha256 is malformed")
    if entry["checksumSha256"] == "0" * SHA256_LENGTH and entry["qualification"] == "QUALIFIED":
        raise ProviderRegistryError(f"entries[{index}] cannot qualify an all-zero checksum placeholder")
    if entry["qualification"] not in _QUALIFICATION_STATES:
        raise ProviderRegistryError(f"entries[{index}].qualification is not closed")
    if entry["device"] not in {"cpu", "cuda", "external-binary", "remote"}:
        raise ProviderRegistryError(f"entries[{index}].device is not allowed")
    if not isinstance(entry["remote"], bool) or not isinstance(entry["defaultEnabled"], bool):
        raise ProviderRegistryError(f"entries[{index}] boolean policy fields are malformed")
    local_path = entry["localPath"]
    if entry["remote"]:
        if local_path is not None or entry["device"] != "remote":
            raise ProviderRegistryError(f"entries[{index}] remote provider has local execution state")
    elif not isinstance(local_path, str) or not _is_absolute_path(local_path):
        raise ProviderRegistryError(f"entries[{index}].localPath must be an explicit absolute path")
    minimum_vram = entry["minimumVramMiB"]
    priority = entry["priority"]
    if isinstance(minimum_vram, bool) or not isinstance(minimum_vram, int) or not 0 <= minimum_vram <= 131072:
        raise ProviderRegistryError(f"entries[{index}].minimumVramMiB is invalid")
    if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 10000:
        raise ProviderRegistryError(f"entries[{index}].priority is invalid")
    tasks = entry["tasks"]
    if (
        not isinstance(tasks, list)
        or not tasks
        or len(tasks) > len(ALLOWED_TASKS)
        or len(tasks) != len(set(tasks))
        or any(task not in ALLOWED_TASKS for task in tasks)
    ):
        raise ProviderRegistryError(f"entries[{index}].tasks is not a closed unique task list")
    limitations = entry["limitations"]
    if (
        not isinstance(limitations, list)
        or len(limitations) > 16
        or len(limitations) != len(set(limitations))
        or any(not isinstance(item, str) or not item or len(item) > 128 for item in limitations)
    ):
        raise ProviderRegistryError(f"entries[{index}].limitations is invalid")
    if entry["qualification"].startswith("DISABLED_") and entry["defaultEnabled"]:
        raise ProviderRegistryError(f"entries[{index}] cannot default-enable a disabled provider")
    return ProviderDescriptor.from_mapping(entry)


@dataclass(frozen=True)
class ProviderRegistry:
    schema_version: str
    default_device: str
    available_vram_mib: int
    gpu: str
    entries: tuple[ProviderDescriptor, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProviderRegistry":
        top = _strict_object(value, _TOP_LEVEL_KEYS, "registry")
        if top["schemaVersion"] != "design-lab/reconstruction-models/v1":
            raise ProviderRegistryError("registry schemaVersion is unsupported")
        hardware = _strict_object(top["hardwarePolicy"], _HARDWARE_KEYS, "hardwarePolicy")
        if hardware["defaultDevice"] not in {"cpu", "cuda"}:
            raise ProviderRegistryError("hardwarePolicy.defaultDevice is unsupported")
        available = hardware["availableVramMiB"]
        if isinstance(available, bool) or not isinstance(available, int) or not 0 <= available <= 131072:
            raise ProviderRegistryError("hardwarePolicy.availableVramMiB is invalid")
        gpu = _bounded_text(hardware["gpu"], "hardwarePolicy.gpu")
        raw_entries = top["entries"]
        if not isinstance(raw_entries, list) or not raw_entries or len(raw_entries) > MAX_REGISTRY_ENTRIES:
            raise ProviderRegistryError("entries must be a bounded non-empty list")
        entries = tuple(_validate_entry(item, index) for index, item in enumerate(raw_entries))
        ids = [entry.artifact_id for entry in entries]
        providers = [entry.provider_id for entry in entries]
        if len(ids) != len(set(ids)):
            raise ProviderRegistryError("registry contains duplicate artifact ids")
        if len(providers) != len(set(providers)):
            raise ProviderRegistryError("registry contains duplicate provider ids")
        return cls(top["schemaVersion"], hardware["defaultDevice"], available, gpu, entries)

    def by_id(self, artifact_id: str) -> ProviderDescriptor:
        matches = [entry for entry in self.entries if entry.artifact_id == artifact_id]
        if len(matches) != 1:
            raise ProviderRegistryError(f"unknown model or binary {artifact_id!r}")
        return matches[0]


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> ProviderRegistry:
    try:
        if _path_has_reparse_component(path):
            raise ProviderRegistryError("provider registry must not resolve through a reparse point")
        before = path.stat()
        if not path.is_file() or before.st_size > MAX_REGISTRY_BYTES or before.st_nlink != 1:
            raise ProviderRegistryError("provider registry is absent, not regular, or oversized")
        payload = path.read_bytes()
        after = path.stat()
    except ProviderRegistryError:
        raise
    except OSError as exc:
        raise ProviderRegistryError(f"cannot read provider registry: {exc}") from exc
    if len(payload) > MAX_REGISTRY_BYTES:
        raise ProviderRegistryError("provider registry exceeds its byte limit")
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ProviderRegistryError("provider registry changed while it was being read")
    try:
        value = json.loads(
            payload.decode("utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_object_no_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ProviderRegistryError(f"provider registry is not strict JSON: {exc}") from None
    if _depth(value) > MAX_REGISTRY_DEPTH:
        raise ProviderRegistryError("provider registry exceeds its nesting-depth limit")
    return ProviderRegistry.from_mapping(value)


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return stat.S_ISLNK(metadata.st_mode) or bool(attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)))


def _path_has_reparse_component(path: Path) -> bool:
    lexical = Path(os.path.abspath(os.fspath(path)))
    chain = (lexical,) + tuple(lexical.parents)
    return any((item.exists() or item.is_symlink()) and _is_reparse(item) for item in chain)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _plain_external_file(path: Path, roots: Sequence[Path]) -> tuple[str | None, Path | None]:
    lexical = Path(os.path.abspath(os.fspath(path)))
    lexical_roots = tuple(Path(os.path.abspath(os.fspath(root))) for root in roots)
    containing = next((root for root in lexical_roots if _within(lexical, root)), None)
    if containing is None:
        return "PATH_DENIED", None
    current = containing
    if not current.is_dir() or _is_reparse(current):
        return "REPARSE_DENIED", None
    for part in lexical.relative_to(containing).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _is_reparse(current):
                return "REPARSE_DENIED", None
    if not lexical.exists():
        return "MISSING", lexical
    if not lexical.is_file():
        return "NOT_REGULAR", lexical
    try:
        if lexical.stat().st_nlink != 1:
            return "NOT_REGULAR", lexical
    except OSError:
        return "NOT_REGULAR", lexical
    return None, lexical


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class RegisteredProvider:
    def __init__(
        self,
        descriptor: ProviderDescriptor,
        *,
        external_roots: Sequence[Path] = APPROVED_EXTERNAL_ROOTS,
        available_vram_mib: int = 8151,
    ) -> None:
        self._descriptor = descriptor
        self._external_roots = tuple(external_roots)
        self._available_vram_mib = available_vram_mib

    def describe(self) -> ProviderDescriptor:
        return self._descriptor

    def _failure(self, code: str, message: str, *, task: str) -> PreflightResult:
        event = FallbackEvent(
            self._descriptor.provider_id,
            code,
            task,
            message,
            True,
        )
        return PreflightResult(
            self._descriptor.provider_id,
            code,
            False,
            (event,),
            None,
            self._available_vram_mib,
        )

    def preflight(
        self, *, task: str, contract: dict[str, Any] | None = None
    ) -> PreflightResult:
        descriptor = self._descriptor
        requested_task = task
        if requested_task not in descriptor.tasks:
            return self._failure(
                "NO_PROVIDER",
                "provider does not implement the requested task",
                task=requested_task,
            )
        if descriptor.commercial_use != "ALLOWED":
            return self._failure(
                "LICENSE_DENIED",
                "commercial-use policy does not allow this provider",
                task=requested_task,
            )
        if descriptor.qualification != "QUALIFIED":
            code = "DISABLED" if descriptor.qualification.startswith("DISABLED_") else descriptor.qualification
            return self._failure(
                code,
                f"provider qualification is {descriptor.qualification}",
                task=requested_task,
            )
        if descriptor.device == "cuda" and descriptor.minimum_vram_mib > self._available_vram_mib:
            return self._failure(
                "OOM",
                f"requires {descriptor.minimum_vram_mib} MiB but only {self._available_vram_mib} MiB is authorized",
                task=requested_task,
            )
        if descriptor.remote:
            if contract is None:
                return self._failure(
                    "REMOTE_CONSENT_REQUIRED",
                    "remote provider requires an exact validated per-file contract",
                    task=requested_task,
                )
            try:
                _authorize_remote_provider(contract, descriptor.provider_id)
            except RemoteProviderDenied:
                return self._failure(
                    "REMOTE_CONSENT_REQUIRED",
                    "remote provider contract or consent validation failed",
                    task=requested_task,
                )
            return PreflightResult(descriptor.provider_id, "READY", True, (), None, self._available_vram_mib)
        assert descriptor.local_path is not None
        denied, path = _plain_external_file(descriptor.local_path, self._external_roots)
        if denied is not None:
            return self._failure(
                denied, f"local artifact path failed {denied}", task=requested_task
            )
        assert path is not None
        try:
            before = path.stat()
            observed = _sha256_file(path)
            after = path.stat()
        except OSError:
            return self._failure(
                "MISSING", "local artifact cannot be read", task=requested_task
            )
        postflight_denied, postflight_path = _plain_external_file(
            descriptor.local_path, self._external_roots
        )
        if postflight_denied is not None or postflight_path != path:
            code = "HASH_CHANGED" if postflight_denied is None else postflight_denied
            return self._failure(
                code,
                "local artifact path changed during hashing",
                task=requested_task,
            )
        if not _same_file_identity(before, after):
            return self._failure(
                "HASH_CHANGED", "local artifact changed while hashing", task=requested_task
            )
        if observed != descriptor.checksum_sha256:
            result = self._failure(
                "HASH_MISMATCH",
                "local artifact checksum does not match the registry",
                task=requested_task,
            )
            return PreflightResult(
                result.provider_id,
                result.status,
                result.ready,
                result.events,
                observed,
                result.available_vram_mib,
            )
        return PreflightResult(descriptor.provider_id, "READY", True, (), observed, self._available_vram_mib)

    def propose(self, request: ProposalRequest) -> ProposalResult:
        raise ProviderError(f"provider adapter {self._descriptor.provider_id!r} is not implemented")


def _validate_remote_consent(contract: Mapping[str, Any], provider_id: str) -> None:
    try:
        policy = contract["providerPolicy"]
        source = contract["source"]
        allowlist = policy["providerAllowlist"]
        selected = policy["selectedProvider"]
        consents = policy["remoteConsents"]
    except (KeyError, TypeError):
        raise RemoteProviderDenied("remote provider policy is malformed") from None
    required = {
        "path": source.get("path"),
        "sha256": str(source.get("sha256", "")).lower(),
        "provider": provider_id,
        "consented": True,
    }
    normalized = []
    for item in consents if isinstance(consents, list) else ():
        if not isinstance(item, dict):
            raise RemoteProviderDenied("remote consent entry is malformed")
        normalized.append(
            {
                "path": item.get("path"),
                "sha256": str(item.get("sha256", "")).lower(),
                "provider": item.get("provider"),
                "consented": item.get("consented"),
            }
        )
    if selected != provider_id or provider_id not in allowlist or normalized != [required]:
        raise RemoteProviderDenied("remote provider lacks exact allowlist and per-file consent")


def _authorize_remote_provider(contract: dict[str, Any], provider_id: str) -> None:
    if contract.get("registries", {}).get("modelRegistry") != "design-lab/config/reconstruction-models.json":
        raise RemoteProviderDenied("run contract does not bind the canonical model registry")
    _validate_remote_consent(contract, provider_id)
    try:
        validate_run_contract(contract)
    except ContractError as exc:
        raise RemoteProviderDenied(str(exc)) from exc
    source = _contract_project_path(contract["source"]["path"])
    try:
        observed_source = _hash_plain_project_file(source, label="remote source")
    except ProposalBoundaryError as exc:
        raise RemoteProviderDenied(str(exc)) from exc
    if observed_source != contract["source"]["sha256"].lower():
        raise RemoteProviderDenied(
            "remote source no longer matches the exact consented path and hash"
        )


def load_enabled_providers(
    contract: dict[str, Any],
    registry: ProviderRegistry | dict[str, Any],
    *,
    requested_ids: Sequence[str] | None = None,
    external_roots: Sequence[Path] = APPROVED_EXTERNAL_ROOTS,
    available_vram_mib: int | None = None,
    task: str | None = None,
) -> list[RegisteredProvider]:
    parsed = registry if isinstance(registry, ProviderRegistry) else ProviderRegistry.from_mapping(registry)
    selected_provider = contract.get("providerPolicy", {}).get("selectedProvider")
    if contract.get("registries", {}).get("modelRegistry") != "design-lab/config/reconstruction-models.json":
        raise ProviderRegistryError("run contract does not bind the canonical model registry")
    if selected_provider != "local":
        try:
            _authorize_remote_provider(contract, str(selected_provider))
        except RemoteProviderDenied:
            raise
    else:
        try:
            validate_run_contract(contract)
        except ContractError as exc:
            raise ProviderRegistryError(f"run contract is invalid: {exc}") from exc
    if requested_ids is not None:
        ids = tuple(requested_ids)
    elif selected_provider == "local":
        ids = tuple(
            entry.artifact_id
            for entry in parsed.entries
            if entry.default_enabled
            and not entry.remote
            and entry.qualification == "QUALIFIED"
            and entry.commercial_use == "ALLOWED"
            and (task is None or task in entry.tasks)
        )
    else:
        ids = tuple(
            entry.artifact_id
            for entry in parsed.entries
            if entry.default_enabled
            and entry.remote
            and entry.provider_id == selected_provider
            and entry.qualification == "QUALIFIED"
            and entry.commercial_use == "ALLOWED"
            and (task is None or task in entry.tasks)
        )
    if not ids or len(ids) != len(set(ids)):
        raise ProviderRegistryError("provider request must be a non-empty unique id sequence")
    descriptors = [parsed.by_id(artifact_id) for artifact_id in ids]
    vram = parsed.available_vram_mib if available_vram_mib is None else available_vram_mib
    loaded: list[RegisteredProvider] = []
    for descriptor in descriptors:
        if not descriptor.default_enabled:
            raise ProviderRegistryError(f"provider {descriptor.artifact_id!r} is disabled")
        if selected_provider == "local" and descriptor.remote:
            raise RemoteProviderDenied("local provider selection cannot activate a remote provider")
        if selected_provider != "local" and descriptor.provider_id != selected_provider:
            raise RemoteProviderDenied("remote provider selection does not match the requested registry entry")
        requested_task = descriptor.tasks[0] if task is None else task
        provider = RegisteredProvider(
            descriptor, external_roots=external_roots, available_vram_mib=vram
        )
        result = provider.preflight(
            task=requested_task,
            contract=contract if selected_provider != "local" else None,
        )
        if not result.ready:
            raise ProviderRegistryError(
                f"provider {descriptor.provider_id!r} failed preflight: {result.status}"
            )
        loaded.append(provider)
    return loaded


@dataclass(frozen=True)
class ProviderSelection:
    selected: RegisteredProvider | None
    events: tuple[FallbackEvent, ...]


def preflight_task(
    registry: ProviderRegistry,
    task: str,
    *,
    external_roots: Sequence[Path] = APPROVED_EXTERNAL_ROOTS,
    available_vram_mib: int | None = None,
    contract: dict[str, Any] | None = None,
) -> ProviderSelection:
    if task not in ALLOWED_TASKS:
        raise ProviderRegistryError(f"unknown provider task {task!r}")
    vram = registry.available_vram_mib if available_vram_mib is None else available_vram_mib
    candidates = sorted(
        (entry for entry in registry.entries if entry.default_enabled and task in entry.tasks),
        key=lambda entry: (entry.priority, entry.artifact_id),
    )
    events: list[FallbackEvent] = []
    for descriptor in candidates:
        if descriptor.remote:
            if contract is None:
                events.append(
                    FallbackEvent(
                        descriptor.provider_id,
                        "REMOTE_CONSENT_REQUIRED",
                        task,
                        "remote provider requires an exact validated per-file contract",
                        True,
                    )
                )
                continue
            provider = RegisteredProvider(
                descriptor, external_roots=external_roots, available_vram_mib=vram
            )
            result = provider.preflight(task=task, contract=contract)
            if result.ready:
                return ProviderSelection(provider, tuple(events))
            events.extend(result.events)
            continue
        provider = RegisteredProvider(descriptor, external_roots=external_roots, available_vram_mib=vram)
        result = provider.preflight(task=task)
        if result.ready:
            return ProviderSelection(provider, tuple(events))
        events.extend(result.events)
    events.append(
        FallbackEvent(
            "provider-registry",
            "NO_PROVIDER",
            task,
            "no qualified provider passed preflight for the requested task",
            False,
        )
    )
    return ProviderSelection(None, tuple(events))


def _assert_plain_project_node(
    path: Path, *, label: str, kind: str, may_be_missing: bool = False
) -> Path:
    lexical_project = Path(os.path.abspath(os.fspath(PROJECT_ROOT)))
    lexical = Path(os.path.abspath(os.fspath(path)))
    if not _within(lexical, lexical_project):
        raise ProposalBoundaryError(f"{label} escapes the trusted project root")
    current = lexical_project
    if not current.is_dir() or _is_reparse(current):
        raise ProposalBoundaryError("trusted project root is absent or a reparse point")
    for part in lexical.relative_to(lexical_project).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _is_reparse(current):
                raise ProposalBoundaryError(f"{label} traverses a reparse point")
    if lexical.exists():
        if kind == "file" and not lexical.is_file():
            raise ProposalBoundaryError(f"{label} is not a regular file")
        if kind == "directory" and not lexical.is_dir():
            raise ProposalBoundaryError(f"{label} is not a directory")
        if kind == "file":
            try:
                if lexical.stat().st_nlink != 1:
                    raise ProposalBoundaryError(f"{label} is hardlinked")
            except OSError as exc:
                raise ProposalBoundaryError(f"cannot inspect {label}") from exc
    elif not may_be_missing:
        raise ProposalBoundaryError(f"{label} is absent")
    return lexical


def _same_file_identity(before: os.stat_result, after: os.stat_result) -> bool:
    return (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_nlink,
    ) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_nlink,
    )


def _hash_plain_project_file(path: Path, *, label: str) -> str:
    checked = _assert_plain_project_node(path, label=label, kind="file")
    try:
        before = checked.stat()
        observed = _sha256_file(checked)
        after = checked.stat()
    except OSError as exc:
        raise ProposalBoundaryError(f"cannot read {label}") from exc
    _assert_plain_project_node(checked, label=label, kind="file")
    if not _same_file_identity(before, after):
        raise ProposalBoundaryError(f"{label} changed while hashing")
    return observed


def _assert_plain_run_path(path: Path, run_root: Path, *, may_be_missing: bool) -> Path:
    lexical_root = Path(os.path.abspath(os.fspath(run_root)))
    lexical = Path(os.path.abspath(os.fspath(path)))
    _assert_plain_project_node(lexical_root, label="run root", kind="directory")
    if not _within(lexical, lexical_root):
        raise ProposalBoundaryError(f"output escapes exact run root: {lexical}")
    current = lexical_root
    for part in lexical.relative_to(lexical_root).parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if _is_reparse(current):
                raise ProposalBoundaryError(f"output traverses a reparse point: {current}")
    return _assert_plain_project_node(
        lexical, label="provider output", kind="file", may_be_missing=may_be_missing
    )


def _contract_project_path(value: str) -> Path:
    return PROJECT_ROOT.joinpath(*Path(value.replace("/", os.sep)).parts)


def bind_proposal_request(
    contract: dict[str, Any],
    task: str,
    artifact_ids: Sequence[str],
    *,
    provider: ProviderDescriptor,
) -> ProposalRequest:
    if task not in ALLOWED_TASKS:
        raise ProposalBoundaryError(f"unknown provider task {task!r}")
    if task not in provider.tasks:
        raise ProposalBoundaryError("provider descriptor does not authorize the requested task")
    try:
        validate_run_contract(contract)
    except ContractError as exc:
        raise ProposalBoundaryError(f"run contract is invalid: {exc}") from exc
    if contract["registries"]["modelRegistry"] != "design-lab/config/reconstruction-models.json":
        raise ProposalBoundaryError("run contract does not bind the canonical model registry")
    selected = contract["providerPolicy"]["selectedProvider"]
    if (selected == "local" and provider.remote) or (selected != "local" and (not provider.remote or provider.provider_id != selected)):
        raise ProposalBoundaryError("provider descriptor does not match the contract-selected execution boundary")
    run_root = _contract_project_path(contract["roots"]["runtime"])
    run_root = _assert_plain_project_node(run_root, label="run root", kind="directory")
    source = _contract_project_path(contract["source"]["path"])
    observed_source = _hash_plain_project_file(source, label="source")
    if observed_source != contract["source"]["sha256"].lower():
        raise ProposalBoundaryError("source hash changed after contract authorization")
    if not artifact_ids or len(artifact_ids) != len(set(artifact_ids)):
        raise ProposalBoundaryError("proposal output roles must be a unique non-empty sequence")
    artifacts = {item["id"]: item for item in contract["artifacts"]}
    outputs: list[AuthorizedOutput] = []
    proposal_count = 0
    for artifact_id in artifact_ids:
        artifact = artifacts.get(artifact_id)
        if artifact is None:
            raise ProposalBoundaryError(f"unknown authorized artifact role {artifact_id!r}")
        if artifact_id == "provider-proposal":
            role = "proposal"
            proposal_count += 1
        elif artifact_id == "provider-asset" or artifact_id.startswith("provider-asset-"):
            role = "asset"
        else:
            raise ProposalBoundaryError(f"artifact id {artifact_id!r} is not a provider output role")
        if artifact["kind"] != "evidence":
            raise ProposalBoundaryError(f"provider output role {artifact_id!r} has the wrong artifact kind")
        path = _assert_plain_run_path(_contract_project_path(artifact["path"]), run_root, may_be_missing=True)
        outputs.append(AuthorizedOutput(role, artifact_id, path, artifact.get("sha256")))
    if proposal_count != 1 or outputs[0].role != "proposal":
        raise ProposalBoundaryError("one proposal role must precede all provider asset roles")
    authorized = set(contract["writeAuthorization"]["targets"])
    if any(artifacts[item.artifact_id]["path"] not in authorized for item in outputs):
        raise ProposalBoundaryError("provider outputs are not exact authorized write targets")
    contract_hash = hashlib.sha256(canonical_json_bytes(contract)).hexdigest()
    return ProposalRequest(
        contract["runId"],
        contract["jobId"],
        run_root,
        source,
        observed_source,
        contract["profile"],
        task,
        contract["providerPolicy"]["selectedProvider"],
        contract_hash,
        tuple(outputs),
        provider.provider_id,
        provider.provider_version,
    )


def _validate_result_diagnostics(
    request: ProposalRequest, result: ProposalResult
) -> None:
    if (
        not isinstance(result.warnings, tuple)
        or len(result.warnings) > 32
        or len(result.warnings) != len(set(result.warnings))
        or any(
            not isinstance(warning, str) or warning not in ALLOWED_WARNING_CODES
            for warning in result.warnings
        )
    ):
        raise ProposalBoundaryError("proposal warnings are not a closed bounded code tuple")
    if not isinstance(result.events, tuple) or len(result.events) > 32:
        raise ProposalBoundaryError("proposal events are not a bounded tuple")
    for event in result.events:
        if not isinstance(event, FallbackEvent):
            raise ProposalBoundaryError("proposal event has the wrong typed contract")
        if event.provider_id != result.provider_id or event.task != request.task:
            raise ProposalBoundaryError("proposal event provider/task identity changed")
        if event.code not in ALLOWED_EVENT_CODES or not isinstance(event.recoverable, bool):
            raise ProposalBoundaryError("proposal event code or recovery state is not closed")
        message = event.message
        sensitive_assignment = (
            any(
                _is_sensitive_assignment_key(match.group(1))
                for match in _ASSIGNMENT_KEY.finditer(message)
            )
            if isinstance(message, str)
            else False
        )
        if (
            not isinstance(message, str)
            or not 1 <= len(message) <= 512
            or any(ord(character) < 32 for character in message)
            or _SENSITIVE_VALUE_MARKER.search(message)
            or sensitive_assignment
            or _WINDOWS_ABSOLUTE.search(message)
            or _UNC_PATH.search(message)
            or _POSIX_ABSOLUTE.search(message)
        ):
            raise ProposalBoundaryError("proposal event message is unsafe for evidence")


def validate_proposal_result(
    request: ProposalRequest,
    result: ProposalResult,
    *,
    expected_provider_id: str | None = None,
    expected_provider_version: str | None = None,
) -> None:
    if (
        result.run_id != request.run_id
        or result.job_id != request.job_id
        or result.contract_sha256 != request.contract_sha256
    ):
        raise ProposalBoundaryError("proposal result run/job/contract identity changed")
    if _hash_plain_project_file(request.source_path, label="proposal source") != request.source_sha256:
        raise ProposalBoundaryError("proposal source hash changed after request binding")
    bound_provider_id = request.provider_id if expected_provider_id is None else expected_provider_id
    bound_provider_version = request.provider_version if expected_provider_version is None else expected_provider_version
    if result.provider_id != bound_provider_id:
        raise ProposalBoundaryError("proposal provider identity changed")
    if result.provider_version != bound_provider_version:
        raise ProposalBoundaryError("proposal provider version changed")
    _validate_result_diagnostics(request, result)
    proposal_outputs = [item for item in request.outputs if item.role == "proposal"]
    asset_outputs = [item for item in request.outputs if item.role == "asset"]
    if len(proposal_outputs) != 1:
        raise ProposalBoundaryError("request does not contain one proposal output")
    proposal_path = _assert_plain_run_path(result.proposal_path, request.run_root, may_be_missing=False)
    if proposal_path != proposal_outputs[0].path:
        raise ProposalBoundaryError("proposal path does not match its authorized role")
    if tuple(result.asset_paths) != tuple(item.path for item in asset_outputs):
        raise ProposalBoundaryError("asset paths do not exactly match authorized asset roles")
    if len(result.asset_sha256) != len(result.asset_paths):
        raise ProposalBoundaryError("asset hash cardinality does not match asset paths")
    declared = ((proposal_path, result.proposal_sha256, proposal_outputs[0].expected_sha256),) + tuple(
        (path, digest, output.expected_sha256)
        for path, digest, output in zip(result.asset_paths, result.asset_sha256, asset_outputs, strict=True)
    )
    for path, digest, contract_digest in declared:
        checked = _assert_plain_run_path(path, request.run_root, may_be_missing=False)
        if not _is_sha256(digest):
            raise ProposalBoundaryError("proposal result contains a malformed sha256")
        before = checked.stat()
        observed = _sha256_file(checked)
        after = checked.stat()
        _assert_plain_run_path(checked, request.run_root, may_be_missing=False)
        if not _same_file_identity(before, after):
            raise ProposalBoundaryError(f"proposal output changed while hashing: {checked.name}")
        if observed != digest.lower():
            raise ProposalBoundaryError(f"proposal result hash changed for {checked.name}")
        if contract_digest is not None and observed != contract_digest:
            raise ProposalBoundaryError(f"proposal result does not match contract hash for {checked.name}")
