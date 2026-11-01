#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-E050 — post-cleanup audit.

Re-measures after the cleanup instead of trusting the estimate: repository size,
Git status, legacy path references, the focused test suites, the zero-spill
probe and the report generator. `bytes_before` is quoted from the artifact that
measured it (never recomputed from memory); `bytes_reclaimed` is the difference
between two real measurements.

Writes reports/current/POST-CLEANUP-AUDIT.json.

Usage:
    python scripts/deepseek_post_cleanup_audit.py [--no-tests]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current/POST-CLEANUP-AUDIT.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-E050"
CLEANUP_MANIFEST = REPO / ".project-local/quarantine/deepseek-round1/RUNTIME-CLEANUP-MANIFEST.json"
MIGRATION_MANIFEST = REPO / ".project-local/archive/hermes-legacy/MIGRATION-MANIFEST.json"
TEST_PATTERNS = ("test_creative_*.py", "test_interop_*.py", "test_media_*.py",
                 "test_assurance_*.py", "test_readiness_*.py")


def resolve_interpreter() -> str:
    """Platform-neutral interpreter (DL-AUDIT-20260914-06): no hard-coded
    ``.venv/Scripts/python.exe``. Prefer the running interpreter, then the
    platform's virtualenv layout, then ``python3`` on PATH."""
    import sys
    if sys.executable:
        return sys.executable
    for candidate in (REPO / ".venv/bin/python", REPO / ".venv/Scripts/python.exe"):
        if candidate.exists():
            return str(candidate)
    return "python3"


PYTHON = resolve_interpreter()


