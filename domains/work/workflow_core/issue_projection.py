"""Issue center: problems derived from facts the store already holds (audit 2026-10-22 §闭环距离 row 2).

The repo had counts (collector delivery/refusal totals, coverage numerators) and task statuses, but no place
that said "these are the problems, which project and software each belongs to, how often it has been seen,
and what evidence backs it". A reader could see `refused_rows=4824` and still not know what is wrong. This
module turns those already-recorded facts into issue rows. It never re-reads a source and never infers a
cause: every row names the table and key it came from.

Three invariants, each enforced by a test rather than by intent:

* **absent is not empty.** A source that could not be read yields no rows and a named source state; a source
  read that holds nothing yields the empty count. Collapsing the two would claim "no problems on this
  machine", which is the opposite statement, and the repo has convicted that shape before (ERR-256 lineage).
* **dedup by identity, not by string equality.** The fingerprint hashes a declared tuple
  (class, project, subject) so the same condition recurring across polls folds into one issue with an
  occurrence count, and a different class on the same subject stays a different issue.
* **priority is a rule table.** Every severity comes from a named rule that is listed in the row itself, so
  a card can say "why is this P1" instead of a reader guessing which number produced it.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

ISSUE_SCHEMA_VERSION = "workflow/issue/v1"
SUMMARY_SCHEMA_VERSION = "worklab/issues-summary/v1"

MAX_ISSUES = 200
ORDER_LABEL = "severity-then-lastSeen-then-fingerprint"
ORDERING_KEY = "(-priorityRank, -lastSeenEpoch, fingerprint)"

SOURCE_STATES = ("read", "absent", "error")

# An evidence ref names the row it points at; the prefix is the ledger's own namespace and does not always
# spell the projection source (`telemetry` events are produced by `telemetry_events`). Anyone asking "did
# the source that produced this evidence answer this round?" needs this mapping, and it lives here because
# this module owns both names.
EVIDENCE_REF_SOURCES = {
    "collector_health": "collector_health",
    "telemetry": "telemetry_events",
    "execution_instances": "execution_instances",
    "tasks": "tasks",
}


def source_of_evidence_ref(evidence_ref: str) -> str:
    prefix = str(evidence_ref or "").split(":", 1)[0]
    return EVIDENCE_REF_SOURCES.get(prefix, prefix)

# Classes are a closed vocabulary: a row whose cause nobody declared is a bug in this module, not a new
# string a UI would have to special-case.
CLASSES = (
    "SOURCE_CIRCUIT_OPEN",
    "SOURCE_REFUSAL",
    "SOURCE_FAILURE",
    "SOURCE_DATA_DROPPED",
    "SOURCE_STALE",
    "SOURCE_INCOMPLETE_COVERAGE",
    "EXECUTION_STALLED",
    "EXECUTION_CONFLICT",
    "TASK_BLOCKED",
    "TASK_FAILED",
)

# Why each rule has the severity it does, in one place. `retryable` here means "a safe re-read exists",
# never "the problem will fix itself".
PRIORITY_RULES: dict[str, dict[str, Any]] = {
    "SOURCE_CIRCUIT_OPEN": {"priority": "P1", "why": "该来源已被熔断，投影里它贡献的字段从现在起是空的，不是少了一条数据。", "retryable": True},
    "SOURCE_REFUSAL": {"priority": "P2", "why": "来源在返回数据，但有行被拒绝：范围或许可不匹配，读到的不是全量。", "retryable": True},
    "SOURCE_FAILURE": {"priority": "P2", "why": "连续失败：最近一次读取没成功，新鲜度从此只在退化。", "retryable": True},
    "SOURCE_DATA_DROPPED": {"priority": "P3", "why": "有行被丢弃，分母仍然可信，但计数不闭合。", "retryable": False},
    "SOURCE_STALE": {"priority": "P2", "why": "时间戳过期：界面显示的可能是旧事实，读者需要知道它多久没更新。", "retryable": True},
    "SOURCE_INCOMPLETE_COVERAGE": {"priority": "P3", "why": "覆盖不完整：读数只描述被采到的那部分总体。", "retryable": False},
    "EXECUTION_STALLED": {"priority": "P2", "why": "执行实例无心跳：任务在跑还是已经没人管，无法从状态列判断。", "retryable": False},
    "EXECUTION_CONFLICT": {"priority": "P1", "why": "同一对象存在冲突证据：两个写入者或对同一事实的相反读数。", "retryable": False},
    "TASK_BLOCKED": {"priority": "P2", "why": "任务处于 BLOCKED：需要外部条件（重试耗尽后停住）。", "retryable": False},
    "TASK_FAILED": {"priority": "P1", "why": "任务 FAILED：包含带外部副作用的失败，不能靠重读恢复。", "retryable": False},
}

PRIORITY_RANK = {"P1": 1, "P2": 2, "P3": 3}

# Coverage / freshness vocabularies already used by the telemetry ledger. Anything outside them is reported
# as an unknown value on the issue rather than silently bucketed into "complete".
STALE_FRESHNESS = ("STALE", "EXPIRED", "UNKNOWN")
INCOMPLETE_COVERAGE = ("PARTIAL", "DEGRADED", "UNKNOWN")

_DETAIL_LIMIT = 160

_HEX16 = re.compile(r"^[0-9a-f]{16}$")


def _fingerprint(issue_class: str, project: str | None, subject: str) -> str:
    """A stable identity: same class + same project + same subject folds recurring polls into one issue."""
    raw = f"{issue_class}|{project or '-'}|{subject}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _detail(text: Any) -> str:
    value = "" if text is None else str(text)
    return value[:_DETAIL_LIMIT]


def _epoch(value: Any) -> float:
    """Best-effort epoch for ordering; unparseable timestamps rank last rather than becoming 0."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        from datetime import datetime
        return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _norm(value: str) -> str:
    return re.sub(r"[\s_\-.]+", "", value).casefold()


