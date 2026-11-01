"""Negative controls for the AG-05 registry field-closure report.

The Atlas closed gap G05 with the wording "close it field by field". The closure
report is the aggregate answer to that, so it must be trustworthy in both
directions: it has to notice a genuine hole, and it has to distinguish a
legitimate explicit-null-with-reason from a hole. A report that never reports
anything is worthless; a report that reports everything is ignored.

Synthetic registry fixtures only. No model asset is read, no runtime started, no
network call.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "scripts" / "ci" / "report_registry_closure.py"


def _load():
    spec = importlib.util.spec_from_file_location("ag05_closure_report", SPEC)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


C = _load()


def _valid() -> tuple[list[dict], dict, dict]:
    providers = {
        "providers": [
            {"id": "p.ok", "binds_to_model": "m.ok", "binds_to_runtime": "rt",
             "binding_status": "SERVED", "binding_status_source": "model.status"},
            {"id": "p.unserved", "binds_to_model": "m.retired",
             "binds_to_runtime": "rt",
             "binding_status": "UNSERVED_RETAINED_PENDING_DECISION",
             "binding_status_source": "model.status",
             "operationalStatus": "runtime endpoint scope only"},
        ]
    }
    models = {
        "models": [
            {"id": "m.ok", "sha256": "a" * 64, "runtime_id": "rt", "status": "active",
             "last_verified": "2026-09-29"},
            {"id": "m.retired", "sha256": None, "runtime_id": None,
             "status": "RETIRED_PENDING_DECISION", "last_verified": None,
             "retirement_note": "retained in place, not served",
             "assetDigest": {"state": "TRUNCATED", "prefix": "aa",
                             "reason": "only a prefix survives"}},
        ],
        "candidateOrphans": [
            {"path": "x.gguf", "sha256": None,
             "assetDigest": {"state": "TRUNCATED", "prefix": "bb", "reason": "residue"}},
        ],
    }
    runtimes = {
        "runtimes": [{"id": "rt"}],
        "processLibraries": [
            {"id": "plib", "executionModel": "in-process", "health_state": "UNKNOWN",
             "probe_note": "presence checked, quality not"},
        ],
    }
    return providers, models, runtimes


def _write(root: Path, providers, models, runtimes) -> None:
    base = root / ".project" / "governance"
    base.mkdir(parents=True, exist_ok=True)
    (base / "provider-registry.json").write_text(json.dumps(providers), encoding="utf-8")
    (base / "model-registry.json").write_text(json.dumps(models), encoding="utf-8")
    (base / "runtime-registry.json").write_text(json.dumps(runtimes), encoding="utf-8")


class ClosureReportNegativeControls(unittest.TestCase):
    def _report(self, providers, models, runtimes):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, providers, models, runtimes)
            return C.build_report(root).as_dict()

    def test_clean_fixture_has_no_unclosed_fields(self) -> None:
        rep = self._report(*_valid())
        self.assertEqual(rep["unclosed"], [], rep["unclosed"])

    def test_dangling_provider_model_reference_is_unclosed(self) -> None:
        p, m, r = _valid()
        p["providers"][0]["binds_to_model"] = "does-not-exist"
        rep = self._report(p, m, r)
        self.assertTrue(any(i["field"] == "binds_to_model" for i in rep["unclosed"]))

    def test_dangling_runtime_reference_is_unclosed(self) -> None:
        p, m, r = _valid()
        p["providers"][0]["binds_to_runtime"] = "ghost"
        rep = self._report(p, m, r)
        self.assertTrue(any(i["field"] == "binds_to_runtime" for i in rep["unclosed"]))

    def test_binding_status_without_source_is_unclosed(self) -> None:
        p, m, r = _valid()
        del p["providers"][1]["binding_status_source"]
        rep = self._report(p, m, r)
        self.assertTrue(any(i["field"] == "binding_status_source" for i in rep["unclosed"]))

    def test_prose_sha256_is_unclosed(self) -> None:
        p, m, r = _valid()
        m["models"][0]["sha256"] = "a18ae2a5f553fe02 (model.bin)"
        rep = self._report(p, m, r)
        self.assertTrue(any(i["field"] == "sha256" for i in rep["unclosed"]))

    def test_missing_runtime_id_is_unclosed_for_an_active_model(self) -> None:
        p, m, r = _valid()
        del m["models"][0]["runtime_id"]
        rep = self._report(p, m, r)
        self.assertTrue(any(i["field"] == "runtime_id" for i in rep["unclosed"]))

    def test_null_runtime_id_on_a_retired_model_is_explicitly_open(self) -> None:
        rep = self._report(*_valid())
        opens = [i for i in rep["explicitly_open"] if i["field"] == "runtime_id"]
        self.assertTrue(opens)
        self.assertTrue(all(i["reason"] for i in opens))

    def test_missing_last_verified_with_a_reason_is_explicitly_open(self) -> None:
        rep = self._report(*_valid())
        opens = [i for i in rep["explicitly_open"] if i["field"] == "last_verified"]
        self.assertTrue(opens)

    def test_missing_last_verified_without_a_reason_is_unclosed(self) -> None:
        p, m, r = _valid()
        m["models"][1].pop("retirement_note", None)
        m["models"][1].pop("assetDigest", None)
        rep = self._report(p, m, r)
        self.assertTrue(any(i["field"] == "last_verified" for i in rep["unclosed"]))

    def test_orphan_prose_digest_is_unclosed(self) -> None:
        p, m, r = _valid()
        m["candidateOrphans"] = [{"path": "y.gguf", "sha256": "deadbeefdeadbeef"}]
        rep = self._report(p, m, r)
        self.assertTrue(any(i["field"] == "sha256" for i in rep["unclosed"]))

    def test_process_library_without_execution_model_is_unclosed(self) -> None:
        p, m, r = _valid()
        del r["processLibraries"][0]["executionModel"]
        rep = self._report(p, m, r)
        self.assertTrue(any(i["field"] == "executionModel" for i in rep["unclosed"]))

    def test_counts_match_the_classified_lists(self) -> None:
        rep = self._report(*_valid())
        self.assertEqual(rep["counts"]["closed"], len(rep["closed"]))
        self.assertEqual(rep["counts"]["explicitly_open"], len(rep["explicitly_open"]))
        self.assertEqual(rep["counts"]["unclosed"], len(rep["unclosed"]))

    def test_every_entry_carries_a_where_and_field(self) -> None:
        rep = self._report(*_valid())
        for bucket in ("closed", "explicitly_open", "unclosed"):
            for item in rep[bucket]:
                self.assertTrue(item.get("where"), bucket)
                self.assertTrue(item.get("field"), bucket)

    def test_missing_registry_is_an_environment_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(C.verify(Path(tmp)), 2)

    def test_live_registries_classify_without_unclosed_fields(self) -> None:
        # The real repository must currently be fully classified: every null is
        # either closed or carries a stated reason. If this fails, a new hole was
        # introduced and the closure report is telling the truth about it.
        rep = C.build_report(ROOT).as_dict()
        self.assertEqual(rep["unclosed"], [], rep["unclosed"])
        self.assertGreater(rep["counts"]["closed"], 0)
        self.assertGreater(rep["counts"]["explicitly_open"], 0)


if __name__ == "__main__":
    unittest.main()
