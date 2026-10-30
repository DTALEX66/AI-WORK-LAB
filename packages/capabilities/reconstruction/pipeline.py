# SPDX-License-Identifier: MIT
"""Resumable deterministic no-AI reconstruction orchestration."""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import ContractError, validate_rir
from .intake import IntakeError, normalize_reference_for_contract
from .metrics import FidelityError, FidelityMetrics, compare_images
from .render import RenderError, load_render_profile, render_svg
from .state import (
    PROJECT_ROOT,
    ArtifactObservation,
    LoadedState,
    PipelineBlockedError,
    PipelineStateError,
    RollbackBlockedError,
    RollbackBoundaryError,
    RollbackSummary,
    artifact_for_role,
    assert_plain_path,
    atomic_write,
    canonical_json_bytes,
    capture_contract_authority,
    contract_path,
    decode_json,
    expected_input_hashes,
    initialize_state,
    load_contract,
    record_transition,
    read_bounded,
    revalidate_loaded_state,
    rollback_run,
    sha256_bytes,
    sha256_file,
    snapshot_artifact,
    verify_artifact_snapshot,
    verify_contract_authority,
)
from .svg import serialize_svg
from .svg_safety import UnsafeSVGError

CAPABILITY_CLAIM = "ORCHESTRATION_ONLY_NO_SEMANTIC_DECOMPOSITION"
if os.name == "nt":
    PINNED_RESVG_BINARY = Path(
        r"D:\All projects\Design External Configuration\toolchains\resvg\v0.47.0\resvg.exe"
    )
else:
    PINNED_RESVG_BINARY = Path("/opt/resvg/v0.47.0/resvg")
TERMINAL_STATES = {
    "PIXEL_VERIFIED_DETERMINISTIC",
    "PARTIAL",
}
PHASE_TARGETS = {
    "analyze": "ANALYZED",
    "reconstruct": "RECONSTRUCTED_LOCAL",
    "verify": "PIXEL_VERIFIED_DETERMINISTIC",
}


class PipelineError(RuntimeError):
    """The pipeline contract, integrity boundary, or execution failed."""


@dataclass(frozen=True)
class RunSummary:
    contract_path: Path
    run_id: str
    state: str
    transitions: tuple[str, ...]
    completed_phases: tuple[str, ...]
    artifact_hashes: dict[str, str]
    passed: bool
    capability_claim: str
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contractPath": os.fspath(self.contract_path),
            "runId": self.run_id,
            "state": self.state,
            "transitions": list(self.transitions),
            "completedPhases": list(self.completed_phases),
            "artifactHashes": dict(sorted(self.artifact_hashes.items())),
            "passed": self.passed,
            "capabilityClaim": self.capability_claim,
            "reason": self.reason,
        }


def _role_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    required = (
        "normalized-reference",
        "reconstruction-rir",
        "sanitized-svg",
        "render-preview",
        "diff-evidence",
        "pipeline-metrics",
        "pipeline-journal",
    )
    roles: dict[str, dict[str, Any]] = {}
    for role in required:
        artifact = artifact_for_role(contract, role)
        assert isinstance(artifact, dict)
        roles[role] = artifact
    checkpoint_artifacts = artifact_for_role(
        contract, "pipeline-checkpoint", allow_many=True
    )
    assert isinstance(checkpoint_artifacts, list)
    expected_checkpoint_paths = {
        contract["roots"]["runtime"] + f"checkpoints/{sequence:04d}.json"
        for sequence in range(1, 9)
    }
    if {item["path"] for item in checkpoint_artifacts} != expected_checkpoint_paths:
        raise PipelineError("contract must predeclare exactly eight sequence checkpoint slots")
    runtime = contract["roots"]["runtime"]
    expected_names = {
        "normalized-reference": "reference.normalized.png",
        "sanitized-svg": "master.svg",
        "render-preview": "preview.png",
        "diff-evidence": "diff.png",
        "pipeline-metrics": "metrics.json",
        "pipeline-journal": "journal.json",
    }
    for role, name in expected_names.items():
        if roles[role]["path"] != runtime + name:
            raise PipelineError(f"{role} must use canonical runtime path {runtime + name}")
    checkpoint_root = runtime + "checkpoints/"
    if contract["cancellationPolicy"] != {
        "cancelable": True,
        "resume": "checkpoint",
        "checkpointPath": checkpoint_root,
    }:
        raise PipelineError("pipeline requires exact cancelable checkpoint-resume policy")
    if not {"analyze", "reconstruct", "verify"}.issubset(contract["requestedOperations"]):
        raise PipelineError("pipeline contract must authorize analyze, reconstruct, and verify")
    return roles


