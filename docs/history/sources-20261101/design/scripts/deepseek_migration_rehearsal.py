#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-F010 — rehearse the creative-v1 migration on a database copy.

The migration is a candidate until it has been exercised in this exact order on a
copy: backup -> migrate -> legacy readback -> new writes -> restart -> rerun
migration -> trigger behaviour -> rollback. The live state database is never
opened.

Writes reports/current/CREATIVE-MIGRATION-REHEARSAL.json.

Usage:
    python scripts/deepseek_migration_rehearsal.py
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
OUT = REPO / "reports/current/CREATIVE-MIGRATION-REHEARSAL.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-F010"
CANDIDATE_STATUS = "MIGRATION_CANDIDATE_PENDING_AUDIT"
LEGACY_COLUMNS = ["version_id", "asset_id", "version_no", "content_sha256", "state", "created_at"]
REQUIRED_TRIGGERS = {"version_rejection_no_update", "version_rejection_no_delete",
                     "requirement_event_no_update", "requirement_event_no_delete",
                     "decision_event_no_update", "decision_event_no_delete"}


def build_legacy_database(path: Path) -> dict:
    """A pre-creative database, built the way the product builds one.

    It is created through the real stores rather than by replaying their DDL, so
    the fixture carries the same ``runtime_migration`` rows a real legacy database
    would. Replaying the DDL by hand would produce a database that only *looks*
    legacy and would hide the migration-ordering bugs this rehearsal exists to
    catch.
    """
    from design_lab.runtime import asset_store, job_store
    assets = asset_store.connect(path)
    assets.close()
    jobs = job_store.connect(path)
    jobs.close()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT INTO project VALUES ('p-legacy','Legacy project','2026-09-01T00:00:00+00:00')")
    conn.execute("INSERT INTO asset VALUES ('poster','p-legacy','psd','2026-09-01T00:00:00+00:00')")
    conn.execute("INSERT INTO asset_version (version_id, asset_id, version_no, content_sha256, state, "
                 "created_at) VALUES ('v-legacy','poster',1,?,'ACTIVE','2026-09-01T00:00:00+00:00')",
                 ("sha256:" + "a" * 64,))
    conn.execute("INSERT INTO artifact VALUES ('a-legacy', 'v-legacy','legacy.psd',?,4096,'output')",
                 ("sha256:" + "b" * 64,))
    conn.commit()
    snapshot = {
        "columns": [row[1] for row in conn.execute("PRAGMA table_info(asset_version)")],
        "versions": conn.execute("SELECT version_id, asset_id, version_no, content_sha256, state "
                                 "FROM asset_version").fetchall(),
        "artifacts": conn.execute("SELECT * FROM artifact").fetchall(),
        "migrations": [row[0] for row in conn.execute("SELECT name FROM runtime_migration "
                                                      "ORDER BY name")],
    }
    conn.close()
    return snapshot


def connect_creative(path: Path):
    from design_lab.creative import store
    return store.connect(path)


