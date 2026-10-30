# SPDX-License-Identifier: MIT
"""Fail-closed local PaddleOCR adapter; it never downloads or calls a remote service."""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Sequence as SequenceABC
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from reconstruction.geometry import ProposalValidationError, TextHypothesis, normalize_text_detection

from .base import FallbackEvent, PreflightResult, ProposalBoundaryError, ProposalRequest, ProposalResult, ProviderDescriptor, ProviderError
from .registry import RegisteredProvider, _assert_plain_run_path, validate_proposal_result


MAX_DETECTIONS = 256
MAX_TOTAL_TEXT_CHARS = 16384
MAX_TOTAL_POLYGON_POINTS = 4096
MAX_PROPOSAL_BYTES = 1024 * 1024


class ProviderOOM(RuntimeError):
    """A backend/CUDA out-of-memory condition safe to report as a fallback."""


class _ProposalRejected(RuntimeError):
    """A bounded proposal could not be accepted without leaving an output residue."""


def _is_backend_oom(exc: RuntimeError) -> bool:
    if isinstance(exc, ProviderOOM):
        return True
    qualified_name = f"{type(exc).__module__}.{type(exc).__name__}".lower()
    message = str(exc).lower()
    return (
        "outofmemory" in qualified_name
        or "cuda out of memory" in message
        or "cudnn_status_alloc_failed" in message
        or "hip out of memory" in message
    )


class PaddleOCRProvider:
    """Bounded OCR adapter with an optional explicitly injected local runner."""

    def __init__(self, descriptor: ProviderDescriptor, *, external_roots: Sequence[Path], available_vram_mib: int = 8151, runner: Callable[[ProposalRequest], Sequence[Mapping[str, Any]]] | None = None) -> None:
        self._registered = RegisteredProvider(descriptor, external_roots=external_roots, available_vram_mib=available_vram_mib)
        self._runner = runner

    def describe(self) -> ProviderDescriptor:
        return self._registered.describe()

    def preflight(self, *, task: str, contract: dict[str, Any] | None = None) -> PreflightResult:
        result = self._registered.preflight(task=task, contract=contract)
        if not result.ready or self._runner is not None:
            return result
        event = FallbackEvent(result.provider_id, "MISSING", task, "local PaddleOCR runtime is not installed", True)
        return PreflightResult(result.provider_id, "MISSING", False, (event,), result.observed_sha256, result.available_vram_mib)

    def propose(self, request: ProposalRequest) -> ProposalResult:
        if request.provider_id != self.describe().provider_id or request.provider_version != self.describe().provider_version:
            raise ProviderError("request provider identity does not match PaddleOCR descriptor")
        preflight = self.preflight(task=request.task)
        if not preflight.ready:
            return _write_fallback(request, self.describe(), preflight.events[0])
        try:
            raw_detections = self._runner(request)
            detections = _bounded_detections(raw_detections, _image_size(request.source_path))
        except MemoryError:
            event = FallbackEvent(self.describe().provider_id, "OOM", request.task, "local PaddleOCR runtime exhausted its authorized memory", True)
            return _write_fallback(request, self.describe(), event)
        except RuntimeError as exc:
            if not _is_backend_oom(exc):
                raise
            event = FallbackEvent(self.describe().provider_id, "OOM", request.task, "local PaddleOCR backend reported out of memory", True)
            return _write_fallback(request, self.describe(), event)
        except (OSError, ProposalValidationError, TypeError, ValueError):
            event = FallbackEvent(self.describe().provider_id, "PROVIDER_DEGRADED", request.task, "local PaddleOCR output was rejected", True)
            return _failure_result(request, self.describe(), event)
        try:
            return _write_payload(request, self.describe(), "PROPOSAL", {"texts": [_text_json(item) for item in detections]}, ())
        except _ProposalRejected:
            event = FallbackEvent(self.describe().provider_id, "PROVIDER_DEGRADED", request.task, "local PaddleOCR proposal was rejected before acceptance", True)
            return _failure_result(request, self.describe(), event)


def _image_size(path: Path) -> tuple[int, int]:
    from PIL import Image
    with Image.open(path) as image:
        return image.size


def _text_json(item: TextHypothesis) -> dict[str, Any]:
    return {"text": item.text, "polygon": [list(point) for point in item.polygon], "confidence": item.confidence, "direction": item.direction}


def _bounded_detections(value: Any, canvas: tuple[int, int]) -> tuple[TextHypothesis, ...]:
    """Reject lazy or unbounded runner output before serializing a proposal."""

    if not isinstance(value, SequenceABC) or isinstance(value, (str, bytes, bytearray, Mapping)):
        raise ProposalValidationError("OCR runner must return a bounded concrete sequence")
    if len(value) > MAX_DETECTIONS:
        raise ProposalValidationError("OCR runner emitted too many detections")
    detections: list[TextHypothesis] = []
    total_text_chars = 0
    total_polygon_points = 0
    for item in value:
        if not isinstance(item, Mapping):
            raise ProposalValidationError("OCR detection must be a mapping")
        detection = normalize_text_detection(item, canvas)
        total_text_chars += len(detection.text)
        total_polygon_points += len(detection.polygon)
        if total_text_chars > MAX_TOTAL_TEXT_CHARS or total_polygon_points > MAX_TOTAL_POLYGON_POINTS:
            raise ProposalValidationError("OCR proposal exceeds its aggregate bounds")
        detections.append(detection)
    return tuple(detections)