def _path_for(contract: dict[str, Any], artifact: dict[str, Any]) -> Path:
    return contract_path(contract, artifact["path"])


def _assert_contract_file_unchanged(contract_file: Path, original_payload: bytes) -> None:
    try:
        current = read_bounded(
            Path(os.path.abspath(os.fspath(contract_file))), label="run contract"
        )
    except (OSError, PipelineStateError) as exc:
        raise PipelineError(f"cannot re-read run contract before commit: {exc}") from exc
    if current != original_payload:
        raise PipelineError("run contract changed during pipeline execution")


def _load_explicit_rir(
    contract: dict[str, Any], roles: dict[str, dict[str, Any]], run_root: Path
) -> tuple[dict[str, Any], bytes, str]:
    artifact = roles["reconstruction-rir"]
    expected_hash = artifact.get("sha256")
    if expected_hash is None:
        raise PipelineError("explicit RIR artifact must be bound to a contract sha256")
    path = _path_for(contract, artifact)
    assert_plain_path(path, run_root, may_be_missing=False)
    try:
        payload = read_bounded(path, label="explicit RIR input")
    except (OSError, PipelineStateError) as exc:
        raise PipelineError(f"cannot read explicit RIR input: {exc}") from exc
    actual_hash = sha256_bytes(payload)
    if actual_hash != expected_hash:
        raise PipelineError("explicit RIR bytes do not match the contract hash")
    value = decode_json(payload, label="explicit RIR input")
    try:
        validate_rir(value)
    except (ContractError, TypeError, ValueError) as exc:
        raise PipelineError(f"explicit RIR is invalid: {exc}") from None
    canvas = contract["canvasPolicy"]
    if value["canvas"] != {
        "width": canvas["width"],
        "height": canvas["height"],
        "colorSpace": "srgb",
    }:
        raise PipelineError("explicit RIR canvas does not match the run contract")
    return value, payload, actual_hash


def _artifact_hashes(loaded: LoadedState) -> dict[str, str]:
    value = loaded.resume_checkpoint.get("artifacts", {})
    if not isinstance(value, dict):
        raise PipelineError("checkpoint artifact ledger is malformed")
    return dict(value)


def _current_artifact_hashes(loaded: LoadedState) -> dict[str, str]:
    value = loaded.checkpoint.get("artifacts", {})
    if not isinstance(value, dict):
        raise PipelineError("current checkpoint artifact ledger is malformed")
    return dict(value)


def _prepare_phase_outputs(
    loaded: LoadedState,
    roles: dict[str, dict[str, Any]],
    phase: str,
) -> dict[str, ArtifactObservation | None]:
    phase_roles = {
        "analyze": ("normalized-reference",),
        "reconstruct": ("sanitized-svg", "render-preview"),
        "verify": ("diff-evidence", "pipeline-metrics"),
    }[phase]
    owned_hashes: dict[str, str] = {}
    for checkpoint in (loaded.resume_checkpoint, loaded.checkpoint):
        owned_hashes.update(checkpoint.get("artifacts", {}))
    owned_paths = set(loaded.journal["createdArtifacts"])
    claims: dict[str, ArtifactObservation | None] = {}
    verify_contract_authority(loaded.contract_authority, loaded.contract)
    for role in phase_roles:
        artifact = roles[role]
        path = _path_for(loaded.contract, artifact)
        if path.exists() or path.is_symlink():
            if artifact["path"] not in owned_paths:
                raise PipelineError(
                    f"pre-existing output target is not owned by this run: {artifact['path']}"
                )
            observation = snapshot_artifact(
                path,
                loaded.run_root,
                expected_sha256=owned_hashes.get(artifact["path"]),
            )
            if artifact["path"] in loaded.resume_checkpoint.get("artifacts", {}):
                raise PipelineError(
                    f"incomplete phase cannot overwrite successful output: {artifact['path']}"
                )
            try:
                verify_artifact_snapshot(observation, loaded.run_root)
                path.unlink()
            except (OSError, PipelineStateError) as exc:
                raise PipelineBlockedError(
                    f"cannot clear prior-owned partial output: {artifact['path']}: {exc}"
                ) from exc
            if path.exists() or path.is_symlink():
                raise PipelineBlockedError(
                    f"prior-owned partial output residue remains: {artifact['path']}"
                )
            observation = None
        else:
            observation = None
        claims[artifact["path"]] = observation
    return claims


