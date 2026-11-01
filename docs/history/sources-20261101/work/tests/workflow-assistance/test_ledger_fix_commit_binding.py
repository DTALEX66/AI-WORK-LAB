"""Gate: an error record that says "fixed" must name the commit, and the named commit must prove it.

`fixedCommit` is the difference between an auditable trail and a diary. Three properties hold here:

1. every bound record's commit exists, contains the file its own `lifecycle.regressionCommand`
   promises to run, and any `verifiedCommit` is a descendant that also contains it;
2. the owed set — PASS records with no fixedCommit — is pinned by the audit, so the gap is visible and
   can only shrink; a new unbound PASS record that the audit does not list fails;
3. no PASS record dated after 2026-10-07 may be created unbound at all.

The rule is applied narrowly on purpose. Earlier sessions fixed defects inside broader commits whose
messages do not cite the ERR id, and 99 such records stay legitimately owed; inventing a SHA for them
would be the exact defect ERR-125 and ERR-134 record, so they are listed instead of guessed.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "taskpacks/current/error-ledger.json"
AUDIT = ROOT / "docs" / "audits" / "LEDGER_FIX_COMMIT_BINDING_2026-10-07.json"
CD_RE = re.compile(r"^(?:cd\s+(?P<dir>[^\s&]+)\s*(?:&&|;)\s*)?(?P<cmd>.*)$")
BINDING_CUTOFF = "2026-10-07"


def git(*args: str) -> int:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True).returncode


def promise_script(command: str) -> str | None:
    m = CD_RE.match((command or "").strip())
    body = (m.group("cmd") if m else command or "").strip()
    try:
        argv = shlex.split(body)
    except ValueError:
        return None
    for token in argv:
        if token.endswith((".py", ".mjs", ".sh")) and "/" in token and not token.startswith("python"):
            return token
    return None


def violations(errors: list[dict], owed_ids: set[str]) -> list[str]:
    out = []
    actual_owed = set()
    for e in errors:
        lc = e.get("lifecycle") or {}
        fix, verified = lc.get("fixedCommit"), lc.get("verifiedCommit")
        script = promise_script(lc.get("regressionCommand") or "")
        eid = e["error_id"]
        if not fix:
            if e.get("status_after") == "PASS":
                actual_owed.add(eid)
                if (e.get("date") or "") > BINDING_CUTOFF:
                    out.append(f"{eid}: PASS dated {e.get('date')} with no fixedCommit")
            continue
        if git("cat-file", "-e", f"{fix}^{{commit}}") != 0:
            out.append(f"{eid}: fixedCommit {fix} is not a commit")
            continue
        if script and not script.startswith(".project-local/") \
                and git("cat-file", "-e", f"{fix}:{script}") != 0:
            out.append(f"{eid}: promised {script} is absent from {fix}")
        if verified:
            if git("cat-file", "-e", f"{verified}^{{commit}}") != 0:
                out.append(f"{eid}: verifiedCommit {verified} is not a commit")
            elif git("merge-base", "--is-ancestor", fix, verified) != 0:
                out.append(f"{eid}: {fix} is not an ancestor of verifiedCommit {verified}")
    unlisted = sorted(actual_owed - owed_ids)
    stale = sorted(owed_ids - actual_owed)
    if unlisted:
        out.append(f"PASS records unbound and absent from the owed list: {unlisted}")
    if stale:
        out.append(f"owed list names records that are no longer unbound: {stale}")
    return out


class LedgerFixCommitBindingGate(unittest.TestCase):
    def setUp(self) -> None:
        self.errors = json.loads(LEDGER.read_text(encoding="utf-8"))["errors"]
        self.audit = json.loads(AUDIT.read_text(encoding="utf-8"))
        self.owed = {o["id"] for o in self.audit["unboundPassRecords"]}

    def test_the_shipped_bindings_are_valid(self) -> None:
        self.assertEqual(violations(self.errors, self.owed), [])

    def test_the_audit_reports_no_anomalies(self) -> None:
        self.assertEqual(self.audit["anomalies"], [])
        self.assertGreaterEqual(self.audit["counts"]["bound"], 20)

    def test_binding_covers_every_record_this_round_touched(self) -> None:
        for eid in ("ERR-131", "ERR-132", "ERR-133", "ERR-134", "ERR-135", "ERR-136", "ERR-137"):
            entry = next(e for e in self.errors if e["error_id"] == eid)
            lc = entry.get("lifecycle") or {}
            self.assertTrue(lc.get("fixedCommit"), f"{eid} must name its fix commit")
            self.assertTrue(lc.get("bindingNote"), f"{eid} must say how the binding was justified")

    def test_an_unverified_fix_does_not_claim_verification(self) -> None:
        for e in self.errors:
            lc = e.get("lifecycle") or {}
            if not lc.get("verifiedCommit"):
                continue
            self.assertEqual(git("cat-file", "-e", f"{lc['verifiedCommit']}^{{commit}}"), 0,
                             f"{e['error_id']} names a commit that does not exist")

    def test_the_owed_list_states_a_reason_for_every_entry(self) -> None:
        for o in self.audit["unboundPassRecords"]:
            self.assertTrue((o.get("reason") or o.get("why") or "").strip(),
                            f"{o['id']} is owed without a stated reason")

    # ---------------- negative controls
    def _clone(self):
        return json.loads(json.dumps(self.errors))

    def test_an_unbound_pass_record_hidden_from_the_owed_list_is_refused(self) -> None:
        errors = self._clone()
        for e in errors:
            if (e.get("lifecycle") or {}).get("fixedCommit"):
                e["lifecycle"]["fixedCommit"] = None
                e["status_after"] = "PASS"
                e["date"] = "2026-10-07"
                break
        found = violations(errors, self.owed)
        self.assertTrue(any("absent from the owed list" in v or "no fixedCommit" in v
                            for v in found), found)

    def test_a_bogus_fix_commit_is_refused(self) -> None:
        errors = self._clone()
        next(e for e in errors if (e.get("lifecycle") or {}).get("fixedCommit"))["lifecycle"][
            "fixedCommit"] = "deadbeef"
        self.assertTrue(any("not a commit" in v
                            for v in violations(errors, self.owed)))

    def test_a_fix_commit_without_the_promised_file_is_refused(self) -> None:
        errors = self._clone()
        e = next(x for x in errors
                 if (x.get("lifecycle") or {}).get("fixedCommit")
                 and promise_script((x["lifecycle"] or {}).get("regressionCommand") or ""))
        e["lifecycle"]["regressionCommand"] = "python tests/ci/test_never_existed.py"
        self.assertTrue(any("absent from" in v for v in violations(errors, self.owed)))

    def test_a_verified_commit_that_predates_the_fix_is_refused(self) -> None:
        errors = self._clone()
        e = next(x for x in errors if (x.get("lifecycle") or {}).get("verifiedCommit"))
        e["lifecycle"]["verifiedCommit"] = e["lifecycle"]["fixedCommit"]
        e["lifecycle"]["fixedCommit"] = "0000000"
        self.assertTrue(any("not a commit" in v for v in violations(errors, self.owed)))

    def test_a_stale_owed_entry_is_refused(self) -> None:
        bound = next(e["error_id"] for e in self.errors
                     if (e.get("lifecycle") or {}).get("fixedCommit"))
        self.assertTrue(any("no longer unbound" in v
                            for v in violations(self.errors, self.owed | {bound})))


if __name__ == "__main__":
    unittest.main(verbosity=2)
