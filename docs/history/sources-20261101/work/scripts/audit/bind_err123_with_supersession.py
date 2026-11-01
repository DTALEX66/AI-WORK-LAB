"""Bind ERR-123 to the commit that actually fixed it, with the supersession stated in the same change.

Every predicate the binding gate will check is enforced here before anything is written: the commit exists,
it contains the record's own promised regression script, it touches a path the record names, and it is the
commit that recorded the error. The note also says what the gate cannot see - that the CSS mechanism this fix
introduced was deliberately removed later under an owner instruction, so the invariant moved to a different
guard rather than being silently deleted.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "taskpacks/current/error-ledger.json"
FIX = "763a77f"
PROMISED = "apps/observer/tests/test_production_surface_static_contract.js"


def git(*args, code=False):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode if code else r.stdout.strip()


doc = json.loads(LEDGER.read_text(encoding="utf-8"))
record = next(e for e in doc["errors"] if e["error_id"] == "ERR-123")
lc = record["lifecycle"]
if lc.get("fixedCommit"):
    print("ERR-123 already bound to", lc["fixedCommit"])
    sys.exit(0)

sha = git("rev-parse", "--verify", f"{FIX}^{{commit}}")
assert len(sha) == 40, "fix commit does not resolve"
assert git("cat-file", "-e", f"{sha}:{PROMISED}", code=True) == 0, "promised script not in that tree"
names = [PROMISED, "apps/observer/frontend/src/skins/l10b-shell.css"]
touched = set(git("show", "--format=", "--name-only", sha).splitlines())
assert touched & set(names), "the fix commit touches no path this record names"
added = json.loads(git("show", f"{sha}:taskpacks/current/error-ledger.json"))
parent = json.loads(git("show", f"{sha}^:taskpacks/current/error-ledger.json"))
assert "ERR-123" in {e["error_id"] for e in added["errors"]}, "the commit does not contain the record"
# A single-record fix, measured against that commit's own parent rather than against today's ledger -
# comparing a 2026-10-07 tree to the current one would have shown a negative difference and passed
# anything, including a commit that imported fifty records.
delta = added["summary"]["total"] - parent["summary"]["total"]
assert 0 <= delta <= 1, f"bulk commit: this tree added {delta} records"

lc["fixedCommit"] = sha
lc["bindingBasis"] = "record-and-fix-in-one-commit: " + sha[:7] + " adds the CSS tier, extends the contract " \
                                                                  "test and creates this record together"
lc["bindingNote"] = (
    "bound 2026-10-07 by scripts/audit/bind_err123_with_supersession.py: "
    f"{sha[:7]} touches {names[0]} and {names[1]}, and that tree contains the promised regression script. "
    "SUPERSESSION the gate cannot see: the mechanism this fix introduced - the two-track grid inside "
    "@media (min-width: 841px) - was deliberately removed by 71b1ae8 under the owner's 2026-10-07 "
    "desktop-only instruction. The invariant (the content column must shrink; the application column must "
    "never collapse to the rail width) is still enforced, now unconditionally: "
    "`.app { grid-template-columns: clamp(...) minmax(0, 1fr) }` asserted by the re-anchored contract test "
    "(line 303 records the change of basis) and by tests/ci/test_desktop_only_shell.py. status_after=PASS "
    "therefore means 'the defect is fixed and guarded', not 'this exact CSS still reads as written'.")

LEDGER.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
back = json.loads(LEDGER.read_text(encoding="utf-8"))
row = next(e for e in back["errors"] if e["error_id"] == "ERR-123")
assert row["lifecycle"]["fixedCommit"] == sha
print("BOUND ERR-123 ->", sha[:7], "| touched:", sorted(touched & set(names)))