def _assert_output_claim(
    loaded: LoadedState,
    artifact: dict[str, Any],
    claims: dict[str, ArtifactObservation | None],
) -> None:
    if artifact["path"] not in claims:
        raise PipelineError(f"output was not phase-snapshotted: {artifact['path']}")
    target = _path_for(loaded.contract, artifact)
    observation = claims[artifact["path"]]
    if observation is None:
        if target.exists() or target.is_symlink():
            raise PipelineError(
                f"previously-missing output target appeared before write: {artifact['path']}"
            )
    else:
        verify_artifact_snapshot(observation, loaded.run_root)
    verify_contract_authority(loaded.contract_authority, loaded.contract)


def _discover_created_output_hashes(
    loaded: LoadedState, written_outputs: dict[str, ArtifactObservation]
) -> dict[str, str]:
    """Bind partial phase outputs before recording FAILED without broad scanning."""

    hashes = _artifact_hashes(loaded)
    by_path = {artifact["path"]: artifact for artifact in loaded.contract["artifacts"]}
    for artifact_path in written_outputs:
        artifact = by_path[artifact_path]
        path = contract_path(loaded.contract, artifact["path"])
        if path.exists() or path.is_symlink():
            verify_artifact_snapshot(written_outputs[artifact_path], loaded.run_root)
            assert_plain_path(path, loaded.run_root, may_be_missing=False)
            if not path.is_file():
                raise PipelineError(
                    f"declared partial artifact is not a regular file: {artifact['path']}"
                )
            digest = sha256_file(path)
            expected = artifact.get("sha256")
            if expected is not None and expected != digest:
                raise PipelineError(
                    f"declared partial artifact conflicts with contract sha256: {artifact['path']}"
                )
            hashes[artifact["path"]] = digest
    return hashes


def _completed(loaded: LoadedState) -> list[str]:
    value = loaded.checkpoint.get("completedPhases", [])
    if not isinstance(value, list) or any(item not in PHASE_TARGETS for item in value):
        raise PipelineError("checkpoint completed-phase ledger is malformed")
    expected = [phase for phase in ("analyze", "reconstruct", "verify") if phase in value]
    if value != expected:
        raise PipelineError("checkpoint completed phases are out of canonical order")
    return list(value)


def _record(
    loaded: LoadedState,
    *,
    state: str,
    phase: str,
    completed: list[str],
    artifacts: dict[str, str],
    inputs: dict[str, str],
    reason: str | None = None,
    resume_from: str | None = None,
) -> LoadedState:
    try:
        return record_transition(
            loaded,
            new_state=state,
            phase=phase,
            completed_phases=completed,
            artifact_hashes=artifacts,
            input_hashes=inputs,
            reason=reason,
            resume_from=resume_from,
        )
    except PipelineBlockedError:
        raise
    except PipelineStateError as exc:
        raise PipelineError(str(exc)) from exc


def _inputs(
    loaded: LoadedState,
    phase: str,
    artifacts: dict[str, str],
    result_state: str,
) -> dict[str, str]:
    try:
        return expected_input_hashes(
            loaded.contract,
            loaded.contract_sha256,
            phase,
            artifacts,
            result_state=result_state,
        )
    except PipelineStateError as exc:
        raise PipelineError(str(exc)) from exc


def _resume_from(loaded: LoadedState) -> str | None:
    state = loaded.checkpoint["state"]
    return state if state in {"FAILED", "CANCELLED"} else None


def _summary(contract_file: Path, loaded: LoadedState) -> RunSummary:
    try:
        revalidate_loaded_state(loaded)
    except PipelineStateError as exc:
        raise PipelineError(str(exc)) from exc
    state = loaded.checkpoint["state"]
    return RunSummary(
        contract_path=Path(os.path.abspath(os.fspath(contract_file))),
        run_id=loaded.contract["runId"],
        state=state,
        transitions=tuple(entry["newState"] for entry in loaded.journal["entries"]),
        completed_phases=tuple(_completed(loaded)),
        artifact_hashes=_current_artifact_hashes(loaded),
        passed=state == "PIXEL_VERIFIED_DETERMINISTIC",
        capability_claim=CAPABILITY_CLAIM,
        reason=loaded.checkpoint.get("reason"),
    )


