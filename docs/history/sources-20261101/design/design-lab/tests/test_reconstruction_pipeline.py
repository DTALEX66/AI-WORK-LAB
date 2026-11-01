# SPDX-License-Identifier: MIT
"""Real lifecycle, CLI, resume, and rollback tests for reconstruction C5."""
from __future__ import annotations

import copy
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

REPO_ROOT = Path(__file__).resolve().parents[2]
DESIGN_LAB = REPO_ROOT / "design-lab"
FIXTURE = DESIGN_LAB / "tests" / "fixtures" / "reconstruction" / "flat-64.png"
PYTHON = Path(sys.executable)
CLI = DESIGN_LAB / "scripts" / "reconstruct_design.py"
sys.path.insert(0, str(DESIGN_LAB))
sys.path.insert(0, str(REPO_ROOT / "packages" / "capabilities"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _layer(layer_id: str, x1: int, y1: int, x2: int, y2: int, fill: str) -> dict:
    return {
        "id": layer_id,
        "type": "primitive",
        "name": layer_id,
        "opacity": 1.0,
        "bounds": {"x": x1, "y": y1, "width": x2 - x1, "height": y2 - y1},
        "inferred": False,
        "zOrder": int(layer_id.split("-")[-1]),
        "visible": True,
        "locked": False,
        "blendMode": "normal",
        "primitive": {
            "kind": "rect",
            "parameters": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
        },
        "style": {
            "fill": fill,
            "stroke": None,
            "strokeWidth": 0,
            "fillRule": "nonzero",
            "lineCap": "butt",
            "lineJoin": "miter",
        },
        "masks": [],
    }


def _explicit_rir(*, mismatch: bool = False) -> dict:
    return {
        "schemaVersion": "design-lab/reconstruction-ir/v1",
        "canvas": {"width": 64, "height": 64, "colorSpace": "srgb"},
        "layers": [
            _layer("quadrant-0", 0, 0, 32, 32, "#142850"),
            _layer("quadrant-1", 32, 0, 64, 32, "#000000" if mismatch else "#e64632"),
            _layer("quadrant-2", 0, 32, 32, 64, "#28be6ec0"),
            _layer("quadrant-3", 32, 32, 64, 64, "#f5d23c40"),
        ],
    }


def _artifact(artifact_id: str, kind: str, path: str, role: str, producer: str, sha: str | None = None) -> dict:
    value = {
        "id": artifact_id,
        "kind": kind,
        "path": path,
        "role": role,
        "producer": producer,
    }
    if sha is not None:
        value["sha256"] = sha
    return value


def _create_contract(token: str, *, mismatch: bool = False) -> tuple[Path, Path, dict]:
    run_id = f"c5-{os.getpid()}-{token}"
    runtime = f".project-local/task-runtime/reconstruction/{run_id}/"
    evidence = f".project-local/task-artifacts/reconstruction/{run_id}/"
    run_dir = REPO_ROOT / runtime
    run_dir.mkdir(parents=True)
    rir_path = run_dir / "input.rir.json"
    rir_path.write_text(
        json.dumps(_explicit_rir(mismatch=mismatch), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    roles = [
        _artifact("normalized-reference", "normalized-source", runtime + "reference.normalized.png", "normalized-reference", "intake-normalizer-v1"),
        _artifact("reconstruction-rir", "rir-input", runtime + "input.rir.json", "reconstruction-rir", "explicit-rir-v1", _sha256(rir_path)),
        _artifact("sanitized-svg", "vector-output", runtime + "master.svg", "sanitized-svg", "rir-svg-serializer-v1"),
        _artifact("render-preview", "evidence", runtime + "preview.png", "render-preview", "resvg-v0.47.0"),
        _artifact("diff-evidence", "evidence", runtime + "diff.png", "diff-evidence", "fidelity-metrics-v1"),
        _artifact("pipeline-metrics", "metrics", runtime + "metrics.json", "pipeline-metrics", "fidelity-metrics-v1"),
        _artifact("pipeline-journal", "journal", runtime + "journal.json", "pipeline-journal", "reconstruction-pipeline-v1"),
    ]
    for sequence in range(1, 9):
        roles.append(
            _artifact(
                f"checkpoint-{sequence:04d}",
                "checkpoint",
                runtime + f"checkpoints/{sequence:04d}.json",
                "pipeline-checkpoint",
                "reconstruction-pipeline-v1",
            )
        )
    now = datetime.now(timezone.utc)
    contract = {
        "schemaVersion": "design-lab/reconstruction-run/v1",
        "runId": run_id,
        "jobId": f"job-{run_id}",
        "source": {
            "sourceId": "flat-64",
            "path": FIXTURE.relative_to(REPO_ROOT).as_posix(),
            "sha256": _sha256(FIXTURE),
            "profileMetadata": {"name": "fixture-srgb", "version": "1"},
            "normalizedReferenceTarget": runtime + "reference.normalized.png",
        },
        "profile": "flat",
        "canvasPolicy": {
            "width": 64,
            "height": 64,
            "colorSpace": "srgb",
            "globalCoordinates": "source-pixel",
            "tilePolicy": {"enabled": False, "tileWidth": 4096, "tileHeight": 4096, "overlap": 0},
        },
        "roots": {"runtime": runtime, "evidence": evidence},
        "providerPolicy": {
            "defaultProvider": "local",
            "providerAllowlist": ["local"],
            "selectedProvider": "local",
            "remoteConsents": [],
        },
        "writeAuthorization": {
            "authorizationId": f"auth-{run_id}",
            "jobId": f"job-{run_id}",
            "runId": run_id,
            "targets": [item["path"] for item in roles],
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
        "requestedOperations": ["analyze", "reconstruct", "verify"],
        "cancellationPolicy": {
            "cancelable": True,
            "resume": "checkpoint",
            "checkpointPath": runtime + "checkpoints/",
        },
        "artifacts": roles,
    }
    contract_path = run_dir.parent / f"{run_id}.contract.json"
    contract_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    return contract_path, run_dir, contract


class ReconstructionPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.paths: list[Path] = []

    def tearDown(self) -> None:
        for path in reversed(self.paths):
            if path.exists():
                shutil.rmtree(path) if path.is_dir() else path.unlink()

    def make_contract(self, *, mismatch: bool = False) -> tuple[Path, Path, dict]:
        contract_path, run_dir, contract = _create_contract(uuid.uuid4().hex, mismatch=mismatch)
        self.paths.extend([contract_path, run_dir])
        return contract_path, run_dir, contract

    def run_cli(self, command: str, contract_path: Path, *extra: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        completed = subprocess.run(
            [str(PYTHON), str(CLI), command, str(contract_path), *extra],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        payload = json.loads(lines[-1]) if lines else {}
        return completed, payload

    def test_interrupted_run_resumes_once_from_last_hash_valid_checkpoint(self) -> None:
        from reconstruction.pipeline import run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        first = run_reconstruction(contract_path, stop_after="ANALYZED")
        self.assertEqual(first.state, "ANALYZED")
        resumed = run_reconstruction(contract_path)
        self.assertEqual(resumed.state, "PIXEL_VERIFIED_DETERMINISTIC")
        self.assertEqual(resumed.transitions.count("ANALYZED"), 1)
        self.assertEqual(resumed.capability_claim, "ORCHESTRATION_ONLY_NO_SEMANTIC_DECOMPOSITION")
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual([e["sequence"] for e in journal["entries"]], list(range(1, len(journal["entries"]) + 1)))
        self.assertTrue(all(e["checkpoint"]["sha256"] for e in journal["entries"]))

    def test_real_cli_subcommands_are_machine_readable_idempotent_and_rollback_exactly(self) -> None:
        contract_path, run_dir, _ = self.make_contract()
        sibling = run_dir / "operator-sentinel.txt"
        sibling.write_text("keep", encoding="utf-8")
        for command, expected in (
            ("analyze", "ANALYZED"),
            ("reconstruct", "RECONSTRUCTED_LOCAL"),
            ("verify", "PIXEL_VERIFIED_DETERMINISTIC"),
            ("resume", "PIXEL_VERIFIED_DETERMINISTIC"),
        ):
            completed, payload = self.run_cli(command, contract_path)
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            self.assertEqual(payload["state"], expected)
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["newState"] for entry in journal["entries"]].count("ANALYZED"), 1)
        metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
        self.assertEqual(metrics["inputAuthority"], "CONTRACT_BOUND_AUTHORITATIVE")
        self.assertEqual(metrics["lifecycleStatus"], "PIXEL_VERIFIED_DETERMINISTIC")
        self.assertIn("metricMaxPixels", metrics)
        self.assertIn("metricMaxBytes", metrics)
        self.assertIn("metricBudgetVersion", metrics)
        self.assertEqual(len(metrics["inputBindings"]), 2)
        self.assertIn("referenceIcc", metrics)
        self.assertIn("actualIcc", metrics)

        completed, payload = self.run_cli("rollback", contract_path)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertEqual(payload["state"], "ROLLED_BACK")
        self.assertEqual(sibling.read_text(encoding="utf-8"), "keep")
        self.assertTrue((run_dir / "input.rir.json").is_file())
        for name in ("reference.normalized.png", "master.svg", "preview.png", "diff.png", "metrics.json", "journal.json"):
            self.assertFalse((run_dir / name).exists(), name)

    def test_every_cli_failure_is_machine_readable_and_nonzero(self) -> None:
        contract_path, _, _ = self.make_contract()
        contract_path.write_text("not-json", encoding="utf-8")
        for command in ("analyze", "reconstruct", "verify", "resume", "rollback"):
            with self.subTest(command):
                completed, payload = self.run_cli(command, contract_path)
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(payload["state"], "FAILED")
                self.assertFalse(payload["passed"])
                self.assertNotIn("Traceback", completed.stderr)

    def test_cli_usage_failures_are_single_line_machine_json(self) -> None:
        cases = (
            (),
            ("unknown",),
            ("analyze", "--unknown-option"),
            ("analyze", "missing.json", "--stop-after", "BOGUS"),
        )
        for argv in cases:
            with self.subTest(argv):
                completed = subprocess.run(
                    [str(PYTHON), str(CLI), *argv],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                lines = [line for line in completed.stdout.splitlines() if line.strip()]
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(len(lines), 1, completed.stdout)
                payload = json.loads(lines[0])
                self.assertEqual(payload["state"], "FAILED")
                self.assertFalse(payload["passed"])
                self.assertEqual(completed.stderr, "")

    def test_corrupt_or_stale_checkpoint_fails_closed_without_journal_overwrite(self) -> None:
        from reconstruction.pipeline import PipelineError, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        journal_path = run_dir / "journal.json"
        before = journal_path.read_bytes()
        (run_dir / "checkpoints" / "0002.json").write_text("{}", encoding="utf-8")
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)
        self.assertEqual(journal_path.read_bytes(), before)

        journal_path.write_text("not-json", encoding="utf-8")
        malformed = journal_path.read_bytes()
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)
        self.assertEqual(journal_path.read_bytes(), malformed)

    def test_stale_contract_or_rir_hash_fails_closed_without_overwrite(self) -> None:
        from reconstruction.pipeline import PipelineError, run_reconstruction

        contract_path, run_dir, contract = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        journal_path = run_dir / "journal.json"
        before = journal_path.read_bytes()
        changed = copy.deepcopy(contract)
        changed["source"]["profileMetadata"]["version"] = "2"
        contract_path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)
        self.assertEqual(journal_path.read_bytes(), before)

        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        (run_dir / "input.rir.json").write_bytes(b"{}")
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)
        self.assertEqual(journal_path.read_bytes(), before)

    def test_malformed_journal_timestamp_or_hash_map_fails_closed(self) -> None:
        from reconstruction.pipeline import PipelineError, run_reconstruction

        for field in ("timestamp", "hash"):
            with self.subTest(field):
                contract_path, run_dir, _ = self.make_contract()
                run_reconstruction(contract_path, stop_after="ANALYZED")
                journal_path = run_dir / "journal.json"
                journal = json.loads(journal_path.read_text(encoding="utf-8"))
                if field == "timestamp":
                    journal["entries"][0]["timestampUtc"] = "not-utc"
                else:
                    journal["entries"][0]["inputHashes"] = {"contract": "short"}
                journal_path.write_text(json.dumps(journal), encoding="utf-8")
                malformed = journal_path.read_bytes()
                with self.assertRaises(PipelineError):
                    run_reconstruction(contract_path)
                self.assertEqual(journal_path.read_bytes(), malformed)

    def test_strict_json_and_fixed_resource_bounds_fail_before_state_mutation(self) -> None:
        from reconstruction.pipeline import PipelineError, run_reconstruction
        from reconstruction.state import PipelineStateError, decode_json

        for payload in (
            b'{"x":1,"x":2}',
            b'{"x":NaN}',
            b"\xff",
            ("{\"x\":" + "[" * 70 + "0" + "]" * 70 + "}").encode("utf-8"),
        ):
            with self.subTest(payload[:20]), self.assertRaises(PipelineStateError):
                decode_json(payload, label="probe")

        contract_path, run_dir, _ = self.make_contract()
        contract_path.write_bytes(b" " * (8 * 1024 * 1024 + 1))
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)
        self.assertFalse((run_dir / "journal.json").exists())

        bounded_contract, bounded_run, _ = self.make_contract()
        run_reconstruction(bounded_contract, stop_after="ANALYZED")
        journal_path = bounded_run / "journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        template = copy.deepcopy(journal["entries"][-1])
        while len(journal["entries"]) <= 8:
            duplicate = copy.deepcopy(template)
            duplicate["sequence"] = len(journal["entries"]) + 1
            journal["entries"].append(duplicate)
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        oversized_journal = journal_path.read_bytes()
        with self.assertRaises(PipelineError):
            run_reconstruction(bounded_contract)
        self.assertEqual(journal_path.read_bytes(), oversized_journal)

    def test_hash_recomputed_illegal_transition_still_fails_closed(self) -> None:
        from reconstruction.pipeline import PipelineError, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        checkpoint_path = run_dir / "checkpoints" / "0002.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["state"] = "PIXEL_VERIFIED_DETERMINISTIC"
        checkpoint["completedPhases"] = ["analyze", "reconstruct", "verify"]
        checkpoint_payload = json.dumps(
            checkpoint, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        checkpoint_path.write_bytes(checkpoint_payload)
        checkpoint_hash = hashlib.sha256(checkpoint_payload).hexdigest()
        journal_path = run_dir / "journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        entry = journal["entries"][-1]
        old_hash = entry["checkpoint"]["sha256"]
        entry["newState"] = "PIXEL_VERIFIED_DETERMINISTIC"
        entry["checkpoint"]["sha256"] = checkpoint_hash
        entry["outputHashes"][entry["checkpoint"]["path"]] = checkpoint_hash
        self.assertNotEqual(old_hash, checkpoint_hash)
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        forged = journal_path.read_bytes()
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)
        self.assertEqual(journal_path.read_bytes(), forged)

    def test_cancelled_run_resumes_without_duplicating_completed_phase(self) -> None:
        from reconstruction.pipeline import run_reconstruction

        contract_path, _, _ = self.make_contract()
        cancelled = run_reconstruction(contract_path, cancel_after="ANALYZED")
        self.assertEqual(cancelled.state, "CANCELLED")
        resumed = run_reconstruction(contract_path)
        self.assertEqual(resumed.state, "PIXEL_VERIFIED_DETERMINISTIC")
        self.assertEqual(resumed.transitions.count("ANALYZED"), 1)

    def test_cancelled_cli_is_nonzero_even_when_target_phase_completed(self) -> None:
        contract_path, _, _ = self.make_contract()
        completed, payload = self.run_cli(
            "analyze", contract_path, "--cancel-after", "ANALYZED"
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(payload["state"], "CANCELLED")
        self.assertIn("analyze", payload["completedPhases"])

    def test_forced_stop_is_honored_at_every_owned_state_boundary(self) -> None:
        from reconstruction.pipeline import run_reconstruction

        for boundary in (
            "CREATED",
            "ANALYZED",
            "RECONSTRUCTED_LOCAL",
            "PIXEL_VERIFIED_DETERMINISTIC",
        ):
            with self.subTest(boundary):
                contract_path, _, _ = self.make_contract()
                summary = run_reconstruction(contract_path, stop_after=boundary)
                self.assertEqual(summary.state, boundary)

    def test_metric_failure_is_partial_and_cli_nonzero(self) -> None:
        contract_path, _, _ = self.make_contract(mismatch=True)
        completed, payload = self.run_cli("verify", contract_path)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(payload["state"], "PARTIAL")
        self.assertFalse(payload["passed"])

    def test_preview_replacement_after_metrics_cannot_promote_pass(self) -> None:
        import reconstruction.pipeline as pipeline_module

        contract_path, run_dir, _ = self.make_contract()
        pipeline_module.run_reconstruction(
            contract_path, stop_after="RECONSTRUCTED_LOCAL"
        )

        def replace_preview(*_args: object) -> None:
            (run_dir / "preview.png").write_bytes(b"replaced-after-metrics")

        with mock.patch.object(
            pipeline_module, "_after_metrics", side_effect=replace_preview
        ), self.assertRaises(pipeline_module.PipelineError):
            pipeline_module.run_reconstruction(contract_path)
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(journal["entries"][-1]["newState"], "RECONSTRUCTED_LOCAL")

    def test_artifact_replacement_after_journal_commit_rolls_back_promotion(self) -> None:
        import reconstruction.state as state_module
        from reconstruction.pipeline import run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        calls = 0

        def replace_once(*_args: object) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                (run_dir / "reference.normalized.png").write_bytes(
                    b"replaced-after-journal"
                )

        with mock.patch.object(
            state_module, "_after_journal_commit", side_effect=replace_once
        ), self.assertRaises(state_module.PipelineBlockedError):
            run_reconstruction(contract_path, target="analyze")
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["newState"] for entry in journal["entries"]], ["CREATED"])
        self.assertFalse((run_dir / "checkpoints" / "0002.json").exists())
        self.assertTrue((run_dir / "reference.normalized.png").exists())

    def test_sequence_slots_support_three_failed_attempts_then_resume_and_reload(self) -> None:
        import reconstruction.pipeline as pipeline_module

        contract_path, run_dir, _ = self.make_contract()
        pipeline_module.run_reconstruction(
            contract_path, stop_after="RECONSTRUCTED_LOCAL"
        )
        for attempt in range(3):
            with self.subTest(attempt), mock.patch.object(
                pipeline_module, "_after_metrics", side_effect=ValueError("transient")
            ):
                failed = pipeline_module.run_reconstruction(contract_path)
                self.assertEqual(failed.state, "FAILED")
        completed = pipeline_module.run_reconstruction(contract_path)
        self.assertTrue(completed.passed)
        reloaded = pipeline_module.run_reconstruction(contract_path)
        self.assertEqual(reloaded.transitions, completed.transitions)
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [entry["checkpoint"]["path"].rsplit("/", 1)[-1] for entry in journal["entries"]],
            [f"{sequence:04d}.json" for sequence in range(1, 8)],
        )
        self.assertEqual(
            [entry["newState"] for entry in journal["entries"]].count("FAILED"), 3
        )

    def test_three_cancellations_consume_distinct_slots_and_resume(self) -> None:
        from reconstruction.pipeline import run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        first = run_reconstruction(contract_path, cancel_after="CREATED")
        self.assertEqual(first.state, "CANCELLED")
        second = run_reconstruction(contract_path, cancel_after="ANALYZED")
        self.assertEqual(second.state, "CANCELLED")
        third = run_reconstruction(
            contract_path, cancel_after="RECONSTRUCTED_LOCAL"
        )
        self.assertEqual(third.state, "CANCELLED")
        completed = run_reconstruction(contract_path)
        self.assertTrue(completed.passed)
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(len(journal["entries"]), 7)
        self.assertEqual(
            [entry["newState"] for entry in journal["entries"]].count("CANCELLED"), 3
        )

    def test_exhausted_checkpoint_slots_fail_as_blocked_without_overwrite(self) -> None:
        import reconstruction.pipeline as pipeline_module

        contract_path, run_dir, _ = self.make_contract()
        pipeline_module.run_reconstruction(
            contract_path, stop_after="RECONSTRUCTED_LOCAL"
        )
        for _ in range(5):
            with mock.patch.object(
                pipeline_module, "_after_metrics", side_effect=ValueError("transient")
            ):
                self.assertEqual(
                    pipeline_module.run_reconstruction(contract_path).state, "FAILED"
                )
        before = (run_dir / "journal.json").read_bytes()
        with self.assertRaises(pipeline_module.PipelineBlockedError):
            pipeline_module.run_reconstruction(contract_path)
        self.assertEqual((run_dir / "journal.json").read_bytes(), before)

    def test_hash_consistent_false_metrics_cannot_validate_pixel_checkpoint(self) -> None:
        from reconstruction.pipeline import PipelineError, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path)
        metrics_path = run_dir / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics["passed"] = False
        metrics_payload = json.dumps(
            metrics, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        metrics_path.write_bytes(metrics_payload)
        metrics_hash = hashlib.sha256(metrics_payload).hexdigest()
        checkpoint_path = run_dir / "checkpoints" / "0004.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        metrics_rel = metrics_path.relative_to(REPO_ROOT).as_posix()
        checkpoint["artifacts"][metrics_rel] = metrics_hash
        checkpoint_payload = json.dumps(
            checkpoint, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        checkpoint_path.write_bytes(checkpoint_payload)
        checkpoint_hash = hashlib.sha256(checkpoint_payload).hexdigest()
        journal_path = run_dir / "journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        entry = journal["entries"][-1]
        entry["checkpoint"]["sha256"] = checkpoint_hash
        entry["outputHashes"][entry["checkpoint"]["path"]] = checkpoint_hash
        entry["outputHashes"][metrics_rel] = metrics_hash
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)

    def test_low_fidelity_metrics_cannot_self_claim_pass(self) -> None:
        from reconstruction.pipeline import PipelineError, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path)
        metrics_path = run_dir / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics.update(
            {
                "matchRatio": 0.0,
                "mismatchCount": 4096,
                "ssim": 0.0,
                "passed": True,
                "failureReasons": [],
                "lifecycleStatus": "PIXEL_VERIFIED_DETERMINISTIC",
            }
        )
        metrics_payload = json.dumps(
            metrics, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        metrics_path.write_bytes(metrics_payload)
        metrics_hash = hashlib.sha256(metrics_payload).hexdigest()
        checkpoint_path = run_dir / "checkpoints" / "0004.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        metrics_rel = metrics_path.relative_to(REPO_ROOT).as_posix()
        checkpoint["artifacts"][metrics_rel] = metrics_hash
        checkpoint_payload = json.dumps(
            checkpoint, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        checkpoint_path.write_bytes(checkpoint_payload)
        checkpoint_hash = hashlib.sha256(checkpoint_payload).hexdigest()
        journal_path = run_dir / "journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        entry = journal["entries"][-1]
        entry["checkpoint"]["sha256"] = checkpoint_hash
        entry["outputHashes"][entry["checkpoint"]["path"]] = checkpoint_hash
        entry["outputHashes"][metrics_rel] = metrics_hash
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)

    def test_exact_phase_input_hashes_reject_recomputed_journal_forgery(self) -> None:
        from reconstruction.pipeline import PipelineError, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        journal_path = run_dir / "journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["entries"][1]["inputHashes"]["contract"] = "0" * 64
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(PipelineError):
            run_reconstruction(contract_path)

    def test_reconstruct_failure_before_svg_uses_phase_start_input_snapshot(self) -> None:
        import reconstruction.pipeline as pipeline_module

        contract_path, run_dir, _ = self.make_contract()
        pipeline_module.run_reconstruction(contract_path, target="analyze")
        with mock.patch.object(
            pipeline_module, "serialize_svg", side_effect=ValueError("before-svg")
        ):
            failed = pipeline_module.run_reconstruction(
                contract_path, target="reconstruct"
            )
        self.assertEqual(failed.state, "FAILED")
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        inputs = journal["entries"][-1]["inputHashes"]
        self.assertEqual(set(inputs), {"contract", "explicitRir", "normalizedReference"})
        self.assertNotIn("sanitizedSvg", inputs)

    def test_contract_revocation_after_metrics_restores_last_authorized_journal(self) -> None:
        import reconstruction.pipeline as pipeline_module

        contract_path, run_dir, contract = self.make_contract()
        pipeline_module.run_reconstruction(
            contract_path, stop_after="RECONSTRUCTED_LOCAL"
        )
        before = (run_dir / "journal.json").read_bytes()

        def revoke(*_args: object) -> None:
            changed = copy.deepcopy(contract)
            changed["writeAuthorization"]["state"] = "revoked"
            contract_path.write_text(json.dumps(changed), encoding="utf-8")

        with mock.patch.object(pipeline_module, "_after_metrics", side_effect=revoke), self.assertRaises(
            pipeline_module.PipelineError
        ):
            pipeline_module.run_reconstruction(contract_path)
        self.assertEqual((run_dir / "journal.json").read_bytes(), before)
        self.assertFalse((run_dir / "diff.png").exists())
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        self.assertTrue(pipeline_module.run_reconstruction(contract_path).passed)

    def test_contract_revocation_after_journal_commit_restores_old_chain(self) -> None:
        import reconstruction.state as state_module
        from reconstruction.pipeline import PipelineError, run_reconstruction

        contract_path, run_dir, contract = self.make_contract()

        def revoke(*_args: object) -> None:
            changed = copy.deepcopy(contract)
            changed["writeAuthorization"]["state"] = "revoked"
            contract_path.write_text(json.dumps(changed), encoding="utf-8")

        with mock.patch.object(state_module, "_after_journal_commit", side_effect=revoke), self.assertRaises(
            PipelineError
        ):
            run_reconstruction(contract_path, target="analyze")
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual([entry["newState"] for entry in journal["entries"]], ["CREATED"])
        self.assertFalse((run_dir / "checkpoints" / "0002.json").exists())
        self.assertFalse((run_dir / "reference.normalized.png").exists())
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        self.assertEqual(run_reconstruction(contract_path, target="analyze").state, "ANALYZED")

    def test_preexisting_unknown_target_is_preserved_and_never_claimed(self) -> None:
        from reconstruction.pipeline import rollback_run, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        target = run_dir / "reference.normalized.png"
        target.write_bytes(b"operator-owned")
        summary = run_reconstruction(contract_path, target="analyze")
        self.assertEqual(summary.state, "FAILED")
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        target_rel = target.relative_to(REPO_ROOT).as_posix()
        self.assertNotIn(target_rel, journal["createdArtifacts"])
        rollback_run(run_dir)
        self.assertEqual(target.read_bytes(), b"operator-owned")

    def test_target_appearing_after_phase_snapshot_is_not_overwritten_or_claimed(self) -> None:
        import reconstruction.pipeline as pipeline_module

        contract_path, run_dir, _ = self.make_contract()
        target = run_dir / "reference.normalized.png"
        original_prepare = pipeline_module._prepare_phase_outputs

        def race(*args: object, **kwargs: object) -> object:
            claims = original_prepare(*args, **kwargs)
            target.write_bytes(b"racing-operator")
            return claims

        with mock.patch.object(
            pipeline_module, "_prepare_phase_outputs", side_effect=race
        ):
            summary = pipeline_module.run_reconstruction(contract_path, target="analyze")
        self.assertEqual(summary.state, "FAILED")
        self.assertEqual(target.read_bytes(), b"racing-operator")
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertNotIn(target.relative_to(REPO_ROOT).as_posix(), journal["createdArtifacts"])

    def test_targeted_data_rollback_then_full_is_idempotent_and_metadata_is_forbidden(self) -> None:
        from reconstruction.pipeline import RollbackBoundaryError, rollback_run, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path)
        targeted = rollback_run(run_dir, Path("preview.png"))
        self.assertTrue(targeted.passed)
        self.assertFalse((run_dir / "preview.png").exists())
        self.assertTrue((run_dir / "journal.json").exists())
        for metadata in (Path("journal.json"), Path("checkpoints") / "0001.json"):
            with self.subTest(metadata), self.assertRaises(RollbackBoundaryError):
                rollback_run(run_dir, metadata)
        full = rollback_run(run_dir)
        again = rollback_run(run_dir)
        self.assertTrue(full.passed)
        self.assertEqual(again.removed, ())

    def test_failed_retry_then_success_can_full_rollback_latest_artifacts(self) -> None:
        import reconstruction.pipeline as pipeline_module

        contract_path, run_dir, _ = self.make_contract()
        pipeline_module.run_reconstruction(
            contract_path, stop_after="RECONSTRUCTED_LOCAL"
        )
        with mock.patch.object(
            pipeline_module, "_after_metrics", side_effect=ValueError("retry")
        ):
            self.assertEqual(
                pipeline_module.run_reconstruction(contract_path).state, "FAILED"
            )
        self.assertTrue(pipeline_module.run_reconstruction(contract_path).passed)
        summary = pipeline_module.rollback_run(run_dir)
        self.assertTrue(summary.passed)
        for name in (
            "reference.normalized.png", "master.svg", "preview.png", "diff.png",
            "metrics.json", "journal.json",
        ):
            self.assertFalse((run_dir / name).exists(), name)

    def test_final_snapshot_revalidation_rejects_each_current_artifact_replacement(self) -> None:
        import reconstruction.state as state_module
        from reconstruction.pipeline import PipelineError, run_reconstruction

        for name in (
            "reference.normalized.png", "master.svg", "preview.png", "diff.png", "metrics.json"
        ):
            with self.subTest(name):
                contract_path, run_dir, _ = self.make_contract()
                run_reconstruction(contract_path)
                fired = False

                def replace_after_metrics(*_args: object) -> None:
                    nonlocal fired
                    if not fired:
                        fired = True
                        (run_dir / name).write_bytes(b"replaced-after-semantic-validation")

                with mock.patch.object(
                    state_module,
                    "_after_metrics_semantic_validation",
                    side_effect=replace_after_metrics,
                ), self.assertRaises(PipelineError):
                    run_reconstruction(contract_path)

    def test_completed_phase_cli_targets_remain_successful_after_pixel_state(self) -> None:
        contract_path, run_dir, _ = self.make_contract()
        completed, _ = self.run_cli("verify", contract_path)
        self.assertEqual(completed.returncode, 0)
        count = len(json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))["entries"])
        for command in ("analyze", "reconstruct", "verify"):
            result, payload = self.run_cli(command, contract_path)
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue(payload["passed"])
        self.assertEqual(
            len(json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))["entries"]),
            count,
        )

    def test_rollback_rejects_absolute_and_parent_targets(self) -> None:
        from reconstruction.pipeline import RollbackBoundaryError, rollback_run, run_reconstruction
        from reconstruction.state import PipelineStateError, initialize_state, load_contract, record_transition

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        for unsafe in (Path("..") / "reports", run_dir.parent / "outside"):
            with self.subTest(str(unsafe)), self.assertRaises(RollbackBoundaryError):
                rollback_run(run_dir, unsafe)

        loaded_contract, _, contract_sha = load_contract(contract_path)
        loaded = initialize_state(loaded_contract, contract_sha)
        with self.assertRaises(PipelineStateError):
            record_transition(
                loaded,
                new_state="PIXEL_VERIFIED_DETERMINISTIC",
                phase="verify",
                completed_phases=[],
                artifact_hashes={},
                input_hashes={"contract": contract_sha},
            )

    def test_rollback_rejects_forged_artifact_ledger(self) -> None:
        from reconstruction.pipeline import RollbackBoundaryError, rollback_run, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        sentinel = run_dir / "operator-sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        journal_path = run_dir / "journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["createdArtifacts"].append(sentinel.relative_to(REPO_ROOT).as_posix())
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(RollbackBoundaryError):
            rollback_run(run_dir)
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_rollback_rejects_forged_rir_input_ledger(self) -> None:
        from reconstruction.pipeline import RollbackBoundaryError, rollback_run, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        rir = run_dir / "input.rir.json"
        journal_path = run_dir / "journal.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
        journal["createdArtifacts"].append(rir.relative_to(REPO_ROOT).as_posix())
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(RollbackBoundaryError):
            rollback_run(run_dir)
        self.assertTrue(rir.is_file())

    def test_rollback_rejects_hardlinked_artifact_without_touching_sibling_inode(self) -> None:
        from reconstruction.pipeline import RollbackBoundaryError, rollback_run, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        normalized = run_dir / "reference.normalized.png"
        sibling = run_dir / "operator-hardlink.png"
        try:
            os.link(normalized, sibling)
        except OSError as exc:
            self.skipTest(f"hardlink unavailable: {exc}")
        original = sibling.read_bytes()
        with self.assertRaises(RollbackBoundaryError):
            rollback_run(run_dir)
        self.assertEqual(sibling.read_bytes(), original)
        self.assertTrue(normalized.exists())

    def test_repeated_rollback_is_idempotent_and_preserves_unknown_sibling(self) -> None:
        from reconstruction.pipeline import RollbackBoundaryError, rollback_run, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        sibling = run_dir / "operator-sentinel.txt"
        sibling.write_text("keep", encoding="utf-8")
        run_reconstruction(contract_path, stop_after="ANALYZED")
        first = rollback_run(run_dir)
        second = rollback_run(run_dir)
        self.assertTrue(first.passed)
        self.assertTrue(second.passed)
        self.assertEqual(second.removed, ())
        self.assertEqual(sibling.read_text(encoding="utf-8"), "keep")
        with self.assertRaises(RollbackBoundaryError):
            rollback_run(run_dir, Path("..") / "outside")

    @unittest.skipUnless(os.name == "nt", "Windows junction coverage")
    def test_rollback_rejects_reparse_target_without_touching_outside_sentinel(self) -> None:
        from reconstruction.pipeline import RollbackBoundaryError, rollback_run, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        normalized = run_dir / "reference.normalized.png"
        normalized.unlink()
        outside = run_dir.parent / f"outside-{uuid.uuid4().hex}"
        outside.mkdir()
        self.paths.append(outside)
        sentinel = outside / "sentinel.txt"
        sentinel.write_text("keep", encoding="utf-8")
        linked = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(normalized), str(outside)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if linked.returncode != 0:
            self.skipTest(f"junction unavailable: {linked.stdout}{linked.stderr}")
        try:
            with self.assertRaises(RollbackBoundaryError):
                rollback_run(run_dir)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
        finally:
            if normalized.exists():
                os.rmdir(normalized)

    def test_failed_phase_ledgers_partial_artifacts_for_exact_rollback(self) -> None:
        from reconstruction.pipeline import rollback_run, run_reconstruction

        contract_path, run_dir, contract = self.make_contract()
        preview = next(item for item in contract["artifacts"] if item.get("role") == "render-preview")
        preview["sha256"] = "0" * 64
        contract_path.write_text(json.dumps(contract), encoding="utf-8")
        summary = run_reconstruction(contract_path)
        self.assertEqual(summary.state, "FAILED")
        self.assertTrue((run_dir / "master.svg").is_file())
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        master_rel = (run_dir / "master.svg").relative_to(REPO_ROOT).as_posix()
        self.assertIn(master_rel, journal["createdArtifacts"])
        rollback_run(run_dir)
        self.assertFalse((run_dir / "master.svg").exists())

    def test_atomic_post_replace_readback_failure_removes_unreturned_output(self) -> None:
        import reconstruction.state as state_module
        from reconstruction.pipeline import run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, target="analyze")

        def fail_master(path: Path) -> None:
            if path.name == "master.svg":
                raise state_module.PipelineStateError("injected post-replace readback failure")

        with mock.patch.object(
            state_module, "_after_atomic_replace", side_effect=fail_master
        ):
            failed = run_reconstruction(contract_path, target="reconstruct")
        self.assertEqual(failed.state, "FAILED")
        self.assertFalse((run_dir / "master.svg").exists())
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(journal["entries"][-1]["newState"], "FAILED")

    def test_atomic_post_replace_cleanup_failure_is_blocked_with_residue(self) -> None:
        import reconstruction.state as state_module
        from reconstruction.pipeline import run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, target="analyze")

        def fail_master(path: Path) -> None:
            if path.name == "master.svg":
                raise state_module.PipelineStateError("injected post-replace readback failure")

        def block_master_cleanup(path: Path) -> None:
            if path.name == "master.svg":
                raise OSError("injected cleanup lock")
            path.unlink()

        with mock.patch.object(
            state_module, "_after_atomic_replace", side_effect=fail_master
        ), mock.patch.object(
            state_module, "_remove_failed_atomic_target", side_effect=block_master_cleanup
        ), self.assertRaises(state_module.PipelineBlockedError) as caught:
            run_reconstruction(contract_path, target="reconstruct")
        self.assertIn("master.svg", str(caught.exception))
        self.assertTrue((run_dir / "master.svg").exists())
        journal = json.loads((run_dir / "journal.json").read_text(encoding="utf-8"))
        self.assertEqual(journal["entries"][-1]["newState"], "ANALYZED")

    @unittest.skipUnless(os.name == "nt", "Windows read-only deletion semantics")
    def test_rollback_lock_or_permission_failure_is_blocked_and_preserves_journal(self) -> None:
        from reconstruction.pipeline import RollbackBlockedError, rollback_run, run_reconstruction

        contract_path, run_dir, _ = self.make_contract()
        run_reconstruction(contract_path, stop_after="ANALYZED")
        normalized = run_dir / "reference.normalized.png"
        normalized.chmod(0o444)
        try:
            with self.assertRaises(RollbackBlockedError):
                rollback_run(run_dir)
            self.assertTrue((run_dir / "journal.json").is_file())
        finally:
            if normalized.exists():
                normalized.chmod(0o666)


if __name__ == "__main__":
    unittest.main()
