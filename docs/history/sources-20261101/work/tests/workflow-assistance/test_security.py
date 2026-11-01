"""Tests for the security plane (WL-300/310/320): the extension registry,
the 7-stage SkillSpector gate, and the Snyk second opinion.

Repo convention (mirrors test_task_governance.py): load each service file
by spec, pre-register in sys.modules under a stable name.  No external
scanner/sandbox is started — the tests drive the gates with synthetic
scanner/sandbox/approval inputs, which is exactly the shape WORK-LAB owns
and verifies; the external tools stay behind ch 35's register-and-recipe
rule.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEC = ROOT / "services" / "security"


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SEC / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class RegistryTests(unittest.TestCase):
    """WL-320: the registry WORK-LAB owns (ch 41), ch 35's eight fields."""

    def _reg(self):
        er = _load("extension_registry.py", "sec_er")
        return er, er.ExtensionRegistry()

    def _entry(self, er, name="acme-skill", etype="skill", version="1.0",
               hash_="sha256:abc", license_="Apache-2.0"):
        return er.ExtensionEntry(
            name=name, type=etype, canonical_url=f"https://github.com/x/{name}",
            version=version, commit="deadbeef", hash=hash_, license=license_,
            install_recipe="git clone + build", capability="prompt-tools")

    def test_idempotent_registration(self):
        er, reg = self._reg()
        e = self._entry(er)
        first = reg.register(e)
        # re-register an IDENTICAL entry -> no-op, same object
        same = self._entry(er)
        again = reg.register(same)
        self.assertIs(first, again)
        self.assertEqual(len(reg), 1)

    def test_drift_is_quarantined_not_overwritten(self):
        er, reg = self._reg()
        reg.register(self._entry(er, hash_="sha256:abc"))
        drifted = reg.register(self._entry(er, hash_="sha256:CHANGED"))
        self.assertTrue(drifted.quarantined)
        # the stored (original) entry is still what verify sees
        self.assertTrue(reg.get("acme-skill", "skill", "1.0").quarantined)
        self.assertIsNotNone(reg.last_error())

    def test_hash_verification_quarantines_mismatch(self):
        er, reg = self._reg()
        e = self._entry(er)
        reg.register(e)
        self.assertTrue(reg.verify_hash(e, "sha256:abc"))
        self.assertFalse(reg.verify_hash(e, "sha256:DIFFERENT"))
        self.assertTrue(e.quarantined)

    def test_manifest_is_the_eight_fields_only(self):
        er, reg = self._reg()
        reg.register(self._entry(er))
        manifest = reg.manifest()
        self.assertEqual(len(manifest), 1)
        keys = set(manifest[0].keys())
        expected = {"name", "canonical_url", "version", "commit", "hash",
                    "license", "install_recipe", "capability"}
        self.assertEqual(keys, expected)   # exactly ch 35's eight fields
        self.assertEqual(reg.list()[0].type, "skill")

    def test_unknown_type_is_rejected(self):
        er, reg = self._reg()
        with self.assertRaises(er.QuarantineError):
            reg.register(self._entry(er, etype="mystery"))


