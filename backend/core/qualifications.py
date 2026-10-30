# SPDX-License-Identifier: MIT
"""Qualification ledger: `can_invoke` is earned by a probe record, never assumed.

Audit F10 was blunt — a pure function built the catalog from constants, a
SQLite file existing was enough to mark `core.projects` VERIFIED, and the FTS5
compile option was enough for knowledge search; `_derive` then handed
`can_invoke=true` to a capability whose authorization was still REQUIRED.
None of those observations said anything about the current candidate.

The rule this module implements instead:

* the six axes stay separate (implementation / qualification / connection /
  authorization / dependency / data_origin) and are never inferred from each
  other;
* `qualification` comes only from a probe record that names this capability,
  this operation, this permission scope, **this candidate version** and a
  freshness window that has not passed;
* a record written against a different candidate, expired, or carrying a
  synthetic origin cannot grant a live qualification — unknown is fail-closed;
* hosts, models and external executors stay NOT_PROBED / NOT_GRANTED. A local
  probe of the built-in surface must not be read as a probe of the host.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

LEDGER_SCHEMA_VERSION = "ai-work-lab/qualification-ledger/v1"
QUALIFICATIONS = ("VERIFIED", "NOT_VERIFIED", "FAILED", "EXPIRED", "NOT_PROBED")
CONNECTION_STATES = ("NOT_REQUIRED", "CONNECTED", "NOT_PROBED", "DISCONNECTED")
AUTHORIZATIONS = ("NOT_REQUIRED", "NOT_GRANTED", "GRANTED")
DEPENDENCIES = ("SATISFIED", "MISSING", "UNKNOWN")
DEPENDENCY_OBSERVATIONS = DEPENDENCIES
#: A probe may only ever speak for these; a host/model/executor capability is
#: qualified by a real host probe behind the Human Gate, which this build does not run.
LOCAL_PROBE_SCOPES = ("local_read", "local_roundtrip_scratch", "loopback_http")
#: How long one probe record is allowed to answer for the current candidate.
DEFAULT_TTL_SECONDS = 900

SUBJECT_ROOTS = ("backend", "domains", "scripts", "migration", "packages")
SUBJECT_SUFFIXES = (".py", ".json", ".csv", ".toml", ".yaml", ".yml", ".md")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def candidate_version(repo_root: Path) -> dict:
    """A version identity for the code actually being served right now.

    It is a digest over the tracked subject tree (path -> sha256), so a probe
    recorded against candidate A cannot silently qualify candidate B after an
    edit. This deliberately does not read Git: the candidate under audit is
    untracked working-tree code, and `git diff` says nothing about it.
    """
    repo_root = Path(repo_root).resolve()
    entries = {}
    for name in SUBJECT_ROOTS:
        base = repo_root / name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUBJECT_SUFFIXES:
                continue
            parts = set(path.relative_to(repo_root).parts)
            if {"__pycache__", ".venv", ".pytest_cache", ".mimosa", ".project-local"} & parts:
                continue
            try:
                entries[path.relative_to(repo_root).as_posix()] = hashlib.sha256(
                    path.read_bytes()).hexdigest()
            except OSError:
                entries[path.relative_to(repo_root).as_posix()] = "UNREADABLE"
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode("utf-8")).hexdigest()
    return {"digest": digest, "files": len(entries),
            "computed_at": _now().isoformat(timespec="seconds")}


class QualificationLedger:
    """Append-capable JSON ledger of probe records, one file per workspace."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[dict]:
        if not self.path.is_file():
            return []
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return []
        rows = document.get("records") if isinstance(document, dict) else None
        return rows if isinstance(rows, list) else []

    def append(self, record: dict) -> dict:
        rows = self.records()
        rows.append(record)
        payload = json.dumps({"schemaVersion": LEDGER_SCHEMA_VERSION, "records": rows},
                             ensure_ascii=False, indent=2)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.path)
        return record

    def latest_for(self, capability_id: str, operation: str) -> dict | None:
        matches = [row for row in self.records()
                   if row.get("capability_id") == capability_id
                   and row.get("operation") == operation]
        if not matches:
            return None
        return max(matches, key=lambda row: str(row.get("observed_at") or ""))


