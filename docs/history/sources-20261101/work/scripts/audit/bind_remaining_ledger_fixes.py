"""Bind remaining PASS records to the commit whose message names them — only when the tree agrees.

The rule is deliberately narrow, because a wrong SHA in an audit trail is worse than an empty one:
a record is bound only when exactly one commit message names that ERR id AND that commit's tree
contains the file the record's own `lifecycle.regressionCommand` promises to run. Anything else —
several commits naming it, no commit naming it, or a promise file that postdates the commit — stays in
the owed list, where the gate can see it.
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LED = REPO / "taskpacks/current/error-ledger.json"
OUT = REPO / ".project-local" / "runs" / "convergence-20261007-h" / "ledger_binding_candidates.json"
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
        if token.endswith((".py", ".mjs", ".sh")) and "/" in token and not token.startswith("python"):
            return token
    return None


def main() -> int:
    apply = "--apply" in sys.argv
    doc = json.loads(LED.read_text(encoding="utf-8"))
    bound_now, owed = [], []
    for e in doc["errors"]:
        lc = e.get("lifecycle") or {}
        if lc.get("fixedCommit") or e.get("status_after") != "PASS":
            continue
        eid = e["error_id"]
        script = promise_script(lc.get("regressionCommand") or "")
        log = git("log", "--all", "--format=%H\x1f%s\x1f%b\x1e", "--grep", eid)
        blocks = [b for b in log.stdout.split("\x1e") if b.strip()]
        hits = []
        for b in blocks:
            parts = b.split("\x1f")
            if len(parts) < 3:
                continue
            sha, subject, body_text = parts[0], parts[1], parts[2]
            mentions = re.findall(rf"\b{eid}\b", subject + "\n" + body_text)
            if mentions:
                hits.append((sha[:7], subject[:70], len(mentions)))
        if not hits:
            owed.append({"id": eid, "promise": script, "why": "no commit message names it"})
            continue
        if len(hits) > 1:
            owed.append({"id": eid, "promise": script,
                         "why": f"{len(hits)} commits name it: {[h[0] for h in hits[:4]]}"})
            continue
        sha, subject, _ = hits[0]
        if script is None:
            owed.append({"id": eid, "promise": None,
                         "why": f"single commit {sha} but no plain script in the promise"})
            continue
        if script.startswith(".project-local/"):
            owed.append({"id": eid, "promise": script,
                         "why": f"promise points into the ignored root (ERR-130), cannot tree-check "
                                f"{sha}"})
            continue
        ok = git("cat-file", "-e", f"{sha}:{script}").returncode == 0
        if not ok:
            owed.append({"id": eid, "promise": script,
                         "why": f"{sha} does not contain {script}"})
            continue
        bound_now.append({"id": eid, "fixedCommit": sha, "subject": subject,
                          "promise": script})
        if apply:
            lc["fixedCommit"] = sha
            lc["bindingNote"] = ("bound 2026-10-07 by scripts/audit/bind_remaining_ledger_fixes.py: "
                                 f"the only commit message naming {eid} is {sha}, and its tree "
                                 f"contains the promised {script}. verifiedCommit stays null until an "
                                 "exact-SHA readback names a green head.")
            e["lifecycle"] = lc

    report = {"boundNow": bound_now, "owed": owed,
              "counts": {"newlyBound": len(bound_now), "stillOwed": len(owed)},
              "rule": "one commit message names the id AND its tree contains the promised file"}
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"newly_bound={len(bound_now)} still_owed={len(owed)}")
    for b in bound_now:
        print(f"  {b['id']} -> {b['fixedCommit']}  ({b['subject'][:48]}…)")
    print("\nowed reasons:")
    from collections import Counter
    for reason, n in Counter(o["why"].split(":")[0] for o in owed).most_common():
        print(f"  {n:>4}  {reason}")
    if apply:
        LED.write_bytes(json.dumps(doc, ensure_ascii=False, indent=2).replace("\n", "\r\n").encode())
        back = json.loads(LED.read_text(encoding="utf-8"))
        now_bound = sum(1 for e in back["errors"]
                        if (e.get("lifecycle") or {}).get("fixedCommit"))
        print(f"ledger rewritten: entries with a fixedCommit = {now_bound}/{len(back['errors'])}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
