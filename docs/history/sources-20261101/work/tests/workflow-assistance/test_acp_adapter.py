"""NX-200: ACP compatibility layer tests.

RED-GREEN coverage:
- init on supported version is OK and not degraded.
- unknown protocol version degrades gracefully (fail closed, falls back).
- unsupported feature negotiates as unsupported (graceful, no crash).
- read-only operations never trigger approval.
- mutation plan/apply requires explicit approval (fail closed).
- Qwen Code pilot returns unavailable when not installed (never project-fails).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]  # WORK-LAB root
sys.path.insert(0, str(ROOT / 'integrations/executors/codex'))
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from acp_adapter import (  # noqa: E402
    CLIENT_CAPABILITIES, build_adapter, make_qwen_code_pilot,
)


class AcpAdapterTest(unittest.TestCase):
    def test_init_supported_version_ok_not_degraded(self) -> None:
        a = build_adapter("hermes")
        r = a.init()
        self.assertEqual(r["status"], "OK")
        self.assertFalse(r["degraded"])

    def test_unknown_protocol_version_degrades_gracefully(self) -> None:
        a = build_adapter("hermes")
        r = a.init(requested_version="99.0.0")
        self.assertEqual(r["status"], "OK")
        self.assertTrue(r["degraded"])
        self.assertIn(r["protocol_version"], ("0.1.0",))

    def test_unsupported_feature_negotiates_as_unsupported(self) -> None:
        a = build_adapter("codex")
        r = a.negotiate(["detect", "teleport", "observe"])
        self.assertEqual(r["status"], "OK")
        self.assertIn("teleport", r["unsupported"])
        self.assertTrue(r["degraded"])

    def test_all_read_only_ops_no_approval(self) -> None:
        for client in CLIENT_CAPABILITIES:
            a = build_adapter(client)
            if not a.installed:
                continue
            for op in ("detect", "capabilities", "observe"):
                fn = getattr(a, op)
                r = fn({}) if op in ("detect", "observe") else fn()
                self.assertIn(r["status"], {"OK", "UNAVAILABLE"})

    def test_mutation_plan_requires_approval(self) -> None:
        a = build_adapter("hermes")
        plan = a.plan({"run_id": "r1", "external_mutation": True})
        self.assertEqual(plan["status"], "WAITING_APPROVAL")
        self.assertTrue(plan["approval"]["required"])
        with self.assertRaises(PermissionError):
            a.apply(plan)  # not approved -> fail closed

    def test_mutation_apply_after_approval_ok(self) -> None:
        a = build_adapter("hermes")
        plan = a.plan({"run_id": "r1", "external_mutation": True})
        plan["approval"]["status"] = "APPROVED"
        r = a.apply(plan)
        self.assertEqual(r["status"], "APPLIED")

    def test_qwen_pilot_unavailable_when_not_installed(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            a = make_qwen_code_pilot()
        r = a.capabilities()
        self.assertEqual(r["status"], "UNAVAILABLE")

    def test_qwen_pilot_available_when_installed(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/qwen-code"):
            a = make_qwen_code_pilot()
        r = a.capabilities()
        self.assertEqual(r["status"], "OK")
        self.assertEqual(r["adapter_id"], "qwen-code")

    def test_unknown_client_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_adapter("no-such-client")


if __name__ == "__main__":
    unittest.main()
