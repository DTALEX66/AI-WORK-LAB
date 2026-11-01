"""CL-06: reusable maintenance solutions, solidified from a repair that actually closed.

Three separations the module refuses to collapse:

1. **Verification is not solidification.** A repair record reaches SUCCEEDED only after an independent
   re-read answered RESOLVED (CL-05). `solidify_solution` is a second, explicit act on top of that: the
   caller supplies the reusable recipe (preconditions, steps, expected result, verification steps, when it
   stops being valid, risks and recovery), and the module refuses to mint a VERIFIED solution from any
   record that has not already closed.
2. **A revision is immutable.** Revision N's words are what every citation of N means. Corrections become
   revision N+1 with `supersedes` naming N; the store refuses an in-place edit and refuses a gap. The
   recommendation is a pointer at a revision, not content inside it.
3. **Search is local and dumb on purpose.** Keyword overlap over the stored text, no model call, no AAOS
   request. The result says which terms matched, which version the recipe was written for, and what limits
   the recipe itself declared -- so a hit on a different version reads as "review before use", not as a
   claim that it still applies.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

SOLUTION_SCHEMA_VERSION = "workflow/solution/v1"
SEARCH_SCHEMA_VERSION = "worklab/solution-search/v1"

STATUSES = ("VERIFIED", "UNVERIFIED")
VERSION_SOURCES = ("MEASURED", "DECLARED", "UNKNOWN")
SOURCE_KINDS = ("REPAIR_RECORD", "MANUAL")
MAX_RESULTS = 20

VERSION_SAME = "SAME_VERSION"
VERSION_CHANGED = "VERSION_CHANGED"
VERSION_UNKNOWN = "UNKNOWN"

UNKNOWN_VERSION_LIMIT = ("软件版本未记录（versionSource=UNKNOWN）：执行前先核对当前版本与适用性，"
                         "本方案不能证明在新版本上仍成立")

_ASCII_TERM = re.compile(r"[a-z0-9][a-z0-9._-]{1,}")
_CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")


def _terms(text: object) -> set[str]:
    """ASCII words (2+ chars) plus CJK bigrams.

    A bigram index is the cheapest way to make Chinese text findable without a segmenter, and it is a
    measured choice: `"缓存"` must hit `"清理缓存目录"`, and no model or word list is consulted.
    """
    lowered = str(text or "").lower()
    # The token class allows `.`, `_` and `-` inside a word (file names, kebab ids), which also swallows
    # the period at the end of a prose sentence: `denylist.` never matches the query `denylist`. Real
    # sentences only entered the library once ledger rows were folded, so the trailing-punctuation strip is
    # part of term extraction itself, applied to both the indexed text and the query, not to one side.
    terms = {token.strip("._-") for token in _ASCII_TERM.findall(lowered)}
    terms.discard("")
    for run in _CJK_RUN.findall(lowered):
        if len(run) == 1:
            terms.add(run)
        else:
            terms.update(run[index:index + 2] for index in range(len(run) - 1))
    return terms


def _document_text(document: Mapping[str, Any]) -> str:
    parts: list[str] = [str(document.get("title") or "")]
    for field in ("preconditions", "steps", "expected", "verificationSteps", "invalidWhen", "limits"):
        parts.extend(str(item) for item in document.get(field) or [])
    for risk in document.get("risks") or []:
        if isinstance(risk, Mapping):
            parts.extend(str(risk.get(key) or "") for key in ("risk", "recovery"))
    parts.extend(str(item) for item in document.get("keywords") or [])
    return "\n".join(parts)


def validate_solution(document: Mapping[str, Any],
                      *, schema: Mapping[str, Any] | None = None) -> list[str]:
    """Machine checks a solution must pass; empty means clean."""
    problems: list[str] = []
    if document.get("schemaVersion") != SOLUTION_SCHEMA_VERSION:
        problems.append(f"schemaVersion must be {SOLUTION_SCHEMA_VERSION}")
    solution_id = document.get("solutionId")
    if not isinstance(solution_id, str) or not re.fullmatch(r"sol-[a-z0-9-]{3,120}", solution_id):
        problems.append("solutionId must match ^sol-[a-z0-9-]{3,120}$")
    revision = document.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        problems.append("revision must be an integer >= 1")
    if not str(document.get("title") or "").strip():
        problems.append("title is required")
    if document.get("status") not in STATUSES:
        problems.append(f"status {document.get('status')!r} is outside {STATUSES}")
    software = document.get("software")
    if not isinstance(software, Mapping):
        problems.append("software is required")
    else:
        for field in ("softwareId", "softwareVersion", "platform"):
            if not isinstance(software.get(field), str):
                problems.append(f"software.{field} must be a string, even when it is empty")
        source = software.get("versionSource")
        if source not in VERSION_SOURCES:
            problems.append(f"software.versionSource {source!r} is outside {VERSION_SOURCES}")
        elif source == "UNKNOWN" and str(software.get("softwareVersion") or ""):
            problems.append("versionSource UNKNOWN contradicts a recorded version; say MEASURED or "
                            "DECLARED for a version someone actually wrote down")
        elif source in ("MEASURED", "DECLARED") and not str(software.get("softwareVersion") or ""):
            problems.append(f"versionSource {source} requires a softwareVersion")
    source_ref = document.get("source")
    if not isinstance(source_ref, Mapping):
        problems.append("source is required")
    else:
        if source_ref.get("kind") not in SOURCE_KINDS:
            problems.append(f"source.kind {source_ref.get('kind')!r} is outside {SOURCE_KINDS}")
        if not str(source_ref.get("ref") or "").strip():
            problems.append("source.ref is required: a recipe has to say where it came from")
        if not str(source_ref.get("updatedAt") or "").strip():
            problems.append("source.updatedAt is required")
    for field, minimum in (("steps", 1), ("verificationSteps", 1)):
        values = document.get(field)
        if not isinstance(values, list) or len(values) < minimum:
            problems.append(f"{field} needs at least {minimum} entr{'y' if minimum == 1 else 'ies'}")
        elif any(not isinstance(item, str) or not item.strip() for item in values):
            problems.append(f"{field} entries must be non-empty strings")
    for field in ("preconditions", "expected", "invalidWhen", "limits"):
        values = document.get(field)
        if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
            problems.append(f"{field} must be a list of strings")
    risks = document.get("risks")
    if not isinstance(risks, list):
        problems.append("risks must be a list")
    else:
        for risk in risks:
            if not isinstance(risk, Mapping) or not str(risk.get("risk") or "").strip() \
                    or not str(risk.get("recovery") or "").strip():
                problems.append("every risk needs both a risk and a recovery")
    keywords = document.get("keywords")
    if not isinstance(keywords, list) or not keywords:
        problems.append("keywords needs at least one entry: a recipe nobody can find is not reused")
    elif len(set(map(str, keywords))) != len(keywords):
        problems.append("keywords must be unique")
    elif any(not isinstance(item, str) or len(item.strip()) < 2 for item in keywords):
        problems.append("keywords entries must be strings of at least 2 characters")
    if not isinstance(document.get("recommended"), bool):
        problems.append("recommended must be a boolean")
    supersedes = document.get("supersedes")
    if supersedes is not None:
        if not isinstance(supersedes, Mapping) or not isinstance(supersedes.get("solutionId"), str) \
                or not isinstance(supersedes.get("revision"), int):
            problems.append("supersedes must be null or {solutionId, revision}")
    if not str(document.get("changes") or "").strip():
        problems.append("changes is required: what this revision changed is part of the revision")
    for field in ("evidenceRefs", "issueRefs"):
        values = document.get(field)
        if not isinstance(values, list) or any(not isinstance(item, str) or not item for item in values):
            problems.append(f"{field} must be a list of non-empty strings")
        elif len(set(values)) != len(values):
            problems.append(f"{field} must not repeat an entry")
    if schema is not None:
        from jsonschema import Draft202012Validator
        for error in Draft202012Validator(schema).iter_errors(document):
            problems.append(f"violates workflow/solution/v1: {error.message}")
    return problems


def load_schema(path: Path | str | None = None) -> dict[str, Any]:
    if path is None:
        path = (Path(__file__).resolve().parents[3] / "packages" / "contracts" / "schemas"
                / "workflow" / "solution.schema.json")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_solution(*, solution_id: str, title: str, software: Mapping[str, Any],
                   source: Mapping[str, Any], steps: Iterable[str],
                   verification_steps: Iterable[str], keywords: Iterable[str],
                   changes: str, revision: int = 1, status: str = "UNVERIFIED",
                   preconditions: Iterable[str] = (), expected: Iterable[str] = (),
                   invalid_when: Iterable[str] = (), risks: Iterable[Mapping[str, str]] = (),
                   limits: Iterable[str] = (), evidence_refs: Iterable[str] = (),
                   issue_refs: Iterable[str] = (),
                   supersedes: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Assemble one revision. No I/O; `solidify_solution` is what binds it to a closed record."""
    limit_list = [str(item) for item in limits]
    if software.get("versionSource") == "UNKNOWN" and UNKNOWN_VERSION_LIMIT not in limit_list:
        limit_list.append(UNKNOWN_VERSION_LIMIT)
    return {
        "schemaVersion": SOLUTION_SCHEMA_VERSION,
        "solutionId": solution_id,
        "revision": revision,
        "title": title,
        "status": status,
        "software": dict(software),
        "source": dict(source),
        "preconditions": [str(item) for item in preconditions],
        "steps": [str(item) for item in steps],
        "expected": [str(item) for item in expected],
        "verificationSteps": [str(item) for item in verification_steps],
        "invalidWhen": [str(item) for item in invalid_when],
        "risks": [{"risk": str(item.get("risk") or ""), "recovery": str(item.get("recovery") or "")}
                  for item in risks],
        "limits": limit_list,
        "evidenceRefs": list(dict.fromkeys(str(item) for item in evidence_refs)),
        "issueRefs": list(dict.fromkeys(str(item) for item in issue_refs)),
        "keywords": list(dict.fromkeys(str(item) for item in keywords)),
        "recommended": False,
        "supersedes": None if supersedes is None else dict(supersedes),
        "changes": changes,
    }