def _write_pipeline_artifact(
    loaded: LoadedState,
    artifact: dict[str, Any],
    payload: bytes,
    claims: dict[str, ArtifactObservation | None],
    written_outputs: dict[str, ArtifactObservation],
) -> tuple[str, str]:
    target = _path_for(loaded.contract, artifact)
    expected = artifact.get("sha256")
    actual = sha256_bytes(payload)
    if expected is not None and actual != expected:
        raise PipelineError(f"output does not match contract sha256 for {artifact['role']}")
    try:
        _assert_output_claim(loaded, artifact, claims)
        atomic_write(target, payload, loaded.run_root)
    except PipelineBlockedError:
        raise
    except PipelineStateError as exc:
        raise PipelineError(str(exc)) from exc
    written_outputs[artifact["path"]] = snapshot_artifact(
        target, loaded.run_root, expected_sha256=actual
    )
    return artifact["path"], actual


def _compensate_phase_outputs(
    loaded: LoadedState, written_outputs: dict[str, ArtifactObservation]
) -> None:
    residues: list[str] = []
    for relative, observation in reversed(tuple(written_outputs.items())):
        path = observation.path
        try:
            verify_artifact_snapshot(observation, loaded.run_root)
            path.unlink()
            if path.exists() or path.is_symlink():
                residues.append(relative)
        except (OSError, PipelineStateError):
            residues.append(relative)
    if residues:
        raise PipelineBlockedError(
            f"phase compensation BLOCKED; residue paths: {sorted(residues)}"
        )


def _hash_bound_handoff_contract(
    contract: dict[str, Any], bindings: dict[str, str]
) -> dict[str, Any]:
    """Create an in-memory exact-content handoff without widening file authorization."""

    snapshot = copy.deepcopy(contract)
    artifacts = {item["path"]: item for item in snapshot["artifacts"]}
    for path, digest in bindings.items():
        artifact = artifacts.get(path)
        if artifact is None:
            raise PipelineError(f"cannot hash-bind undeclared handoff artifact {path}")
        expected = artifact.get("sha256")
        if expected is not None and expected != digest:
            raise PipelineError(f"handoff artifact conflicts with contract sha256: {path}")
        artifact["sha256"] = digest
    return snapshot


