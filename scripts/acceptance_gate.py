# SPDX-License-Identifier: MIT
"""V10 acceptance gate: audit a unified store's completion claims, read-only.

The 2026-10-30 audit showed the old gate answered "BACKED / exit 0" to a store
whose COMPLETED task rested on a result bound to a non-existent attempt and pack,
with an empty command, no evidence and an unrelated fingerprint — and that a later
FAIL did not stop the earlier PASS from supporting readiness. It only looked for a
PASS row and for orphan verifications, so a forged row that *looked* connected
passed.

What it does now:

* opens the database **read-only** and reuses the service's own
  ``UnifiedStore.completion_support`` / ``integrity_report``. One rule, one
  implementation: a gate that re-derived readiness its own way would drift from
  the server and both would go green separately;
* checks the whole relation, not the presence of a PASS: task → attempt → result
  → verdict, the pinned binding digest, whether the verdict certifies the bytes it
  points at, whether its evidence references are readable and in scope, and whether
  the *newest* verdict on that axis still says PASS;
* separates **historical fact** from **current readiness**. A PASS that was real at
  the time is never erased; it simply stops supporting a claim about now once a
  later FAIL, a moved subject or a superseded revision overtakes it;
* reports batch readiness and full-product readiness as two answers. Completing
  this batch's tasks is not "the product is ready", and this gate refuses to say so.

Exit codes: 0 = every completion claim is currently backed; 1 = at least one is
not; 2 = the store could not be read or the invocation is wrong. This is a local
audit tool, not a release verdict, and it never writes to the store it audits.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
for entry in (str(TARGET_ROOT), str(TARGET_ROOT / "domains" / "design")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backend.core import refs as ref_rules  # noqa: E402
from backend.core.qualifications import QualificationLedger, candidate_version  # noqa: E402
from backend.core.unified_store import UnifiedStore  # noqa: E402

#: Gates that full-product readiness still waits on. Hard-coded as a *question
#: list*, not a claim: this tool cannot observe a host, a person or a release.
FULL_PRODUCT_GATES = (
    "真实宿主 E3（Photoshop/Illustrator 保存-重开-读回）",
    "真人具名专业验收（本批只有合成夹具）",
    "外部执行器真实资格",
    "受控业务数据迁移的真实数据验证",
    "离线隔离安装与安装态回归",
    "release / 安装态分发 / 回滚演练",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _pack_exists(work_store_path: Path | None, plan_id: str) -> tuple[bool, str]:
    """Does the WORK record the attempt claims still exist? Read-only."""
    if work_store_path is None or not Path(work_store_path).is_file():
        return False, "work store not supplied or not present"
    if not plan_id:
        return True, "no work pack bound (design flavor)"
    try:
        conn = sqlite3.connect("file:" + str(work_store_path).replace("\\", "/") + "?mode=ro",
                               uri=True)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT plan_id, status FROM action_plans WHERE plan_id = ?",
                               (plan_id,)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return False, "work store unreadable: " + type(exc).__name__
    if row is None:
        return False, "action_plans has no row " + repr(plan_id)
    return True, "action_plans row present with status " + repr(row["status"])


def _evidence_state(store: UnifiedStore, verification: dict, *,
                    allowed_roots: list[Path]) -> tuple[list[str], list[str], list[str]]:
    """Split one verdict's evidence into what was *opened*, what was refused, and
    what is only an identifier.

    A `scheme:opaque` reference is admissible and attributable, but the gate cannot
    open it as a file — claiming it as "readable evidence" would be an overclaim. So
    it is reported in its own bucket, and a PASS whose only support is opaque
    identifiers says so in the output.
    """
    readable: list[str] = []
    refused: list[str] = []
    identifiers: list[str] = []
    for reference in verification["evidence_refs"]:
        text = str(reference)
        is_file_like = ":" not in text or text.split(":", 1)[0] == "file"
        try:
            ref_rules.validate(text, allowed_roots=allowed_roots, for_read=is_file_like)
        except ref_rules.RefError as exc:
            refused.append(text + " → " + str(exc))
            continue
        if is_file_like:
            readable.append(text)
        else:
            identifiers.append(text)
    return readable, refused, identifiers


def audit(store_path: Path, *, work_store_path: Path | None = None,
          approvals_path: Path | None = None, evidence_root: Path | None = None) -> dict:
    store = UnifiedStore.open_readonly(store_path)
    version = candidate_version(TARGET_ROOT)
    problems: list[dict] = []
    evidence_audit: list[dict] = []
    historical: list[dict] = []
    current: list[dict] = []
    allowed_roots = [Path(evidence_root)] if evidence_root else []
    if allowed_roots:
        allowed_roots.append(store_path.parent)

    tasks = store.list_tasks()
    ledger = QualificationLedger(Path(approvals_path)) if approvals_path else None
    for task in tasks:
        task_id = task["task_id"]
        support = store.completion_support(task_id)
        claim = {"task_id": task_id, "title": task["title"], "lifecycle": task["lifecycle"],
                 "supported": support["supported"], "problems": support["problems"],
                 "chain": support["chain"]}
        if task["lifecycle"] == "COMPLETED":
            current.append(claim)
            if not support["supported"]:
                problems.append(dict(kind="COMPLETION_NOT_BACKED", id=task_id,
                                     detail="; ".join(support["problems"])))
        if support["historical_fact"]:
            historical.append(claim)
        if support["chain"].get("result_id"):
            result = store.get_result(support["chain"]["result_id"])
            flavor = (result or {}).get("binding", {}).get("flavor")
            if (result is not None and result["pack_id"]
                    and flavor in (None, "work_repair_pack")):
                exists, detail = _pack_exists(work_store_path, result["pack_id"])
                if not exists:
                    problems.append(dict(kind="PACK_RECORD_ABSENT", id=result["result_id"],
                                         detail=detail))
            verdict = store.latest_verdict(support["chain"]["result_id"], "technical")
            if verdict is not None and verdict["outcome"] == "PASS":
                readable, refused, identifiers = _evidence_state(store, verdict,
                                                                 allowed_roots=allowed_roots)
                for entry in refused:
                    problems.append(dict(kind="EVIDENCE_NOT_READABLE", id=verdict["verification_id"],
                                         detail=entry))
                evidence_audit.append(dict(
                    verification_id=verdict["verification_id"],
                    readable_files=readable, identifier_refs=identifiers, refused=refused,
                    note="identifier_refs 是服务端自己签发的引用名，门能核验其归属与摘要，"
                         "但无法把它们当打开过的文件证据"))
                if not readable and not refused and not identifiers:
                    problems.append(dict(kind="PASS_WITHOUT_EVIDENCE", id=verdict["verification_id"],
                                         detail="no evidence reference to check"))
                if verdict.get("candidate_version") and (
                        verdict["candidate_version"] != version["digest"]):
                    problems.append(dict(kind="VERDICT_FROM_OTHER_CANDIDATE",
                                         id=verdict["verification_id"],
                                         detail="verdict was computed against candidate "
                                                + str(verdict["candidate_version"])[:12]
                                                + "…, the running candidate is "
                                                + version["digest"][:12] + "…"))
    integrity = store.integrity_report()
    for entry in integrity["problems"]:
        problems.append(entry)

    live_eligible = [claim for claim in current
                     if claim["supported"]
                     and claim["chain"].get("task_origin") == "live"
                     and claim["chain"].get("result_origin") == "live"
                     and claim["chain"].get("technical_origin") == "live"]
    synthetic_supported = [claim for claim in current if claim["supported"]
                           and claim not in live_eligible]
    batch_ready = not problems
    return {
        "schemaVersion": "ai-work-lab/acceptance-gate/v2",
        "observed_at": _now(),
        "store": str(store_path),
        "work_store": str(work_store_path) if work_store_path else None,
        "candidate_version": version["digest"],
        "candidate_files": version["files"],
        "checked_tasks": len(tasks),
        "verdict": "BACKED" if batch_ready else "REFUSED",
        "batch_readiness": {
            "ready": batch_ready,
            "supported_now": [claim["task_id"] for claim in current if claim["supported"]],
            "synthetic_only": [claim["task_id"] for claim in synthetic_supported],
            "live_eligible": [claim["task_id"] for claim in live_eligible],
            "note": "本批就绪只判断当前有效核验；合成链不会成为 live 证据",
        },
        "full_product_readiness": {
            "ready": False,
            "reason": "本工具只能审计统一存储内的完成声明；下列门不在本存储内，未运行即不就绪",
            "outstanding_gates": list(FULL_PRODUCT_GATES),
        },
        "current_claims": current,
        "historical_claims": historical,
        "historical_note": "historical_claims 记录「曾经有过 PASS」这一事实，不因为当前不就绪而被抹去；"
                           "它不支撑当前就绪声明",
        "problems": problems,
        "evidence_audit": evidence_audit,
        "problem_count": len(problems),
        "integrity_counts": integrity["counts"],
        "qualification_ledger_present": bool(ledger),
    }


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or "--help" in args:
        print("usage: python scripts/acceptance_gate.py <unified.sqlite3> "
              "[--work-store <canonical/work-store.sqlite3>] [--approvals <path>] "
              "[--evidence-root <dir>]", file=sys.stderr)
        return 2
    store_path = Path(args[0])
    if not store_path.is_file():
        print(json.dumps({"verdict": "UNREADABLE", "reason": "no such store: " + str(store_path)}))
        return 2
    options = dict(zip([key.lstrip("--") for key in args[1::2]], args[2::2]))
    try:
        report = audit(store_path,
                       work_store_path=Path(options["work-store"]) if "work-store" in options else None,
                       approvals_path=Path(options["approvals"]) if "approvals" in options else None,
                       evidence_root=Path(options["evidence-root"]) if "evidence-root" in options
                       else None)
    except sqlite3.Error as exc:
        print(json.dumps({"verdict": "UNREADABLE", "reason": type(exc).__name__ + ": " + str(exc)}))
        return 2
    # ensure_ascii keeps the report pure ASCII on stdout: a cp936 console cannot
    # encode "→" or "…", and a tool whose output an auditor pipes into json.loads
    # must not fail because of the machine's code page.
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0 if report["verdict"] == "BACKED" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