# The six ways a row can end up attributed or not. They are a closed vocabulary because "we could not
# attribute this" and "attribution was impossible by source" are different facts a reader acts on.
SOFTWARE_STATES = ("discovered", "not-discovered", "unmatched", "ambiguous",
                   "source-names-no-software", "identity-source-absent")


def _software_index(rows: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Case/punctuation-insensitive identity index over the software rows the root already built.

    Both `softwareId` and `displayName` become keys, because a producer names itself either way. A key that
    resolves to more than one product is kept as ambiguous rather than guessed: attributing a problem to the
    wrong installed software is worse than leaving it unattributed.
    """
    if rows is None:
        return {"state": "absent", "byKey": {}, "byId": {}}
    by_key: dict[str, list[str]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        software_id = str(row.get("softwareId") or "")
        if not software_id:
            continue
        by_id[software_id] = row
        for name in (software_id, str(row.get("displayName") or "")):
            if not name:
                continue
            bucket = by_key.setdefault(_norm(name), [])
            if software_id not in bucket:
                bucket.append(software_id)
    return {"state": "read", "byKey": by_key, "byId": by_id}


def _resolve_software(index: dict[str, Any], named: str | None) -> dict[str, Any]:
    """The three attribution fields for a row whose source named `named` (possibly nothing)."""
    if index["state"] == "absent":
        return {"softwareId": None, "softwareVersion": None,
                "softwareVersionSource": "identity-source-absent"}
    if not named:
        return {"softwareId": None, "softwareVersion": None,
                "softwareVersionSource": "source-names-no-software"}
    matches = index["byKey"].get(_norm(named)) or []
    if len(matches) > 1:
        return {"softwareId": None, "softwareVersion": None, "softwareVersionSource": "ambiguous"}
    if not matches:
        return {"softwareId": None, "softwareVersion": None, "softwareVersionSource": "unmatched"}
    row = index["byId"][matches[0]]
    version = row.get("discoveredVersion")
    return {"softwareId": matches[0],
            "softwareVersion": str(version) if version else None,
            "softwareVersionSource": "discovered" if version else "not-discovered"}


def _issue(*, issue_class: str, project: str | None, subject: str, source: str,
           evidence_ref: str, first_seen: str | None, last_seen: str | None,
           occurrences: int, magnitude: dict[str, Any], detail: str,
           software: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build one row. `software` is the attribution triple; omitting it means the source named no product.

    The default is deliberate: collector and task facts do not carry a product identity, and writing
    "unattributable" at every one of those call sites would invite someone to "fix" the repetition by
    guessing a match instead.
    """
    rule = PRIORITY_RULES[issue_class]
    return {
        "schemaVersion": ISSUE_SCHEMA_VERSION,
        "fingerprint": _fingerprint(issue_class, project, subject),
        "class": issue_class,
        "projectId": project,
        "subject": subject,
        "origin": source,
        "evidenceRef": evidence_ref,
        "priority": rule["priority"],
        "priorityRule": rule["why"],
        "safeToReread": rule["retryable"],
        "firstSeenAt": first_seen,
        "lastSeenAt": last_seen,
        "occurrences": int(occurrences),
        "magnitude": magnitude,
        "detail": detail,
        "status": "OPEN",
        **(software or _no_software()),
    }


def _no_software() -> dict[str, Any]:
    return {"softwareId": None, "softwareVersion": None,
            "softwareVersionSource": "source-names-no-software"}


def _from_collector_health(rows: list[dict[str, Any]], index: dict[str, Any]) -> list[dict[str, Any]]:
    """Circuit / refusal / failure / drop facts per collector, as recorded by the durable worker.

    A collector name is not a product identity — `git` and `usage-files` describe what was read, not which
    installed software it belongs to — so every row here reports source-names-no-software rather than
    matching a product by string luck.
    """
    issues: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("name") or "")
        if not name:
            continue
        updated = str(row.get("updated_at") or "")
        open_until = row.get("circuit_open_until")
        if open_until not in (None, 0) and float(open_until) > time.time():
            issues.append(_issue(
                issue_class="SOURCE_CIRCUIT_OPEN", project=None, subject=name,
                source="collector_health", evidence_ref=f"collector_health:{name}",
                first_seen=updated or None, last_seen=updated or None, occurrences=1,
                magnitude={"openUntil": float(open_until),
                           "consecutiveFailures": int(row.get("consecutive_failures") or 0)},
                detail=f"collector={name} 熔断窗口未关闭"))
        failures = int(row.get("consecutive_failures") or 0)
        if failures > 0:
            issues.append(_issue(
                issue_class="SOURCE_FAILURE", project=None, subject=name,
                source="collector_health", evidence_ref=f"collector_health:{name}",
                first_seen=str(row.get("last_success_at") or "") or None,
                last_seen=updated or None, occurrences=failures,
                magnitude={"consecutiveFailures": failures, "totalRuns": int(row.get("total_runs") or 0)},
                detail=f"collector={name} 连续失败 {failures} 次"))
        refused = int(row.get("refused_rows") or 0)
        if refused > 0:
            issues.append(_issue(
                issue_class="SOURCE_REFUSAL", project=None, subject=name,
                source="collector_health", evidence_ref=f"collector_health:{name}",
                first_seen=str(row.get("last_run_at") or "") or None,
                last_seen=updated or None, occurrences=refused,
                magnitude={"refusedRows": refused, "deliveredRows": int(row.get("delivered_rows") or 0)},
                detail=_detail(row.get("last_refusal_reason")) or f"collector={name} 有行被拒绝"))
        dropped = int(row.get("dropped_count") or 0)
        if dropped > 0:
            issues.append(_issue(
                issue_class="SOURCE_DATA_DROPPED", project=None, subject=name,
                source="collector_health", evidence_ref=f"collector_health:{name}",
                first_seen=str(row.get("last_run_at") or "") or None,
                last_seen=updated or None, occurrences=dropped,
                magnitude={"droppedCount": dropped, "deliveredRows": int(row.get("delivered_rows") or 0)},
                detail=f"collector={name} 丢弃 {dropped} 行"))
    return issues