def _metrics_payload(metrics: FidelityMetrics, render_hash: str) -> bytes:
    value = {
        "schemaVersion": "design-lab/reconstruction-metrics/v1",
        "profileId": metrics.profile_id,
        "pixelmatchVersion": metrics.pixelmatch_version,
        "pixelThreshold": metrics.pixel_threshold,
        "antiAliasDetection": metrics.anti_alias_detection,
        "matchMinimum": metrics.match_minimum,
        "ssimMinimum": metrics.ssim_minimum,
        "maeLimitVersion": metrics.mae_limit_version,
        "maeLimit": metrics.mae_limit,
        "edgeMetric": metrics.edge_metric,
        "width": metrics.width,
        "height": metrics.height,
        "matchRatio": metrics.match_ratio,
        "mismatchCount": metrics.mismatch_count,
        "excludedAaCount": metrics.excluded_aa_count,
        "ssim": metrics.ssim,
        "meanRgbaError": metrics.mean_rgba_error,
        "alphaMeanError": metrics.alpha_mean_error,
        "edgeError": metrics.edge_error,
        "maxDiffWindow": metrics.max_diff_window,
        "components": [dataclasses.asdict(item) for item in metrics.components],
        "denseRegions": [dataclasses.asdict(item) for item in metrics.dense_regions],
        "failureReasons": list(metrics.failure_reasons),
        "passed": metrics.passed,
        "lifecycleStatus": metrics.lifecycle_status,
        "registryDigest": metrics.registry_digest,
        "metricMaxPixels": metrics.metric_max_pixels,
        "metricMaxBytes": metrics.metric_max_bytes,
        "metricBudgetVersion": metrics.metric_budget_version,
        "referenceSha256": metrics.input_bindings[0].sha256,
        "previewSha256": render_hash,
        "diffSha256": metrics.diff_sha256,
        "mismatchMaskSha256": metrics.mismatch_mask_sha256,
        "excludedAaMaskSha256": hashlib.sha256(
            metrics.excluded_aa_mask
        ).hexdigest(),
        "inputAuthority": metrics.input_authority,
        "inputBindings": [
            {
                "path": binding.path.relative_to(PROJECT_ROOT).as_posix(),
                "role": binding.role,
                "producer": binding.producer,
                "sha256": binding.sha256,
            }
            for binding in metrics.input_bindings
        ],
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
    return canonical_json_bytes(value)


def _after_metrics(_metrics: FidelityMetrics) -> None:
    """Test seam at the exact post-comparison/pre-promotion boundary."""


def _validate_metric_bindings(
    metrics: FidelityMetrics,
    *,
    normalized_path: Path,
    normalized_hash: str,
    preview_path: Path,
    preview_hash: str,
) -> None:
    expected = {
        "normalized-reference": (
            normalized_path,
            normalized_hash,
            "intake-normalizer-v1",
        ),
        "render-preview": (preview_path, preview_hash, "resvg-v0.47.0"),
    }
    observed = {binding.role: binding for binding in metrics.input_bindings}
    if set(observed) != set(expected):
        raise PipelineError("metrics input bindings are not the exact authoritative pair")
    for role, (path, digest, producer) in expected.items():
        binding = observed[role]
        if (
            binding.path != path
            or binding.sha256 != digest
            or binding.producer != producer
        ):
            raise PipelineError(f"metrics input binding changed for {role}")


def _run_analyze(
    loaded: LoadedState,
    contract_file: Path,
    contract_payload: bytes,
    roles: dict[str, dict[str, Any]],
    rir_hash: str,
    claims: dict[str, ArtifactObservation | None],
    written_outputs: dict[str, ArtifactObservation],
) -> LoadedState:
    _assert_contract_file_unchanged(contract_file, contract_payload)
    source_path = contract_path(loaded.contract, loaded.contract["source"]["path"])
    if sha256_file(source_path) != loaded.contract["source"]["sha256"]:
        raise PipelineError("source bytes do not match the run contract")
    _assert_output_claim(loaded, roles["normalized-reference"], claims)
    result = normalize_reference_for_contract(
        source_path,
        loaded.contract,
        max_axis=loaded.contract["canvasPolicy"]["tilePolicy"]["tileWidth"],
    )
    written_outputs[roles["normalized-reference"]["path"]] = snapshot_artifact(
        _path_for(loaded.contract, roles["normalized-reference"]),
        loaded.run_root,
        expected_sha256=result.normalized_sha256,
    )
    artifacts = _artifact_hashes(loaded)
    artifacts[roles["normalized-reference"]["path"]] = result.normalized_sha256
    completed = ["analyze"]
    verify_contract_authority(loaded.contract_authority, loaded.contract)
    return _record(
        loaded,
        state="ANALYZED",
        phase="analyze",
        completed=completed,
        artifacts=artifacts,
        inputs=_inputs(loaded, "analyze", artifacts, "ANALYZED"),
        resume_from=_resume_from(loaded),
    )


def _run_reconstruct(
    loaded: LoadedState,
    contract_file: Path,
    contract_payload: bytes,
    roles: dict[str, dict[str, Any]],
    rir: dict[str, Any],
    rir_hash: str,
    claims: dict[str, ArtifactObservation | None],
    written_outputs: dict[str, ArtifactObservation],
) -> LoadedState:
    _assert_contract_file_unchanged(contract_file, contract_payload)
    svg_payload = serialize_svg(rir, PROJECT_ROOT)
    svg_rel, svg_hash = _write_pipeline_artifact(
        loaded, roles["sanitized-svg"], svg_payload, claims, written_outputs
    )
    profile = load_render_profile(
        loaded.contract["canvasPolicy"]["width"],
        loaded.contract["canvasPolicy"]["height"],
        PINNED_RESVG_BINARY,
    )
    _assert_output_claim(loaded, roles["render-preview"], claims)
    render_result = render_svg(
        _path_for(loaded.contract, roles["sanitized-svg"]),
        _path_for(loaded.contract, roles["render-preview"]),
        profile,
        run_contract=_hash_bound_handoff_contract(
            loaded.contract, {roles["sanitized-svg"]["path"]: svg_hash}
        ),
    )
    written_outputs[roles["render-preview"]["path"]] = snapshot_artifact(
        _path_for(loaded.contract, roles["render-preview"]),
        loaded.run_root,
        expected_sha256=render_result.output_sha256,
    )
    artifacts = _artifact_hashes(loaded)
    artifacts[svg_rel] = svg_hash
    artifacts[roles["render-preview"]["path"]] = render_result.output_sha256
    completed = ["analyze", "reconstruct"]
    return _record(
        loaded,
        state="RECONSTRUCTED_LOCAL",
        phase="reconstruct",
        completed=completed,
        artifacts=artifacts,
        inputs=_inputs(loaded, "reconstruct", artifacts, "RECONSTRUCTED_LOCAL"),
        resume_from=_resume_from(loaded),
    )


def _run_verify(
    loaded: LoadedState,
    contract_file: Path,
    contract_payload: bytes,
    roles: dict[str, dict[str, Any]],
    claims: dict[str, ArtifactObservation | None],
    written_outputs: dict[str, ArtifactObservation],
) -> LoadedState:
    _assert_contract_file_unchanged(contract_file, contract_payload)
    profile = load_render_profile(
        loaded.contract["canvasPolicy"]["width"],
        loaded.contract["canvasPolicy"]["height"],
        PINNED_RESVG_BINARY,
    )
    preview_path = _path_for(loaded.contract, roles["render-preview"])
    normalized_path = _path_for(loaded.contract, roles["normalized-reference"])
    normalized_observation = snapshot_artifact(normalized_path, loaded.run_root)
    preview_observation = snapshot_artifact(preview_path, loaded.run_root)
    render_hash = preview_observation.sha256
    normalized_hash = normalized_observation.sha256
    _assert_output_claim(loaded, roles["diff-evidence"], claims)
    metrics = compare_images(
        _path_for(loaded.contract, roles["normalized-reference"]),
        preview_path,
        profile=profile,
        diff_output_path=_path_for(loaded.contract, roles["diff-evidence"]),
        run_contract=_hash_bound_handoff_contract(
            loaded.contract,
            {
                roles["normalized-reference"]["path"]: normalized_hash,
                roles["render-preview"]["path"]: render_hash,
            },
        ),
    )
    written_outputs[roles["diff-evidence"]["path"]] = snapshot_artifact(
        _path_for(loaded.contract, roles["diff-evidence"]),
        loaded.run_root,
        expected_sha256=metrics.diff_sha256,
    )
    _after_metrics(metrics)
    verify_contract_authority(loaded.contract_authority, loaded.contract)
    _validate_metric_bindings(
        metrics,
        normalized_path=normalized_path,
        normalized_hash=normalized_hash,
        preview_path=preview_path,
        preview_hash=render_hash,
    )
    verify_artifact_snapshot(normalized_observation, loaded.run_root)
    verify_artifact_snapshot(preview_observation, loaded.run_root)
    diff_observation = snapshot_artifact(
        _path_for(loaded.contract, roles["diff-evidence"]),
        loaded.run_root,
        expected_sha256=metrics.diff_sha256,
    )
    metrics_payload = _metrics_payload(metrics, render_hash)
    metrics_rel, metrics_hash = _write_pipeline_artifact(
        loaded, roles["pipeline-metrics"], metrics_payload, claims, written_outputs
    )
    artifacts = _artifact_hashes(loaded)
    artifacts[roles["diff-evidence"]["path"]] = metrics.diff_sha256
    artifacts[metrics_rel] = metrics_hash
    completed = ["analyze", "reconstruct", "verify"]
    authoritative_pass = (
        metrics.passed
        and metrics.lifecycle_status == "PIXEL_VERIFIED_DETERMINISTIC"
        and metrics.input_authority == "CONTRACT_BOUND_AUTHORITATIVE"
    )
    state = "PIXEL_VERIFIED_DETERMINISTIC" if authoritative_pass else "PARTIAL"
    reason = None if authoritative_pass else (
        ",".join(metrics.failure_reasons)
        or "NON_AUTHORITATIVE_DETERMINISTIC_METRICS"
    )
    verify_artifact_snapshot(diff_observation, loaded.run_root)
    return _record(
        loaded,
        state=state,
        phase="verify",
        completed=completed,
        artifacts=artifacts,
        inputs=_inputs(loaded, "verify", artifacts, state),
        reason=reason,
        resume_from=_resume_from(loaded),
    )


def run_reconstruction(
    contract_path_value: Path,
    *,
    target: str = "verify",
    stop_after: str | None = None,
    cancel_after: str | None = None,
) -> RunSummary:
    """Run or resume the deterministic no-AI vertical slice from hash-valid state."""

    contract_file = Path(os.path.abspath(os.fspath(contract_path_value)))
    if target not in PHASE_TARGETS:
        raise PipelineError(f"unknown pipeline target {target!r}")
    try:
        contract, contract_payload, contract_sha = load_contract(contract_file)
        roles = _role_map(contract)
        authority = capture_contract_authority(
            contract_file, contract, contract_payload, contract_sha
        )
        run_root = contract_path(contract, contract["roots"]["runtime"].rstrip("/"))
        rir, _rir_payload, rir_hash = _load_explicit_rir(contract, roles, run_root)
        loaded = initialize_state(contract, contract_sha, authority)
    except (PipelineStateError, PipelineError) as exc:
        raise PipelineError(str(exc)) from exc
    if stop_after is not None and stop_after not in {
        "CREATED", "ANALYZED", "RECONSTRUCTED_LOCAL", "PIXEL_VERIFIED_DETERMINISTIC", "PARTIAL"
    }:
        raise PipelineError(f"unknown stop boundary {stop_after!r}")
    if cancel_after is not None and cancel_after not in {
        "CREATED", "ANALYZED", "RECONSTRUCTED_LOCAL"
    }:
        raise PipelineError(f"unknown cancellation boundary {cancel_after!r}")

    def boundary(current: LoadedState) -> RunSummary | None:
        state = current.checkpoint["state"]
        if cancel_after == state:
            if state == "CANCELLED":
                return _summary(contract_file, current)
            cancelled = _record(
                current,
                state="CANCELLED",
                phase="cancel",
                completed=_completed(current),
                artifacts=_artifact_hashes(current),
                inputs=_inputs(
                    current, "cancel", _artifact_hashes(current), "CANCELLED"
                ),
                reason=f"forced cancellation after {state}",
                resume_from=state,
            )
            return _summary(contract_file, cancelled)
        if stop_after == state:
            return _summary(contract_file, current)
        return None

    early = boundary(loaded)
    if early is not None:
        return early
    completed = _completed(loaded)
    if loaded.checkpoint["state"] in TERMINAL_STATES:
        return _summary(contract_file, loaded)

    phases = ("analyze", "reconstruct", "verify")
    target_index = phases.index(target)
    for phase in phases[: target_index + 1]:
        if phase in completed:
            continue
        if len(loaded.journal["entries"]) >= 8:
            raise PipelineBlockedError(
                "pipeline journal checkpoint slots are exhausted before phase write"
            )
        claims: dict[str, ArtifactObservation | None] = {}
        written_outputs: dict[str, ArtifactObservation] = {}
        try:
            claims = _prepare_phase_outputs(loaded, roles, phase)
            if phase == "analyze":
                loaded = _run_analyze(
                    loaded, contract_file, contract_payload, roles, rir_hash, claims,
                    written_outputs,
                )
            elif phase == "reconstruct":
                loaded = _run_reconstruct(
                    loaded, contract_file, contract_payload, roles, rir, rir_hash, claims,
                    written_outputs,
                )
            else:
                loaded = _run_verify(
                    loaded, contract_file, contract_payload, roles, claims, written_outputs
                )
        except PipelineBlockedError:
            raise
        except (PipelineError, PipelineStateError, IntakeError, RenderError, FidelityError, UnsafeSVGError, OSError, ValueError) as exc:
            reason = f"{type(exc).__name__}: {exc}"
            try:
                failed_artifacts = _discover_created_output_hashes(
                    loaded, written_outputs
                )
                failed = _record(
                    loaded,
                    state="FAILED",
                    phase=phase,
                    completed=completed,
                    artifacts=failed_artifacts,
                    inputs=_inputs(loaded, phase, _artifact_hashes(loaded), "FAILED"),
                    reason=reason,
                    resume_from=loaded.checkpoint["state"],
                )
            except (PipelineError, PipelineStateError):
                _compensate_phase_outputs(loaded, written_outputs)
                raise PipelineError(reason) from exc
            return _summary(contract_file, failed)
        completed = _completed(loaded)
        early = boundary(loaded)
        if early is not None:
            return early
    return _summary(contract_file, loaded)


__all__ = [
    "PipelineError",
    "PipelineBlockedError",
    "RollbackBlockedError",
    "RollbackBoundaryError",
    "RollbackSummary",
    "RunSummary",
    "rollback_run",
    "run_reconstruction",
]
