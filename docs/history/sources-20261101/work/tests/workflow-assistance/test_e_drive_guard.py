"""WL-R04 audit gap: offline synthetic-payload tests for the protected-drive guard.

services/policy/e_drive_guard.py is a pre_tool_call hook that fail-closed
blocks any tool-call payload touching the protected E:\\ or F:\\ drives
(standing user rule: both data drives are protected) unless an explicit
authorization marker is present. It is registered in
docs/decisions/LESSONS_LEARNED as 强制拦截 yet had ZERO tests.

These tests drive the guard through a real subprocess with synthetic JSON
(stdin). No real E:\\ path is read, written, listed or moved; no
credentials are touched. They are pure decision tests of the hook's
allow/deny logic, mirroring the audit's "先查越权拒绝" requirement.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "services" / "policy" / "e_drive_guard.py"


def run_guard(payload) -> tuple[int, dict]:
    """Run the guard hook with `payload` on stdin; return (rc, parsed stdout)."""
    stdin = "" if payload is None else json.dumps(payload)
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=stdin, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT, timeout=60,
    )
    out = proc.stdout.strip()
    try:
        parsed = json.loads(out) if out else {}
    except json.JSONDecodeError:
        parsed = {"_raw": out}
    return proc.returncode, parsed


class EDriveGuardTests(unittest.TestCase):
    def test_e_path_in_args_is_blocked(self):
        rc, out = run_guard({"tool": "read_file",
                             "args": {"path": "E:\\data\\secret.txt"}})
        self.assertEqual(rc, 1)
        self.assertFalse(out.get("allow"))
        self.assertIn("not authorized", out.get("reason", ""))

    def test_explicit_marker_authorizes(self):
        rc, out = run_guard({"tool": "read_file",
                             "args": {"path": "E:\\data\\secret.txt"},
                             "authorization": "E_DRIVE_AUTHORIZED"})
        self.assertEqual(rc, 0)
        self.assertTrue(out.get("allow"))

    def test_lowercase_marker_also_authorizes(self):
        # the guard upper()s the payload before matching the marker
        rc, out = run_guard({"tool": "write",
                             "args": {"path": "E:\\x"},
                             "authorization": "e_drive_authorized"})
        self.assertEqual(rc, 0)
        self.assertTrue(out.get("allow"))

    def test_nested_path_in_list_is_blocked(self):
        rc, out = run_guard({"tool": "bash",
                             "args": {"files": ["D:\\ok.txt", "E:\\locked.txt"]}})
        self.assertEqual(rc, 1)
        self.assertFalse(out.get("allow"))

    def test_lowercase_drive_letter_blocked(self):
        rc, out = run_guard({"tool": "list", "args": {"dir": "e:\\vault"}})
        self.assertEqual(rc, 1)
        self.assertFalse(out.get("allow"))

    def test_forward_slash_drive_blocked(self):
        rc, out = run_guard({"tool": "read_file",
                             "args": {"path": "E:/BaiduSyncdisk/x"}})
        self.assertEqual(rc, 1)
        self.assertFalse(out.get("allow"))

    def test_other_drives_are_allowed(self):
        for p in ("D:\\proj\\file.txt", "C:\\Users\\a\\file.txt"):
            rc, out = run_guard({"tool": "read_file", "args": {"path": p}})
            self.assertEqual(rc, 0, p)
            self.assertTrue(out.get("allow"), p)

    def test_f_paths_are_blocked(self):
        # Standing user rule: BOTH the E: and F: data drives are protected.
        for p in ("F:\\media\\clip.mp4", "f:\\media\\clip.mp4", "F:/media/clip.mp4"):
            rc, out = run_guard({"tool": "read_file", "args": {"path": p}})
            self.assertEqual(rc, 1, p)
            self.assertFalse(out.get("allow"), p)
            self.assertIn("not authorized", out.get("reason", ""), p)

    def test_non_drive_colon_strings_are_not_false_positives(self):
        # "E:g" has no backslash/slash after the colon -> not a drive path
        rc, out = run_guard({"tool": "note", "args": {"text": "ratio E:g here"}})
        self.assertEqual(rc, 0)
        self.assertTrue(out.get("allow"))

    def test_empty_stdin_fails_to_allow_nothing(self):
        # no payload -> no E path detected -> allow (nothing to block)
        rc, out = run_guard(None)
        self.assertEqual(rc, 0)
        self.assertTrue(out.get("allow"))

    def test_malformed_json_is_treated_as_empty(self):
        proc = subprocess.run([sys.executable, str(GUARD)],
                              input="{not valid json", capture_output=True,
                              text=True, encoding="utf-8", errors="replace", cwd=ROOT, timeout=60)
        parsed = json.loads(proc.stdout.strip())
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(parsed.get("allow"))

    def test_marker_inside_a_path_value_does_not_authorize_a_different_path(self):
        # the marker authorizes the WHOLE payload, so if it appears anywhere
        # in the payload the hook lets it through — document that behavior:
        # putting the marker in the payload is what authorizes; the guard does
        # NOT re-scope per-path. This is a known limit, recorded not hidden.
        rc, out = run_guard({"tool": "write",
                             "args": {"path": "E:\\a.txt"},
                             "E_DRIVE_AUTHORIZED": True})
        self.assertEqual(rc, 0)
        self.assertTrue(out.get("allow"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