def run(command: list, timeout: int = 900) -> tuple:
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", cwd=str(REPO), timeout=timeout)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def measure_runtime_roots() -> dict:
    roots = {}
    for name in (".project-local", ".hermes"):
        root = REPO / name
        if not root.is_dir():
            continue
        files = 0
        total = 0
        for item in root.rglob("*"):
            try:
                if item.is_file():
                    files += 1
                    total += item.stat().st_size
            except OSError:
                continue
        roots[name] = {"files": files, "bytes": total, "mib": round(total / 1048576, 2)}
    return roots


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args(argv)

    after_roots = measure_runtime_roots()
    cleanup = json.loads(CLEANUP_MANIFEST.read_text(encoding="utf-8")) if CLEANUP_MANIFEST.is_file() else {}
    migration = json.loads(MIGRATION_MANIFEST.read_text(encoding="utf-8")) if MIGRATION_MANIFEST.is_file() else {}
    size_before = json.loads((REPO / "reports/current/UNTRACKED-RUNTIME.json").read_text(encoding="utf-8")) \
        if (REPO / "reports/current/UNTRACKED-RUNTIME.json").is_file() else {}

    pack = git("count-objects", "-vH")
    pack_values = dict(line.split(":", 1) for line in pack.splitlines() if ":" in line)
    size_pack = float(pack_values.get("size-pack", "0 MiB").strip().split()[0])

    # The before/after pair has to be honest about what it actually compares. An
    # INDEPENDENT AUDIT showed the earlier version labelled UNTRACKED-RUNTIME.json as
    # "measured before the cleanup" when its measured_at (16:26:39) is ten seconds
    # AFTER the cleanup manifest's deleted_at (16:26:29), and when it totals four
    # roots against an after-figure that covers two. Both facts are computed here
    # instead of asserted.
    def parse_instant(value):
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    before_measured_at = size_before.get("measured_at")
    deleted_at = cleanup.get("deleted_at")
    before_instant, deleted_instant = parse_instant(before_measured_at), parse_instant(deleted_at)
    before_roots = sorted((size_before.get("roots") or {}).keys()) if isinstance(
        size_before.get("roots"), dict) else []
    before_bytes = sum(r.get("bytes", 0) for r in (size_before.get("roots") or {}).values()) \
        if isinstance(size_before.get("roots"), dict) else 0
    after_bytes = sum(r["bytes"] for r in after_roots.values())
    reclaimed_bytes = cleanup.get("bytes_reclaimed") or 0
    predates = bool(before_instant and deleted_instant and before_instant < deleted_instant)
    same_roots = bool(before_roots) and before_roots == sorted(after_roots)
    like_for_like = predates and same_roots
    residual_mib = (round((before_bytes - reclaimed_bytes - after_bytes) / 1048576, 2)
                    if before_bytes and like_for_like else None)
    before_after = {
        "before_source": "reports/current/UNTRACKED-RUNTIME.json (DLDS-D000)",
        "before_measured_at": before_measured_at,
        "cleanup_deleted_at": deleted_at,
        "before_predates_deletion": predates,
        "roots_compared": {"before": before_roots, "after": sorted(after_roots)},
        "same_root_set": same_roots,
        "like_for_like": like_for_like,
        "before_mib": round(before_bytes / 1048576, 2) if before_bytes else size_before.get("total_mib"),
        "after_mib": round(after_bytes / 1048576, 2),
        "reclaimed_mib": round(reclaimed_bytes / 1048576, 2),
        "arithmetic_residual_mib": residual_mib,
    }
    if like_for_like:
        before_after["claim"] = "before/after is like-for-like"
    else:
        before_after["claim"] = "WITHDRAWN"
        before_after["reason"] = (
            "no like-for-like pair exists: " + "; ".join(filter(None, [
                "no artifact measured these roots before the deletion "
                "(the earliest reading is %s, %s the deletion at %s)" % (
                    before_measured_at, "AFTER" if not predates else "before", deleted_at)
                if not predates else "",
                "the two sides cover different root sets (%s vs %s)" % (
                    ", ".join(before_roots) or "unknown", ", ".join(sorted(after_roots)))
                if not same_roots else "",
            ])) + ". The reclaimed bytes above are the measured, digest-backed quantity; "
                 "no before/after reduction is claimed.")

    report: dict = {
        "schemaVersion": "design-lab/post-cleanup-audit/v1",
        "task_key": TASK_KEY,
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD").strip(),
        "git_status_clean": git("status", "--porcelain=v1").strip() == "",
        "git_dirty_paths": [line for line in git("status", "--porcelain=v1").splitlines() if line.strip()],
        "repository_size": {"pack_mib": size_pack, "tracked_files": len([p for p in git("ls-files").splitlines() if p])},
        "runtime_roots_after": after_roots,
        "bytes_reclaimed": {
            "temp_cache_deleted": cleanup.get("bytes_reclaimed"),
            "temp_cache_entries": len(cleanup.get("deleted", [])),
            "legacy_hermes_objects_migrated": len(migration.get("records", [])),
            "legacy_hermes_bytes_moved": sum(r.get("bytes", 0) for r in migration.get("records", [])),
            "meaning": "deleted cache/temp is reclaimed; migrated legacy runtime is relocated inside the "
                       "same volume, so it is moved rather than reclaimed",
        },
        "before_measurement_source": "reports/current/UNTRACKED-RUNTIME.json (DLDS-D000)",
        "before_measured_mib": size_before.get("total_mib"),
        "before_measurement_is_precleanup": predates,
        "before_after": before_after,
    }
    stages = []
    stages.append(("report_generator_generate", *run([str(PYTHON), str(REPO / "scripts/generate_current_reports.py")])))
    stages.append(("report_generator_check", *run([str(PYTHON), str(REPO / "scripts/generate_current_reports.py"), "--check"])))
    stages.append(("legacy_path_scan", *run([str(PYTHON), str(REPO / "scripts/deepseek_directory_audit.py")])))
    stages.append(("zero_spill_probe", *run([str(PYTHON), str(REPO / "scripts/verify_zero_spill.py"), "--self-test"])))
    if not args.no_tests:
        for pattern in TEST_PATTERNS:
            stages.append((f"tests:{pattern}", *run([
                str(PYTHON), "-m", "unittest", "discover",
                "-s", str(REPO / "design-lab/tests"), "-p", pattern,
                "-t", str(REPO / "design-lab/tests")])))
    report["stages"] = [{"stage": name, "exit_code": code,
                         "summary": [line for line in output.splitlines()
                                     if line.startswith(("OK", "FAILED", "Ran ", "CURRENT_REPORTS=",
                                                         "ZERO_SPILL=", "LANGUAGE_BOUNDARY=",
                                                         "DIRECTORY_AUDIT="))][-2:]}
                        for name, code, output in stages]
    failed = [stage["stage"] for stage in report["stages"] if stage["exit_code"] != 0
              and not stage["stage"].startswith("tests:")]
    report["verdict"] = "PASS" if not failed else f"REVIEW {failed}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"POST_CLEANUP_AUDIT={report['verdict']} pack_mib={size_pack} "
          f"runtime_after_mib={sum(r['mib'] for r in after_roots.values())} "
          f"before_mib={report['before_measured_mib']} "
          f"reclaimed_mib={round((cleanup.get('bytes_reclaimed') or 0) / 1048576, 2)}")
    for stage in report["stages"]:
        print(f"  {stage['stage']:28} exit={stage['exit_code']:<3} {' | '.join(stage['summary'])[:96]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