def _group_by_source(rows: list[dict[str, Any]]) -> dict[tuple[str | None, str], list[dict[str, Any]]]:
    """Rows per (project, producer), oldest first -- the newest row is the only present-tense claim.

    The loop below used to emit an anomaly for every historical row, so a producer whose every later reading
    was healthy kept raising `SOURCE_INCOMPLETE_COVERAGE` forever: the shipped store carried a 2026-10-19
    PARTIAL row as a standing issue that no repair could close, which also made an independent re-read
    unable to answer RESOLVED. Recency now decides whether the producer is in the state at all, while the
    older anomalous rows still set `firstSeenAt` and the occurrence count -- history is folded, not dropped.
    """
    grouped: dict[tuple[str | None, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("project_id") or "") or None, str(row.get("producer") or "") or "UNKNOWN")
        grouped.setdefault(key, []).append(row)
    for entries in grouped.values():
        entries.sort(key=lambda row: str(row.get("occurred_at") or ""))
    return grouped


def _latest_is_anomalous(entries: list[dict[str, Any]], field: str, vocabulary: tuple[str, ...]) -> bool:
    """Whether the readings at the newest timestamp still show the anomaly.

    Recency gates the claim; it does not aggregate it. Every anomalous row is still emitted as its own
    candidate so `_ordered_unique` remains the single place folding happens -- pre-folding here would make
    the fold read as zero occurrences, which is a bug this module's own comment warned about and a test
    still catches. What changes is only that a producer whose newest readings are healthy stops claiming
    a present-tense problem: the shipped store carried a 2026-10-19 PARTIAL row as an issue no repair could
    ever close, so an independent re-read could not answer RESOLVED.

    Rows tied at the newest timestamp are ALL current. Two readings that cannot be ordered do not license
    suppressing either one -- that would claim more knowledge about recency than the rows carry.
    """
    newest = max((str(row.get("occurred_at") or "") for row in entries), default="")
    return any(str(row.get(field) or "").upper() in vocabulary
               for row in entries if str(row.get("occurred_at") or "") == newest)


