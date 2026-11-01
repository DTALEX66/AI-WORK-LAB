# SPDX-License-Identifier: MIT
"""DL-P1-140: audio provider contract tests (STRUCTURAL / E1 evidence only).

Every assertion here is structural: no audio model is opened, no inference is
run and no host is started. Where a test proves that a stage cannot run, it
asserts the fail-closed error code instead of a runtime result.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

TMP_ROOT = ROOT / ".project-local/task-runtime/media-audio-tests"
DIGEST = "sha256:" + "a" * 64

from design_lab.adapters.spi import LIFECYCLE, ProviderAdapter  # noqa: E402
from design_lab.creative.media import MediaError  # noqa: E402
from design_lab.creative.media import audio_provider as ap  # noqa: E402


class MediaAudioTests(unittest.TestCase):
    def setUp(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.tmp = Path(tempfile.mkdtemp(prefix="case-", dir=TMP_ROOT))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.asset_dir = self.tmp / "model-library"
        self.asset_dir.mkdir()

    def registry(self, **kwargs) -> ap.AudioModelRegistry:
        return ap.AudioModelRegistry(alias_roots={"model-library": self.asset_dir}, **kwargs)

    def qualified_registry(self, model_id: str = "asr-local") -> ap.AudioModelRegistry:
        registry = self.registry()
        registry.register_local_model(
            model_id, path_ref="model-library", sha256=DIGEST, license_id="MIT"
        )
        registry.qualify_local_model(model_id, host_live_reference="host-live:qual-0001")
        return registry

    # -- capability declarations -----------------------------------------
    def test_declared_capabilities_are_unsupported_at_e1(self) -> None:
        provider = ap.AudioProvider()
        capabilities = provider.declare_capabilities()
        self.assertEqual([item["stage"] for item in capabilities], list(ap.AUDIO_STAGES))
        for item in capabilities:
            self.assertFalse(item["supported"])
            self.assertEqual(item["evidence"], "E1")
            self.assertIsNone(item["reference"])

    def test_probe_reports_declarations_only(self) -> None:
        provider = ap.AudioProvider(registry=self.registry())
        record = provider.probe({})
        self.assertEqual(record["status"], "structural")
        self.assertEqual(record["host_execution"], "NOT_EXECUTED")
        self.assertTrue(record["declared_only"])
        self.assertEqual(record["probed"], [])
        self.assertEqual(record["evidence"]["level"], "E1")
        self.assertEqual(record["evidence"]["task_ids"], ["DL-P1-140"])
        self.assertEqual(record["models"]["qualified"], 0)
        self.assertEqual(record["models"]["resolution"], "NOT_EXECUTED")

    def test_capability_upgrade_requires_measured_evidence(self) -> None:
        provider = ap.AudioProvider()
        with self.assertRaises(MediaError) as caught:
            provider.declare_capabilities({"asr": {"level": "E1", "reference": "note"}})
        self.assertEqual(caught.exception.code, "AUDIO_EVIDENCE_NOT_MEASURED")
        upgraded = provider.declare_capabilities(
            {"asr": {"level": "E2", "reference": "host-live:asr-0001"}}
        )
        asr = next(item for item in upgraded if item["stage"] == "asr")
        self.assertTrue(asr["supported"])
        self.assertEqual(asr["evidence"], "E2")
        others = [item for item in upgraded if item["stage"] != "asr"]
        self.assertTrue(all(not item["supported"] for item in others))

    def test_evidence_requirements_are_explicit_per_stage(self) -> None:
        for stage in ap.AUDIO_STAGES:
            requirements = ap.evidence_requirements(stage)
            self.assertGreaterEqual(len(requirements), 6)
            self.assertTrue(all(isinstance(item, str) and item for item in requirements))
        self.assertNotEqual(
            ap.evidence_requirements("asr"), ap.evidence_requirements("music")
        )
        with self.assertRaises(MediaError) as caught:
            ap.evidence_requirements("voice-clone")
        self.assertEqual(caught.exception.code, "AUDIO_STAGE_UNKNOWN")

    # -- SPI lifecycle ----------------------------------------------------
    def test_provider_conforms_to_provider_adapter_spi(self) -> None:
        provider = ap.AudioProvider()
        self.assertIsInstance(provider, ProviderAdapter)
        self.assertEqual(provider.adapter_type, "provider")
        self.assertEqual(provider.adapter_id, "design-lab.audio-provider.structural")
        self.assertTrue(provider.version)
        for method in LIFECYCLE:
            self.assertTrue(callable(getattr(provider, method)), method)

    def test_execute_always_fails_closed(self) -> None:
        provider = ap.AudioProvider(registry=self.qualified_registry())
        with self.assertRaises(MediaError) as caught:
            provider.execute({"operation_id": "op-1", "stage": "asr", "model_id": "asr-local"})
        self.assertEqual(
            caught.exception.code, "AUDIO_EXECUTION_NOT_EXECUTED_STRUCTURAL_ONLY"
        )
        self.assertIn("NOT_EXECUTED", str(caught.exception))
        self.assertIn("host-live qualification", str(caught.exception))
        with self.assertRaises(MediaError) as bad_stage:
            provider.execute({"stage": "voice-clone"})
        self.assertEqual(bad_stage.exception.code, "AUDIO_STAGE_UNKNOWN")
        with self.assertRaises(MediaError) as bad_envelope:
            provider.execute(["not", "a", "mapping"])
        self.assertEqual(bad_envelope.exception.code, "AUDIO_ENVELOPE_INVALID")

    def test_prepare_hashes_the_request_and_stays_structural(self) -> None:
        from design_lab.runtime.attempt_contract import request_hash

        provider = ap.AudioProvider(registry=self.qualified_registry())
        plan = provider.prepare(
            {"operation_id": "op-1", "stage": "tts", "model_id": "asr-local"}
        )
        self.assertEqual(plan["status"], "PREPARED_STRUCTURAL_ONLY")
        self.assertEqual(plan["model_resolution"], "NOT_EXECUTED")
        self.assertEqual(plan["host_execution"], "NOT_EXECUTED")
        self.assertIn("AUDIO_STAGE_UNSUPPORTED_NO_MEASURED_EVIDENCE", plan["blocked_by"])
        expected = request_hash(
            {
                "operation_id": "op-1",
                "stage": "tts",
                "model_id": "asr-local",
                "declared_supported": False,
            }
        )
        self.assertEqual(plan["request_hash"], expected)
        self.assertEqual(len(plan["evidence_requirements"]), len(ap.evidence_requirements("tts")))
        with self.assertRaises(MediaError) as unknown_model:
            provider.prepare({"operation_id": "op-1", "stage": "tts", "model_id": "nope"})
        self.assertEqual(unknown_model.exception.code, "AUDIO_MODEL_UNKNOWN")

    def test_observe_readback_and_rollback_never_claim_a_run(self) -> None:
        provider = ap.AudioProvider()
        observation = provider.observe({"operation_id": "op-1", "stage": "asr"})
        self.assertEqual(observation["status"], "NOT_EXECUTED")
        self.assertEqual(observation["observations"], [])
        self.assertTrue(observation["observation_contract"])
        self.assertIn(
            "transcript length and sha256 (never the transcript text)",
            observation["observation_contract"],
        )
        readback = provider.readback({"operation_id": "op-1"})
        self.assertEqual(readback["artifact_readback"], "NOT_EXECUTED")
        self.assertIsNone(readback["record"])
        rollback = provider.rollback({"operation_id": "op-1"})
        self.assertFalse(rollback["executed"])
        self.assertEqual(rollback["status"], "NOT_EXECUTED")
        self.assertTrue(rollback["actions"])

    def test_readback_accepts_a_record_without_claiming_verification(self) -> None:
        provider = ap.AudioProvider()
        record = ap.AudioJobRecord(
            operation_id="op-1", stage="tts", model_id="asr-local",
            input_sha256=DIGEST, output_sha256=None, sample_rate=48000,
            duration_seconds=1.5, language="en",
        )
        readback = provider.readback({"record": record})
        self.assertEqual(readback["record"]["operation_id"], "op-1")
        self.assertEqual(readback["artifact_readback"], "NOT_EXECUTED")
        with self.assertRaises(MediaError) as caught:
            provider.readback({"record": {"operation_id": "op-1"}})
        self.assertEqual(caught.exception.code, "AUDIO_RECORD_INVALID")

    # -- local external model registry ------------------------------------
    def test_registration_records_an_unqualified_disabled_declaration(self) -> None:
        registry = self.registry()
        entry = registry.register_local_model(
            "tts-local", path_ref="model-library", sha256=DIGEST, license_id="Apache-2.0"
        )
        self.assertEqual(entry["qualification"], "UNQUALIFIED_DECLARED")
        self.assertFalse(entry["defaultEnabled"])
        self.assertEqual(entry["evidence"], "E1")
        self.assertEqual(entry["sha256"], DIGEST)
        self.assertEqual(registry.qualified_model_ids(), [])

    def test_registration_rejects_paths_and_bad_hashes(self) -> None:
        registry = self.registry()
        with self.assertRaises(MediaError) as absolute:
            registry.register_local_model(
                "m1", path_ref="D:/All projects/Model library", sha256=DIGEST, license_id="MIT"
            )
        self.assertEqual(absolute.exception.code, "AUDIO_MODEL_PATH_REF_INVALID")
        with self.assertRaises(MediaError) as relative:
            registry.register_local_model(
                "m1", path_ref="models/asr", sha256=DIGEST, license_id="MIT"
            )
        self.assertEqual(relative.exception.code, "AUDIO_MODEL_PATH_REF_INVALID")
        with self.assertRaises(MediaError) as zero:
            registry.register_local_model(
                "m1", path_ref="model-library", sha256="sha256:" + "0" * 64,
                license_id="MIT",
            )
        self.assertEqual(zero.exception.code, "MEDIA_SHA256_INVALID")
        with self.assertRaises(MediaError) as short:
            registry.register_local_model(
                "m1", path_ref="model-library", sha256="sha256:abc", license_id="MIT"
            )
        self.assertEqual(short.exception.code, "MEDIA_SHA256_INVALID")

    def test_qualification_requires_a_host_live_receipt(self) -> None:
        registry = self.registry()
        registry.register_local_model(
            "asr-local", path_ref="model-library", sha256=DIGEST, license_id="MIT"
        )
        for reference in ("measured-on-host", "host-live:", "D:/receipts/1.json"):
            with self.assertRaises(MediaError) as caught:
                registry.qualify_local_model("asr-local", host_live_reference=reference)
            self.assertEqual(caught.exception.code, "AUDIO_QUALIFICATION_UNPROVEN")
        entry = registry.qualify_local_model(
            "asr-local", host_live_reference="host-live:qual-0001"
        )
        self.assertEqual(entry["qualification"], "QUALIFIED")
        self.assertFalse(entry["defaultEnabled"])
        with self.assertRaises(MediaError) as unknown:
            registry.qualify_local_model("nope", host_live_reference="host-live:x")
        self.assertEqual(unknown.exception.code, "AUDIO_MODEL_UNKNOWN")

    def test_resolver_fails_closed_on_every_unproven_case(self) -> None:
        with self.assertRaises(MediaError) as unknown:
            ap.resolve_audio_model(self.registry(), "missing")
        self.assertEqual(unknown.exception.code, "AUDIO_MODEL_UNKNOWN")

        unqualified = self.registry()
        unqualified.register_local_model(
            "asr-local", path_ref="model-library", sha256=DIGEST, license_id="MIT"
        )
        with self.assertRaises(MediaError) as caught:
            ap.resolve_audio_model(unqualified, "asr-local")
        self.assertEqual(caught.exception.code, "AUDIO_MODEL_UNQUALIFIED")

        zero = ap.AudioModelRegistry(alias_roots={"model-library": self.asset_dir})
        zero.import_declarations(
            {
                "models": [
                    {
                        "model_id": "asr-local",
                        "path_ref": "model-library",
                        "sha256": "sha256:" + "0" * 64,
                        "license_id": "MIT",
                        "qualification": "QUALIFIED",
                        "host_live_reference": "host-live:legacy",
                    }
                ]
            }
        )
        with self.assertRaises(MediaError) as zero_hash:
            ap.resolve_audio_model(zero, "asr-local")
        self.assertEqual(zero_hash.exception.code, "AUDIO_MODEL_HASH_ZERO")

        missing_file = ap.AudioModelRegistry(
            alias_roots={"model-library": self.tmp / "not-there"}
        )
        missing_file.register_local_model(
            "asr-local", path_ref="model-library", sha256=DIGEST, license_id="MIT"
        )
        missing_file.qualify_local_model("asr-local", host_live_reference="host-live:q")
        with self.assertRaises(MediaError) as missing:
            ap.resolve_audio_model(missing_file, "asr-local")
        self.assertEqual(missing.exception.code, "AUDIO_MODEL_FILE_MISSING")

        unknown_alias = ap.AudioModelRegistry(alias_roots={"model-library": self.asset_dir})
        unknown_alias.import_declarations(
            {
                "models": [
                    {
                        "model_id": "asr-local",
                        "path_ref": "other-root",
                        "sha256": DIGEST,
                        "license_id": "MIT",
                        "qualification": "QUALIFIED",
                        "host_live_reference": "host-live:q",
                    }
                ]
            }
        )
        with self.assertRaises(MediaError) as alias:
            ap.resolve_audio_model(unknown_alias, "asr-local")
        self.assertEqual(alias.exception.code, "AUDIO_MODEL_ALIAS_UNKNOWN")

        conflicted = self.qualified_registry()
        conflicted.mark_license_conflict("asr-local", "license withdrawn by the vendor")
        with self.assertRaises(MediaError) as license_conflict:
            ap.resolve_audio_model(conflicted, "asr-local")
        self.assertEqual(license_conflict.exception.code, "AUDIO_MODEL_UNQUALIFIED")

    def test_resolver_returns_a_qualified_model_without_rehashing(self) -> None:
        registry = self.qualified_registry()
        resolved = ap.resolve_audio_model(registry, "asr-local")
        self.assertEqual(resolved["status"], "QUALIFIED")
        self.assertEqual(resolved["sha256"], DIGEST)
        self.assertEqual(resolved["path_ref"], "model-library")
        self.assertEqual(resolved["host_live_reference"], "host-live:qual-0001")
        self.assertFalse(resolved["hash_reverified"])
        self.assertEqual(resolved["resolved_path"], self.asset_dir.as_posix())

    def test_denied_license_blocks_resolution_even_when_qualified(self) -> None:
        registry = self.qualified_registry()
        registry.deny_license("MIT")
        with self.assertRaises(MediaError) as caught:
            ap.resolve_audio_model(registry, "asr-local")
        self.assertEqual(caught.exception.code, "AUDIO_MODEL_LICENSE_CONFLICT")

    def test_resolver_rejects_a_foreign_registry(self) -> None:
        with self.assertRaises(MediaError) as caught:
            ap.resolve_audio_model(
                {"models": [{"model_id": "x"}]}, "x"
            )
        self.assertEqual(caught.exception.code, "AUDIO_REGISTRY_INVALID")

    # -- job record -------------------------------------------------------
    def test_job_record_round_trip_is_exact(self) -> None:
        record = ap.AudioJobRecord(
            operation_id="op-42",
            stage="music",
            model_id="music-local",
            input_sha256=DIGEST,
            output_sha256="sha256:" + "b" * 64,
            sample_rate=44100,
            duration_seconds=12.5,
            language="en-GB",
            transcript_sha256="sha256:" + "c" * 64,
            readback={"artifact_bytes": 2205000, "status": "NOT_EXECUTED"},
        )
        document = record.to_dict()
        self.assertEqual(json.loads(json.dumps(document)), document)
        self.assertEqual(ap.AudioJobRecord.from_dict(document), record)
        self.assertEqual(ap.AudioJobRecord.from_dict(record.to_dict()).to_dict(), document)
        self.assertNotIn("transcript", document)

    def test_job_record_refuses_transcript_text(self) -> None:
        for key in ("transcript", "transcript_text", "text"):
            with self.assertRaises(MediaError) as caught:
                ap.AudioJobRecord(
                    operation_id="op-1", stage="asr",
                    readback={key: "the private words of the user"},
                )
            self.assertEqual(
                caught.exception.code, "AUDIO_TRANSCRIPT_TEXT_MUST_NOT_BE_STORED"
            )

    def test_job_record_validates_its_fields(self) -> None:
        with self.assertRaises(MediaError) as stage:
            ap.AudioJobRecord(operation_id="op-1", stage="sfx2")
        self.assertEqual(stage.exception.code, "AUDIO_RECORD_INVALID")
        with self.assertRaises(MediaError):
            ap.AudioJobRecord(operation_id="op-1", stage="sfx", sample_rate=0)
        with self.assertRaises(MediaError):
            ap.AudioJobRecord(operation_id="op-1", stage="sfx", duration_seconds=-1)
        with self.assertRaises(MediaError):
            ap.AudioJobRecord(operation_id="op-1", stage="sfx", input_sha256="sha256:00")
        with self.assertRaises(MediaError) as keys:
            ap.AudioJobRecord.from_dict({"operation_id": "op-1", "stage": "sfx"})
        self.assertEqual(keys.exception.code, "AUDIO_RECORD_INVALID")

    # -- documents and schemas --------------------------------------------
    def test_registry_document_matches_schema_and_leaks_no_path(self) -> None:
        from jsonschema import Draft202012Validator

        from design_lab.creative.media import load_schema, reject_absolute_paths

        registry = self.qualified_registry()
        document = registry.to_dict()
        self.assertIsInstance(document["models"][0]["defaultEnabled"], bool)
        Draft202012Validator.check_schema(load_schema("media-audio-provider"))
        Draft202012Validator(load_schema("media-audio-provider")).validate(document)
        self.assertEqual(document["host_execution"], "NOT_EXECUTED")
        self.assertEqual(document["declared_aliases"], ["model-library"])
        self.assertIn("media-audio-provider", str(load_schema("media-audio-provider")["$id"]))
        self.assertEqual(
            load_schema("media-audio-provider")["$id"],
            "https://dtalex66.local/schemas/media-audio-provider.json",
        )
        with self.assertRaises(MediaError) as leaked:
            reject_absolute_paths(
                {"models": [{"path_ref": "D:/All projects/Model library"}]}, "test"
            )
        self.assertEqual(leaked.exception.code, "MEDIA_ABSOLUTE_PATH_LEAK")

    def test_schema_rejects_a_qualified_model_without_a_receipt(self) -> None:
        from jsonschema import Draft202012Validator

        from design_lab.creative.media import load_schema

        document = ap.AudioModelRegistry().to_dict()
        document["models"] = [
            {
                "model_id": "m",
                "path_ref": "model-library",
                "sha256": DIGEST,
                "license_id": "MIT",
                "qualification": "QUALIFIED",
                "defaultEnabled": False,
                "evidence": "E1",
                "note": "structural claim",
            }
        ]
        errors = list(Draft202012Validator(load_schema("media-audio-provider")).iter_errors(document))
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