def probe_record(*, capability_id: str, operation: str, scope: str, subject: str,
                 version: dict, outcome: str, evidence_refs: list, detail: str,
                 data_origin: str, ttl_seconds: int = DEFAULT_TTL_SECONDS,
                 command: str = "", authorization: str = "NOT_REQUIRED",
                 connection: str = "NOT_REQUIRED", dependency: str = "SATISFIED") -> dict:
    if scope not in LOCAL_PROBE_SCOPES:
        raise ValueError("PROBE_SCOPE_REFUSED " + repr(scope) + " is not a locally probeable scope")
    if data_origin not in ("live", "test", "demo"):
        raise ValueError("DATA_ORIGIN_UNKNOWN " + repr(data_origin))
    observed = _now()
    return {
        "schemaVersion": LEDGER_SCHEMA_VERSION,
        "capability_id": capability_id,
        "operation": operation,
        "scope": scope,
        "subject": subject,
        "outcome": outcome,
        "observed_at": observed.isoformat(timespec="seconds"),
        "expires_at": (observed + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds"),
        "ttl_seconds": ttl_seconds,
        "candidate_digest": version["digest"],
        "candidate_files": version["files"],
        "command": command,
        "evidence_refs": list(evidence_refs),
        "detail": detail,
        "data_origin": data_origin,
        "authorization": authorization,
        "connection": connection,
        "dependency": dependency,
        "self_reported": False,
    }


def _expires(row: dict) -> datetime | None:
    """When this probe stops answering for the present. No window = no claim."""
    raw = row.get("expires_at") or row.get("observed_at")
    if not isinstance(raw, str):
        return None
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if not row.get("expires_at") and isinstance(row.get("ttl_seconds"), int):
        moment = moment + timedelta(seconds=row["ttl_seconds"])
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def derive(capability: dict, row, *, version: dict, now: datetime | None = None) -> dict:
    """Qualification and callability from one probe record — fail closed."""
    now = now or _now()
    reasons: list[str] = []
    implementation = capability.get("implementation", "DECLARED")
    authorization = capability.get("authorization", "NOT_REQUIRED")
    connection_need = capability.get("connection_state", "NOT_REQUIRED")
    # Dependency satisfaction is an observation, not a declaration: an accepted
    # probe record that named the dependency it checked speaks for it, and only
    # the *declared* UNKNOWN survives when nothing observed it.
    dependency = capability.get("dependency", "UNKNOWN")
    dependency_source = "declared"

    if implementation != "IMPLEMENTED":
        reasons.append("implementation=" + str(implementation))
    if authorization == "NOT_REQUIRED":
        authorization_state = "NOT_REQUIRED"
    elif authorization == "GRANTED":
        authorization_state = "GRANTED"
    else:
        authorization_state = authorization
        reasons.append("authorization=" + authorization + " (fail closed)")

    qualification = "NOT_PROBED"
    qualification_detail = "no probe record for this capability + operation"
    if row is None:
        reasons.append("qualification=NOT_PROBED")
    else:
        if row.get("candidate_digest") != version["digest"]:
            qualification = "EXPIRED"
            reasons.append("qualification=EXPIRED (probe was recorded against candidate "
                           + str(row.get("candidate_digest"))[:12] + "…, not the running "
                           + version["digest"][:12] + "…)")
            qualification_detail = "candidate version mismatch"
        elif _expires(row) is None or _expires(row) <= now:
            qualification = "EXPIRED"
            reasons.append("qualification=EXPIRED (probe freshness window has passed)")
            qualification_detail = "freshness window passed"
        elif row.get("data_origin") != "live":
            qualification = "NOT_VERIFIED"
            reasons.append("qualification=NOT_VERIFIED (probe origin is "
                           + repr(row.get("data_origin")) + "; a synthetic probe never "
                           "grants a live qualification)")
            qualification_detail = "synthetic probe origin"
        elif row.get("scope") not in LOCAL_PROBE_SCOPES:
            qualification = "NOT_VERIFIED"
            reasons.append("qualification=NOT_VERIFIED (unqualified probe scope)")
            qualification_detail = "probe scope not in vocabulary"
        elif row.get("outcome") != "VERIFIED":
            qualification = str(row.get("outcome"))
            reasons.append("qualification=" + qualification)
            qualification_detail = "probe outcome " + qualification
        else:
            qualification = "VERIFIED"
            qualification_detail = "probe record accepted"
            if row.get("dependency") in DEPENDENCY_OBSERVATIONS:
                dependency = row["dependency"]
                dependency_source = "observed by probe " + str(row.get("observed_at"))
            if row.get("connection") not in ("NOT_REQUIRED", "CONNECTED"):
                reasons.append("connection=" + str(row.get("connection")))
            if row.get("authorization") == "NOT_GRANTED":
                reasons.append("authorization=NOT_GRANTED")

    if dependency != "SATISFIED":
        reasons.append("dependency=" + dependency + " (" + dependency_source + ")")

    if connection_need not in ("NOT_REQUIRED", "CONNECTED"):
        reasons.append("connection=" + connection_need)

    can_invoke = not reasons and qualification == "VERIFIED"
    return {
        "qualification": qualification,
        "qualification_detail": qualification_detail,
        "authorization": authorization_state,
        "connection_state": row.get("connection") if (
            row is not None and qualification == "VERIFIED") else connection_need,
        "dependency": dependency,
        "dependency_source": dependency_source,
        "can_invoke": can_invoke,
        "unavailable_reasons": reasons,
        "probe": None if row is None else {
            "observed_at": row.get("observed_at"),
            "candidate_digest": row.get("candidate_digest"),
            "scope": row.get("scope"),
            "subject": row.get("subject"),
            "data_origin": row.get("data_origin"),
            "evidence_refs": row.get("evidence_refs"),
            "command": row.get("command"),
        },
    }


def scratch_roundtrip_probe(*, capability_id: str, operation: str, version: dict,
                            runner) -> dict:
    """A probe that performs the operation on a scratch copy and reads it back.

    `runner(scratch_path)` must return ``(ok: bool, detail: str)``. The result is
    always `data_origin=test` — the subject is a fixture, not the user's store —
    so `derive` will never let it grant a live qualification. It exists to prove
    the machinery works, which is what a synthetic probe is allowed to prove.
    """
    with tempfile.TemporaryDirectory(prefix="aiwl-probe-") as temp_dir:
        scratch = Path(temp_dir) / "subject.sqlite3"
        try:
            ok, detail = runner(scratch)
        except Exception as exc:  # noqa: BLE001 - a failed probe is a finding, not a crash
            ok, detail = False, type(exc).__name__ + ": " + str(exc)[:200]
    return probe_record(capability_id=capability_id, operation=operation,
                        scope="local_roundtrip_scratch", subject=str(scratch.name),
                        version=version, outcome="VERIFIED" if ok else "FAILED",
                        evidence_refs=["probe:" + capability_id + "/scratch-roundtrip"],
                        detail=detail, data_origin="test")


def loopback_http_probe(*, capability_id: str, operation: str, version: dict,
                        base_url: str, path: str, command: list[str],
                        token: str) -> dict:
    """A probe that really issues the loopback request through a separate process.

    Origin is live: the subject is the service this build is actually serving, and
    the evidence is the child process's own exit code and response bytes. The
    bearer token travels to the child on **stdin**, never in argv, a URL or a file —
    the same handshake rule the launcher follows, so earning this qualification does
    not leak the service token into a process list.
    """
    start = _now()
    try:
        proc = subprocess.run([sys.executable, "-B", "-c", _HTTP_SNIPPET, base_url + path]
                              + [str(x) for x in command], capture_output=True, timeout=30,
                              input=token + "\n", encoding="utf-8", errors="replace")
        ok = proc.returncode == 0
        detail = "child exit " + repr(proc.returncode) + " body " + (proc.stdout or "")[:200]
    except subprocess.TimeoutExpired:
        ok, detail = False, "probe timed out"
    end = _now()
    return probe_record(capability_id=capability_id, operation=operation,
                        scope="loopback_http", subject=base_url + path, version=version,
                        outcome="VERIFIED" if ok else "FAILED",
                        evidence_refs=["probe:" + capability_id + "/loopback"],
                        detail=detail + " window " + start.isoformat() + ".." + end.isoformat(),
                        data_origin="live", command=" ".join([sys.executable, "-B", "-c",
                                                              "<authenticated http get>",
                                                              base_url + path]))


_HTTP_SNIPPET = (
    "import sys,http.client,urllib.parse;"
    "t=sys.stdin.readline().strip();"
    "u=urllib.parse.urlsplit(sys.argv[1]);"
    "h={'Host':u.netloc,'Authorization':'Bearer '+t};"
    "c=http.client.HTTPConnection(u.hostname,u.port,timeout=10);"
    "c.request('GET',u.path or '/',headers=h);r=c.getresponse();"
    "b=r.read();print(r.status,len(b));sys.exit(0 if r.status==200 else 1)"
)
