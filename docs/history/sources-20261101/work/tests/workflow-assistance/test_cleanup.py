"""Tests for the cleanup plane (WL-400/410/420/430): repo-slimming audit,
spill-cleanup governance, outdated-archive (ch 40 freeze list), and the
G01-G14 final audit.

Repo convention: load each service file by spec, pre-register in
sys.modules under a stable name.  The cleanup plane is read-only by
construction — no test may observe a deletion.  The repo-slimming auditor
is driven against a tiny synthetic tree (fast + deterministic) plus, in a
separate non-mutating test, the real WORK-LAB repo root to prove the four
ch 34 reports actually produce against it.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLEAN = ROOT / "services" / "cleanup"
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import project_temp  # noqa: E402


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, CLEAN / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class RepoSlimmingTests(unittest.TestCase):
    """WL-400: the four ch 34 reports, produced read-only."""

    def _synthetic_tree(self) -> str:
        # The auditor classifies by paths relative to the root it is handed (`_classify`,
        # `spill_report`), so an in-boundary fixture reports exactly what the system-temp root did.
        d = str(project_temp.fixture_dir(prefix="wlsim-"))
        Path(d, "node_modules/pkg/a.js").parent.mkdir(parents=True)
        Path(d, "node_modules/pkg/a.js").write_text("x" * 100)
        Path(d, "models").mkdir()
        Path(d, "models/thing.gguf").write_bytes(b"\0" * 2_000_000)  # 2MB
        Path(d, ".project-local", "logs").mkdir(parents=True)
        Path(d, ".project-local/logs/app.log").write_text("boot")
        Path(d, "src").mkdir()
        Path(d, "src/main.py").write_text("print('hi')")
        return d

    def test_four_reports_produce_against_synthetic_tree(self):
        rs = _load("repo_slimming.py", "cl_rs")
        d = self._synthetic_tree()
        a = rs.RepoSlimmingAuditor(d)
        recs = a.scan()
        self.assertTrue(recs)
        # each of the four ch 34 reports is a serialisable dict
        for rep in (a.repository_size(recs), a.largest_files(recs),
                   a.external_data(recs), a.spill_report(recs)):
            self.assertIsInstance(rep, dict)
            self.assertEqual(rep["schema"], "work-lab/repo-slimming/v1")
            json.dumps(rep)                      # must serialise
        # classification: the 2MB .gguf lands in models and is flagged
        ext = a.external_data(recs)
        flagged = [f["path"].replace(os.sep, "/") for f in ext["findings"]]
        self.assertTrue(any("models/thing.gguf" in p for p in flagged))
        # node_modules is flagged as regenerate
        self.assertTrue(any("node_modules" in p for p in flagged))
        # the .project-local log is NOT a spill (it is sanctioned)
        spills = [s["path"] for s in a.spill_report(recs)["spills"]]
        self.assertFalse(any(".project-local" in p for p in spills))

    def test_audit_to_files_writes_the_four_ch34_jsons(self):
        rs = _load("repo_slimming.py", "cl_rs")
        d = self._synthetic_tree()
        out = os.path.join(d, "out")
        written = rs.RepoSlimmingAuditor(d).audit_to_files(out)
        expected = {"repository-size.json", "largest-files.json",
                    "external-data.json", "spill-report.json"}
        self.assertEqual(set(os.path.basename(p) for p in written.values()), expected)
        for p in written.values():
            with open(p, encoding="utf-8") as fh:
                json.load(fh)                     # every file is valid JSON

    def test_real_repo_root_produces_all_four(self):
        # prove the auditor actually runs against the live WORK-LAB repo and
        # yields non-empty, serialisable reports (no mutation, read-only).
        rs = _load("repo_slimming.py", "cl_rs")
        a = rs.RepoSlimmingAuditor(str(ROOT))
        recs = a.scan()
        self.assertGreater(len(recs), 100)
        size = a.repository_size(recs)
        self.assertEqual(size["file_count"], len(recs))
        self.assertEqual(size["total_bytes"], sum(r.size for r in recs))
        for rep in (a.largest_files(recs), a.external_data(recs),
                   a.spill_report(recs)):
            json.dumps(rep)


class SpillGovernanceTests(unittest.TestCase):
    """WL-410: the four dispositions + the fail-closed credential rule."""

    def _gov(self, **kw):
        sc = _load("spill_cleanup.py", "cl_sc")
        return sc, sc.SpillGovernor(**kw)

    def test_sanctioned_root_is_kept(self):
        sc, gov = self._gov()
        d = gov.decide({"path": ".project-local/logs/app.log"})
        self.assertEqual(d.disposition, "keep_in_place")

    def test_global_state_db_is_blocked_fail_closed(self):
        sc, gov = self._gov()
        # a global Hermes state.db OUTSIDE the project must be BLOCKED, not
        # auto-migrated — this is the fail-closed rule the user's rules demand.
        d = gov.decide({"path": "C:/Users/ALOX/AppData/Local/hermes/state.db".lower()})
        self.assertEqual(d.disposition, "blocked")
        self.assertFalse(d.reversible)

    def test_project_local_state_db_is_kept_not_blocked(self):
        # the project-local copy under .project-local is sanctioned -> keep
        sc, gov = self._gov()
        d = gov.decide({"path": ".project-local/state.db"})
        self.assertEqual(d.disposition, "keep_in_place")

    def test_regenerable_needs_authorization_to_regenerate(self):
        sc, gov = self._gov()
        # without authorization: it is flagged, not auto-removed
        self.assertEqual(gov.decide({"path": "node_modules/pkg/x.js"}).disposition,
                         "migrate")
        # with authorization: proven regenerable
        gov2 = sc.SpillGovernor(user_authorized=["node_modules/pkg/x.js"])
        self.assertEqual(gov2.decide({"path": "node_modules/pkg/x.js"}).disposition,
                         "regenerate_ok")

    def test_govern_report_summary_and_receipt(self):
        sc, gov = self._gov()
        spills = [{"path": ".project-local/state.db"},
                 {"path": "C:/x/AppData/Local/hermes/state.db"},
                 {"path": "out/generated.bin"}]
        rep = gov.govern(spills)
        self.assertEqual(rep["decision_count"], 3)
        self.assertEqual(rep["summary"]["keep_in_place"], 1)
        self.assertEqual(rep["summary"]["blocked"], 1)
        self.assertEqual(rep["summary"]["migrate"], 1)
        int(sc.SpillGovernor.report_receipt_sha256(rep), 16)


class OutdatedArchiveTests(unittest.TestCase):
    """WL-420: ch 40's ten frozen surfaces -> the five owned forms."""

    def _arch(self, **kw):
        oa = _load("outdated_archive.py", "cl_oa")
        return oa, oa.OutdatedArchiver(**kw)

    def test_ten_frozen_surfaces_defined(self):
        oa, _ = self._arch()
        self.assertEqual(len(oa.FROZEN_SURFACES), 10)
        # every redirect is one of ch 40's five owned forms
        five = {"Adapter", "Provider", "Protocol", "Policy", "Registry"}
        for redirect in oa.FROZEN_SURFACES.values():
            self.assertIn(redirect, five)

    def test_frozen_surface_maps_to_keep_as_adapter_by_default(self):
        oa, arch = self._arch()
        d = arch.decide("components/generic-agent-runtime/runtime.py")
        self.assertEqual(d.surface, "generic-agent-runtime")
        self.assertEqual(d.redirect, "Adapter")
        self.assertEqual(d.disposition, "keep_as_adapter")
        self.assertTrue(d.reversible)

    def test_authorized_frozen_surface_may_migrate_then_delete(self):
        oa, arch = self._arch(user_authorized=["components/generic-memory-db/db.py"])
        d = arch.decide("components/generic-memory-db/db.py")
        self.assertEqual(d.disposition, "migrate_then_delete")

    def test_unknown_path_is_kept_not_assumed_frozen(self):
        oa, arch = self._arch()
        d = arch.decide("src/core/service.py")
        self.assertEqual(d.surface, "generic")
        self.assertEqual(d.disposition, "keep")

    def test_archive_report_receipt_is_deterministic(self):
        oa, arch = self._arch()
        rep = arch.archive(["components/generic-model-sdk/sdk.py"])
        self.assertEqual(rep["frozen_found"], 1)
        self.assertEqual(oa.OutdatedArchiver.receipt_sha256(rep),
                         oa.OutdatedArchiver.receipt_sha256(rep))