def _write_fallback(request: ProposalRequest, descriptor: ProviderDescriptor, event: FallbackEvent) -> ProposalResult:
    try:
        return _write_payload(request, descriptor, "FALLBACK", {"texts": []}, (event,))
    except _ProposalRejected:
        return _failure_result(request, descriptor, event)


def _proposal_target(request: ProposalRequest) -> Path:
    outputs = [item for item in request.outputs if item.role == "proposal"]
    if len(outputs) != 1 or outputs[0].artifact_id != "provider-proposal":
        raise ProviderError("request does not contain exactly one authorized proposal output")
    return _assert_plain_run_path(outputs[0].path, request.run_root, may_be_missing=True)


def _failure_result(request: ProposalRequest, descriptor: ProviderDescriptor, event: FallbackEvent) -> ProposalResult:
    """Return typed failure metadata without writing a proposal artifact."""

    target = _proposal_target(request)
    return ProposalResult(
        descriptor.provider_id,
        descriptor.provider_version,
        target,
        "",
        (),
        (),
        (),
        (event,),
        request.run_id,
        request.job_id,
        request.contract_sha256,
    )


def _owned_output_matches(target: Path, request: ProposalRequest, descriptor: ProviderDescriptor, digest: str) -> bool:
    try:
        checked = _assert_plain_run_path(target, request.run_root, may_be_missing=False)
        if hashlib.sha256(checked.read_bytes()).hexdigest() != digest:
            return False
        document = json.loads(checked.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return False
    return document.get("runId") == request.run_id and document.get("jobId") == request.job_id and document.get("contractSha256") == request.contract_sha256 and document.get("provider") == descriptor.provider_id


def _remove_owned_output(target: Path, request: ProposalRequest, descriptor: ProviderDescriptor, digest: str) -> None:
    if not _owned_output_matches(target, request, descriptor, digest):
        raise ProviderError("rejected proposal is not the current identity-bound output")
    target.unlink()
    if target.exists():
        raise ProviderError("rejected proposal residue remains after cleanup")


def _node_identity(state: os.stat_result) -> tuple[int, int, int]:
    return state.st_dev, state.st_ino, state.st_nlink


def _remove_owned_stage(stage: Path, owner: tuple[int, int, int]) -> None:
    try:
        link_state = os.lstat(stage)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ProviderError("proposal staging path cannot be inspected before cleanup") from exc
    try:
        path_state = os.stat(stage)
    except OSError as exc:
        raise ProviderError("proposal staging path cannot be resolved before cleanup") from exc
    if _node_identity(link_state) != owner or _node_identity(path_state) != owner:
        raise ProviderError("proposal staging ownership changed before cleanup")
    stage.unlink()
    try:
        os.lstat(stage)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ProviderError("proposal staging cleanup cannot be verified") from exc
    else:
        raise ProviderError("proposal staging residue remains after cleanup")


def _write_payload(request: ProposalRequest, descriptor: ProviderDescriptor, status: str, payload: dict[str, Any], events: tuple[FallbackEvent, ...]) -> ProposalResult:
    target = _proposal_target(request)
    target.parent.mkdir(parents=True, exist_ok=True)
    target = _assert_plain_run_path(target, request.run_root, may_be_missing=True)
    document = {"schema": "design-lab/reconstruction-proposal/v1", "provider": descriptor.provider_id, "version": descriptor.provider_version, "task": request.task, "status": status, "trust": "untrusted-proposal", "runId": request.run_id, "jobId": request.job_id, "contractSha256": request.contract_sha256, "events": [{"code": event.code, "recoverable": event.recoverable} for event in events], **payload}
    encoded = json.dumps(document, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_PROPOSAL_BYTES:
        raise _ProposalRejected("proposal serialization exceeds its byte limit")
    digest = hashlib.sha256(encoded).hexdigest()
    stage = target.parent / f".{target.name}.{digest[:16]}.stage"
    stage_created = False
    stage_owner: tuple[int, int, int] | None = None
    stream = None
    try:
        stream = stage.open("xb")
        stage_created = True
        try:
            # The open handle is the only authoritative owner immediately after creation.
            stage_owner = _node_identity(os.fstat(stream.fileno()))
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            stream.close()
        _assert_plain_run_path(stage, request.run_root, may_be_missing=False)
        if target.exists():
            raise _ProposalRejected("proposal output is already occupied")
        os.replace(stage, target)
        result = ProposalResult(descriptor.provider_id, descriptor.provider_version, target, digest, (), (), (), events, request.run_id, request.job_id, request.contract_sha256)
        try:
            validate_proposal_result(request, result)
        except ProposalBoundaryError as exc:
            _remove_owned_output(target, request, descriptor, digest)
            raise _ProposalRejected("proposal failed post-write boundary validation") from exc
        return result
    except FileExistsError as exc:
        raise _ProposalRejected("proposal staging is already occupied") from exc
    except OSError as exc:
        raise _ProposalRejected("proposal staging or acceptance failed") from exc
    finally:
        if stage_created and stage_owner is not None:
            _remove_owned_stage(stage, stage_owner)