def _from_telemetry(rows: list[dict[str, Any]], index: dict[str, Any]) -> list[dict[str, Any]]:
    """Freshness and coverage per event — the honest "this reading is old / only partial" signal.

    The producer string is what gets asked of the identity index; a literal "UNKNOWN" is treated as no name,
    so it reports source-names-no-software instead of matching some product by luck.

    One candidate per event on purpose: folding happens only in ``_ordered_unique``, so `occurrences` and
    `foldedOccurrences` describe one mechanism everywhere. Aggregating here as well would report a fold that
    already happened as zero, and a denominator reading 0 when the truth is 2.
    """
    issues: list[dict[str, Any]] = []
    grouped = _group_by_source(rows)
    for row in rows:
        project = str(row.get("project_id") or "") or None
        producer = str(row.get("producer") or "") or "UNKNOWN"
        occurred = str(row.get("occurred_at") or "") or None
        freshness = str(row.get("freshness") or "").upper()
        coverage = str(row.get("coverage") or "").upper()
        evidence = f"telemetry:{row.get('event_id') or '?'}"
        software = _resolve_software(index, None if producer == "UNKNOWN" else producer)
        entries = grouped[(project, producer)]
        if freshness in STALE_FRESHNESS and _latest_is_anomalous(entries, "freshness", STALE_FRESHNESS):
            issues.append(_issue(
                issue_class="SOURCE_STALE", project=project, subject=f"{producer}:freshness",
                source="telemetry_events", evidence_ref=evidence,
                first_seen=occurred, last_seen=occurred, occurrences=1,
                magnitude={"freshness": freshness},
                detail=f"producer={producer} 读数新鲜度为 {freshness}", software=software))
        if coverage in INCOMPLETE_COVERAGE and _latest_is_anomalous(entries, "coverage", INCOMPLETE_COVERAGE):
            issues.append(_issue(
                issue_class="SOURCE_INCOMPLETE_COVERAGE", project=project, subject=f"{producer}:coverage",
                source="telemetry_events", evidence_ref=evidence,
                first_seen=occurred, last_seen=occurred, occurrences=1,
                magnitude={"coverage": coverage},
                detail=f"producer={producer} 覆盖为 {coverage}，读数只描述已采到的部分",
                software=software))
    return issues