class SkillspectorGateTests(unittest.TestCase):
    """WL-300: the 7-stage pipeline, fail-closed at every stage."""

    def _gate(self, **kw):
        sg = _load("skillspector_gate.py", "sec_sg")
        return sg, sg.SkillspectorGate(**kw)

    def _ext(self, **over):
        er = _load("extension_registry.py", "sec_er")
        d = dict(name="acme", type="skill",
                 canonical_url="https://github.com/x/acme", version="1.0",
                 commit="c", hash="sha256:h", license="Apache-2.0",
                 install_recipe="r", capability="cap")
        d.update(over)
        return er.ExtensionEntry(**d)

    def test_contract_governed_types_agree_with_registry(self):
        # the gate is self-contained; assert its local type set matches the
        # registry's canonical five (ch 26) so the two never drift.
        sg = _load("skillspector_gate.py", "sec_sg")
        er = _load("extension_registry.py", "sec_er")
        self.assertEqual(set(sg._GOVERNED_TYPES), set(er.ExtensionType.ALL))

    def test_full_pass_requires_all_stages(self):
        sg, gate = self._gate()
        scanner = sg.ScannerResult(approved=True, findings=[])
        verdict = gate.evaluate(self._ext(), scanner=scanner,
                                sandbox_passed=True,
                                approval={"granted": True, "granted_by": "work-lab-gate"})
        self.assertTrue(verdict.allowed)
        self.assertEqual(verdict.stage_reached, "approval")
        int(verdict.receipt_sha256(), 16)   # deterministic receipt

    def test_missing_scanner_is_fail_closed(self):
        sg, gate = self._gate()
        verdict = gate.evaluate(self._ext(), scanner=None, sandbox_passed=True,
                                approval={"granted": True})
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.stage_reached, "hash")   # stopped before skillspector
        self.assertTrue(any("SkillSpector" in r for r in verdict.reasons))

    def test_unapproved_scanner_cannot_pass(self):
        sg, gate = self._gate()
        scanner = sg.ScannerResult(approved=False, findings=[])
        verdict = gate.evaluate(self._ext(), scanner=scanner,
                                sandbox_passed=True, approval={"granted": True})
        self.assertFalse(verdict.allowed)

    def test_blocking_finding_denies(self):
        sg, gate = self._gate()
        f = sg.Finding(category="data_exfiltration", severity="critical")
        scanner = sg.ScannerResult(approved=True, findings=[f])
        verdict = gate.evaluate(self._ext(), scanner=scanner,
                                sandbox_passed=True, approval={"granted": True})
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.stage_reached, "hash")

    def test_bad_license_denies(self):
        sg, gate = self._gate()
        verdict = gate.evaluate(self._ext(license="some-private-eula"),
                                scanner=sg.ScannerResult(approved=True))
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.stage_reached, "canonical_repo")

    def test_hash_mismatch_denies(self):
        sg, gate = self._gate()
        scanner = sg.ScannerResult(approved=True)
        verdict = gate.evaluate(self._ext(), scanner=scanner,
                                actual_hash="sha256:MOVED")
        self.assertFalse(verdict.allowed)
        self.assertEqual(verdict.stage_reached, "license")

    def test_scanner_cannot_grant_the_pass(self):
        # ch 41: the PASS authority is WORK-LAB, not the scanner.
        sg, gate = self._gate()
        scanner = sg.ScannerResult(approved=True)
        verdict = gate.evaluate(self._ext(), scanner=scanner, sandbox_passed=True,
                                approval={"granted": True, "granted_by": "SkillSpector"})
        self.assertFalse(verdict.allowed)
        self.assertTrue(any("WORK-LAB" in r or "scanner" in r for r in verdict.reasons))


class SnykSecondOpinionTests(unittest.TestCase):
    """WL-310: the two ch 27 isolation rules + honest absence."""

    def _snyk(self):
        sn = _load("snyk_second_opinion.py", "sec_sn")
        return sn, sn.SnykSecondOpinion(known_mcp={"trusted-mcp"})

    def _ext(self, **over):
        er = _load("extension_registry.py", "sec_er")
        d = dict(name="mystery-mcp", type="mcp", canonical_url="u", version="1")
        d.update(over)
        return er.ExtensionEntry(**d)

    def test_unknown_mcp_forces_isolation(self):
        sn, so = self._snyk()
        out = so.evaluate(self._ext(), gate_allows=True, snyk=sn.SnykResult.none())
        self.assertTrue(out.requires_isolation)
        self.assertEqual(out.relation, "absent")   # no snyk data -> absent, not clean

    def test_stdio_mcp_forbids_host_direct_scan(self):
        sn, so = self._snyk()
        ext = self._ext(name="stdio-mcp", capability="stdio transport")
        # snyk scanned it host-direct -> policy violation
        result = sn.SnykResult(available=True, mode=sn.ScanMode.HOST_DIRECT,
                               vulnerabilities=[])
        out = so.evaluate(ext, gate_allows=True, snyk=result)
        self.assertFalse(out.host_direct_allowed)
        self.assertEqual(out.relation, "disagrees")
        self.assertTrue(any("stdio" in r for r in out.reasons))

    def test_blocking_snyk_finding_disagrees_with_allow(self):
        sn, so = self._snyk()
        ext = self._ext(name="trusted-mcp", type="mcp")
        result = sn.SnykResult(available=True, mode=sn.ScanMode.ISOLATED,
                               vulnerabilities=[{"severity": "critical"}])
        out = so.evaluate(ext, gate_allows=True, snyk=result)
        self.assertEqual(out.relation, "disagrees")
        int(out.receipt_sha256(), 16)

    def test_clean_snyk_agrees_with_allow(self):
        sn, so = self._snyk()
        ext = self._ext(name="trusted-mcp", type="mcp")
        result = sn.SnykResult(available=True, mode=sn.ScanMode.ISOLATED,
                               vulnerabilities=[{"severity": "low"}])
        out = so.evaluate(ext, gate_allows=True, snyk=result)
        self.assertEqual(out.relation, "agrees")


if __name__ == "__main__":
    unittest.main(verbosity=2)
