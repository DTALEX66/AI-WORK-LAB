# SPDX-License-Identifier: MIT
"""Fail-closed AI provider registry, preflight, and proposal-boundary tests."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DESIGN_LAB.parent
REGISTRY_PATH = DESIGN_LAB / "config" / "reconstruction-models.json"
if str(DESIGN_LAB) not in sys.path:
    sys.path.insert(0, str(DESIGN_LAB))
    sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_reparse(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link, target_is_directory=target.is_dir())
        return
    except (OSError, NotImplementedError) as symlink_error:
        if os.name != "nt" or not target.is_dir():
            raise symlink_error
    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise OSError("junction creation unavailable")


def _remove_reparse(path: Path) -> None:
    if path.is_symlink():
        path.unlink()
    else:
        path.rmdir()


def _entry(
    artifact_id: str,
    path: Path | None,
    digest: str,
    *,
    provider_id: str | None = None,
    remote: bool = False,
    default_enabled: bool = True,
    commercial_use: str = "ALLOWED",
    minimum_vram_mib: int = 0,
    priority: int = 10,
    tasks: list[str] | None = None,
) -> dict:
    return {
        "artifactKind": "model" if artifact_id != "vtracer" else "binary",
        "id": artifact_id,
        "providerId": provider_id or f"{artifact_id}-local",
        "version": "version-1",
        "revision": "revision-1",
        "source": "https://example.test/provider",
        "license": "Apache-2.0",
        "commercialUse": commercial_use,
        "checksumSha256": digest,
        "storageClass": "Model library/model" if artifact_id != "vtracer" else "Design External Configuration/toolchain",
        "localPath": None if path is None else str(path),
        "remote": remote,
        "device": "remote" if remote else ("cuda" if minimum_vram_mib else "cpu"),
        "minimumVramMiB": minimum_vram_mib,
        "tasks": tasks or ["semantic-analysis"],
        "defaultEnabled": default_enabled,
        "priority": priority,
        "limitations": [],
        "qualification": "UNQUALIFIED_CHECKSUM" if digest == "0" * 64 else "QUALIFIED",
    }


def _registry(*entries: dict) -> dict:
    return {
        "schemaVersion": "design-lab/reconstruction-models/v1",
        "hardwarePolicy": {
            "defaultDevice": "cuda",
            "availableVramMiB": 8151,
            "gpu": "NVIDIA GeForce RTX 5060",
        },
        "entries": list(entries),
    }


def _contract(source: Path, run_dir: Path, artifacts: list[dict], *, selected: str = "local") -> dict:
    now = datetime.now(timezone.utc)
    source_rel = source.relative_to(PROJECT_ROOT).as_posix()
    run_id = run_dir.name
    targets = [item["path"] for item in artifacts]
    remote = []
    allowlist = ["local"]
    if selected != "local":
        allowlist.append(selected)
        remote = [{"path": source_rel, "sha256": _sha256(source), "provider": selected, "consented": True}]
    return {
        "schemaVersion": "design-lab/reconstruction-run/v1",
        "runId": run_id,
        "jobId": "job-provider-test",
        "source": {
            "sourceId": "source-provider-test",
            "path": source_rel,
            "sha256": _sha256(source),
            "profileMetadata": {"name": "test", "version": "1"},
            "normalizedReferenceTarget": f".project-local/task-runtime/reconstruction/{run_id}/reference.normalized.png",
        },
        "profile": "flat",
        "canvasPolicy": {
            "width": 1,
            "height": 1,
            "colorSpace": "srgb",
            "globalCoordinates": "source-pixel",
            "tilePolicy": {"enabled": False, "tileWidth": 4096, "tileHeight": 4096, "overlap": 0},
        },
        "roots": {
            "runtime": f".project-local/task-runtime/reconstruction/{run_id}/",
            "evidence": f".project-local/task-artifacts/reconstruction/{run_id}/",
        },
        "providerPolicy": {
            "defaultProvider": "local",
            "providerAllowlist": allowlist,
            "selectedProvider": selected,
            "remoteConsents": remote,
        },
        "writeAuthorization": {
            "authorizationId": "auth-provider-test",
            "jobId": "job-provider-test",
            "runId": run_id,
            "targets": targets,
            "issuedAt": (now - timedelta(minutes=1)).isoformat(),
            "expiresAt": (now + timedelta(hours=1)).isoformat(),
            "state": "authorized",
        },
        "registries": {
            "toolRegistry": "design-lab/config/reconstruction-tools.json",
            "modelRegistry": "design-lab/config/reconstruction-models.json",
        },
        "lifecycle": {
            "state": "authorized",
            "history": [{"from": "created", "to": "authorized", "at": (now - timedelta(minutes=1)).isoformat()}],
        },
        "requestedOperations": ["analyze"],
        "cancellationPolicy": {
            "cancelable": True,
            "resume": "checkpoint",
            "checkpointPath": f".project-local/task-runtime/reconstruction/{run_id}/checkpoint.json",
        },
        "artifacts": artifacts,
    }


class ReconstructionProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = PROJECT_ROOT / ".project-local" / "task-runtime" / "provider-tests" / uuid.uuid4().hex
        self.scratch.mkdir(parents=True)
        self.external = self.scratch / "external"
        self.external.mkdir()
        self.source = self.scratch / "source.png"
        self.source.write_bytes(b"source")
        self.run_dir = PROJECT_ROOT / ".project-local" / "task-runtime" / "reconstruction" / f"provider-{uuid.uuid4().hex}"
        self.run_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.scratch, ignore_errors=True)
        shutil.rmtree(self.run_dir, ignore_errors=True)

    def model_file(self, payload: bytes = b"model") -> Path:
        path = self.external / "model.bin"
        path.write_bytes(payload)
        return path

    def artifacts(self) -> list[dict]:
        runtime = self.run_dir.relative_to(PROJECT_ROOT).as_posix()
        return [
            {"id": "provider-proposal", "kind": "evidence", "path": f"{runtime}/proposals/semantic.json"},
            {"id": "provider-asset", "kind": "evidence", "path": f"{runtime}/assets/layer.png"},
        ]

    def proposal_diagnostic_case(self):
        from reconstruction.providers import (
            FallbackEvent,
            ProposalResult,
            ProviderDescriptor,
            bind_proposal_request,
        )

        artifacts = self.artifacts()
        contract = _contract(self.source, self.run_dir, artifacts)
        model = self.model_file()
        descriptor = ProviderDescriptor.from_mapping(_entry("fixture", model, _sha256(model)))
        request = bind_proposal_request(
            contract,
            "semantic-analysis",
            ("provider-proposal", "provider-asset"),
            provider=descriptor,
        )
        proposal, asset = [PROJECT_ROOT / item["path"] for item in artifacts]
        proposal.parent.mkdir(parents=True)
        asset.parent.mkdir(parents=True)
        proposal.write_bytes(b"proposal")
        asset.write_bytes(b"asset")
        event = FallbackEvent(
            "fixture-local",
            "PROVIDER_DEGRADED",
            "semantic-analysis",
            "bounded degradation",
            True,
        )
        result = ProposalResult(
            "fixture-local",
            "version-1",
            proposal,
            _sha256(proposal),
            (asset,),
            (_sha256(asset),),
            ("LOW_CONFIDENCE",),
            (event,),
            request.run_id,
            request.job_id,
            request.contract_sha256,
        )
        return request, result, event

    def test_provider_contract_types_are_frozen_and_typed(self) -> None:
        from reconstruction.providers import FallbackEvent, PreflightResult, ProposalRequest, ProposalResult, ProviderDescriptor

        descriptor = ProviderDescriptor.from_mapping(_entry("fixture", None, "0" * 64, remote=True))
        event = FallbackEvent("fixture-local", "MISSING", "semantic-analysis", "not installed", True)
        preflight = PreflightResult("fixture-local", "MISSING", False, (event,), None, 8151)
        request = ProposalRequest(
            "run", "job", self.run_dir, self.source, _sha256(self.source), "flat",
            "semantic-analysis", "local", "a" * 64, (), "fixture-local", "version-1",
        )
        result = ProposalResult(
            "fixture-local", "version-1", self.run_dir / "proposal.json", "0" * 64,
            (), (), (), (event,), "run", "job", "a" * 64,
        )
        for value, field in ((descriptor, "provider_id"), (event, "code"), (preflight, "status"), (request, "task"), (result, "proposal_sha256")):
            with self.subTest(type=type(value).__name__), self.assertRaises(dataclasses.FrozenInstanceError):
                setattr(value, field, "mutated")

    def test_tracked_registry_has_exact_pins_and_policy_disables(self) -> None:
        from reconstruction.providers.registry import load_registry

        registry = load_registry(REGISTRY_PATH)
        by_id = {entry.artifact_id: entry for entry in registry.entries}
        expected = {
            "layerd": ("0292c51", "679f743"),
            "sam2": ("2b90b9f", "ee5bba1"),
            "birefnet": ("e2bf8e4", "e2bf8e4"),
            "paddleocr": ("b03f464", "b03f464"),
            "grounding-dino": ("a2bb814", "a2bb814"),
            "starvector-1b": ("380ab95", "380ab95"),
            "vtracer": ("1.0.0-alpha.3", "5822102"),
        }
        self.assertEqual({key: (by_id[key].version, by_id[key].revision) for key in expected}, expected)
        self.assertNotIn("h3", by_id)
        self.assertFalse(by_id["starvector-1b"].default_enabled)
        self.assertEqual(by_id["omniparser"].commercial_use, "DENIED")
        self.assertFalse(by_id["omniparser"].default_enabled)
        self.assertIn("opaque-only", by_id["vtracer"].limitations)

    def test_registry_rejects_duplicate_keys_nonfinite_size_depth_unknown_fields_and_duplicate_ids(self) -> None:
        from reconstruction.providers import ProviderRegistryError
        from reconstruction.providers.registry import load_registry

        cases = {
            "duplicate key": b'{"schemaVersion":"design-lab/reconstruction-models/v1","schemaVersion":"x","hardwarePolicy":{},"entries":[]}',
            "nonfinite": b'{"schemaVersion":"design-lab/reconstruction-models/v1","hardwarePolicy":{"defaultDevice":"cuda","availableVramMiB":NaN,"gpu":"x"},"entries":[]}',
            "too deep": json.dumps({"a": [[[[[[[[[[[[[[[[[[[[0]]]]]]]]]]]]]]]]]]]]}).encode(),
            "too large": b" " * (1024 * 1024 + 1),
        }
        for label, payload in cases.items():
            path = self.scratch / f"{label}.json"
            path.write_bytes(payload)
            with self.subTest(label), self.assertRaises(ProviderRegistryError):
                load_registry(path)
        model = self.model_file()
        entry = _entry("fixture", model, _sha256(model))
        for label, value in (
            ("unknown field", {**_registry(entry), "extra": True}),
            ("duplicate id", _registry(entry, {**entry, "providerId": "another"})),
            ("unknown task", _registry({**entry, "tasks": ["invented"]})),
            ("qualified placeholder hash", _registry({**entry, "checksumSha256": "0" * 64})),
        ):
            path = self.scratch / f"valid-{label}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.subTest(label), self.assertRaises(ProviderRegistryError):
                load_registry(path)

    def test_registry_file_cannot_resolve_through_a_reparse_directory(self) -> None:
        from reconstruction.providers import ProviderRegistryError
        from reconstruction.providers.registry import load_registry

        target = self.scratch / "registry-target"
        target.mkdir()
        model = self.model_file()
        (target / "models.json").write_text(json.dumps(_registry(_entry("fixture", model, _sha256(model)))), encoding="utf-8")
        link = self.scratch / "registry-link"
        try:
            _make_reparse(target, link)
        except OSError as exc:
            self.skipTest(str(exc))
        try:
            with self.assertRaises(ProviderRegistryError):
                load_registry(link / "models.json")
        finally:
            _remove_reparse(link)

    def test_local_preflight_present_missing_hash_oom_and_license_denied_are_structured(self) -> None:
        from reconstruction.providers.registry import ProviderRegistry, RegisteredProvider

        model = self.model_file()
        digest = _sha256(model)
        base = _entry("fixture", model, digest)
        cases = (
            ("READY", base, 8151, True),
            ("MISSING", {**base, "localPath": str(self.external / "missing.bin")}, 8151, False),
            ("HASH_MISMATCH", {**base, "checksumSha256": "1" * 64}, 8151, False),
            ("OOM", {**base, "minimumVramMiB": 9000, "device": "cuda"}, 8151, False),
            ("LICENSE_DENIED", {**base, "commercialUse": "DENIED"}, 8151, False),
        )
        for status, mapping, vram, ready in cases:
            descriptor = ProviderRegistry.from_mapping(_registry(mapping)).entries[0]
            result = RegisteredProvider(
                descriptor, external_roots=(self.external,), available_vram_mib=vram
            ).preflight(task="semantic-analysis")
            with self.subTest(status):
                self.assertEqual((result.status, result.ready), (status, ready))
                if not ready:
                    self.assertEqual(result.events[0].code, status)
                    self.assertTrue(result.events[0].recoverable)

    def test_local_preflight_rejects_path_escape_directory_reparse_and_hash_change(self) -> None:
        from reconstruction.providers.registry import ProviderRegistry, RegisteredProvider

        outside = self.scratch / "outside.bin"
        outside.write_bytes(b"outside")
        directory = self.external / "directory"
        directory.mkdir()
        target_dir = self.external / "target"
        target_dir.mkdir()
        target = target_dir / "model.bin"
        target.write_bytes(b"target")
        link = self.external / "linked"
        try:
            _make_reparse(target_dir, link)
        except OSError as exc:
            self.skipTest(str(exc))
        try:
            for status, path in (("PATH_DENIED", outside), ("NOT_REGULAR", directory), ("REPARSE_DENIED", link / "model.bin")):
                descriptor = ProviderRegistry.from_mapping(_registry(_entry("fixture", path, _sha256(target)))).entries[0]
                result = RegisteredProvider(
                    descriptor, external_roots=(self.external,), available_vram_mib=8151
                ).preflight(task="semantic-analysis")
                with self.subTest(status):
                    self.assertEqual(result.status, status)
            descriptor = ProviderRegistry.from_mapping(_registry(_entry("fixture", target, _sha256(target)))).entries[0]
            provider = RegisteredProvider(descriptor, external_roots=(self.external,), available_vram_mib=8151)
            self.assertTrue(provider.preflight(task="semantic-analysis").ready)
            target.write_bytes(b"changed")
            self.assertEqual(provider.preflight(task="semantic-analysis").status, "HASH_MISMATCH")
        finally:
            if link.exists() or link.is_symlink():
                _remove_reparse(link)

    def test_local_preflight_rejects_hardlink_added_during_hash(self) -> None:
        import reconstruction.providers.registry as registry_module
        from reconstruction.providers.registry import ProviderRegistry, RegisteredProvider

        model = self.model_file(b"race-model")
        descriptor = ProviderRegistry.from_mapping(
            _registry(_entry("fixture", model, _sha256(model)))
        ).entries[0]
        provider = RegisteredProvider(
            descriptor, external_roots=(self.external,), available_vram_mib=8151
        )
        sibling = self.external / "racing-hardlink.bin"
        original_hash = registry_module._sha256_file

        def add_hardlink(path: Path) -> str:
            digest = original_hash(path)
            os.link(path, sibling)
            return digest

        try:
            with mock.patch.object(registry_module, "_sha256_file", side_effect=add_hardlink):
                result = provider.preflight(task="semantic-analysis")
            self.assertFalse(result.ready)
            self.assertIn(result.status, {"NOT_REGULAR", "HASH_CHANGED"})
        finally:
            if sibling.exists():
                sibling.unlink()

    def test_remote_provider_requires_exact_per_file_consent_and_allowlist(self) -> None:
        from reconstruction.providers import RemoteProviderDenied
        from reconstruction.providers.registry import ProviderRegistry, load_enabled_providers

        remote = _entry("remote", None, "1" * 64, provider_id="remote-v1", remote=True)
        registry = ProviderRegistry.from_mapping(_registry(remote))
        contract = _contract(self.source, self.run_dir, self.artifacts(), selected="remote-v1")
        loaded = load_enabled_providers(contract, registry, requested_ids=("remote",), external_roots=(self.external,))
        self.assertEqual([item.describe().provider_id for item in loaded], ["remote-v1"])
        self.assertEqual(
            [item.describe().provider_id for item in load_enabled_providers(contract, registry, external_roots=(self.external,))],
            ["remote-v1"],
        )
        corruptions = []
        for field, value in (("provider", "remote-v2"), ("sha256", "0" * 64), ("path", "design-lab/other.png"), ("consented", False)):
            changed = json.loads(json.dumps(contract))
            changed["providerPolicy"]["remoteConsents"][0][field] = value
            corruptions.append((field, changed))
        changed = json.loads(json.dumps(contract))
        changed["providerPolicy"]["providerAllowlist"] = ["local"]
        corruptions.append(("allowlist", changed))
        for label, changed in corruptions:
            with self.subTest(label), self.assertRaises(RemoteProviderDenied):
                load_enabled_providers(changed, registry, requested_ids=("remote",), external_roots=(self.external,))
        self.source.write_bytes(b"changed-after-consent")
        with self.assertRaises(RemoteProviderDenied):
            load_enabled_providers(contract, registry, requested_ids=("remote",), external_roots=(self.external,))

    def test_unknown_model_and_disabled_model_fail_closed(self) -> None:
        from reconstruction.providers import ProviderRegistryError
        from reconstruction.providers.registry import ProviderRegistry, load_enabled_providers

        model = self.model_file()
        registry = ProviderRegistry.from_mapping(_registry(_entry("fixture", model, _sha256(model), default_enabled=False)))
        contract = _contract(self.source, self.run_dir, self.artifacts())
        changed = json.loads(json.dumps(contract))
        changed["registries"]["modelRegistry"] = "design-lab/config/reconstruction-tools.json"
        with self.assertRaises(ProviderRegistryError):
            load_enabled_providers(changed, registry, requested_ids=("fixture",), external_roots=(self.external,))
        for requested in (("missing",), ("fixture",)):
            with self.subTest(requested), self.assertRaises(ProviderRegistryError):
                load_enabled_providers(contract, registry, requested_ids=requested, external_roots=(self.external,))

    def test_fallback_order_is_stable_and_records_every_unavailable_candidate(self) -> None:
        from reconstruction.providers.registry import ProviderRegistry, preflight_task

        model = self.model_file()
        registry = ProviderRegistry.from_mapping(
            _registry(
                _entry("oom", model, _sha256(model), minimum_vram_mib=9000, priority=1),
                _entry("missing", self.external / "missing.bin", "1" * 64, priority=2),
                _entry("ready", model, _sha256(model), priority=3),
            )
        )
        selection = preflight_task(registry, "semantic-analysis", external_roots=(self.external,), available_vram_mib=8151)
        self.assertEqual(selection.selected.describe().artifact_id, "ready")
        self.assertEqual([event.code for event in selection.events], ["OOM", "MISSING"])
        self.assertEqual([event.provider_id for event in selection.events], ["oom-local", "missing-local"])

    def test_unqualified_provider_never_becomes_ready_or_enters_execution_set(self) -> None:
        from reconstruction.providers import ProviderRegistryError
        from reconstruction.providers.registry import ProviderRegistry, RegisteredProvider, load_enabled_providers

        model = self.model_file(b"exact-but-unqualified")
        mapping = {
            **_entry("unqualified", model, _sha256(model)),
            "qualification": "UNQUALIFIED_CHECKSUM",
        }
        registry = ProviderRegistry.from_mapping(_registry(mapping))
        result = RegisteredProvider(
            registry.entries[0], external_roots=(self.external,), available_vram_mib=8151
        ).preflight(task="semantic-analysis")
        self.assertFalse(result.ready)
        self.assertEqual(result.status, "UNQUALIFIED_CHECKSUM")
        contract = _contract(self.source, self.run_dir, self.artifacts())
        with self.assertRaises(ProviderRegistryError):
            load_enabled_providers(
                contract,
                registry,
                requested_ids=("unqualified",),
                task="semantic-analysis",
                external_roots=(self.external,),
            )

    def test_execution_set_rejects_every_failed_preflight_status(self) -> None:
        from reconstruction.providers import ProviderRegistryError
        from reconstruction.providers.registry import ProviderRegistry, load_enabled_providers

        model = self.model_file(b"preflight")
        base = _entry("fixture", model, _sha256(model))
        cases = (
            {**base, "localPath": str(self.external / "missing.bin")},
            {**base, "checksumSha256": "1" * 64},
            {**base, "minimumVramMiB": 9000, "device": "cuda"},
            {**base, "commercialUse": "DENIED"},
        )
        contract = _contract(self.source, self.run_dir, self.artifacts())
        for mapping in cases:
            registry = ProviderRegistry.from_mapping(_registry(mapping))
            with self.subTest(mapping=mapping), self.assertRaises(ProviderRegistryError):
                load_enabled_providers(
                    contract,
                    registry,
                    requested_ids=("fixture",),
                    task="semantic-analysis",
                    external_roots=(self.external,),
                    available_vram_mib=8151,
                )

    def test_remote_preflight_requires_exact_contract_and_no_provider_is_structured(self) -> None:
        from reconstruction.providers.registry import ProviderRegistry, preflight_task

        remote = _entry("remote", None, "1" * 64, provider_id="remote-v1", remote=True)
        registry = ProviderRegistry.from_mapping(_registry(remote))
        denied = preflight_task(registry, "semantic-analysis", external_roots=(self.external,))
        self.assertIsNone(denied.selected)
        self.assertEqual([event.code for event in denied.events], ["REMOTE_CONSENT_REQUIRED", "NO_PROVIDER"])
        contract = _contract(self.source, self.run_dir, self.artifacts(), selected="remote-v1")
        allowed = preflight_task(
            registry,
            "semantic-analysis",
            contract=contract,
            external_roots=(self.external,),
        )
        self.assertEqual(allowed.selected.describe().provider_id, "remote-v1")

    def test_no_provider_and_failure_events_bind_the_requested_task(self) -> None:
        from reconstruction.providers.registry import ProviderRegistry, preflight_task

        missing = {
            **_entry(
                "missing",
                self.external / "missing.bin",
                "1" * 64,
                tasks=["ocr", "semantic-analysis"],
            )
        }
        registry = ProviderRegistry.from_mapping(_registry(missing))
        selection = preflight_task(
            registry, "semantic-analysis", external_roots=(self.external,), available_vram_mib=8151
        )
        self.assertIsNone(selection.selected)
        self.assertEqual([event.code for event in selection.events], ["MISSING", "NO_PROVIDER"])
        self.assertTrue(all(event.task == "semantic-analysis" for event in selection.events))

    def test_source_full_chain_hardlink_and_hash_race_are_rejected(self) -> None:
        import reconstruction.providers.registry as registry_module
        from reconstruction.providers import ProposalBoundaryError, ProviderDescriptor, bind_proposal_request

        descriptor = ProviderDescriptor.from_mapping(_entry("fixture", self.model_file(), _sha256(self.model_file())))
        artifacts = self.artifacts()

        hardlink = self.scratch / "source-hardlink.png"
        try:
            os.link(self.source, hardlink)
        except OSError as exc:
            self.skipTest(f"hardlink unavailable: {exc}")
        hardlink_contract = _contract(hardlink, self.run_dir, artifacts)
        with self.assertRaises(ProposalBoundaryError):
            bind_proposal_request(
                hardlink_contract,
                "semantic-analysis",
                ("provider-proposal", "provider-asset"),
                provider=descriptor,
            )
        hardlink.unlink()

        target = self.scratch / "source-target"
        target.mkdir()
        (target / "source.png").write_bytes(b"linked-source")
        link = self.scratch / "source-link"
        try:
            _make_reparse(target, link)
        except OSError as exc:
            self.skipTest(str(exc))
        try:
            linked_contract = _contract(link / "source.png", self.run_dir, artifacts)
            with self.assertRaises(ProposalBoundaryError):
                bind_proposal_request(
                    linked_contract,
                    "semantic-analysis",
                    ("provider-proposal", "provider-asset"),
                    provider=descriptor,
                )
        finally:
            _remove_reparse(link)

        race_contract = _contract(self.source, self.run_dir, artifacts)
        original_digest = _sha256(self.source)

        def mutate_during_hash(path: Path) -> str:
            path.write_bytes(b"same-source-mutated")
            return original_digest

        with mock.patch.object(registry_module, "_sha256_file", side_effect=mutate_during_hash), self.assertRaises(
            ProposalBoundaryError
        ):
            bind_proposal_request(
                race_contract,
                "semantic-analysis",
                ("provider-proposal", "provider-asset"),
                provider=descriptor,
            )

    def test_proposal_warnings_and_events_are_closed_bounded_and_private(self) -> None:
        from reconstruction.providers import (
            ProposalBoundaryError,
            validate_proposal_result,
        )

        request, result, event = self.proposal_diagnostic_case()
        validate_proposal_result(request, result)
        mutations = (
            ("warnings type", dataclasses.replace(result, warnings=["LOW_CONFIDENCE"])),
            ("unknown warning", dataclasses.replace(result, warnings=("free text",))),
            ("warning count", dataclasses.replace(result, warnings=("LOW_CONFIDENCE",) * 33)),
            ("events type", dataclasses.replace(result, events=[event])),
            ("event code", dataclasses.replace(result, events=(dataclasses.replace(event, code="UNKNOWN"),))),
            ("event provider", dataclasses.replace(result, events=(dataclasses.replace(event, provider_id="other"),))),
            ("event task", dataclasses.replace(result, events=(dataclasses.replace(event, task="ocr"),))),
            ("event secret", dataclasses.replace(result, events=(dataclasses.replace(event, message="bearer token leaked"),))),
            ("event length", dataclasses.replace(result, events=(dataclasses.replace(event, message="x" * 513),))),
        )
        for label, changed in mutations:
            with self.subTest(label), self.assertRaises(ProposalBoundaryError):
                validate_proposal_result(request, changed)

    def test_diagnostic_absolute_paths_are_rejected_without_url_or_relative_false_positives(self) -> None:
        from reconstruction.providers import ProposalBoundaryError, validate_proposal_result

        request, result, event = self.proposal_diagnostic_case()
        for message in (
            "documentation https://example.test/provider/status",
            "relative home/profiles cache",
        ):
            with self.subTest(accepted=message):
                validate_proposal_result(
                    request,
                    dataclasses.replace(result, events=(dataclasses.replace(event, message=message),)),
                )
        for message in (
            r"D:\private\file",
            r"failed (D:\private\file.json)",
            "path=/home/alex/private.json",
            r"path=\\server\share\private.json",
        ):
            with self.subTest(rejected=message), self.assertRaises(ProposalBoundaryError):
                validate_proposal_result(
                    request,
                    dataclasses.replace(result, events=(dataclasses.replace(event, message=message),)),
                )

    def test_diagnostic_sensitive_assignments_are_normalized_without_prefix_false_positives(self) -> None:
        from reconstruction.providers import ProposalBoundaryError, validate_proposal_result

        request, result, event = self.proposal_diagnostic_case()
        for message in ("tokenizer ready", "sessionDuration=30", "sessionElapsed=30"):
            with self.subTest(accepted=message):
                validate_proposal_result(
                    request,
                    dataclasses.replace(result, events=(dataclasses.replace(event, message=message),)),
                )
        for message in (
            "prompt=private material",
            "session: abc",
            "sessionData=value",
            "sessionPath=home/profiles",
            "sessionId=abc",
            "credential=value",
            "credential_id=value",
            "auth=enabled",
            "authHeader=value",
            "authState=enabled",
            "private=value",
            "privateData=value",
            "privateRuntime=value",
        ):
            with self.subTest(rejected=message), self.assertRaises(ProposalBoundaryError):
                validate_proposal_result(
                    request,
                    dataclasses.replace(result, events=(dataclasses.replace(event, message=message),)),
                )

    def test_request_and_result_are_exactly_bound_to_contract_run_root_roles_identity_and_hashes(self) -> None:
        from reconstruction.providers import ProposalBoundaryError, bind_proposal_request, validate_proposal_result

        artifacts = self.artifacts()
        contract = _contract(self.source, self.run_dir, artifacts)
        from reconstruction.providers import ProviderDescriptor

        descriptor = ProviderDescriptor.from_mapping(_entry("fixture", self.model_file(), _sha256(self.model_file())))
        request = bind_proposal_request(
            contract, "semantic-analysis", ("provider-proposal", "provider-asset"), provider=descriptor
        )
        self.assertEqual(request.run_root, self.run_dir)
        self.assertEqual([item.role for item in request.outputs], ["proposal", "asset"])
        proposal, asset = [PROJECT_ROOT / item["path"] for item in artifacts]
        proposal.parent.mkdir(parents=True)
        asset.parent.mkdir(parents=True)
        proposal.write_bytes(b"proposal")
        asset.write_bytes(b"asset")
        from reconstruction.providers import ProposalResult

        result = ProposalResult(
            "fixture-local", "version-1", proposal, _sha256(proposal), (asset,), (_sha256(asset),), (), (),
            request.run_id, request.job_id, request.contract_sha256,
        )
        validate_proposal_result(request, result)
        for label, changed in (
            ("proposal escape", dataclasses.replace(result, proposal_path=self.scratch / "outside.json")),
            ("asset escape", dataclasses.replace(result, asset_paths=(self.scratch / "outside.png",))),
            ("proposal hash", dataclasses.replace(result, proposal_sha256="0" * 64)),
            ("asset hash", dataclasses.replace(result, asset_sha256=("0" * 64,))),
            ("provider identity", dataclasses.replace(result, provider_id="other")),
            ("run identity", dataclasses.replace(result, run_id="other")),
            ("job identity", dataclasses.replace(result, job_id="other")),
            ("contract identity", dataclasses.replace(result, contract_sha256="0" * 64)),
        ):
            with self.subTest(label), self.assertRaises(ProposalBoundaryError):
                validate_proposal_result(request, changed)
        self.source.write_bytes(b"changed")
        with self.assertRaises(ProposalBoundaryError):
            validate_proposal_result(request, result)
        with self.assertRaises(ProposalBoundaryError):
            bind_proposal_request(
                contract, "semantic-analysis", ("provider-proposal", "provider-asset"), provider=descriptor
            )

    def test_output_reparse_and_unknown_role_are_rejected(self) -> None:
        from reconstruction.providers import ProposalBoundaryError, ProviderDescriptor, bind_proposal_request

        artifacts = self.artifacts()
        contract = _contract(self.source, self.run_dir, artifacts)
        descriptor = ProviderDescriptor.from_mapping(_entry("fixture", self.model_file(), _sha256(self.model_file())))
        outside = self.scratch / "outside"
        outside.mkdir()
        link = self.run_dir / "proposals"
        try:
            _make_reparse(outside, link)
        except OSError as exc:
            self.skipTest(str(exc))
        try:
            with self.assertRaises(ProposalBoundaryError):
                bind_proposal_request(
                    contract, "semantic-analysis", ("provider-proposal", "provider-asset"), provider=descriptor
                )
        finally:
            _remove_reparse(link)
        changed = json.loads(json.dumps(contract))
        changed["artifacts"][0]["id"] = "not-a-provider-role"
        changed["writeAuthorization"]["targets"] = [item["path"] for item in changed["artifacts"]]
        with self.assertRaises(ProposalBoundaryError):
            bind_proposal_request(
                changed, "semantic-analysis", ("not-a-provider-role", "provider-asset"), provider=descriptor
            )


if __name__ == "__main__":
    unittest.main()
