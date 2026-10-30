# SPDX-License-Identifier: MIT
"""Immutable contracts for untrusted reconstruction model providers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol


class ProviderError(RuntimeError):
    """Base class for provider-boundary failures."""


class ProviderRegistryError(ProviderError):
    """The registry is malformed, ambiguous, or requests an unknown provider."""


class RemoteProviderDenied(ProviderError):
    """Remote inference was not authorized for this exact source and provider."""


class ProposalBoundaryError(ProviderError):
    """A proposal request or result escaped its immutable run contract."""


ALLOWED_TASKS = (
    "semantic-analysis",
    "ocr",
    "ui-analysis",
    "layer-decomposition",
    "foreground-matting",
    "open-vocabulary-boxes",
    "vector-candidate",
)
ALLOWED_WARNING_CODES = (
    "LOW_CONFIDENCE",
    "INFERRED_CONTENT",
    "OPTIONAL_OUTPUT_OMITTED",
    "PROVIDER_DEGRADED",
)
ALLOWED_EVENT_CODES = (
    "MISSING",
    "HASH_MISMATCH",
    "HASH_CHANGED",
    "LICENSE_DENIED",
    "UNQUALIFIED_NOT_INSTALLED",
    "UNQUALIFIED_CHECKSUM",
    "DISABLED",
    "OOM",
    "PATH_DENIED",
    "NOT_REGULAR",
    "REPARSE_DENIED",
    "REMOTE_CONSENT_REQUIRED",
    "PROVIDER_DEGRADED",
    "NO_PROVIDER",
)


@dataclass(frozen=True)
class ProviderDescriptor:
    artifact_kind: str
    artifact_id: str
    provider_id: str
    provider_version: str
    revision: str
    source: str
    license: str
    commercial_use: str
    checksum_sha256: str
    storage_class: str
    local_path: Path | None
    remote: bool
    device: str
    minimum_vram_mib: int
    tasks: tuple[str, ...]
    default_enabled: bool
    priority: int
    limitations: tuple[str, ...]
    qualification: str

    @property
    def version(self) -> str:
        return self.provider_version

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ProviderDescriptor":
        return cls(
            artifact_kind=value["artifactKind"],
            artifact_id=value["id"],
            provider_id=value["providerId"],
            provider_version=value["version"],
            revision=value["revision"],
            source=value["source"],
            license=value["license"],
            commercial_use=value["commercialUse"],
            checksum_sha256=value["checksumSha256"].lower(),
            storage_class=value["storageClass"],
            local_path=None if value["localPath"] is None else Path(value["localPath"]),
            remote=value["remote"],
            device=value["device"],
            minimum_vram_mib=value["minimumVramMiB"],
            tasks=tuple(value["tasks"]),
            default_enabled=value["defaultEnabled"],
            priority=value["priority"],
            limitations=tuple(value["limitations"]),
            qualification=value["qualification"],
        )


@dataclass(frozen=True)
class FallbackEvent:
    provider_id: str
    code: str
    task: str
    message: str
    recoverable: bool


@dataclass(frozen=True)
class PreflightResult:
    provider_id: str
    status: str
    ready: bool
    events: tuple[FallbackEvent, ...]
    observed_sha256: str | None
    available_vram_mib: int


@dataclass(frozen=True)
class AuthorizedOutput:
    role: str
    artifact_id: str
    path: Path
    expected_sha256: str | None


@dataclass(frozen=True)
class ProposalRequest:
    run_id: str
    job_id: str
    run_root: Path
    source_path: Path
    source_sha256: str
    profile: str
    task: str
    selected_provider: str
    contract_sha256: str
    outputs: tuple[AuthorizedOutput, ...]
    provider_id: str
    provider_version: str


@dataclass(frozen=True)
class ProposalResult:
    provider_id: str
    provider_version: str
    proposal_path: Path
    proposal_sha256: str
    asset_paths: tuple[Path, ...]
    asset_sha256: tuple[str, ...]
    warnings: tuple[str, ...]
    events: tuple[FallbackEvent, ...]
    run_id: str
    job_id: str
    contract_sha256: str


class Provider(Protocol):
    def describe(self) -> ProviderDescriptor: ...

    def preflight(
        self, *, task: str, contract: dict[str, Any] | None = None
    ) -> PreflightResult: ...

    def propose(self, request: ProposalRequest) -> ProposalResult: ...
