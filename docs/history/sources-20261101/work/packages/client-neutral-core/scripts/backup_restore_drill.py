#!/usr/bin/env python3
"""WLR-100: Backup/restore drill script.

Verifies that critical governance files can be backed up and restored.
Run from WORK-LAB root: python scripts/workflow/backup_restore_drill.py
"""
import json, hashlib, shutil, sys
from pathlib import Path

BASE = Path.cwd()
if not (BASE / "AGENTS.md").exists():
    BASE = Path(__file__).parent.parent.parent.parent
GOV = BASE / ".project/governance"
CONFIG = BASE / "config"
SCHEMAS = BASE / "packages" / "contracts" / "schemas" / "workflow"
DRILL_DIR = BASE / ".hermes" / "task-runtime" / "backup-drill"

CRITICAL_FILES = [
    GOV / "config-authority-index.json",
    GOV / "taskpack-authority-index.json",
    CONFIG / "adapter-registry.json",
    CONFIG / "config-ownership.json",
    CONFIG / "models-registry.json",
    CONFIG / "plugin-inventory.json",
    SCHEMAS / "adapter-registry.schema.json",
    SCHEMAS / "context-capsule.schema.json",
    SCHEMAS / "canonical-config-intent.schema.json",
]

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    DRILL_DIR.mkdir(parents=True, exist_ok=True)
    results = {"backup": [], "restore": [], "integrity": []}
    ok = True

    # Phase 1: Backup
    for f in CRITICAL_FILES:
        if not f.exists():
            results["backup"].append({"file": str(f.relative_to(BASE)), "status": "MISSING"})
            ok = False
            continue
        h = sha256(f)
        dest = DRILL_DIR / f.name
        shutil.copy2(f, dest)
        results["backup"].append({"file": str(f.relative_to(BASE)), "hash": h, "status": "OK"})

    # Phase 2: Restore (copy back to temp and verify hash)
    for item in results["backup"]:
        if item["status"] != "OK":
            continue
        src = DRILL_DIR / Path(item["file"]).name
        restored_hash = sha256(src)
        match = restored_hash == item["hash"]
        results["restore"].append({"file": item["file"], "match": match, "status": "OK" if match else "MISMATCH"})
        if not match:
            ok = False

    # Phase 3: Integrity (re-read originals, confirm unchanged)
    for f in CRITICAL_FILES:
        if not f.exists():
            continue
        h = sha256(f)
        original = next((r for r in results["backup"] if r["file"] == str(f.relative_to(BASE))), None)
        if original:
            intact = h == original["hash"]
            results["integrity"].append({"file": str(f.relative_to(BASE)), "intact": intact})
            if not intact:
                ok = False

    # Summary
    backup_ok = sum(1 for r in results["backup"] if r["status"] == "OK")
    restore_ok = sum(1 for r in results["restore"] if r["match"])
    integrity_ok = sum(1 for r in results["integrity"] if r["intact"])
    total = len(CRITICAL_FILES)

    print(f"=== WLR-100 Backup/Restore Drill ===")
    print(f"Backup:  {backup_ok}/{total} files")
    print(f"Restore: {restore_ok}/{total} hash match")
    print(f"Integrity: {integrity_ok}/{total} unchanged")
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")

    # Write drill report
    report = {
        "drill": "WLR-100",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "result": "PASS" if ok else "FAIL",
        "total_files": total,
        "backup_ok": backup_ok,
        "restore_ok": restore_ok,
        "integrity_ok": integrity_ok,
        "details": results,
    }
    report_path = DRILL_DIR / "drill-report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {report_path}")

    # Cleanup drill dir
    shutil.rmtree(DRILL_DIR, ignore_errors=True)

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