def _from_executions(rows: list[dict[str, Any]], index: dict[str, Any]) -> list[dict[str, Any]]:
    """Stalled or conflicted executions, attributed to the agent the row itself names."""
    issues: list[dict[str, Any]] = []
    for row in rows:
        execution_id = str(row.get("execution_id") or "")
        if not execution_id:
            continue
        project = str(row.get("anchor_project_id") or "") or None
        updated = str(row.get("updated_at") or "") or None
        agent = str(row.get("agent") or "") or "UNKNOWN"
        software = _resolve_software(index, None if agent == "UNKNOWN" else agent)
        conflict = row.get("conflict_evidence")
        if conflict not in (None, "", [], {}):
            if isinstance(conflict, str):
                try:
                    conflict = json.loads(conflict)
                except (json.JSONDecodeError, TypeError):
                    conflict = _detail(conflict)
            issues.append(_issue(
                issue_class="EXECUTION_CONFLICT", project=project, subject=execution_id,
                source="execution_instances", evidence_ref=f"execution_instances:{execution_id}",
                first_seen=str(row.get("started_at") or "") or None, last_seen=updated,
                occurrences=1, magnitude={"conflictEvidence": conflict},
                detail=f"execution={execution_id} 带冲突证据", software=software))
        state = str(row.get("state") or "").upper()
        heartbeat = str(row.get("last_heartbeat_at") or "")
        transport = str(row.get("transport_state") or "").upper()
        if state in {"RUNNING", "ACTIVE"} and (not heartbeat or transport in {"STALE", "DISCONNECTED"}):
            issues.append(_issue(
                issue_class="EXECUTION_STALLED", project=project, subject=execution_id,
                source="execution_instances", evidence_ref=f"execution_instances:{execution_id}",
                first_seen=str(row.get("started_at") or "") or None, last_seen=updated,
                occurrences=1,
                magnitude={"state": state, "transportState": transport or "UNKNOWN",
                           "lastHeartbeatAt": heartbeat or None,
                           "stateQuality": str(row.get("state_quality") or "UNKNOWN")},
                detail=f"execution={execution_id} 状态为 {state} 但"
                       f"{'无心跳' if not heartbeat else '传输已过期'}", software=software))
    return issues


def _from_tasks(rows: list[dict[str, Any]], index: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "").upper()
        if status not in {"BLOCKED", "FAILED"}:
            continue
        task_id = str(row.get("task_id") or "")
        if not task_id:
            continue
        project = str(row.get("project_id") or "") or None
        updated = str(row.get("updated_at") or "") or None
        issues.append(_issue(
            issue_class="TASK_BLOCKED" if status == "BLOCKED" else "TASK_FAILED",
            project=project, subject=task_id, source="tasks",
            evidence_ref=f"tasks:{task_id}", first_seen=str(row.get("created_at") or "") or None,
            last_seen=updated, occurrences=1,
            magnitude={"status": status, "leaseHolder": str(row.get("lease_holder") or "") or None,
                       "fencingToken": row.get("fencing_token")},
            detail=f"task={task_id} 处于 {status}"))
    return issues


def _later(current: str | None, incoming: str | None) -> str | None:
    return incoming if incoming and (not current or _epoch(incoming) > _epoch(current)) else current


def _earlier(current: str | None, incoming: str | None) -> str | None:
    return incoming if incoming and (not current or _epoch(incoming) < _epoch(current)) else current