def solidify_solution(store: Any, plan_id: str, document: Mapping[str, Any],
                      *, schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Bind a recipe document to a repair record that already closed, then store it as a revision.

    Refusals are named and happen before the write: a recipe minted from a repair nobody verified would
    be indistinguishable from one that was, and that distinction is the feature.
    """
    problems = validate_solution(document, schema=schema)
    if problems:
        raise ValueError("SOLUTION_INVALID " + "; ".join(problems))
    if document.get("status") != "VERIFIED":
        raise ValueError("SOLUTION_NOT_VERIFIED solidify mints only VERIFIED material; import unverified "
                         "notes through the MANUAL route instead of reusing this one")
    row = store.read_action_plan(plan_id)
    if row is None:
        raise ValueError(f"SOLUTION_RECORD_NOT_FOUND plan {plan_id}")
    payload = row.get("payload")
    if not isinstance(payload, Mapping) or payload.get("schemaVersion") != "worklab/repair-record/v1":
        raise ValueError(f"SOLUTION_RECORD_UNREADABLE plan {plan_id} is not a repair record")
    if row.get("status") != "SUCCEEDED":
        raise ValueError(f"SOLUTION_RECORD_NOT_SUCCEEDED plan {plan_id} is {row.get('status')}; "
                         "verification and solidification are separate steps")
    verifications = list(payload.get("verifications") or [])
    resolved = [entry for entry in verifications if entry.get("outcome") == "RESOLVED"]
    if not resolved:
        raise ValueError(f"SOLUTION_NO_RESOLVED_VERIFICATION plan {plan_id} has no RESOLVED re-read; "
                         "a recipe cannot be solidified from an unverified repair")
    verification = resolved[-1]
    verification_id = str(verification.get("verificationId") or "")
    expected_ref = f"action_plan:{plan_id}#verification:{verification_id}"
    source = document.get("source") or {}
    if source.get("kind") != "REPAIR_RECORD" or source.get("ref") != expected_ref:
        raise ValueError(f"SOLUTION_SOURCE_MISMATCH solidify from a closed record must cite "
                         f"source.kind=REPAIR_RECORD and source.ref={expected_ref!r}")
    pack = payload.get("pack") or {}
    binds = pack.get("binds") or {}
    bound_fingerprints = [str(item) for item in binds.get("issueFingerprints") or []]
    if sorted(map(str, document.get("issueRefs") or [])) != sorted(bound_fingerprints):
        raise ValueError("SOLUTION_ISSUE_REFS_MISMATCH issueRefs must be exactly the fingerprints the "
                         f"closed pack bound ({len(bound_fingerprints)} bound)")
    required_evidence = [str(item) for item in binds.get("evidenceRefs") or []]
    required_evidence.append(expected_ref)
    missing = [ref for ref in required_evidence if ref not in set(map(str, document.get("evidenceRefs") or []))]
    if missing:
        raise ValueError(f"SOLUTION_EVIDENCE_MISSING the recipe omits {len(missing)} evidence ref(s) the "
                         f"closed pack carried, first: {missing[0]!r}")
    saved = store.save_solution({
        "solutionId": document["solutionId"],
        "revision": int(document["revision"]),
        "title": document["title"],
        "status": document["status"],
        "softwareId": (document.get("software") or {}).get("softwareId"),
        "softwareVersion": (document.get("software") or {}).get("softwareVersion"),
        "platform": (document.get("software") or {}).get("platform"),
        "keywords": list(document.get("keywords") or []),
        "payload": dict(document),
    })
    changed = bool(saved.get("changed"))
    recommended = bool(saved.get("recommended"))
    if int(document["revision"]) == 1 and not recommended:
        saved = store.recommend_solution(str(document["solutionId"]), 1)
        recommended = True
    return {
        "schemaVersion": "worklab/solution-solidification/v1",
        "status": "SOLIDIFIED" if changed else "UNCHANGED",
        "solutionId": saved.get("solutionId"),
        "revision": saved.get("revision"),
        "recommended": recommended,
        "verificationId": verification_id,
        "verificationOutcome": verification.get("outcome"),
        "evidenceLevel": verification.get("evidenceLevel"),
        "sourceRef": expected_ref,
        "contentIncluded": False,
    }


def import_unverified(store: Any, document: Mapping[str, Any],
                      *, schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Store material that has NOT been through a WORK-LAB re-read.

    This is the other half of "verified and unverified are different": the imported note keeps
    `status=UNVERIFIED`, a `source.kind=MANUAL` ref, and is never auto-recommended. Promotion is a new
    revision produced by `solidify_solution` after a record actually closes -- there is no in-place flip.
    """
    problems = validate_solution(document, schema=schema)
    if problems:
        raise ValueError("SOLUTION_INVALID " + "; ".join(problems))
    if document.get("status") != "UNVERIFIED":
        raise ValueError("SOLUTION_IMPORT_ONLY_UNVERIFIED import stores notes nobody re-read; a VERIFIED "
                         "document must come from solidify_solution and a closed repair record")
    if (document.get("source") or {}).get("kind") != "MANUAL":
        raise ValueError("SOLUTION_SOURCE_MISMATCH imported material must cite source.kind=MANUAL")
    saved = store.save_solution({
        "solutionId": document["solutionId"],
        "revision": int(document["revision"]),
        "title": document["title"],
        "status": document["status"],
        "softwareId": (document.get("software") or {}).get("softwareId"),
        "softwareVersion": (document.get("software") or {}).get("softwareVersion"),
        "platform": (document.get("software") or {}).get("platform"),
        "keywords": list(document.get("keywords") or []),
        "payload": dict(document),
    })
    return {"schemaVersion": "worklab/solution-import/v1",
            "status": "IMPORTED" if saved.get("changed") else "UNCHANGED",
            "solutionId": saved.get("solutionId"), "revision": saved.get("revision"),
            "documentStatus": saved.get("status"), "recommended": bool(saved.get("recommended")),
            "contentIncluded": False}


def documents_from_error_ledger(ledger: Mapping[str, Any], *, ledger_ref: str,
                                ) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Fold closed error-ledger rows into UNVERIFIED recipe documents.

    Every field is a quotation of a recorded field or a statement about the record itself; nothing here
    supplies a step, a version or a platform the ledger did not write down. Rows missing the two things a
    recipe cannot be read without -- what was done and how it was re-checked -- are returned as skipped
    with the reason, because silently dropping them would make "253 folded" mean something else.
    """
    documents: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    generated_at = str(ledger.get("generated_at") or "").strip()
    for entry in ledger.get("errors") or []:
        if not isinstance(entry, Mapping):
            continue
        error_id = str(entry.get("error_id") or "").strip()
        if not error_id:
            skipped.append({"errorId": "(absent)", "reason": "no error_id to cite"})
            continue
        status_after = str(entry.get("status_after") or "")
        if status_after != "PASS":
            skipped.append({"errorId": error_id, "reason": f"status_after={status_after or '(absent)'}"})
            continue
        fix = str(entry.get("fix") or "").strip()
        regression = str(entry.get("regression_test") or "").strip()
        if not fix:
            skipped.append({"errorId": error_id, "reason": "no recorded fix"})
            continue
        if not regression:
            skipped.append({"errorId": error_id, "reason": "no recorded regression_test"})
            continue
        root_cause = str(entry.get("root_cause") or "").strip() or fix
        classification = str(entry.get("classification") or "").strip()
        phase = str(entry.get("phase") or "").strip().lower()
        entrypoint = str(entry.get("entrypoint") or "").strip()
        evidence_level = str(entry.get("evidence_level") or "").strip()
        boundary = str(entry.get("remaining_boundary") or "").strip()
        keywords: list[str] = []
        for candidate in (classification.lower(), phase,
                          *(_ASCII_TERM.findall(entrypoint.lower())[:4])):
            token = str(candidate or "").strip()
            if len(token) >= 2 and token not in keywords:
                keywords.append(token)
        if not keywords:
            keywords = ["error-ledger", classification.lower() or "unclassified"]
        issue_refs = [error_id]
        task_id = str(entry.get("task_id") or "").strip()
        if task_id and task_id not in issue_refs:
            issue_refs.append(task_id)
        limits = [f"折入自错误台账 {error_id}：证据等级 {evidence_level or 'UNKNOWN'}，"
                  "台账未绑定修复提交（fixedCommit 缺失），本方案未经 WORK-LAB 复核"]
        documents.append(build_solution(
            solution_id=f"sol-{error_id.lower()}",
            title=root_cause,
            software={"softwareId": "work-lab", "softwareVersion": "", "platform": "",
                      "versionSource": "UNKNOWN"},
            source={"kind": "MANUAL", "ref": f"{ledger_ref}#{error_id}",
                    "updatedAt": generated_at or "UNKNOWN"},
            revision=1,
            status="UNVERIFIED",
            steps=[fix],
            verification_steps=[regression],
            invalid_when=([f"台账记录的剩余边界（原文）：{boundary}"] if boundary else []),
            limits=limits,
            evidence_refs=[f"{ledger_ref}#{error_id}"],
            issue_refs=issue_refs,
            keywords=keywords,
            changes=f"首版：由错误台账 {error_id}（status_after={status_after}）折入；"
                    "保持 UNVERIFIED，不自动推荐。",
        ))
    return documents, skipped


def fold_error_ledger(store: Any, *, ledger_path: Path, dry_run: bool = False,
                      limit: int | None = None,
                      schema: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Write each eligible ledger row as an UNVERIFIED revision, or report what would be written."""
    ledger = json.loads(Path(ledger_path).read_text(encoding="utf-8"))
    documents, skipped = documents_from_error_ledger(
        ledger, ledger_ref=Path(ledger_path).as_posix())
    selected = documents[:limit] if limit else documents
    result: dict[str, Any] = {
        "schemaVersion": "worklab/solution-fold/v1",
        "ledger": Path(ledger_path).as_posix(),
        "eligible": len(documents),
        "skipped": skipped,
        "selected": len(selected),
        "dryRun": bool(dry_run),
        "imported": 0,
        "unchanged": 0,
        "refused": [],
    }
    if dry_run:
        return result
    for document in selected:
        problems = validate_solution(document, schema=schema)
        if problems:
            result["refused"].append({"solutionId": document.get("solutionId"),
                                      "problems": problems})
            continue
        outcome = import_unverified(store, document, schema=schema)
        if outcome["status"] == "IMPORTED":
            result["imported"] += 1
        else:
            result["unchanged"] += 1
    return result


def _version_hint(software: Mapping[str, Any], current_version: str | None) -> dict[str, Any]:
    recorded = str(software.get("softwareVersion") or "")
    if not recorded or not current_version:
        return {"state": VERSION_UNKNOWN, "recordedVersion": recorded or None,
                "currentVersion": current_version or None,
                "message": "没有可比较的版本记录：执行前请自行核对适用性"}
    if recorded == str(current_version):
        return {"state": VERSION_SAME, "recordedVersion": recorded, "currentVersion": str(current_version),
                "message": "记录的版本与当前版本一致（以方案自报为准，不是本次实测）"}
    return {"state": VERSION_CHANGED, "recordedVersion": recorded, "currentVersion": str(current_version),
            "message": f"方案记录版本 {recorded}，当前版本 {current_version}：执行前先复核步骤是否仍适用"}


def search_solutions(rows: Iterable[Mapping[str, Any]], *, query: str = "",
                     software_id: str | None = None, current_version: str | None = None,
                     fingerprints: Iterable[str] = (), limit: int = MAX_RESULTS) -> dict[str, Any]:
    """Rank stored solutions by local keyword overlap; no model, no AAOS, no network."""
    rows = list(rows)
    terms = _terms(query)
    wanted_fingerprints = {str(item) for item in fingerprints}
    matched: list[dict[str, Any]] = []
    unreadable = 0
    for row in rows:
        document = row.get("payload")
        if not isinstance(document, Mapping):
            unreadable += 1
            continue
        software = document.get("software") or {}
        if software_id and str(software.get("softwareId") or "") != software_id:
            continue
        if terms:
            keyword_terms = set()
            for keyword in document.get("keywords") or []:
                keyword_terms |= _terms(keyword)
            title_terms = _terms(document.get("title"))
            body_terms = _terms(_document_text(document))
            matched_terms = sorted(terms & (keyword_terms | title_terms | body_terms))
            if not matched_terms:
                continue
            score = sum(3 if term in keyword_terms else 2 if term in title_terms else 1
                        for term in matched_terms)
        else:
            matched_terms, score = [], 0
        issue_refs = [str(item) for item in document.get("issueRefs") or []]
        issue_match = bool(wanted_fingerprints & set(issue_refs))
        matched.append({
            "solutionId": document.get("solutionId"),
            "revision": document.get("revision"),
            "title": document.get("title"),
            "status": document.get("status"),
            "recommended": bool(row.get("recommended")),
            "software": dict(software),
            "versionHint": _version_hint(software, current_version),
            "limits": list(document.get("limits") or []),
            "steps": list(document.get("steps") or []),
            "verificationSteps": list(document.get("verificationSteps") or []),
            "preconditions": list(document.get("preconditions") or []),
            "risks": list(document.get("risks") or []),
            "invalidWhen": list(document.get("invalidWhen") or []),
            "issueRefs": issue_refs,
            "evidenceRefs": list(document.get("evidenceRefs") or []),
            "source": dict(document.get("source") or {}),
            "score": score,
            "matchedTerms": matched_terms,
            "issueMatch": issue_match,
        })
    matched.sort(key=lambda item: (not item["issueMatch"], -int(item["score"]),
                                   not item["recommended"], -int(item["revision"] or 0),
                                   str(item["solutionId"])))
    returned = matched[:max(0, int(limit))]
    return {"results": returned, "summary": {
        "schemaVersion": SEARCH_SCHEMA_VERSION,
        "mode": "SEARCH" if terms else "BROWSE",
        "query": query,
        "terms": sorted(terms),
        "softwareFilter": software_id,
        "currentVersion": current_version,
        "solutionsRead": len(rows),
        "unreadable": unreadable,
        "matched": len(matched),
        "returned": len(returned),
        "cap": int(limit),
        "truncated": len(matched) > len(returned),
        "versionChangeWarnings": sum(1 for item in returned
                                     if item["versionHint"]["state"] == VERSION_CHANGED),
        "issueMatches": sum(1 for item in returned if item["issueMatch"]),
        "aaosRequired": False,
        "modelUsed": None,
        "inferencePerformed": False,
        "contentIncluded": False,
    }}


def store_view(store: Any, *, query: str = "", software_id: str | None = None,
               current_version: str | None = None, fingerprints: Iterable[str] = (),
               limit: int = MAX_RESULTS) -> dict[str, Any]:
    """The sidecar's read model. A read failure is typed, never an empty library."""
    try:
        rows = store.list_solutions()
    except Exception as error:  # noqa: BLE001 - the caller needs a typed answer, not a traceback
        return {"schemaVersion": SEARCH_SCHEMA_VERSION, "status": "SOURCE_ABSENT",
                "reason": f"方案库不可读：{type(error).__name__}", "query": query,
                "results": [], "summary": None}
    outcome = search_solutions(rows, query=query, software_id=software_id,
                               current_version=current_version, fingerprints=fingerprints,
                               limit=limit)
    summary = outcome["summary"]
    status = "OK" if summary["returned"] else ("EMPTY" if not summary["solutionsRead"] else "NO_MATCH")
    reason = {
        "OK": "已读取方案库并返回匹配结果；检索不使用模型，也不依赖 AAOS。",
        "EMPTY": "已读取方案库：库中没有已固化方案。这是实测的 0，不是缺字段。",
        "NO_MATCH": "已读取方案库：存在的方案都不匹配本次查询。",
    }[status]
    return {"schemaVersion": SEARCH_SCHEMA_VERSION, "status": status, "reason": reason,
            "query": query, "results": outcome["results"], "summary": summary}


def _render_line(item: Mapping[str, Any]) -> str:
    hint = (item.get("versionHint") or {}).get("state")
    return (f"SOLUTION {item.get('solutionId')} r{item.get('revision')} "
            f"status={item.get('status')} recommended={str(bool(item.get('recommended'))).lower()} "
            f"versionHint={hint} title={item.get('title')}")


def _print_fold(summary: Mapping[str, Any]) -> None:
    reasons: dict[str, int] = {}
    for item in summary["skipped"]:
        key = str(item["reason"]).split("=")[0]
        reasons[key] = reasons.get(key, 0) + 1
    print(f"SOLUTION_FOLD ledger={summary['ledger']} eligible={summary['eligible']} "
          f"selected={summary['selected']} dryRun={str(summary['dryRun']).lower()} "
          f"imported={summary['imported']} unchanged={summary['unchanged']} "
          f"refused={len(summary['refused'])} skipped={len(summary['skipped'])} "
          f"skipReasons={json.dumps(reasons, ensure_ascii=False, sort_keys=True)}")
    for item in summary["refused"][:5]:
        print(f"SOLUTION_FOLD_REFUSED {item['solutionId']} "
              f"{'; '.join(item['problems'][:3])}")


def main(argv: list[str] | None = None) -> int:
    """CLI over one canonical store. The store is never created here (see `repair_state`)."""
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("solidify", "import", "fold-ledger", "list", "search", "show"))
    parser.add_argument("--runtime-root", type=Path,
                        default=root / ".project-local" / "runs" / "issues-live-readback")
    parser.add_argument("--plan-id")
    parser.add_argument("--document", type=Path)
    parser.add_argument("--ledger", type=Path,
                        default=root / "taskpacks" / "current" / "error-ledger.json")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what fold-ledger would write; never touches the store")
    parser.add_argument("--solution-id")
    parser.add_argument("--revision", type=int)
    parser.add_argument("--query", default="")
    parser.add_argument("--software-id")
    parser.add_argument("--version")
    parser.add_argument("--fingerprint", action="append", default=[])
    parser.add_argument("--limit", type=int, default=MAX_RESULTS)
    parser.add_argument("--max", type=int,
                        help="fold-ledger only: cap the rows written (default: every eligible row)")
    args = parser.parse_args(argv)

    if args.command == "fold-ledger" and args.dry_run:
        if not args.ledger.is_file():
            print(f"SOLUTION_FOLD_LEDGER_MISSING {args.ledger}")
            return 3
        _print_fold(fold_error_ledger(None, ledger_path=args.ledger, dry_run=True,
                                      limit=args.max, schema=load_schema()))
        return 0

    db = args.runtime_root / "canonical.sqlite"
    if not db.is_file():
        print(f"SOLUTION_LIBRARY_NO_STORE {db} -- refusing to create a store and report an empty library")
        return 3
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from canonical_store import CanonicalStore

    store = CanonicalStore(db)
    try:
        if args.command == "solidify":
            if not (args.plan_id and args.document):
                parser.error("solidify requires --plan-id and --document")
            document = json.loads(args.document.read_text(encoding="utf-8"))
            result = solidify_solution(store, args.plan_id, document, schema=load_schema())
            print(f"SOLUTION_SOLIDIFIED status={result['status']} solution={result['solutionId']} "
                  f"revision={result['revision']} recommended={str(result['recommended']).lower()} "
                  f"verification={result['verificationId']} evidence={result['evidenceLevel']}")
            return 0
        if args.command == "import":
            if not args.document:
                parser.error("import requires --document")
            document = json.loads(args.document.read_text(encoding="utf-8"))
            result = import_unverified(store, document, schema=load_schema())
            print(f"SOLUTION_IMPORTED status={result['status']} solution={result['solutionId']} "
                  f"revision={result['revision']} documentStatus={result['documentStatus']} "
                  f"recommended={str(result['recommended']).lower()}")
            return 0
        if args.command == "fold-ledger":
            if not args.ledger.is_file():
                print(f"SOLUTION_FOLD_LEDGER_MISSING {args.ledger}")
                return 3
            summary = fold_error_ledger(store, ledger_path=args.ledger, limit=args.max,
                                        schema=load_schema())
            _print_fold(summary)
            return 0 if not summary["refused"] else 1
        if args.command == "list":
            outcome = store_view(store, limit=args.limit)
        elif args.command == "search":
            outcome = store_view(store, query=args.query, software_id=args.software_id,
                                 current_version=args.version, fingerprints=args.fingerprint,
                                 limit=args.limit)
        else:
            if not args.solution_id:
                parser.error("show requires --solution-id")
            row = store.read_solution(args.solution_id, args.revision)
            if row is None:
                print(f"SOLUTION_ABSENT solution {args.solution_id} revision {args.revision}")
                return 1
            print(json.dumps(row, ensure_ascii=False, indent=2))
            return 0
        for item in outcome["results"]:
            print(_render_line(item))
        summary = outcome["summary"]
        print(f"SOLUTION_SEARCH status={outcome['status']} mode={summary['mode']} "
              f"matched={summary['matched']} returned={summary['returned']} "
              f"truncated={str(summary['truncated']).lower()} "
              f"versionWarnings={summary['versionChangeWarnings']}")
        return 0
    except (ValueError, OSError) as error:
        print(f"SOLUTION_LIBRARY_REFUSED {error}")
        return 1
    finally:
        store.close()


if __name__ == "__main__":
    raise SystemExit(main())
