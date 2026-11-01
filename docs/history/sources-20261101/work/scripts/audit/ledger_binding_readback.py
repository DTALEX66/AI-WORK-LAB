"""Record the ledger's fix-commit bindings, and name the PASS entries that still have none.

`fixedCommit` is what makes an error record auditable: without it, "fixed" is a claim about a past
session. Binding is checked against the tree, not typed in — the promised script must exist in the
named commit.

The honest part is the second list. 28 records carry today's date and 21 of them predate this round's
discipline; their fixes are real but I cannot name the commit for each one from evidence I have in
hand, and inventing a SHA is exactly what ERR-125/ERR-134 exist to forbid. So they are listed as an
owed set, and the gate requires that set to match the ledger exactly: the gap stays visible and can
only shrink, never silently grow.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LED = REPO / "taskpacks/current/error-ledger.json"
OUT = REPO / "docs/audits/LEDGER_FIX_COMMIT_BINDING_2026-10-07.json"
CD_RE = re.compile(r"^(?:cd\s+(?P<dir>[^\s&]+)\s*(?:&&|;)\s*)?(?P<cmd>.*)$")


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def promise_script(command: str) -> str | None:
    m = CD_RE.match((command or "").strip())
    body = (m.group("cmd") if m else command or "").strip()
    try:
        argv = shlex.split(body)
    except ValueError:
        return None
    for token in argv:
        if token.endswith((".py", ".mjs", ".sh")) and "/" in token:
            return token
    return None


def in_tree(sha: str, rel: str) -> bool:
    return git("cat-file", "-e", f"{sha}:{rel}").returncode == 0


def main() -> int:
    errors = json.loads(LED.read_text(encoding="utf-8"))["errors"]
    bound, unbound_pass, anomalies = [], [], []
    for e in errors:
        lc = e.get("lifecycle") or {}
        fix, verified = lc.get("fixedCommit"), lc.get("verifiedCommit")
        script = promise_script(lc.get("regressionCommand") or "")
        if not fix:
            if e.get("status_after") == "PASS":
                unbound_pass.append({"id": e["error_id"], "date": e.get("date"),
                                     "promise": script,
                                     "reason": "fixed by an earlier session; the commit is not "
                                               "established by evidence in hand, and inventing a SHA "
                                               "is what ERR-125/ERR-134 forbid"})
            continue
        is_commit = git("cat-file", "-e", f"{fix}^{{commit}}").returncode == 0
        if not is_commit:
            anomalies.append(f"{e['error_id']}: fixedCommit {fix} is not a commit")
            continue
        promise_ok = (script is None or script.startswith(".project-local/")
                      or in_tree(fix, script))
        if not promise_ok:
            anomalies.append(f"{e['error_id']}: promised {script} is absent from {fix}")
        verified_ok = True
        if verified:
            verified_ok = git("cat-file", "-e", f"{verified}^{{commit}}").returncode == 0
            if verified_ok and script and not script.startswith(".project-local/"):
                verified_ok = in_tree(verified, script)
            if verified_ok:
                anc = git("merge-base", "--is-ancestor", fix, verified).returncode
                if anc != 0:
                    anomalies.append(f"{e['error_id']}: {fix} is not an ancestor of "
                                     f"verifiedCommit {verified}")
        bound.append({"id": e["error_id"], "statusAfter": e.get("status_after"),
                      "fixedCommit": fix, "verifiedCommit": verified,
                      "promise": script, "promisePresentInFixTree": promise_ok,
                      "verifiedTreeChecked": bool(verified and verified_ok),
                      "bindingNotePresent": bool(lc.get("bindingNote"))})

    doc = {
        "schemaVersion": "work-lab/ledger-fix-commit-binding/v1",
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "generatedBy": "scripts/audit/ledger_binding_readback.py",
        "rules": {
            "fixedCommit": "must be a real commit and must contain the file the entry's own "
                           "lifecycle.regressionCommand promises to run",
            "verifiedCommit": "must be a real commit that descends from fixedCommit; it names the "
                              "head whose exact-SHA Actions readback came back green",
            "null": "an unverified fix stays null, and a PASS record with no fixedCommit is listed "
                    "as owed rather than left silently unbound",
        },
        "counts": {"bound": len(bound), "unboundPassRecords": len(unbound_pass),
                   "anomalies": len(anomalies)},
        "bound": bound,
        "unboundPassRecords": unbound_pass,
        "anomalies": anomalies,
    }
    OUT.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode())
    back = json.loads(OUT.read_text(encoding="utf-8"))
    assert back["counts"]["bound"] == len(bound)
    print(f"bound={len(bound)} unboundPass={len(unbound_pass)} anomalies={len(anomalies)}")
    for b in bound:
        print(f"  {b['id']}: fixed={b['fixedCommit']} verified={b['verifiedCommit'] or 'PENDING'} "
              f"promiseInTree={b['promisePresentInFixTree']}")
    for a in anomalies:
        print(f"  ANOMALY {a}")
    print(f"report -> {OUT.relative_to(REPO).as_posix()} ({OUT.stat().st_size} bytes)")
    return 1 if anomalies else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