def _ordered_unique(issues: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Fold same-fingerprint issues into one row (summing occurrences, unioning magnitude), then order.

    The fold has to happen before the cap: truncating a list that still contains duplicates would spend
    seats on the same problem twice and report the omission count against the wrong total.
    """
    merged: dict[str, dict[str, Any]] = {}
    folded = 0
    for issue in issues:
        key = issue["fingerprint"]
        keep = merged.get(key)
        if keep is None:
            merged[key] = dict(issue)
            continue
        folded += 1
        keep["occurrences"] = int(keep["occurrences"]) + int(issue["occurrences"])
        for field, value in issue["magnitude"].items():
            keep["magnitude"].setdefault(field, value)
        keep["firstSeenAt"] = _earlier(keep["firstSeenAt"], issue["firstSeenAt"])
        keep["lastSeenAt"] = _later(keep["lastSeenAt"], issue["lastSeenAt"])
        if keep["origin"] != issue["origin"]:
            keep["origin"] = f"{keep['origin']}+{issue['origin']}"
    rows = list(merged.values())
    rows.sort(key=lambda item: (PRIORITY_RANK[item["priority"]], -_epoch(item["lastSeenAt"]),
                                item["fingerprint"]))
    return rows, folded


def project_issues(*, collector_health: list[dict[str, Any]] | None,
                   telemetry: list[dict[str, Any]] | None,
                   executions: list[dict[str, Any]] | None,
                   tasks: list[dict[str, Any]] | None,
                   software: list[dict[str, Any]] | None = None,
                   generated_at: str | None = None,
                   max_issues: int = MAX_ISSUES,
                   telemetry_limit: int | None = 5000) -> dict[str, Any]:
    """(issues, summary, absentReason). A source passed as None was not read and says so in the summary.

    Every argument is data the caller already read: this function performs no I/O, so "could not read the
    store" stays where it belongs (the composition root) instead of being re-decided here.
    """
    started = time.perf_counter()
    index = _software_index(software)
    sources = [
        ("collector_health", collector_health, _from_collector_health),
        ("telemetry_events", telemetry, _from_telemetry),
        ("execution_instances", executions, _from_executions),
        ("tasks", tasks, _from_tasks),
    ]
    per_source: list[dict[str, Any]] = []
    collected: list[dict[str, Any]] = []
    for name, rows, build in sources:
        if rows is None:
            per_source.append({"source": name, "state": "absent", "rowsScanned": None,
                               "issuesDerived": None})
            continue
        derived = build(rows, index)
        collected.extend(derived)
        per_source.append({"source": name, "state": "read", "rowsScanned": len(rows),
                           "issuesDerived": len(derived)})
    # The identity list is a source too: absent must be reportable, or `attributed: 0` would read as
    # "no problem belongs to any software" instead of "nothing was known about software".
    problem_sources = list(per_source)
    per_source.append({"source": "software",
                       "state": "read" if index["state"] == "read" else "absent",
                       "rowsScanned": len(index["byId"]) if index["state"] == "read" else None,
                       "issuesDerived": None})

    ordered, folded = _ordered_unique(collected)
    issues = ordered[:max_issues]
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)

    priority_counts = {p: sum(1 for item in issues if item["priority"] == p) for p in PRIORITY_RANK}
    truncated_scans = {"telemetry_events": bool(telemetry_limit is not None
                                                and telemetry is not None
                                                and len(telemetry) >= telemetry_limit)}
    summary = {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "generatedAt": generated_at or _now_iso(),
        "sources": per_source,
        "sourcesRead": sum(1 for item in per_source if item["state"] == "read"),
        "sourcesAbsent": sum(1 for item in per_source if item["state"] == "absent"),
        # Every denominator a reader needs to know what the list is NOT: rows scanned, distinct issues,
        # duplicates folded away, and the tail the cap dropped.
        "rowsScanned": sum(int(item["rowsScanned"] or 0) for item in per_source),
        "scanLimits": {"telemetry_events": telemetry_limit},
        "scanTruncated": truncated_scans,
        "distinctIssueCount": len(ordered),
        "emittedCount": len(issues),
        "omittedCount": max(0, len(ordered) - len(issues)),
        "foldedOccurrences": folded,
        "cap": int(max_issues),
        "truncated": bool(len(ordered) > len(issues)),
        "complete": bool(len(ordered) <= len(issues)
                         and all(item["state"] == "read" for item in problem_sources)
                         and not any(truncated_scans.values())),
        "priorityCounts": priority_counts,
        # Each emitted row lands in exactly one of these four buckets.
        "softwareAttribution": {
            "attributed": sum(1 for row in issues if row["softwareId"]),
            "unmatched": sum(1 for row in issues if row["softwareVersionSource"] == "unmatched"),
            "ambiguous": sum(1 for row in issues if row["softwareVersionSource"] == "ambiguous"),
            "unattributable": sum(1 for row in issues
                                  if row["softwareVersionSource"] in ("source-names-no-software",
                                                                      "identity-source-absent")),
            "versionKnown": sum(1 for row in issues if row.get("softwareVersion")),
            "identitySourceAbsent": index["state"] != "read",
        },
        "classesPresent": sorted({item["class"] for item in issues}),
        "classVocabulary": list(CLASSES),
        "projectsCovered": sorted({item["projectId"] for item in issues if item["projectId"]}),
        "unattributedCount": sum(1 for item in issues if not item["projectId"]),
        "order": ORDER_LABEL,
        "orderingKey": ORDERING_KEY,
        "orderingRule": "P1<P2<P3, then newest lastSeenAt, then fingerprint ascending",
        "derivationScope": "canonical-store-facts-only",
        "inferencePerformed": False,
        "contentIncluded": False,
        "cost": {"elapsedMs": elapsed_ms},
    }
    return {"issues": issues, "summary": summary, "absentReason": None}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_issue(row: dict[str, Any]) -> list[str]:
    """Machine checks the projection must pass on every emitted row; empty means clean."""
    problems: list[str] = []
    if row.get("schemaVersion") != ISSUE_SCHEMA_VERSION:
        problems.append("schemaVersion is not workflow/issue/v1")
    if not _HEX16.match(str(row.get("fingerprint") or "")):
        problems.append("fingerprint must be 16 hex chars (the blocker contract's shape)")
    if row.get("class") not in CLASSES:
        problems.append(f"class {row.get('class')!r} is outside the declared vocabulary")
    if row.get("priority") not in PRIORITY_RANK:
        problems.append(f"priority {row.get('priority')!r} is not P1/P2/P3")
    if not str(row.get("priorityRule") or ""):
        problems.append("every priority must carry the rule sentence that produced it")
    if not str(row.get("evidenceRef") or ""):
        problems.append("an issue without an evidenceRef cannot be re-checked by anyone")
    if int(row.get("occurrences") or 0) < 1:
        problems.append("occurrences must be at least 1; a zero-occurrence issue is an invented row")
    state = row.get("softwareVersionSource")
    if state not in SOFTWARE_STATES:
        problems.append(f"softwareVersionSource {state!r} is outside the attribution vocabulary")
    if row.get("softwareId") and state not in ("discovered", "not-discovered"):
        problems.append("a row attributed to a product must say how its version was obtained")
    if not row.get("softwareId") and row.get("softwareVersion"):
        problems.append("a version without a product identity is a fabricated linkage")
    return problems


def load_issues(store: Any, *, generated_at: str | None = None, max_issues: int = MAX_ISSUES,
                telemetry_limit: int = 5000,
                software_rows: list[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]] | None,
                                                      dict[str, Any] | None,
                                                      str | None]:
    """Composition-root entry point: (issues, summary, absentReason), never a crash on the read path.

    If NO source could be read the key is absent entirely (``(None, None, reason)``) — an empty list with a
    summary of four absent sources would still put a row-shaped claim in front of a reader who has none.

    ``software_rows`` are the identity rows the composition root already built (registry x discovery). They
    are injected because labelling a problem must never trigger install discovery; ``None`` means they were
    never built, and every row then reports identity-source-absent.
    """
    readers = (("collector_health", lambda: store.list_collector_health()),
               ("telemetry_events", lambda: store.list_telemetry_events(limit=telemetry_limit)),
               ("execution_instances", lambda: store.list_executions()),
               ("tasks", lambda: store.list_tasks()))
    read: dict[str, Any] = {}
    errors: list[str] = []
    for name, call in readers:
        try:
            read[name] = call()
        except Exception as error:  # noqa: BLE001 - a source that will not answer is a reported gap
            read[name] = None
            errors.append(f"{name}:{type(error).__name__}")
    if all(value is None for value in read.values()):
        reason = "no-source-readable"
        if errors:
            reason = f"{reason}:{','.join(errors)}"
        return None, None, reason
    try:
        projection = project_issues(collector_health=read["collector_health"],
                                    telemetry=read["telemetry_events"],
                                    executions=read["execution_instances"],
                                    tasks=read["tasks"], software=software_rows,
                                    generated_at=generated_at, max_issues=max_issues,
                                    telemetry_limit=telemetry_limit)
    except Exception as error:  # noqa: BLE001 - a junk column is a reported gap, never a dead read path
        return None, None, f"projection-error:{type(error).__name__}"
    if errors:
        projection["summary"]["sourceErrors"] = errors
    return projection["issues"], projection["summary"], projection["absentReason"]