class FinalAuditTests(unittest.TestCase):
    """WL-430: G01-G14 — a single non-PASS gate forbids promotion."""

    def _fa(self, **kw):
        fa = _load("final_audit.py", "cl_fa")
        return fa, fa.FinalAudit(**kw)

    def test_fourteen_gates_defined(self):
        fa, _ = self._fa()
        self.assertEqual(len(fa.Gate.ALL), 14)
        self.assertEqual(fa.Gate._COUNT, 14)

    def test_missing_evidence_is_pending_never_pass(self):
        fa, audit = self._fa()
        rep = audit.run()
        # no evidence supplied -> every gate is PENDING, promotion forbidden
        self.assertEqual(rep["pending"], sorted([g[0] for g in fa.Gate.ALL]))
        self.assertFalse(rep["all_pass"])
        self.assertFalse(rep["promotion_allowed"])

    def test_single_fail_forbids_promotion(self):
        fa, _ = self._fa()
        ev = fa.all_pass_evidence()
        ev["G04"] = {"pass": False, "note": "secret scan flagged a token"}
        audit = fa.FinalAudit(ev)
        rep = audit.run()
        self.assertIn("G04", rep["failed"])
        self.assertFalse(rep["promotion_allowed"])

    def test_fourteen_passes_allow_promotion(self):
        fa, _ = self._fa()
        audit = fa.FinalAudit(fa.all_pass_evidence())
        rep = audit.run()
        self.assertEqual(rep["pass_count"], 14)
        self.assertTrue(rep["all_pass"])
        self.assertTrue(rep["promotion_allowed"])
        int(audit.receipt_sha256(rep), 16)


if __name__ == "__main__":
    unittest.main(verbosity=2)
