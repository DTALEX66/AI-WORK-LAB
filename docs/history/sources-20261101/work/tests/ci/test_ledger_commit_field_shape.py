"""The ledger's commit fields hold commits or nothing — and the gate that says so is proven to fire.

85 of these fields had drifted to hand-typed 7-character abbreviations, one held prose, one held two
SHAs separated by a newline. `verify_error_ledger.py` accepted all of it, because until now it could not
be pointed at a synthetic ledger: my first "falsification" wrote a bad copy and the verifier read the good
one, so it passed and I nearly reported the rule as working. That is why `--ledger` exists and why this
test drives it with copies under the project's own run root.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LEDGER = REPO / "taskpacks" / "current" / "error-ledger.json"
VERIFY = REPO / "scripts" / "ci" / "verify_error_ledger.py"
EXPAND = REPO / "scripts" / "audit" / "expand_record_commit_shas.py"
WORKDIR = REPO / ".project-local" / "runs" / "qoder-20261007-a" / "sha-shape-falsify"


def verify(path: Path) -> tuple[int, str]:
    proc = subprocess.run([sys.executable, str(VERIFY), "--ledger", str(path)],
                          cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout + proc.stderr).strip()


class LedgerCommitFieldShape(unittest.TestCase):
    def mutated(self, name: str, error_id: str, field: str, value) -> Path:
        WORKDIR.mkdir(parents=True, exist_ok=True)
        target = WORKDIR / name
        shutil.copy(LEDGER, target)
        doc = json.loads(target.read_text(encoding="utf-8"))
        next(r for r in doc["errors"] if r["error_id"] == error_id)["lifecycle"][field] = value
        target.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    def tearDown(self) -> None:
        shutil.rmtree(WORKDIR, ignore_errors=True)

    def test_the_real_ledger_passes_and_the_rule_is_not_vacuous(self) -> None:
        code, out = verify(LEDGER)
        self.assertEqual(0, code, out)
        self.assertIn("ERROR_LEDGER_PASS", out)

    def test_an_abbreviated_commit_is_refused(self) -> None:
        code, out = verify(self.mutated("abbrev.json", "ERR-187", "fixedCommit", "98df72c"))
        self.assertEqual(1, code, "an abbreviated SHA slipped through")
        self.assertIn("must be a full 40-hex commit or null", out)

    def test_prose_in_a_commit_field_is_refused(self) -> None:
        code, out = verify(self.mutated("prose.json", "ERR-187", "introducedCommit", "not a commit"))
        self.assertEqual(1, code, "prose in a commit field passed")
        self.assertIn("introducedCommit", out)

    def test_null_remains_legal(self) -> None:
        """A record whose fix is not yet bound must still verify, or the rule pushes people to invent SHAs."""
        code, out = verify(self.mutated("null.json", "ERR-187", "verifiedCommit", None))
        self.assertEqual(0, code, out)

    def test_no_abbreviated_commit_survives_in_the_ledger(self) -> None:
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        offenders = [(r["error_id"], k, (r.get("lifecycle") or {}).get(k))
                     for r in doc["errors"]
                     for k in ("introducedCommit", "fixedCommit", "verifiedCommit")
                     if (r.get("lifecycle") or {}).get(k)
                     and not re_full_hex(str((r.get("lifecycle") or {}).get(k)))]
        self.assertEqual([], offenders)


def re_full_hex(value: str) -> bool:
    import re
    return bool(re.fullmatch(r"[0-9a-f]{40}", value))


class ExpanderReportsHonestCounts(unittest.TestCase):
    def test_the_expander_audits_without_writing_and_exits_clean(self) -> None:
        proc = subprocess.run([sys.executable, str(EXPAND)], cwd=REPO,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("COMMIT_SHA_AUDIT", proc.stdout)
        fields = dict(kv.split("=") for kv in proc.stdout.split()[1:])
        self.assertEqual("0", fields["expandable"],
                         "abbreviations remain that the expander can resolve")

    def test_check_mode_is_the_enforceable_form(self) -> None:
        proc = subprocess.run([sys.executable, str(EXPAND), "--check"], cwd=REPO,
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("COMMIT_SHA_CHECK_PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
