"""Negative controls for the AG-05/AG-06 fail-closed verifiers.

These two verifiers were added on 2026-10-01 to stop silent-wrong-truth in the
model/provider/runtime registries and in the ACP adapter capability surface. A
verifier that cannot fail is worthless, so every rule is exercised with a
deliberately broken fixture and asserted to produce the named failure.

All fixtures are written under a temporary directory. The real repository
registries are never touched, no model asset is read, no runtime is started, and
no network call is made.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_CI = ROOT / "scripts" / "ci"
FEDERATION_DIR = ROOT / "services" / "execution-federation"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


MRI = _load("ag05_model_registry_integrity", SCRIPTS_CI / "verify_model_registry_integrity.py")
ACP = _load("ag06_acp_adapter_honesty", SCRIPTS_CI / "verify_acp_adapter_honesty.py")


def _valid_registries() -> tuple[dict, dict, dict]:
    """A minimal but fully valid registry triple."""
    provider = {
        "schemaVersion": "work-lab/provider-registry/v1",
        "providers": [
            {
                "id": "local.fast.default",
                "binds_to_model": "qwen-small",
                "binds_to_runtime": "lmstudio",
            },
            {
                "id": "local.legacy",
                "binds_to_model": "qwen-old",
                "binds_to_runtime": "lmstudio",
                "binding_status": "UNSERVED_RETAINED_PENDING_DECISION",
                "binding_status_source": "model-registry.json models[id=qwen-old].status",
                "operationalStatus": "RUNTIME endpoint scope only: the HTTP server is up.",
            },
            {
                "id": "local.asr",
                "binds_to_model": "whisper",
                "binds_to_runtime": "faster-whisper",
            },
        ],
    }
    model = {
        "schemaVersion": "work-lab/model-registry/v1",
        "models": [
            {"id": "qwen-small", "sha256": "a" * 64, "status": "active",
             "runtime_id": "lmstudio",
             "localVerification": {
                 "presence": "VERIFIED_FILE", "digestState": "RECOMPUTED_MATCH",
                 "sha256Recomputed": "a" * 64, "bytesObserved": 1024,
                 "checkedAt": "2026-10-07", "basis": "fixture: sha256 over the file bytes",
                 "tool": "scripts/audit/model_library_readback.py"}},
            {"id": "qwen-old", "sha256": None, "status": "RETIRED_PENDING_DECISION",
             "runtime_id": None,
             "assetDigest": {"state": "TRUNCATED", "prefix": "deadbeefdeadbeef",
                             "reason": "only a prefix survives in the record"},
             "localVerification": {
                 "presence": "VERIFIED_DIR", "digestState": "NOT_RECOMPUTED",
                 "bytesRetained": 4096, "bytesObserved": 4096, "checkedAt": "2026-10-07",
                 "basis": "fixture: directory of leftover layers, never hashed as one artifact",
                 "tool": "scripts/audit/model_library_readback.py",
                 "directoryManifest": [{"relative_path": "layer.bin", "bytes": 4096,
                                        "sha256": "d" * 64}]}},
            {"id": "whisper", "sha256": None, "status": "active",
             "runtime_id": "faster-whisper"},
        ],
        "candidateOrphans": [
            {"path": "leftover.gguf", "sha256": None, "bytes": 512,
             "assetDigest": {"state": "TRUNCATED", "prefix": "a18ae2a5f553fe02",
                             "reason": "partial download residue; full digest never captured"},
             "recheck": {"state": "PRESENT", "checkedAt": "2026-10-07", "bytesObserved": 512,
                         "sha256Recomputed": "a18ae2a5f553fe02" + "0" * 48,
                         "duplicateTested": True, "byteDuplicateOf": None}},
        ],
    }
    runtime = {
        "schemaVersion": "work-lab/runtime-registry/v1",
        "runtimes": [{"id": "lmstudio", "status": "RUNNING"}],
        "processLibraries": [
            {"id": "faster-whisper", "executionModel": "in-process", "listensOnPort": False},
        ],
    }
    return provider, model, runtime


def _write(root: Path, provider: dict, model: dict, runtime: dict) -> None:
    base = root / ".project" / "governance"
    base.mkdir(parents=True, exist_ok=True)
    (base / "provider-registry.json").write_text(json.dumps(provider), encoding="utf-8")
    (base / "model-registry.json").write_text(json.dumps(model), encoding="utf-8")
    (base / "runtime-registry.json").write_text(json.dumps(runtime), encoding="utf-8")


class ModelRegistryIntegrityNegativeControls(unittest.TestCase):
    def _run(self, provider: dict, model: dict, runtime: dict) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, provider, model, runtime)
            import contextlib
            import io

            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = MRI.verify(root)
            return code, err.getvalue()

    def test_valid_fixture_passes(self) -> None:
        code, err = self._run(*_valid_registries())
        self.assertEqual(code, 0, err)
        self.assertEqual(err, "")

    def test_unresolved_model_binding_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["binds_to_model"] = "does-not-exist"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("BINDING_UNRESOLVED", err)

    def test_unresolved_runtime_binding_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["binds_to_runtime"] = "ghost-runtime"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("RUNTIME_BINDING_UNRESOLVED", err)

    def test_duplicate_provider_id_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"].append(dict(p["providers"][0]))
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("PROVIDER_ID_DUPLICATE", err)

    def test_served_claim_contradicting_retired_model_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][1]["binding_status"] = "SERVED"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("BINDING_STATUS_CONTRADICTS_MODEL", err)

    def test_unknown_binding_status_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][1]["binding_status"] = "PROBABLY_FINE"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("BINDING_STATUS_UNKNOWN", err)

    def test_unserved_model_without_binding_status_fails(self) -> None:
        p, m, r = _valid_registries()
        del p["providers"][1]["binding_status"]
        del p["providers"][1]["binding_status_source"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("UNSERVED_MODEL_WITHOUT_BINDING_STATUS", err)

    # --- AG-05g: a byte claim must say what it was computed over -------------

    def test_digest_claim_without_a_verification_basis_fails(self) -> None:
        p, m, r = _valid_registries()
        del m["models"][0]["localVerification"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("LOCAL_VERIFICATION_MISSING", err)

    def test_recomputed_digest_contradicting_the_record_fails(self) -> None:
        p, m, r = _valid_registries()
        m["models"][0]["localVerification"]["sha256Recomputed"] = "f" * 64
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("LOCAL_VERIFICATION_CONTRADICTS_SHA256", err)

    def test_match_claim_without_observed_bytes_fails(self) -> None:
        p, m, r = _valid_registries()
        del m["models"][0]["localVerification"]["bytesObserved"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("LOCAL_VERIFICATION_BYTES_MISSING", err)

    def test_verified_health_word_without_recomputation_fails(self) -> None:
        p, m, r = _valid_registries()
        m["models"][0]["health"] = "DOWNLOADED_HASH_VERIFIED"
        m["models"][0]["localVerification"]["digestState"] = "NOT_RECOMPUTED"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("HEALTH_CLAIMS_VERIFIED_WITHOUT_RECOMPUTATION", err)

    def test_undated_readback_fails(self) -> None:
        p, m, r = _valid_registries()
        m["models"][0]["localVerification"]["checkedAt"] = "recently"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("LOCAL_VERIFICATION_UNDATED", err)

    def test_retiring_model_without_a_cost_fails(self) -> None:
        p, m, r = _valid_registries()
        del m["models"][1]["localVerification"]["bytesRetained"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("RETIRING_MODEL_WITHOUT_A_COST", err)

    def test_retiring_model_released_to_zero_still_passes(self) -> None:
        p, m, r = _valid_registries()
        verification = m["models"][1]["localVerification"]
        verification["bytesRetained"] = 0
        verification["presence"] = "ABSENT"
        del verification["directoryManifest"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 0, err)

    def test_zero_retained_with_verified_presence_fails(self) -> None:
        p, m, r = _valid_registries()
        m["models"][1]["localVerification"]["bytesRetained"] = 0
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("ZERO_RETAINED_WITH_VERIFIED_PRESENCE", err)

    def test_directory_model_without_a_manifest_fails(self) -> None:
        p, m, r = _valid_registries()
        del m["models"][1]["localVerification"]["directoryManifest"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("DIR_MANIFEST_MISSING", err)

    def test_orphan_without_a_recheck_fails(self) -> None:
        p, m, r = _valid_registries()
        del m["candidateOrphans"][0]["recheck"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("ORPHAN_RECHECK_MISSING", err)

    def test_orphan_prose_path_asserted_present_fails(self) -> None:
        p, m, r = _valid_registries()
        m["candidateOrphans"][0]["path"] = "ollama/blobs/sha256-81fb…-partial (+16 files)"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("ORPHAN_PATH_NOT_RESOLVABLE_AS_WRITTEN", err)

    def test_orphan_stale_prefix_claim_fails(self) -> None:
        p, m, r = _valid_registries()
        m["candidateOrphans"][0]["recheck"]["sha256Recomputed"] = "0" * 64
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("ORPHAN_PREFIX_CLAIM_STALE", err)

    def test_orphan_present_without_a_duplicate_test_fails(self) -> None:
        p, m, r = _valid_registries()
        del m["candidateOrphans"][0]["recheck"]["duplicateTested"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("ORPHAN_DUPLICATE_UNTESTED", err)

    def test_operational_status_using_serving_vocabulary_fails(self) -> None:
        # The exact defect AG-05 fixed: an unserved binding whose status line
        # still read "loads this model on demand".
        p, m, r = _valid_registries()
        p["providers"][1]["operationalStatus"] = (
            "OPERATIONAL: the server loads this model on demand."
        )
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("OPERATIONAL_STATUS_OVERREACHES", err)

    def test_prose_sha256_fails(self) -> None:
        p, m, r = _valid_registries()
        m["models"][0]["sha256"] = "e76620f83d5f5b69 (model.bin, 1.507 GB)"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("MODEL_SHA256_UNVERIFIABLE", err)

    def test_truncated_digest_without_reason_fails(self) -> None:
        p, m, r = _valid_registries()
        del m["models"][1]["assetDigest"]["reason"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("ASSET_DIGEST_TRUNCATED_WITHOUT_REASON", err)

    def test_complete_digest_with_bad_hash_fails(self) -> None:
        p, m, r = _valid_registries()
        m["models"][1]["assetDigest"] = {"state": "COMPLETE", "sha256": "abc"}
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("ASSET_DIGEST_INCOMPLETE", err)

    def test_process_library_claiming_a_port_fails(self) -> None:
        p, m, r = _valid_registries()
        r["processLibraries"][0]["listensOnPort"] = True
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("PROCESS_LIBRARY_CLAIMS_PORT", err)

    def test_process_library_without_execution_model_fails(self) -> None:
        p, m, r = _valid_registries()
        del r["processLibraries"][0]["executionModel"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("PROCESS_LIBRARY_EXECUTION_MODEL", err)

    def test_missing_provider_registry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code = MRI.verify(Path(tmp))
            self.assertEqual(code, 1)

    def test_unresolved_model_runtime_id_fails(self) -> None:
        p, m, r = _valid_registries()
        m["models"][0]["runtime_id"] = "ghost-runtime"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("MODEL_RUNTIME_ID_UNRESOLVED", err)

    def test_missing_model_runtime_id_fails(self) -> None:
        # `runtime` prose must never stand in for a resolvable id.
        p, m, r = _valid_registries()
        del m["models"][0]["runtime_id"]
        m["models"][0]["runtime"] = "lmstudio (:1234), prose only"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("MODEL_RUNTIME_ID_MISSING", err)

    def test_active_model_with_null_runtime_id_fails(self) -> None:
        p, m, r = _valid_registries()
        m["models"][0]["runtime_id"] = None
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("UNBOUND_RUNTIME_ON_ACTIVE_MODEL", err)

    def test_process_library_runtime_id_is_accepted(self) -> None:
        p, m, r = _valid_registries()
        m["models"][2]["runtime_id"] = "faster-whisper"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 0, err)

    def test_orphan_prose_digest_fails(self) -> None:
        p, m, r = _valid_registries()
        m["candidateOrphans"] = [{"path": "residue.gguf", "sha256": "a18ae2a5f553fe02"}]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("ORPHAN_SHA256_UNVERIFIABLE", err)

    def test_orphan_truncated_digest_with_reason_passes(self) -> None:
        p, m, r = _valid_registries()
        m["candidateOrphans"] = [{
            "path": "residue.gguf", "sha256": None,
            "assetDigest": {"state": "TRUNCATED", "prefix": "a18ae2a5f553fe02",
                            "reason": "partial download residue; full digest never captured"},
            "recheck": {"state": "ABSENT_NOW", "checkedAt": "2026-10-07"},
        }]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 0, err)

    def test_runtime_note_naming_another_live_runtime_fails(self) -> None:
        # A note that points the reader at a DIFFERENT live runtime than the one
        # actually bound is the AG-05e defect.
        p, m, r = _valid_registries()
        r["runtimes"].append({"id": "llamacpp", "status": "INSTALLED"})
        p["providers"][0]["runtime_note"] = "reranking is served by llamacpp with --pooling rank"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("RUNTIME_NOTE_NAMES_OTHER_RUNTIME", err)

    def test_runtime_note_naming_another_runtime_MARKED_historical_passes(self) -> None:
        p, m, r = _valid_registries()
        r["runtimes"].append({"id": "llamacpp", "status": "INSTALLED"})
        p["providers"][0]["runtime_note"] = (
            "CORRECTED 2026-10-01: previously said llamacpp served this; it is historical. "
            "The active binding is lmstudio."
        )
        code, err = self._run(p, m, r)
        self.assertEqual(code, 0, err)

    def test_runtime_note_not_mentioning_other_runtimes_passes(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["runtime_note"] = "served by the active runtime"
        code, err = self._run(p, m, r)
        self.assertEqual(code, 0, err)

    # --- structured negative capabilities (AG-05f) ----------------------
    def test_well_formed_negative_capability_passes(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["negative_capabilities"] = [{
            "capability": "rerank.expose_score", "state": "UNAVAILABLE",
            "why": "the API never returns logprobs",
            "evidence": "runtime_limitation (b)", "escape_hatch": None,
        }]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 0, err)

    def test_negative_capability_with_unknown_state_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["negative_capabilities"] = [{
            "capability": "x", "state": "MAYBE", "why": "w", "evidence": "e"}]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("NEGATIVE_CAPABILITY_STATE_UNKNOWN", err)

    def test_negative_capability_without_why_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["negative_capabilities"] = [{
            "capability": "x", "state": "UNAVAILABLE", "evidence": "e"}]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("NEGATIVE_CAPABILITY_WITHOUT_WHY", err)

    def test_negative_capability_without_evidence_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["negative_capabilities"] = [{
            "capability": "x", "state": "UNAVAILABLE", "why": "w"}]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("NEGATIVE_CAPABILITY_WITHOUT_EVIDENCE", err)

    def test_negative_capability_without_name_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["negative_capabilities"] = [{
            "state": "UNAVAILABLE", "why": "w", "evidence": "e"}]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("NEGATIVE_CAPABILITY_NO_NAME", err)

    def test_negative_capability_contradicting_a_positive_one_fails(self) -> None:
        # A provider that both claims and denies the same capability is
        # refusing to say what it can do.
        p, m, r = _valid_registries()
        p["providers"][0]["capabilities"] = ["text", "ocr"]
        p["providers"][0]["negative_capabilities"] = [{
            "capability": "ocr", "state": "UNAVAILABLE", "why": "w", "evidence": "e"}]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("NEGATIVE_CAPABILITY_CONTRADICTS_POSITIVE", err)

    def test_malformed_negative_capability_entry_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["negative_capabilities"] = ["not an object"]
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("NEGATIVE_CAPABILITY_MALFORMED", err)

    def test_live_registry_declares_its_known_limitations(self) -> None:
        # The three recorded limitations (binary-only rerank, the 4B reasoning
        # quirk, the unverified OCR matrix) must exist as DATA, not only prose.
        code = MRI.verify(ROOT)
        self.assertEqual(code, 0)
        import json as _json

        registry = _json.loads(
            (ROOT / ".project/governance/provider-registry.json").read_text(encoding="utf-8"))
        named = {
            neg["capability"]
            for provider in registry["providers"]
            for neg in (provider.get("negative_capabilities") or [])
        }
        for expected in ("rerank.expose_score", "rerank.endpoint",
                         "reasoning.long_chain_visible", "ocr.full_matrix_verified"):
            self.assertIn(expected, named)

    def test_null_binding_without_note_fails(self) -> None:
        p, m, r = _valid_registries()
        p["providers"][0]["binds_to_model"] = None
        code, err = self._run(p, m, r)
        self.assertEqual(code, 1)
        self.assertIn("BINDING_NULL_WITHOUT_NOTE", err)


class AcpHonestyNegativeControls(unittest.TestCase):
    """The cross-check must fail a class that over-claims an unwired operation.

    NOTE: at this commit no real adapter declares the over-claim (AG-06 removed
    it from codex/dsh/openhands), so the check cannot fire against the live
    federation. A verifier that is only exercised by already-clean input is not
    proven, so these tests inject an over-claiming adapter through the same
    entry point the gate uses.
    """

    class _BaseLike:
        """Mimics ExecutorAcpAdapter: `resume` exists but is a degraded no-op."""

        executor = "fake-overclaimer"

        def __init__(self, supports: list[str]) -> None:
            self._supports = sorted(supports)

        def capabilities(self):
            return {"executor": self.executor, "supports": self._supports,
                    "launchable": False, "notes": []}

        def resume(self, *, session_id: str = ""):
            class R:
                status = "NOT_IMPLEMENTED"
                ok = False
            return R()

        def new(self, *, project_id: str = "", out_dir=None, source_session=None):
            class R:
                status = "NOT_LAUNCHABLE"
                ok = False
            return R()

        def prompt(self, *, session_id: str = "", text: str = ""):
            class R:
                status = "NOT_SUPPORTED"
                ok = False
            return R()

        def cancel(self, *, session_id: str = ""):
            class R:
                status = "NOT_SUPPORTED"
                ok = False
            return R()

        def fork(self, *, session_id: str = ""):
            class R:
                status = "NOT_SUPPORTED"
                ok = False
            return R()

    def _verify_with(self, adapter) -> tuple[int, str]:
        """Run the real verify() with the federation loader patched."""

        class FakeFederation:
            def __init__(self, a):
                self._a = a

            def executors(self):
                return [a.executor for a in self._a]

            def get(self, name):
                for a in self._a:
                    if a.executor == name:
                        return a
                return None

        original = ACP._load_federation
        ACP._load_federation = lambda root: type(
            "M", (), {"default_federation": staticmethod(lambda: FakeFederation([adapter]))}
        )
        import contextlib
        import io

        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                code = ACP.verify(ROOT)
        finally:
            ACP._load_federation = original
        return code, err.getvalue()

    def test_over_claimed_resume_is_detected(self) -> None:
        # The exact defect AG-06 fixed: advertise `resume` while resume() is the
        # base no-op, so `supports` reads as "this executor can be resumed".
        code, err = self._verify_with(self._BaseLike(["resume", "session"]))
        self.assertEqual(code, 1, "an over-claimed execution capability must fail closed")
        self.assertIn("DECLARED_CAPABILITY_WITHOUT_IMPLEMENTATION", err)

    def test_no_claim_passes(self) -> None:
        code, err = self._verify_with(self._BaseLike(["session"]))
        self.assertEqual(code, 0, err)

    def test_matrix_keeps_the_four_levels_separate(self) -> None:
        entry = ACP.build_matrix(self._BaseLike([]))
        row = entry["operations"]["new"]
        for key in ("declared", "implemented", "executable", "native_verified"):
            self.assertIn(key, row)
        # Overridden is not the same as executable: this is the whole point.
        self.assertTrue(row["implemented"])
        self.assertFalse(row["executable"])
        self.assertFalse(row["native_verified"])

    def test_declared_and_executable_are_not_conflated(self) -> None:
        entry = ACP.build_matrix(self._BaseLike(["resume"]))
        self.assertTrue(entry["operations"]["resume"]["declared"])
        self.assertFalse(entry["operations"]["resume"]["executable"])


if __name__ == "__main__":
    unittest.main()