def _rehearse(workdir: Path, steps: list) -> bool:
    def step(name: str, ok: bool, detail: str) -> None:
        steps.append({"step": name, "ok": bool(ok), "detail": detail})

    def blocked(conn, statement: str) -> bool:
        try:
            conn.execute(statement)
            conn.rollback()
            return False
        except sqlite3.DatabaseError:
            conn.rollback()
            return True

    original = workdir / "legacy.db"
    legacy = build_legacy_database(original)
    step("legacy_database_built", len(legacy["columns"]) == 6,
         f"pre-migration columns={legacy['columns']} migrations={legacy['migrations']}")

    backup = workdir / "legacy.db.pre-migration.bak"
    shutil.copyfile(original, backup)
    step("backup", backup.is_file(),
         f"backup written ({backup.stat().st_size} bytes); this file is the rollback source")

    conn = connect_creative(original)
    step("migration",
         bool(conn.execute("SELECT 1 FROM runtime_migration WHERE name='creative-v1'").fetchone()),
         "runtime_migration records creative-v1")
    auto = list(workdir.glob("legacy.db.pre-creative-v1-*.bak"))
    step("migration_backup", len(auto) == 1,
         f"the store took its own pre-migration backup: {[p.name for p in auto]}")

    row = conn.execute("SELECT version_id, asset_id, version_no, content_sha256, state, branch, "
                       "generation, parent_version_id FROM asset_version WHERE version_id='v-legacy'"
                       ).fetchone()
    step("legacy_readback", tuple(row[:5]) == tuple(legacy["versions"][0]) and row[5:] == ("main", 1, None),
         f"legacy row intact and V2 defaults applied: {row}")
    step("artifact_readback", conn.execute("SELECT * FROM artifact").fetchall() == legacy["artifacts"],
         "artifact rows unchanged by the migration")

    from design_lab.creative import asset_versions, version_guard
    child = asset_versions.create_version(
        conn, "poster", "sha256:" + "c" * 64,
        artifacts=[("child.psd", "sha256:" + "c" * 64, 1024, "deliverable")],
        parent_version_id="v-legacy", label="rehearsal")
    step("new_write", child["created"] and child["generation"] == 2,
         f"creative writer created generation 2 on branch {child['branch']}")
    rejected = version_guard.reject_version(conn, child["version_id"], reason="rehearsal rejection",
                                           actor="DLDS-F010", evidence_ref="rehearsal")
    step("rejection_write", rejected["created"], "rejection recorded without rewriting the version row")

    conn.close()
    conn = connect_creative(original)
    step("restart", conn.execute("SELECT COUNT(*) FROM runtime_migration WHERE name='creative-v1'")
         .fetchone()[0] == 1, "reconnect does not migrate again")
    step("restart_readback", conn.execute("SELECT COUNT(*) FROM asset_version").fetchone()[0] == 2,
         "both versions survive the restart")
    step("rerun_migration", len(list(workdir.glob("legacy.db.pre-creative-v1-*.bak"))) == 1,
         "a second connect neither migrates nor backs up again")

    triggers = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}

    # Append-only triggers are per row: an empty table proves nothing, so write a
    # job, a requirement and a decision first.
    from design_lab.creative import creative_job, decision_ledger, requirement_ledger
    job = creative_job.create_job(conn, {
        "schemaVersion": "design-lab/creative-job/v1", "project_id": "p-legacy",
        "brief_ref": {"brief_id": "brief-rehearsal", "sha256": "sha256:" + "d" * 64},
        "rights_profile": {"profile_id": "rights-rehearsal", "gate_state": "CHECKED"},
        "deliverables": [{"deliverable_id": "poster", "asset_kind": "psd",
                          "host_target": "photoshop-2025", "editable": True}],
        "host_targets": [{"host_id": "photoshop-2025", "mode": "process-isolated",
                          "editable_source": True, "evidence_level": "E1"}]},
        idempotency_scope="rehearsal", idempotency_key="rehearsal-1")
    requirement_ledger.define_requirement(conn, job_id=job["job_id"], req_id="REQ-rehearsal",
                                          statement="rehearsal requirement",
                                          acceptance="the trigger refuses a rewrite", actor="DLDS-F010")
    decision_ledger.propose(conn, job_id=job["job_id"], dec_id="DEC-rehearsal",
                            options=[{"option_id": "A", "summary": "rehearsal option"}],
                            actor="DLDS-F010")
    step("job_requirement_decision_writes", True,
         "a creative job, a requirement and a decision were written through the ledgers")

    immutability = (blocked(conn, "DELETE FROM version_rejection")
                    and blocked(conn, "UPDATE version_rejection SET reason='x'")
                    and blocked(conn, "DELETE FROM requirement_event")
                    and blocked(conn, "UPDATE decision_event SET rationale='x'"))
    step("triggers", REQUIRED_TRIGGERS <= triggers and immutability,
         f"missing={sorted(REQUIRED_TRIGGERS - triggers)}; append-only enforced={immutability}")
    conn.close()

    rollback = workdir / "rollback.db"
    shutil.copyfile(backup, rollback)
    rolled = sqlite3.connect(rollback)
    columns = [r[1] for r in rolled.execute("PRAGMA table_info(asset_version)")]
    rows = rolled.execute("SELECT * FROM asset_version").fetchall()
    rolled.close()
    step("rollback", columns == LEGACY_COLUMNS and len(rows) == 1,
         f"restoring the backup returns the original {len(columns)}-column schema and {len(rows)} row")

    conn = connect_creative(rollback)
    ok_forward = conn.execute("SELECT COUNT(*) FROM asset_version").fetchone()[0] == 1
    conn.close()
    step("rollback_then_migrate", ok_forward, "the same backup migrates forward again cleanly")

    return all(item["ok"] for item in steps)


def main() -> int:
    parent = REPO / ".project-local/task-runtime/creative-migration-rehearsal"
    parent.mkdir(parents=True, exist_ok=True)
    steps: list = []
    with tempfile.TemporaryDirectory(dir=parent, ignore_cleanup_errors=True) as temporary:
        workdir = Path(temporary)
        try:
            passed = _rehearse(workdir, steps)
        finally:
            # Windows keeps a database locked while a connection is open, which
            # would otherwise leave an undeletable temporary directory behind.
            for leftover in list(workdir.glob("*.db")) + list(workdir.glob("*.bak")):
                try:
                    leftover.unlink()
                except OSError:
                    pass
    document = {
        "schemaVersion": "design-lab/creative-migration-rehearsal/v1",
        "task_key": TASK_KEY,
        "rehearsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "migration": "design-lab/schemas/state/design-lab-state-creative-v1.sql",
        "status_before": CANDIDATE_STATUS,
        "status_after": "REHEARSED_PASS_PENDING_ACCEPTANCE" if passed else CANDIDATE_STATUS,
        "accepted_as_production": False,
        "acceptance_note": "a passing rehearsal permits the production label; it does not grant it. "
                           "That is an owner/Codex acceptance act.",
        "database": "a copy under .project-local/task-runtime/; the live state database was never opened",
        "steps": steps,
        "passed": passed,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"MIGRATION_REHEARSAL={'PASS' if passed else 'FAIL'} steps={len(steps)} "
          f"status={document['status_after']}")
    for item in steps:
        print(f"  {'ok  ' if item['ok'] else 'FAIL'} {item['step']:24} {item['detail'][:94]}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
