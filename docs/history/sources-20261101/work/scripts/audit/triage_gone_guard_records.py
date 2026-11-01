"""For the PASS records whose named check is gone: is it moved, or is the PASS claim unsupported?

A record whose regression command points at a file that no longer exists cannot be re-verified by that
command. Two very different states look identical in the ledger: the guard was re-pointed (so the claim
still has a home), and the guard was removed (so the PASS is now a claim with no check). This separates
them by basename, by history, and by the same symbol's presence under another path.
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRIAGE = ROOT / "docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json"
LEDGER = ROOT / "taskpacks/current/error-ledger.json"

doc = json.loads(TRIAGE.read_text(encoding="utf-8"))
records = {e["error_id"]: e for e in json.loads(LEDGER.read_text(encoding="utf-8"))["errors"]}
tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout.split()
basenames: dict[str, list[str]] = {}
for path in tracked:
    basenames.setdefault(Path(path).name, []).append(path)

gone = [r for r in doc["rows"] if r.get("state") == "PATH_GONE"]
print("PATH_GONE records", len(gone))
for r in gone:
    name = Path(r["operand"]).name
    live = basenames.get(name, [])
    history = subprocess.run(["git", "log", "--oneline", "--diff-filter=D", "--", r["operand"]],
                             cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.strip().splitlines()
    print(f"{r['errorId']} date={r['date']} operand={r['operand']}")
    print(f"   basename_now={live or 'NOT_ANYWHERE'} deletion_commits={history[:1] or 'none_found'}")
    print(f"   command={r['command'][:100]}")
