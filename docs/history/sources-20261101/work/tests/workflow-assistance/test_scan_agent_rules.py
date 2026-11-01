from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCANNER = ROOT / "packages/client-neutral-core/scripts/security/scan_agent_rules.py"


def run_scanner(text: str) -> subprocess.CompletedProcess[str]:
    return run_scanner_bytes(text.encode("utf-8"), "sample.md")


def run_scanner_bytes(raw: bytes, name: str = "sample.md") -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as raw_dir:
        sample = Path(raw_dir) / name
        sample.write_bytes(raw)
        return subprocess.run(
            [sys.executable, str(SCANNER), str(sample)],
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
            check=False,
        )


class ScanAgentRulesTests(unittest.TestCase):
    def test_bare_upstream_shorthand_is_flagged(self) -> None:
        result = run_scanner("git rev-parse @{upstream}\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unquoted @-brace git revision shorthand", result.stdout)

    def test_bare_reflog_forms_are_flagged(self) -> None:
        result = run_scanner("git log -1 @{-1}\ngit show @{1}\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout.count("unquoted @-brace"), 2)

    def test_single_quoted_shorthand_is_clean(self) -> None:
        result = run_scanner(
            "git rev-parse '@{upstream}'\ngit log -1 '@{u}'\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_double_quoted_shorthand_is_clean(self) -> None:
        result = run_scanner('Write-Output "@{upstream}"\n')
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_explicit_refs_and_powershell_hashtables_are_clean(self) -> None:
        result = run_scanner(
            "git rev-parse origin/main\n"
            "git rev-parse HEAD\n"
            "$env:ENV = @{ name = 'x' }\n"
            "$x = @{key = 1; other = 2}\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_crlf_shell_script_is_flagged(self) -> None:
        result = run_scanner_bytes(b"#!/bin/sh\r\necho hi\r\n", "sample.sh")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CRLF line endings", result.stdout)

    def test_lf_shell_script_is_clean(self) -> None:
        result = run_scanner_bytes(b"#!/bin/sh\necho hi\n", "sample.sh")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_powershell_remove_item_without_literal_path_and_stop_is_flagged(self) -> None:
        result = run_scanner_bytes(
            b"Remove-Item $target -Recurse -Force\n",
            "cleanup.ps1",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe PowerShell cleanup", result.stdout)

    def test_powershell_remove_item_with_literal_path_and_stop_is_clean(self) -> None:
        result = run_scanner_bytes(
            b"Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction Stop\n"
            b"if (Test-Path -LiteralPath $target) { throw 'cleanup postcondition failed' }\n",
            "cleanup.ps1",
        )
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
