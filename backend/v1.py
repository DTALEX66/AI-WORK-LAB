# SPDX-License-Identifier: MIT
"""The unified /api/v1 surface: Task/Attempt/Result/Verification envelope.

A delegate mounted into the migrated DESIGN-LAB server kernel: every request
here has already passed the kernel's Host/Origin/Sec-Fetch-Site/Bearer guard,
and refusals raise ``RequestError(status, code)`` so they travel the kernel's
error taxonomy. Design-domain reads delegate to the migrated design stores;
work-side pack lifecycle delegates to the migrated WORK-LAB machinery. This
module adds the envelope only — it owns no second state machine.

Key invariants implemented here (08_前后端交接约定.json, and the 2026-10-30
audit's F02/F03/F05/F07/F08/F10 rework):

* pack generation never declares a handoff; only POST handoff-declarations does,
  and it records the user's own statement (copiedByUser / userDeclaredHandoff);
* **both domains go through one result binding contract** before anything is
  stored. It used to be that only a work pack was validated, so a design result
  could name another project, another task, another attempt, a stale version,
  an all-zero digest and a traversing attachment and still be written with 201;
* a pinned revision is verified against **that stored revision**, not against
  ``detail()``'s newest row, and the digest compared is the same canonical
  content on both sides. "The plan exists" is no longer read as "revision 1
  matched";
* result received != task completed: technical verification runs server-side,
  and completion is computed by the store's ``completion_support`` — which reads
  the *newest* verdict per axis, so a later FAIL is not erased by an older PASS;
* professional acceptance resolves against the local human-approval ledger.
  A non-empty ``verifier_ref`` is no longer a person, and an agent, model or
  service reference is refused by name;
* client-asserted PASS is never accepted — outcomes are computed here;
* capability ``can_invoke`` comes from a probe record bound to this candidate
  version, not from a constant, a file existing or a compile option;
* data_origin is inherited down the chain and a caller cannot re-declare it
  upward — a synthetic project/task does not become live evidence mid-flight;
* improvement tasks answer their honest contract-only state.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# The migrated DESIGN-LAB package sits one directory deeper than the repository
# root, so it is reachable only through this explicit path (the same bootstrap
# backend/app.py performs). Repeating it here is not decoration: a clean
# `import backend.v1` died on `No module named 'design_lab'` because it relied on
# whoever imported it first having arranged sys.path — the same import-order
# dependency the audit reported for the WORK sidecar as F09. Anchored to this
# file, never to the current working directory, and idempotent.
_SELF_ROOT = Path(__file__).resolve().parents[1]
for _entry in (str(_SELF_ROOT), str(_SELF_ROOT / "domains" / "design")):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from backend.core import binding as binding_rules
from backend.core import origins as origin_rules
from backend.core import refs as ref_rules
from backend.core.capabilities import CATALOG_SPEC, derive_catalog
from backend.core.human_gate import ApprovalLedger, ApprovalError, validate_human_ref
from backend.core.qualifications import (CONNECTION_STATES, QualificationLedger,
                                         candidate_version, derive)
from backend.core.unified_store import (ATTEMPT_STATES, TASK_LIFECYCLE, TASK_KINDS,
                                        UnifiedStore, StoreError, DIGEST_V2)
from backend.core.workpacks import WorkPacks, WorkPackError


from design_lab.http_service import RequestError

#: Where a file reference in a result is allowed to resolve. The workspace's own
#: local root and its ``exports`` directory — never an arbitrary absolute path
#: and never a parent-directory hop out of the workspace.
EVIDENCE_ROOT_NAMES = (".project-local/ai-work-lab/evidence", "exports")

DESIGN_TARGET_VERSION_PREFIX = "plan-r"

#: Tool/connection declarations — identity, entry point and the ONE
#: capability/operation pair whose probe record speaks for the row.  No status
#: lives here, and that is the whole point: audit F10 was closed by making
#: capability qualification come from a record bound to the running candidate,
#: and this surface had regressed to exactly the shape that finding removed — a
#: hard-coded list whose ``CONNECTED_LOCAL`` was produced by no probe and no
#: store read, so ``test_v09_honesty`` could only ever compare a constant against
#: a constant.  Each row now reuses the ledger ``_v1_capabilities`` already reads
#: (``backend.core.qualifications`` via ``backend.core.probes``); no second store,
#: no new ledger, no new vocabulary.
#:
#: Nothing in this build ever records ``connection="CONNECTED"`` — the local read
#: probes observe ``NOT_REQUIRED`` and host/model/executor surfaces stay behind the
#: Human Gate at ``NOT_PROBED`` — so the honest answer of these two routes is
#: ``NOT_PROBED`` (or the value a real accepted record actually carries).  A
#: green label has to be earned by a record, and every row says which record it
#: looked for.
TOOL_SPEC = (
    {"tool_id": "design-lab-service", "role": "design domain runtime",
     "entry": "backend.app (this process)",
     "capability_id": "design.plans", "operation": "plans.read",
     "implementation": "IMPLEMENTED", "authorization": "NOT_REQUIRED",
     "dependency": "UNKNOWN",
     "note": "迁移的 DESIGN 运行时就在本进程服务；状态只由 design.plans 的探测记录决定"},
    {"tool_id": "work-repair-machinery", "role": "task pack lifecycle",
     "entry": "domains/work/workflow_core",
     "capability_id": "work.repair_packs", "operation": "repair_pack.lifecycle",
     "implementation": "IMPLEMENTED", "authorization": "REQUIRED",
     "dependency": "UNKNOWN",
     "note": "打包/审批/结果回写走迁移的 WORK 机器；本批未对其做任何连接探测"},
    {"tool_id": "work-observer-control", "role": "WORK read surfaces + gated control plane",
     "entry": "domains/work/control (mounted through backend.core.work_surfaces)",
     "capability_id": "work.observer.read_surface", "operation": "observer.snapshot_reads",
     "implementation": "IMPLEMENTED", "authorization": "NOT_REQUIRED",
     "dependency": "UNKNOWN",
     "note": "观察者只读面由 backend.core.probes 的 observer 探测作证；控制面授权仍是独立轴"},
    {"tool_id": "quality-gate", "role": "work verification gate",
     "entry": "work:services/orchestration/run_quality_gate.py (source anchor)",
     "capability_id": "work.quality_gate", "operation": "quality_gate.run",
     "implementation": "PARTIAL", "authorization": "REQUIRED",
     "dependency": "UNKNOWN",
     "note": "源锚点存在即已迁入；本仓没有为该门写过任何探测记录，所以它不会亮"},
)

CONNECTION_SPEC = (
    {"connection_id": "design-native-hosts", "tool_ref": "photoshop/illustrator(COM)",
     "capability_id": "design.native_hosts", "operation": "native_host.invoke",
     "implementation": "IMPLEMENTED", "authorization": "NOT_GRANTED",
     "dependency": "UNKNOWN",
     "note": "P2 逐次 Human Gate 后受控探测；本机宿主连接未探测，不因内置本地探测升格"},
    {"connection_id": "design-comfy", "tool_ref": "ComfyUI(HTTP)",
     "capability_id": "design.generative", "operation": "generative.invoke",
     "implementation": "IMPLEMENTED", "authorization": "NOT_GRANTED",
     "dependency": "UNKNOWN",
     "note": "不联网；本机生成服务未探测，生成能力与连接同属未取证"},
    {"connection_id": "work-adapters", "tool_ref": "config/adapter-registry.json",
     "capability_id": "work.executors", "operation": "executor.invoke",
     "implementation": "PARTIAL", "authorization": "NOT_GRANTED",
     "dependency": "UNKNOWN",
     "note": "适配器合同已迁入；执行器连接未探测"},
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


PROJECT_ID_PATTERN = r"([0-9a-f]{32})"
TASK_ID_PATTERN = r"([0-9a-f]{32})"
ATTEMPT_ID_PATTERN = r"([0-9a-f]{32})"
RESULT_ID_PATTERN = r"([0-9a-f]{32})"


def _routes():
    from design_lab.http_service import Route
    from backend.core.work_surfaces import WORK_SURFACE_ROUTES
    table = [
        Route("GET", "/api/v1/health", "_v1_health", exact=True),
        Route("GET", "/api/v1/projects", "_v1_list_projects", exact=True),
        Route("POST", "/api/v1/projects", "_v1_create_project", exact=True),
        Route("GET", "/api/v1/capabilities", "_v1_capabilities", exact=True),
        Route("GET", "/api/v1/qualification-evidence", "_v1_qualification_evidence", exact=True),
        Route("GET", "/api/v1/connections", "_v1_connections", exact=True),
        Route("GET", "/api/v1/tools", "_v1_tools", exact=True),
        Route("GET", "/api/v1/improvements", "_v1_improvements", exact=True),
        Route("GET", "/api/v1/tasks", "_v1_list_tasks", exact=True, path_only=True),
        Route("POST", "/api/v1/tasks", "_v1_create_task", exact=True),
        Route("GET", "/api/v1/tasks/" + TASK_ID_PATTERN, "_v1_get_task"),
        Route("GET", "/api/v1/tasks/" + TASK_ID_PATTERN + "/completion", "_v1_task_completion"),
        Route("POST", "/api/v1/tasks/" + TASK_ID_PATTERN + "/attempts", "_v1_create_attempt"),
        Route("GET", "/api/v1/attempts/" + ATTEMPT_ID_PATTERN, "_v1_get_attempt"),
        Route("POST", "/api/v1/attempts/" + ATTEMPT_ID_PATTERN + "/pack", "_v1_build_pack"),
        Route("POST", "/api/v1/attempts/" + ATTEMPT_ID_PATTERN + "/approval", "_v1_approve"),
        Route("POST", "/api/v1/attempts/" + ATTEMPT_ID_PATTERN + "/handoff-declarations",
              "_v1_declare_handoff"),
        Route("POST", "/api/v1/attempts/" + ATTEMPT_ID_PATTERN + "/results", "_v1_import_result"),
        Route("GET", "/api/v1/results/" + RESULT_ID_PATTERN, "_v1_get_result"),
        Route("POST", "/api/v1/results/" + RESULT_ID_PATTERN + "/verifications",
              "_v1_verify_result"),
        Route("GET", "/api/v1/knowledge/search", "_v1_knowledge_search", exact=True,
              path_only=True),
        Route("GET", "/api/v1/search", "_v1_search", exact=True, path_only=True),
        Route("GET", "/api/v1/integrity", "_v1_integrity", exact=True),
        Route("GET", "/api/v1/design/plans", "_v1_design_plans", exact=True, path_only=True),
        Route("GET", "/api/v1/design/plans/" + r"([a-z]+-[a-z0-9]+)" + r"/revisions/([0-9]+)",
              "_v1_design_plan_revision"),
        Route("GET", "/api/v1/design/target-profiles", "_v1_design_target_profiles", exact=True,
              path_only=True),
    ]
    return table + list(WORK_SURFACE_ROUTES)


V1_ROUTES = _routes()


def _reject(status, code):
    raise RequestError(status, code)


def _require(mapping, key, code):
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        _reject(400, code)
    return value.strip()


def _query_pairs(handler) -> list:
    """The raw ordered query pairs of this request, before any dict() collapses them.

    Ordered and un-collapsed on purpose: ``dict(parse_qsl(...))`` silently keeps the last of
    ``?x=1&x=2``, which is the same class of swallow as the un-named filter values this helper was
    written for.
    """
    from urllib.parse import parse_qsl, urlsplit
    return parse_qsl(urlsplit(handler.path).query, keep_blank_values=True)


#: The only query name ``GET /api/v1/tasks`` defines. Anything else is refused by name instead of
#: being ignored, and a blank value is not "no filter": both would answer the full task table to a
#: caller that believes it asked for one project (cloud audit N02). An unknown project answers the
#: same 404 the POST on this path already answers, because 200 plus an empty list cannot be told
#: apart from "this project exists and has no tasks yet" -- and the front end is required to show
#: the difference rather than render a swallowed error as "no tasks".
TASK_LIST_FILTER_NAMES = ("project_id",)

#: The two domains a project may be registered into, and the only two the store accepts
#: (``unified_store.register_project`` raises ``PROJECT_SOURCE_UNKNOWN`` for anything else). The
#: handler used to branch ``if source == "work": … else: design``, so every other word -- an
#: uppercase ``WORK``, a typo, a ``bogus`` that also forgot the work root -- landed a real project
#: in the design domain and answered 201. Refusing by name before either store is touched is the
#: whole fix. Case is not normalised -- ``WORK`` and ``Design`` are refused, not folded -- while the
#: outer whitespace ``_require`` already trims stays trimmed (``"  work  "`` registers as work,
#: measured): the store column, the design runtime's routing and the task packages all spell these
#: two words exactly, and inventing a third spelling here is what a caller has to guess next time.
PROJECT_SOURCES = ("work", "design")


def _professional_required(value: dict, acceptance: dict) -> bool:
    """Read the professional-acceptance requirement without inferring it.

    Two spellings are in use and both stay valid: the request's own ``professional_required`` -- the
    name of the store column and of the response key -- and the nested
    ``acceptance.professional_required`` that every existing caller already sends. The cloud audit
    (N03) measured the old behaviour: only the nested one was read, so a top-level ``true`` answered
    201 and was stored as ``0``. The same line also ran whatever it found through ``bool()``, and on
    this machine the string ``"false"`` measured ``1`` -- a requirement imposed on a caller who asked
    for none. A declared value therefore has to be a JSON boolean and the two spellings have to
    agree; only a task where neither appears falls back to the store's documented default.
    """
    declared = [("professional_required" in value, value.get("professional_required")),
                ("professional_required" in acceptance,
                 acceptance.get("professional_required"))]
    for present, item in declared:
        if present and not isinstance(item, bool):
            _reject(400, "PROFESSIONAL_REQUIRED_NOT_BOOLEAN")
    given = [item for present, item in declared if present]
    if len(set(given)) > 1:
        _reject(400, "PROFESSIONAL_REQUIRED_CONFLICT")
    return given[0] if given else False


def _input_refs(value: dict) -> list:
    """The task's declared structured references, or a named refusal.

    Measured before this guard: the caller's ``input_refs`` was passed through only when it was
    already a list, and every other shape -- a string, a dict, ``null`` -- answered 201 with ``[]``
    stored, so the references a pack was supposed to be built from vanished without a word. An
    absent key is a real empty list; a declared non-list is a shape nobody asked to be guessed.
    """
    if "input_refs" not in value:
        return []
    refs = value["input_refs"]
    if not isinstance(refs, list):
        _reject(400, "TASK_INPUT_REFS_NOT_ARRAY")
    for ref in refs:
        if not isinstance(ref, dict):
            _reject(400, "TASK_INPUT_REF_NOT_OBJECT")
        kind = ref.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            _reject(400, "TASK_INPUT_REF_KIND_MISSING")
    return refs


class V1API:
    """Delegate handlers; each receives (kernel_handler, route_match)."""

    def __init__(self, *, design_service, unified: UnifiedStore, work: WorkPacks,
                 knowledge_factory, plans_factory, profiles_factory, version: str,
                 approvals: ApprovalLedger, qualifications: QualificationLedger,
                 repo_root: Path, local_root: Path, workspace_root: Path,
                 data_mode: str = "live"):
        self.design_service = design_service
        self.unified = unified
        self.work = work
        self.approvals = approvals
        self.qualifications = qualifications
        self.repo_root = Path(repo_root)
        self.local_root = Path(local_root)
        self.workspace_root = Path(workspace_root)
        self._knowledge_factory = knowledge_factory
        self._plans_factory = plans_factory
        self._profiles_factory = profiles_factory
        self.version = version
        self.data_mode = data_mode
        self.started_at = _now()
        self._candidate: dict | None = None
        self._probes_run = False

    # -- helpers ---------------------------------------------------------------
    def candidate(self) -> dict:
        """The version identity of the code actually serving this request."""
        if self._candidate is None:
            self._candidate = candidate_version(self.repo_root)
        return self._candidate

    def evidence_roots(self) -> list[Path]:
        roots = [self.local_root]
        roots.extend(self.workspace_root / name for name in EVIDENCE_ROOT_NAMES)
        return [root for root in roots]

    def _task_or_404(self, task_id):
        task = self.unified.get_task(task_id)
        if task is None:
            _reject(404, "TASK_NOT_FOUND")
        return task

    def _attempt_or_404(self, attempt_id):
        attempt = self.unified.get_attempt(attempt_id)
        if attempt is None:
            _reject(404, "ATTEMPT_NOT_FOUND")
        return attempt

    def _attempt_of_task(self, attempt, task):
        if attempt["task_id"] != task["task_id"]:
            _reject(409, "ATTEMPT_WRONG_TASK")

    def _work_project(self, task):
        """The work project binding a task's pack must point at a registered root."""
        for ref in task["input_refs"]:
            if isinstance(ref, dict) and ref.get("kind") == "work_project":
                project = self.unified.get_project(str(ref.get("project_id") or ""))
                if project is None:
                    _reject(409, "PROJECT_NOT_REGISTERED")
                return project
        _reject(409, "WORK_PROJECT_REF_MISSING")

    def _design_ref(self, task):
        design_project_id = None
        plan_id = None
        for ref in task["input_refs"]:
            if isinstance(ref, dict) and ref.get("kind") == "design_plan_ref":
                design_project_id = str(ref.get("design_project_id") or "")
                plan_id = str(ref.get("plan_id") or "")
        return design_project_id, plan_id

    def _declared_result_ids(self, scope: str) -> list[str]:
        """The ids already imported against THIS pack, across attempts.

        Scoped by the pack identity rather than by the attempt so a retry that
        answers the same pinned pack cannot import the same result twice — and not
        scoped wider than that, because a different pack is a different question.
        """
        if not scope:
            return []
        return [row["declared_result_id"] for row in self.unified.list_results()
                if row["declared_result_id"] and (row["pack_id"] or "") == scope]

    def _binding_facts(self, task, attempt):
        """Server-side facts a result document is compared against.

        Nothing in here comes from the request. That is the point: the audit's
        design counterexample carried self-reported ids and a self-reported
        version, and the old code stored them.
        """
        pack_ref = attempt["pack_ref"] or {}
        handoff = attempt["handoff"] or {}
        plan_revision = pack_ref.get("plan_revision")
        # A work pack has a durable record id; a design pack does not, but it is
        # still *named* by the plan revision it pins. Storing that as the pack
        # identity is what lets a duplicate result id be caught across attempts —
        # keying on the attempt's own binding digest would not, because a retry
        # mints a new binding by construction.
        pack_identity = (attempt["pack_plan_id"]
                         or ("design-pack:" + str(pack_ref.get("plan_id") or "")
                             + ":r" + str(plan_revision)))
        return {
            "task_id": task["task_id"],
            "project_id": task["project_id"],
            "attempt_id": attempt["attempt_id"],
            "pack_id": pack_identity,
            "design_project_id": pack_ref.get("design_project_id")
                                 or self._design_ref(task)[0] or "",
            "plan_id": pack_ref.get("plan_id") or self._design_ref(task)[1] or "",
            "plan_revision": pack_ref.get("plan_revision"),
            "plan_content_sha256": pack_ref.get("plan_content_sha256") or "",
            "binding_sha256": attempt["binding_sha256"] or pack_ref.get("binding_sha256") or "",
            "revision_policy": pack_ref.get("revision_policy") or "LATEST_AT_PACK",
            "handoff_target_version": handoff.get("target_version"),
            "handoff_declared_at": handoff.get("declared_at"),
            "existing_result_ids": self._declared_result_ids(pack_identity),
            "project_origin": (self.unified.get_project(task["project_id"]) or {}).get("data_origin"),
            "task_origin": task["data_origin"],
            "attempt_origin": attempt["data_origin"],
            "handoff_origin": attempt["data_origin"],
            "pack_origin": attempt["data_origin"],
            "candidate_version": attempt["candidate_version"] or self.candidate()["digest"],
        }

    # -- health & catalogs ------------------------------------------------------
    def _v1_health(self, handler, match):
        handler.guard()
        issues, _summary, absent_reason = self.work.issues_now()
        version = self.candidate()
        return handler.send_json(200, {
            "service": "ai-work-lab",
            "version": self.version,
            "data_mode": self.data_mode,
            "started_at": self.started_at,
            "design_api": "migrated design_lab http_service",
            "unified_store": str(self.unified.path),
            "work_store": str(self.work.store.path if hasattr(self.work.store, "path") else "canonical"),
            "work_issue_source": ("readable" if issues is not None
                                  else "absent:" + repr(absent_reason)),
            "candidate_version": {"digest": version["digest"], "files": version["files"],
                                  "computed_at": version["computed_at"]},
            "envelope": "08_前后端交接约定.json v1-draft",
            "envelope_rework": "2026-10-30 audit F02/F03/F04/F05/F07/F08/F10",
        })

    def _v1_list_projects(self, handler, match):
        projects = []
        for project in self.unified.list_projects():
            projects.append(project)
        design_projects = self.design_service.list_projects()
        return handler.send_json(200, {
            "unified": projects,
            "design_runtime": design_projects,
        })

    def _v1_create_project(self, handler, match):
        handler.guard()
        value = handler.body(fields={"name", "source"}, optional={"root_path", "data_origin"},
                             limit=16384)
        source = _require(value, "source", "PROJECT_SOURCE_REQUIRED")
        if source not in PROJECT_SOURCES:
            _reject(400, "PROJECT_SOURCE_UNKNOWN")
        name = _require(value, "name", "PROJECT_NAME_REQUIRED")
        declared = value.get("data_origin")
        if declared is None or declared == "":
            declared = "live"
        elif not isinstance(declared, str):
            # Measured before this line existed: a list reached origin_rules.check() and left the
            # process answering 500 INTERNAL, while an integer answered 400 by accident of the
            # exception text. A value that is not a word is a refusal, never a crash.
            _reject(400, "DATA_ORIGIN_UNKNOWN")
        try:
            origin_rules.check(declared)
        except origin_rules.OriginError as exc:
            _reject(400, str(exc).split(" ")[0])
            return
        root_path = value.get("root_path")
        if source == "work":
            if not isinstance(root_path, str) or not root_path.strip():
                _reject(400, "WORK_PROJECT_ROOT_REQUIRED")
            root = Path(root_path.strip())
            if not root.is_dir():
                _reject(400, "WORK_PROJECT_ROOT_MISSING")
            # The root only has to exist; whether the *origin* is real is settled by
            # the chain, not by this call. A project labelled test stays test all the
            # way down and can never be promoted later, so pointing a synthetic
            # project at a real checkout (what a read-only probe does) cannot turn a
            # fixture into live evidence.
            project = self.unified.register_project(source="work", display_name=name,
                                                    root_path=str(root), data_origin=declared)
        else:
            design_project = self.design_service.create_project(name)
            project = self.unified.register_project(source="design", display_name=name,
                                                    root_path=design_project["id"],
                                                    data_origin=declared)
        return handler.send_json(201, project)

    def _v1_capabilities(self, handler, match):
        handler.guard()
        version = self.candidate()
        ledger = self.qualifications
        # probe_runner is deliberately absent: a GET must not be the thing that
        # records a qualification. backend/app.build_workspace runs the read probes
        # once when the process starts, and this handler reports what those records
        # already say — which is why a long-lived process can honestly report
        # EXPIRED once a probe's freshness window has passed.
        catalog = derive_catalog(spec=CATALOG_SPEC, version=version, ledger=ledger,
                                 design_routes=89,
                                 work_store_ok=bool(getattr(self.work.store, "path", None))
                                                 and Path(self.work.store.path).exists(),
                                 unified_store_ok=self.unified.path.exists())
        return handler.send_json(200, {
            "capabilities": catalog,
            "count": len(catalog),
            "candidate_version": version["digest"],
            "qualification_rule": "can_invoke is derived from a probe record bound to this "
                                  "candidate version; no constant, file existence or compile "
                                  "option grants it",
        })

    def _v1_qualification_evidence(self, handler, match):
        handler.guard()
        rows = self.qualifications.records()
        version = self.candidate()["digest"]
        return handler.send_json(200, {
            "schemaVersion": "ai-work-lab/qualification-ledger/v1",
            "candidate_version": version,
            "records": [{**row, "matches_running_candidate": row.get("candidate_digest") == version}
                        for row in rows],
            "count": len(rows),
            "does_not_say": ["a record with a different candidate_digest or a passed freshness "
                             "window grants nothing",
                             "a record whose data_origin is test or demo can never be a live "
                             "qualification"],
        })

    def _probe_backed_surface(self, specs) -> list[dict]:
        """Project declared tool/connection rows from the qualification ledger.

        Same rule ``derive()`` already applies to capabilities, applied to the
        connection axis: the value comes from the newest probe record naming this
        capability + operation, and that record only answers for the candidate
        version it was written against, inside its freshness window, with a live
        origin.  An accepted record contributes the connection axis it actually
        observed; anything else — no record, foreign candidate, expired window,
        synthetic origin, FAILED outcome — leaves ``NOT_PROBED`` together with the
        reason ``derive`` produced.  There is no literal on this path to go stale.
        """
        version = self.candidate()
        rows = []
        for spec in specs:
            capability = {"capability_id": spec["capability_id"],
                          "operation": spec["operation"],
                          "implementation": spec["implementation"],
                          "authorization": spec["authorization"],
                          # The connection axis is projected below from the record
                          # itself; declaring NOT_REQUIRED here keeps ``derive`` from
                          # echoing a declared need back as a reason while the real
                          # reason is the qualification it could not accept.
                          "connection_state": "NOT_REQUIRED",
                          "dependency": spec["dependency"]}
            record = self.qualifications.latest_for(spec["capability_id"], spec["operation"])
            derived = derive(capability, record, version=version)
            observed = str((record or {}).get("connection") or "")
            accepted = derived["qualification"] == "VERIFIED"
            state = observed if (accepted and observed in CONNECTION_STATES) else "NOT_PROBED"
            reasons = list(derived["unavailable_reasons"])
            if accepted and observed not in CONNECTION_STATES:
                reasons.append("connection axis absent from the accepted probe record "
                               + repr(record.get("observed_at")))
            rows.append({
                **{key: value for key, value in spec.items()
                   if key in ("tool_id", "connection_id", "role", "tool_ref", "entry", "note")},
                "state": state,
                "qualification": derived["qualification"],
                "qualification_detail": derived["qualification_detail"],
                "authorization": derived["authorization"],
                "dependency": derived["dependency"],
                "dependency_source": derived["dependency_source"],
                "connection_observed_by_probe": observed or None,
                "unavailable_reasons": reasons,
                "candidate_version": version["digest"],
                "bound_capability": spec["capability_id"],
                "operation": spec["operation"],
                "evidence": None if record is None else {
                    **derived["probe"],
                    "expires_at": record.get("expires_at"),
                    "outcome": record.get("outcome"),
                    "connection": record.get("connection"),
                    "matches_running_candidate": record.get("candidate_digest") == version["digest"],
                },
                "declared_by": "backend.v1.TOOL_SPEC/CONNECTION_SPEC (declaration only, no status)",
            })
        return rows

    def _surface_payload(self, key: str, specs, what: str) -> dict:
        rows = self._probe_backed_surface(specs)
        return {key: rows, "count": len(rows),
                "state_rule": what + " state is read from the qualification-ledger record "
                                    "bound to this candidate version; no constant, file "
                                    "existence or compile option grants CONNECTED, and the "
                                    "default is NOT_PROBED with reasons",
                "candidate_version": self.candidate()["digest"]}

    def _v1_connections(self, handler, match):
        handler.guard()
        # Derived, not declared: what the ledger says about each connection's bound
        # capability, or NOT_PROBED with the reason.  Nothing on this path is a
        # literal, so a simulated connection success cannot read as a real one.
        return handler.send_json(200, self._surface_payload(
            "connections", CONNECTION_SPEC, "connection"))

    def _v1_tools(self, handler, match):
        handler.guard()
        return handler.send_json(200, self._surface_payload("tools", TOOL_SPEC, "tool"))

    def _v1_improvements(self, handler, match):
        handler.guard()
        # Honest answer: the improvement envelope exists as a data contract; no
        # executor, no activation, no self-modification this batch.
        return handler.send_json(200, {
            "status": "CONTRACT_ONLY",
            "implementation": "DECLARED",
            "activation_state": "UNAVAILABLE",
            "reason": "自身改写执行链按 P3 延期；候选/差异/验证/激活/回滚数据合同保留，本轮不接受执行请求",
            "contract_ref": "08_前后端交接约定.json#ImprovementCandidate",
        })

    def _v1_integrity(self, handler, match):
        handler.guard()
        # the attempt -> pack_plan_id hop lives across two stores; this process is the only
        # place that holds both readers, so it hands the plan reader to the report rather than
        # letting an unchecked link be reported as a clean one.
        report = self.unified.integrity_report(plan_reader=self.work.read_record)
        return handler.send_json(200, report)

    # -- tasks -----------------------------------------------------------------
    def _v1_list_tasks(self, handler, match):
        handler.guard()
        pairs = _query_pairs(handler)
        unknown = sorted({name for name, _ in pairs if name not in TASK_LIST_FILTER_NAMES})
        if unknown:
            _reject(400, "TASK_FILTER_PARAM_UNKNOWN")
        if sum(1 for name, _ in pairs if name == "project_id") > 1:
            _reject(400, "TASK_FILTER_PROJECT_ID_DUPLICATE")
        raw = dict(pairs).get("project_id")
        if raw is not None and not raw.strip():
            _reject(400, "TASK_FILTER_PROJECT_ID_EMPTY")
        project_id = raw.strip() if raw is not None else None
        if project_id is not None and self.unified.get_project(project_id) is None:
            _reject(404, "PROJECT_NOT_FOUND")
        return handler.send_json(200, {"tasks": self.unified.list_tasks(project_id=project_id)})

    def _v1_create_task(self, handler, match):
        handler.guard()
        value = handler.body(fields={"project_id", "kind", "title"},
                             optional={"input_refs", "acceptance", "professional_required"},
                             limit=262144)
        project_id = _require(value, "project_id", "TASK_PROJECT_REQUIRED")
        project = self.unified.get_project(project_id)
        if project is None:
            _reject(404, "PROJECT_NOT_FOUND")
        kind = _require(value, "kind", "TASK_KIND_REQUIRED")
        title = _require(value, "title", "TASK_TITLE_REQUIRED")
        acceptance = value.get("acceptance")
        if "acceptance" in value and not isinstance(acceptance, dict):
            # `null` is a declared non-document, not an absent key: measured, the old line answered
            # 201 for a string, a list, an integer and a boolean alike, storing `{}` each time.
            _reject(400, "TASK_ACCEPTANCE_NOT_OBJECT")
        acceptance = acceptance if isinstance(acceptance, dict) else {}
        professional_required = _professional_required(value, acceptance)
        declared = acceptance.get("data_origin", "live")
        try:
            origin_rules.check(declared)
        except origin_rules.OriginError:
            _reject(400, "DATA_ORIGIN_UNKNOWN")
            return
        policy = acceptance.get("revision_policy") or "LATEST_AT_PACK"
        if policy not in binding_rules.REVISION_POLICIES:
            _reject(400, "REVISION_POLICY_UNKNOWN")
            return
        try:
            task = self.unified.create_task(
                project_id=project_id, kind=kind, title=title,
                input_refs=_input_refs(value),
                acceptance=acceptance, professional_required=professional_required,
                data_origin=declared, candidate_version=self.candidate()["digest"])
        except StoreError as exc:
            _reject(400, str(exc).split(" ")[0])
            return
        return handler.send_json(201, task)

    def _v1_get_task(self, handler, match):
        handler.guard()
        return handler.send_json(200, self._task_or_404(match[1]))

    def _v1_task_completion(self, handler, match):
        """Why this task is or is not backed right now, in the store's own words."""
        handler.guard()
        task = self._task_or_404(match[1])
        support = self.unified.completion_support(task["task_id"])
        return handler.send_json(200, {**support, "lifecycle": task["lifecycle"],
                                       "historical_fact_note": "supported=False never erases that a "
                                                                "PASS was once recorded; the two "
                                                                "questions are separate"})

    def _v1_create_attempt(self, handler, match):
        handler.guard()
        task = self._task_or_404(match[1])
        value = handler.body(fields={"idempotency_key"},
                             optional={"execution_mode", "base_fingerprint", "data_origin"},
                             limit=16384)
        idempotency_key = _require(value, "idempotency_key", "IDEMPOTENCY_KEY_REQUIRED")
        execution_mode = value.get("execution_mode") or "MANUAL_COPY"
        base_fingerprint = str(value.get("base_fingerprint") or "")
        declared = value.get("data_origin")
        try:
            if declared is not None:
                declared = origin_rules.refuse_promotion(declared, task["data_origin"],
                                                        where="ATTEMPT")
        except origin_rules.OriginError as exc:
            _reject(409, str(exc).split(" ")[0])
            return
        try:
            attempt, created = self.unified.create_attempt(
                task["task_id"], idempotency_key=idempotency_key,
                execution_mode=execution_mode, base_fingerprint=base_fingerprint,
                data_origin=declared, candidate_version=self.candidate()["digest"])
        except StoreError as exc:
            _reject(400, str(exc).split(" ")[0])
            return
        if created:
            self.unified.set_task_lifecycle(task["task_id"], "ACTIVE",
                                            current_attempt_id=attempt["attempt_id"])
        status = 201 if created else 200
        return handler.send_json(status, self.unified.get_attempt(attempt["attempt_id"]))

    def _v1_get_attempt(self, handler, match):
        handler.guard()
        attempt = self._attempt_or_404(match[1])
        attempt["results"] = self.unified.list_results(attempt_id=attempt["attempt_id"])
        return handler.send_json(200, attempt)

    # -- pack ------------------------------------------------------------------
    def _v1_build_pack(self, handler, match):
        handler.guard()
        attempt = self._attempt_or_404(match[1])
        task = self._task_or_404(attempt["task_id"])
        self._attempt_of_task(attempt, task)
        if attempt["execution_state"] not in ("PREPARED",):
            _reject(409, "ATTEMPT_STATE " + repr(attempt["execution_state"]) + " cannot generate a pack")
        value = handler.body(fields={}, optional={"manual"}, limit=16384)
        if value.get("manual") is False:
            _reject(400, "ADAPTER_DISPATCH_NOT_ALLOWED 本轮禁止外部派发；仅支持 manual 人工任务包")
        if task["kind"] in ("work", "repair"):
            payload = self._build_work_pack(attempt, task)
        elif task["kind"] == "design":
            payload = self._build_design_pack(attempt, task)
        else:
            _reject(400, "PACK_KIND_UNSUPPORTED")
            return
        return handler.send_json(201, payload)

    def _build_work_pack(self, attempt, task):
        project = self._work_project(task)
        try:
            built = self.work.build_and_record_pack(
                project_id=project["project_id"], project_root=project["root_path"] or "")
        except WorkPackError as exc:
            _reject(409, str(exc).split(" ")[0])
            return
        pack = built["pack"]
        record = built["record"]
        pack_body = built["handoff_text"]
        binds = pack.get("binds") or {}
        binding_doc = binding_rules.work_binding_document(
            task_id=task["task_id"], project_id=project["project_id"],
            attempt_id=attempt["attempt_id"], pack_id=pack.get("packId") or "",
            pack_record_version=int(record.get("version") or 1),
            issue_fingerprints=list(binds.get("issueFingerprints") or []),
            target_version=str(pack.get("targetVersion") or record.get("targetVersion") or ""),
            candidate_version=self.candidate()["digest"])
        binding_sha256 = binding_rules.canonical_digest(binding_doc)
        pack_ref = {
            "flavor": "work_repair_pack",
            "pack_id": pack.get("packId"),
            "status": record.get("status"),
            "record_version": record.get("version"),
            "body_sha256": _sha256_text(pack_body),
            "body_chars": len(pack_body),
            "binding": binding_doc,
            "binding_sha256": binding_sha256,
            "issue_fingerprints": sorted(str(fp) for fp in (binds.get("issueFingerprints") or [])),
            "evidence_refs": sorted(str(ref) for ref in (binds.get("evidenceRefs") or [])),
        }
        attempt = self.unified.update_attempt(
            attempt["attempt_id"], execution_state="WAITING_HANDOFF",
            pack_plan_id=pack.get("packId"), pack_ref=pack_ref, binding_sha256=binding_sha256)
        self.unified.set_task_lifecycle(task["task_id"], "ACTIVE",
                                        current_attempt_id=attempt["attempt_id"])
        return {"attempt": attempt, "pack": pack, "handoff_text": pack_body,
                "note": "正文请人工复制给外部执行者；导出不产生接收确认，交接声明须由用户提交"}

    def _build_design_pack(self, attempt, task):
        design_project_id, plan_id = self._design_ref(task)
        if not design_project_id or not plan_id:
            _reject(409, "DESIGN_PLAN_REF_MISSING")
            return
        try:
            plans = self._plans_factory(self.design_service)
            detail = plans.detail(design_project_id, plan_id)
        except ValueError as exc:
            code = getattr(exc, "code", "DESIGN_PLAN_UNAVAILABLE")
            _reject(404 if code == "ASSISTANCE_PLAN_NOT_FOUND" else 400, code)
            return
        revision = detail.get("latest_revision") or detail.get("revision")
        # Pin the *stored revision row*, read back through the revision route that
        # itself refuses to serve bytes that no longer hash to their published
        # digest. This is the digest the pack binds; detail()'s newest row is not
        # the same object and is never compared against it again.
        try:
            pinned = plans.revision(design_project_id, plan_id, revision)
        except ValueError as exc:
            _reject(409, getattr(exc, "code", "DESIGN_PLAN_REVISION_UNAVAILABLE"))
            return
        target_bindings = self._pin_target_profiles(task)
        policy = str(task["acceptance"].get("revision_policy") or "LATEST_AT_PACK")
        binding_doc = binding_rules.design_binding_document(
            task_id=task["task_id"], project_id=task["project_id"],
            attempt_id=attempt["attempt_id"], design_project_id=design_project_id,
            plan_id=plan_id, plan_revision=pinned["revision"],
            plan_content_sha256=pinned["content_sha256"], target_bindings=target_bindings,
            revision_policy=policy,
            acceptance_ref_digest=binding_rules.canonical_digest(task["acceptance"]),
            candidate_version=self.candidate()["digest"])
        binding_sha256 = binding_rules.canonical_digest(binding_doc)
        body = json.dumps({
            "kind": "design_task_pack",
            "task_id": task["task_id"],
            "design_project_id": design_project_id,
            "plan_id": plan_id,
            "plan_revision": pinned["revision"],
            "plan_content_sha256": pinned["content_sha256"],
            "plan_document": pinned["document"],
            "target_bindings": target_bindings,
            "revision_policy": policy,
            "binding": binding_doc,
            "binding_sha256": binding_sha256,
            "delivery": task["acceptance"].get("delivery"),
            "acceptance": task["acceptance"],
            "target_version": DESIGN_TARGET_VERSION_PREFIX + str(pinned["revision"]),
            "statement": "本包为可复制正文与引用；执行在外部工具进行；导出不产生接收确认",
        }, ensure_ascii=False, indent=2, sort_keys=True)
        pack_ref = {
            "flavor": "design_task_pack",
            "design_project_id": design_project_id,
            "plan_id": plan_id,
            "plan_revision": pinned["revision"],
            "plan_content_sha256": pinned["content_sha256"],
            "latest_revision_at_pack": detail.get("latest_revision"),
            "target_bindings": target_bindings,
            "revision_policy": policy,
            "binding": binding_doc,
            "binding_sha256": binding_sha256,
            "body_sha256": _sha256_text(body),
            "body_chars": len(body),
        }
        attempt = self.unified.update_attempt(
            attempt["attempt_id"], execution_state="WAITING_HANDOFF", pack_ref=pack_ref,
            binding_sha256=binding_sha256)
        self.unified.set_task_lifecycle(task["task_id"], "ACTIVE",
                                        current_attempt_id=attempt["attempt_id"])
        return {"attempt": attempt, "pack_body": body, "pack_ref": pack_ref}

    def _pin_target_profiles(self, task) -> list[dict]:
        """Resolve every target-profile reference to the row this pack answers.

        A reference that does not address one real profile is a refusal, not a
        silently dropped entry: a "versioned target combination" that quietly lost
        a member is how an unbound pack gets built. A reference addresses a
        profile by ``profile_id`` or by the config's own ``profile_key``; a prose
        hint such as ``software_ref`` is not an address and never resolves.
        """
        profiles = self._profiles_factory(self.design_service)
        bindings: list[dict] = []
        for ref in task["input_refs"]:
            if not isinstance(ref, dict) or ref.get("kind") != "target_profile_ref":
                continue
            profile_id = str(ref.get("profile_id") or "").strip()
            if not profile_id:
                profile_key = str(ref.get("profile_key") or "").strip()
                if profile_key:
                    profile_id = self._seed_profile_id(profile_key)
                    if profile_id is None:
                        _reject(409, "TARGET_PROFILE_KEY_UNKNOWN " + repr(profile_key)
                                + " is not a profile_key in the tracked config")
                        return []
                else:
                    _reject(409, "TARGET_PROFILE_REF_UNRESOLVED a target_profile_ref carries "
                                 "neither profile_id nor profile_key; the pack cannot pin a member "
                                 "of the combination it names, and a prose hint is not an address")
                    return []
            try:
                document = profiles.detail(profile_id)
            except ValueError as exc:
                _reject(409, getattr(exc, "code", "TARGET_PROFILE_UNRESOLVED"))
                return []
            bindings.append({
                "profile_id": profile_id,
                "revision": document.get("revision"),
                "content_sha256": document.get("content_sha256"),
                "origin": document.get("origin"),
                "declared_version": document.get("version"),
            })
        return sorted(bindings, key=lambda row: str(row["profile_id"]))

    @staticmethod
    def _seed_profile_id(profile_key: str) -> str | None:
        from design_lab.target_profile import load_seeds, _seed_id
        for seed in load_seeds():
            if seed.get("profile_key") == profile_key:
                return _seed_id(profile_key)
        return None

    # -- approval / handoff ------------------------------------------------------
    def _v1_approve(self, handler, match):
        handler.guard()
        attempt = self._attempt_or_404(match[1])
        task = self._task_or_404(attempt["task_id"])
        if task["kind"] not in ("work", "repair"):
            _reject(400, "APPROVAL_WORK_ONLY")
            return
        if not attempt["pack_plan_id"]:
            _reject(409, "ATTEMPT_HAS_NO_PACK")
        value = handler.body(fields={"authorization_ref", "expected_version"}, limit=16384)
        try:
            record = self.work.approve(
                attempt["pack_plan_id"],
                authorization_ref=_require(value, "authorization_ref", "GRANT_REF_REQUIRED"),
                expected_version=int(value["expected_version"]))
        except (WorkPackError, ValueError) as exc:
            _reject(409, str(exc).split(" ")[0] if str(exc) else "WORK_APPROVAL_REFUSED")
            return
        return handler.send_json(200, {"record": record})

    def _v1_declare_handoff(self, handler, match):
        handler.guard()
        attempt = self._attempt_or_404(match[1])
        task = self._task_or_404(attempt["task_id"])
        if attempt["execution_state"] != "WAITING_HANDOFF":
            _reject(409, "ATTEMPT_STATE " + repr(attempt["execution_state"])
                    + " is not WAITING_HANDOFF")
        value = handler.body(fields={"claim", "target_version", "actor"},
                             optional={"channel", "claimed_recipient", "expected_version"},
                             limit=16384)
        claim = _require(value, "claim", "CLAIM_REQUIRED")
        target_version = _require(value, "target_version", "TARGET_VERSION_REQUIRED")
        # An omitted actor used to default to "user" -- a live human -- which is the label the
        # synthetic-on-live guard below reads, so the default disarmed the guard.
        actor = _require(value, "actor", "HANDOFF_ACTOR_REQUIRED")
        declared_version = value.get("expected_version")
        if "expected_version" in value and (isinstance(declared_version, bool)
                                            or not isinstance(declared_version, int)
                                            or declared_version < 1):
            _reject(400, "HANDOFF_EXPECTED_VERSION_INVALID")
            return
        if claim not in ("copiedByUser", "userDeclaredHandoff"):
            _reject(400, "CLAIM_UNKNOWN")
            return
        if origin_rules.is_synthetic(actor_role_of(actor)) and attempt["data_origin"] == "live":
            _reject(409, "HANDOFF_ACTOR_SYNTHETIC_ON_LIVE a simulated actor cannot declare a handoff "
                         "against a live attempt; create the attempt as test/demo instead")
        if attempt["pack_plan_id"]:
            current_record = self.work.read_record(attempt["pack_plan_id"]) or {}
            try:
                record = self.work.declare_handoff(
                    attempt["pack_plan_id"], claim=claim,
                    expected_version=(declared_version if declared_version is not None
                                      else int(current_record.get("version") or 1)),
                    target_version=target_version,
                    channel=value.get("channel"),
                    claimed_recipient=value.get("claimed_recipient"))
            except (WorkPackError, ValueError) as exc:
                _reject(409, str(exc).split(" ")[0] if str(exc) else "WORK_HANDOFF_REFUSED")
                return
        else:
            record = None
        handoff = {"claim": claim, "target_version": target_version, "channel": value.get("channel"),
                   "actor": actor, "declared_at": _now(),
                   "actor_origin": actor_role_of(actor),
                   "work_record_version": (record or {}).get("version")}
        attempt = self.unified.update_attempt(attempt["attempt_id"],
                                              execution_state="HANDOFF_DECLARED",
                                              handoff=handoff)
        return handler.send_json(200, {"attempt": attempt, "work_record": record,
                                       "note": "交接声明是用户操作；测试夹具模拟须标记 data_origin=test"})

    # -- results & verification ---------------------------------------------------
    def _v1_import_result(self, handler, match):
        """One entry point, one contract, both domains — and no partial write.

        Every problem is collected first. Nothing is stored, and the attempt is
        not advanced, until the document binds to the server's own facts.
        """
        handler.guard()
        attempt = self._attempt_or_404(match[1])
        task = self._task_or_404(attempt["task_id"])
        if attempt["execution_state"] != "HANDOFF_DECLARED":
            _reject(409, "ATTEMPT_STATE " + repr(attempt["execution_state"])
                    + " has no declared handoff to answer")
        if not attempt["pack_ref"]:
            _reject(409, "ATTEMPT_HAS_NO_PACK_REF a result must answer a pinned pack")
        value = handler.body(fields={"result", "data_origin"}, limit=262144)
        data_origin = _require(value, "data_origin", "DATA_ORIGIN_REQUIRED")
        try:
            origin_rules.check(data_origin)
        except origin_rules.OriginError:
            _reject(400, "DATA_ORIGIN_UNKNOWN")
            return
        result_doc = value.get("result")
        if not isinstance(result_doc, dict):
            _reject(400, "RESULT_DOCUMENT_REQUIRED")
        facts = self._binding_facts(task, attempt)
        try:
            effective_origin = origin_rules.refuse_promotion(data_origin, origin_rules.combine(
                facts["task_origin"], facts["attempt_origin"], facts["pack_origin"],
                facts["project_origin"]), where="RESULT")
        except origin_rules.OriginError as exc:
            _reject(409, str(exc).split(" ")[0])
            return
        problems = self._result_problems(result_doc, task, attempt, facts)
        if problems:
            _reject(422, problems[0].split(" ")[0])
            return
        content_sha256 = binding_rules.canonical_digest(result_doc)
        binding = {
            "task_id": facts["task_id"], "attempt_id": facts["attempt_id"],
            "project_id": facts["project_id"], "pack_id": facts["pack_id"],
            "flavor": (attempt["pack_ref"] or {}).get("flavor"),
            "plan_id": facts["plan_id"], "plan_revision": facts["plan_revision"],
            "plan_content_sha256": facts["plan_content_sha256"],
            "design_project_id": facts["design_project_id"],
            "binding_sha256": facts["binding_sha256"],
            "revision_policy": facts["revision_policy"],
            "handoff_target_version": facts["handoff_target_version"],
            "handoff_declared_at": facts["handoff_declared_at"],
        }
        origin_chain = {"project": self.unified.get_project(task["project_id"])["data_origin"],
                        "task": facts["task_origin"], "attempt": facts["attempt_origin"],
                        "declared": data_origin, "effective": effective_origin}
        result = self.unified.record_result(
            task_id=task["task_id"], attempt_id=attempt["attempt_id"],
            pack_id=facts["pack_id"],
            declared_result_id=str(result_doc.get("resultId") or ""),
            subject_fingerprint=facts["binding_sha256"],
            artifact_refs=result_doc.get("evidenceRefs") or [],
            content_sha256=content_sha256, raw=result_doc, data_origin=effective_origin,
            binding=binding, candidate_version=self.candidate()["digest"],
            origin_chain=origin_chain, digest_vocabulary=DIGEST_V2)
        attempt = self.unified.update_attempt(attempt["attempt_id"],
                                              execution_state="RESULT_RECEIVED")
        return handler.send_json(201, {"result": result, "attempt": attempt,
                                       "staleness": binding_rules.staleness_assessment(
                                           result_doc, facts)})

    def _result_problems(self, result_doc, task, attempt, facts):
        """The shared half plus each domain's own validator. Ordered, all collected."""
        if (attempt["pack_ref"] or {}).get("flavor") == "design_task_pack":
            problems = binding_rules.validate_design_result(
                result_doc, facts, allowed_roots=self.evidence_roots())
        else:
            from domains.work.workflow_core import repair_verification
            existing = self._declared_result_ids(facts["pack_id"])
            problems = repair_verification.validate_external_result(
                result_doc, pack_id=facts["pack_id"], project_id=facts["project_id"],
                handoff={"targetVersion": facts["handoff_target_version"],
                         "declaredAt": facts["handoff_declared_at"]},
                existing_result_ids=existing)
            problems = problems + binding_rules.validate_work_envelope(
                result_doc, facts, allowed_roots=self.evidence_roots())
        return problems

    def _v1_get_result(self, handler, match):
        handler.guard()
        result = self.unified.get_result(match[1])
        if result is None:
            _reject(404, "RESULT_NOT_FOUND")
        return handler.send_json(200, result)

    def _v1_verify_result(self, handler, match):
        handler.guard()
        result = self.unified.get_result(match[1])
        if result is None:
            _reject(404, "RESULT_NOT_FOUND")
        value = handler.body(fields={"axis"},
                             optional={"professional_verdict", "verifier_ref", "approval_ref",
                                       "statement"},
                             limit=16384)
        axis = _require(value, "axis", "AXIS_REQUIRED")
        attempt = self.unified.get_attempt(result["attempt_id"])
        task = self.unified.get_task(result["task_id"])
        if axis == "technical":
            outcome, detail, evidence, checks, validity = self._technical_verification(
                result, attempt, task)
            verification = self.unified.record_verification(
                result_id=result["result_id"], axis="technical", outcome=outcome,
                subject_fingerprint=result["content_sha256"],
                command_ref="backend.v1 technical rules + migrated verify_repair_record",
                evidence_refs=evidence, detail=detail, checks=checks,
                current_validity=validity, candidate_version=self.candidate()["digest"],
                data_origin=result["data_origin"])
            # a PASS closes the work record with the verdict's own evidence; a FAIL
            # leaves it open — the retry path is a new attempt with a new pack
            if outcome == "PASS" and attempt["pack_plan_id"]:
                current = self.work.read_record(attempt["pack_plan_id"]) or {}
                if current.get("status") == "APPROVED":
                    try:
                        self.work.record_outcome(
                            attempt["pack_plan_id"], outcome="SUCCEEDED",
                            evidence_level="independent",
                            evidence_refs=["unified-verification:" + verification["verification_id"]],
                            expected_version=current.get("version"))
                    except (WorkPackError, ValueError) as exc:
                        _reject(409, str(exc).split(" ")[0] if str(exc) else "WORK_OUTCOME_REFUSED")
                        return
            state = self._maybe_complete(task, result)
            return handler.send_json(201, {**verification, "task_lifecycle_after": state})
        if axis == "professional":
            return self._v1_professional(handler, result, attempt, task, value)
        _reject(400, "AXIS_UNSUPPORTED 本批仅支持 technical/professional")

    def _v1_professional(self, handler, result, attempt, task, value):
        """Professional acceptance: a claim is stored, a human verdict is resolved.

        The submitter may state what they believe happened (that becomes a PENDING
        row with the claim kept). A PASS is only minted when the request names an
        approval id the local human-approval ledger resolves for exactly this
        result and these bytes — and even then the row records
        ``identity_state`` so nobody reads it as identity proofing.
        """
        verdict = value.get("professional_verdict")
        approval_ref = value.get("approval_ref")
        verifier_ref = value.get("verifier_ref")
        if verdict != "PASS":
            verification = self.unified.record_verification(
                result_id=result["result_id"], axis="professional", outcome="PENDING",
                subject_fingerprint=result["content_sha256"],
                detail="无人工评审：保持 PENDING，不以模型或自身总结替代",
                identity_state=None, data_origin=result["data_origin"])
            state = self._maybe_complete(task, result)
            return handler.send_json(201, {**verification, "task_lifecycle_after": state})
        if verifier_ref is not None:
            # Refuse a machine role even before looking for the approval, so the
            # error names the actual mistake in a forged request.
            try:
                validate_human_ref(verifier_ref)
            except ApprovalError as exc:
                _reject(409, str(exc).split(" ")[0])
                return
        if not approval_ref:
            _reject(409, "PROFESSIONAL_VERDICT_NEEDS_LOCAL_APPROVAL a named human verdict resolves "
                         "against scripts/human_approval.py; a verdict string alone is a submission "
                         "claim, not acceptance")
            return
        try:
            approval = self.approvals.resolve(str(approval_ref), result_id=result["result_id"],
                                              subject_fingerprint=result["content_sha256"])
        except ApprovalError as exc:
            _reject(409, str(exc).split(" ")[0])
            return
        effective = origin_rules.combine(approval["data_origin"], result["data_origin"])
        verification = self.unified.record_verification(
            result_id=result["result_id"], axis="professional", outcome="PASS",
            subject_fingerprint=result["content_sha256"],
            verifier_ref=approval["verifier_ref"], approval_ref=approval["approval_id"],
            identity_state=approval["identity_state"],
            evidence_refs=["approval:" + approval["approval_id"]],
            detail=approval["statement"], data_origin=effective,
            checks={"approval_resolved": True, "approval_origin": approval["data_origin"],
                    "identity_state": approval["identity_state"]})
        state = self._maybe_complete(task, result)
        return handler.send_json(201, {**verification, "task_lifecycle_after": state})

    def _technical_verification(self, result, attempt, task):
        """(outcome, detail, evidence, checks, current_validity).

        The work branch asks the migrated projection a factual question. The
        design branch re-reads **the revision the pack pinned** and compares the
        same canonical binding document on both sides. It never answers "the plan
        exists" in place of "revision N still hashes to what was pinned".
        """
        if attempt["pack_plan_id"]:
            pack_row = self.work.read_record(attempt["pack_plan_id"])
            if pack_row is None:
                # The pack row itself is gone. Handing an empty pack to the projection would
                # answer "the pack bound no fingerprint to re-check" -- a different fact, one that
                # hides which identifier dangled and reads as if a re-check had taken place. This
                # call site holds both stores, so it reports what it actually observed: no record.
                dangling = str(attempt["pack_plan_id"])
                return ("BLOCKED",
                        "pack_plan_id %s resolves to no action plan row; the bound fingerprints "
                        "were not re-read because there is no record to read them from" % dangling,
                        [],
                        {"pack_record_absent": True, "pack_plan_id": dangling,
                         "issue_projection_reread": False, "evidence_level": "none",
                         "fingerprints_present": 0, "fingerprints_absent": 0,
                         "sources_unanswered": []},
                        "UNVERIFIABLE")
            pack_payload = pack_row.get("payload") or {}
            pack = pack_payload.get("pack") or {}
            verdict = self.work.verify(pack)
            mapping = {"RESOLVED": "PASS", "UNRESOLVED": "FAIL", "UNVERIFIABLE": "BLOCKED"}
            outcome = mapping.get(verdict.get("outcome"), "BLOCKED")
            checks = {"issue_projection_reread": bool(verdict.get("readPerformed")),
                      "evidence_level": verdict.get("evidenceLevel"),
                      "fingerprints_present": len(verdict.get("fingerprintsPresent") or []),
                      "fingerprints_absent": len(verdict.get("fingerprintsAbsent") or []),
                      "sources_unanswered": verdict.get("sourcesUnanswered") or []}
            validity = "CURRENT" if outcome == "PASS" else "NOT_APPLICABLE"
            return outcome, verdict.get("reason"), [
                "work-issue-projection:" + verdict.get("verifiedAt", "")], checks, validity
        pack_ref = attempt["pack_ref"] or {}
        if pack_ref.get("flavor") == "design_task_pack":
            return self._design_technical(result, attempt, task, pack_ref)
        return ("BLOCKED", "无可执行技术规则", [], {"rule_present": False}, "UNVERIFIABLE")

    def _design_technical(self, result, attempt, task, pack_ref):
        plans = self._plans_factory(self.design_service)
        pinned_revision = pack_ref.get("plan_revision")
        pinned_digest = pack_ref.get("plan_content_sha256") or ""
        design_project_id = pack_ref.get("design_project_id")
        plan_id = pack_ref.get("plan_id")
        checks = {"pinned_revision": pinned_revision, "pinned_content_sha256": pinned_digest,
                  "revision_readback": None, "binding_recomputed": None,
                  "target_profiles_reread": None, "pinned_is_current": None}
        if not (design_project_id and plan_id and pinned_revision and pinned_digest):
            return ("BLOCKED", "打包时未固定方案修订或内容摘要，无法核验", [], checks, "UNVERIFIABLE")
        try:
            readback = plans.revision(design_project_id, plan_id, pinned_revision)
        except ValueError as exc:
            code = getattr(exc, "code", "DESIGN_PLAN_REVISION_UNAVAILABLE")
            checks["revision_readback"] = code
            outcome = "BLOCKED" if code in ("ASSISTANCE_PLAN_REVISION_UNREADABLE",
                                            "ASSISTANCE_PLAN_REVISION_BYTES_MOVED") else "FAIL"
            return (outcome, "固定修订读回失败：" + repr(code), [], checks, "UNVERIFIABLE")
        matches = readback.get("content_sha256") == pinned_digest
        checks["revision_readback"] = "read"
        checks["pinned_content_matches_readback"] = matches
        checks["pinned_is_current"] = bool(readback.get("is_latest"))
        # Recompute the binding from what the store says now, with the same
        # canonical serializer the pack used. Two vocabularies, compared once.
        current_binding = binding_rules.design_binding_document(
            task_id=task["task_id"], project_id=task["project_id"],
            attempt_id=attempt["attempt_id"], design_project_id=design_project_id,
            plan_id=plan_id, plan_revision=readback["revision"],
            plan_content_sha256=readback["content_sha256"],
            target_bindings=pack_ref.get("target_bindings") or [],
            revision_policy=pack_ref.get("revision_policy") or "LATEST_AT_PACK",
            acceptance_ref_digest=binding_rules.canonical_digest(task["acceptance"]),
            candidate_version=attempt["candidate_version"] or self.candidate()["digest"])
        recomputed = binding_rules.canonical_digest(current_binding)
        checks["binding_recomputed"] = recomputed
        binding_matches = recomputed == (attempt["binding_sha256"] or pack_ref.get("binding_sha256"))
        profiles_state = self._verify_target_profiles(pack_ref.get("target_bindings") or [])
        checks["target_profiles_reread"] = profiles_state
        evidence = ["design-plan-readback:" + str(plan_id) + ":r" + str(pinned_revision)]
        validity = binding_rules.current_validity(
            pinned_matches=matches and binding_matches,
            superseded=not readback.get("is_latest"),
            readable=True, revision_policy=pack_ref.get("revision_policy") or "LATEST_AT_PACK")
        if not (matches and binding_matches):
            return ("FAIL", "固定修订 " + repr(pinned_revision) + " 的读回摘要与打包固定值不一致；"
                            "被固定的内容/摘要/引用不符时不得判为通过", evidence, checks, validity)
        if profiles_state.get("mismatched"):
            return ("FAIL", "目标组合中 " + repr(profiles_state["mismatched"])
                            + " 个档案的读回摘要与打包固定值不一致", evidence, checks, "STALE")
        if validity == "SUPERSEDED":
            return ("BLOCKED", "固定修订 " + repr(pinned_revision) + " 精确读回且摘要一致，但方案已推进到"
                            "修订 " + repr(readback.get("latest_revision"))
                            + "；该任务按 LATEST_AT_PACK 判定当前不成立（历史事实保留，"
                            "如需按不可变旧修订验收请设 acceptance.revision_policy=IMMUTABLE_PIN）",
                    evidence, checks, validity)
        return ("PASS", "固定修订 " + repr(pinned_revision) + " 按同一规范化口径读回且摘要一致；"
                        "目标组合与绑定摘要均匹配", evidence, checks, validity)

    def _verify_target_profiles(self, bindings: list[dict]) -> dict:
        if not bindings:
            return {"read": 0, "mismatched": [], "note": "本包未固定任何目标档案"}
        profiles = self._profiles_factory(self.design_service)
        mismatched: list[str] = []
        for row in bindings:
            try:
                document = profiles.detail(row["profile_id"])
            except ValueError:
                mismatched.append(row["profile_id"] + ":UNREADABLE")
                continue
            if document.get("content_sha256") != row.get("content_sha256"):
                mismatched.append(row["profile_id"])
        return {"read": len(bindings), "mismatched": mismatched}

    def _maybe_complete(self, task, result):
        """Ask the store whether the chain backs COMPLETED *now*, then write it."""
        support = self.unified.completion_support(task["task_id"])
        if support["supported"]:
            try:
                self.unified.set_task_lifecycle(task["task_id"], "COMPLETED")
                return "COMPLETED"
            except StoreError:
                pass
        try:
            self.unified.set_task_lifecycle(task["task_id"], "ACTIVE")
        except StoreError:
            pass
        return "ACTIVE"

    # -- unified retrieval & design reads ---------------------------------------
    def _v1_knowledge_search(self, handler, match):
        handler.guard()
        return self._search(handler, include_knowledge=True)

    def _v1_search(self, handler, match):
        """The one unified retrieval surface both domains answer through."""
        handler.guard()
        return self._search(handler, include_knowledge=True)

    def _search(self, handler, *, include_knowledge: bool):
        params = self._query_params(handler)

        def number(name, default):
            raw = params.get(name)
            if raw is None or raw == "":
                return default
            try:
                return int(raw)
            except ValueError:
                raise RequestError(400, "KNOWLEDGE_FILTER_MALFORMED") from None

        # A blank filter here is a form field left empty, which asks the same question as omitting
        # it -- deliberately the opposite of the evidence-range route, where a blank digest pin is
        # a malformed claim rather than an absent one.
        query = params.get("q") or ""
        try:
            knowledge = self._knowledge_factory(self.design_service).search(
                query=query or None,
                entry_type=params.get("type") or None,
                domain=params.get("domain") or None,
                task=params.get("task") or None,
                target=params.get("target") or None,
                offset=number("offset", 0), limit=number("limit", 20))
        except ValueError as exc:
            raise RequestError(400, getattr(exc, "code", "KNOWLEDGE_QUERY_INVALID")) from None
        solutions = self._solution_search(query, limit=number("limit", 20))
        return handler.send_json(200, {
            "knowledge": knowledge if include_knowledge else None,
            "solutions": solutions,
            "content_types": {"knowledge": "design knowledge entry",
                              "solutions": "work maintenance solution"},
            "query": query,
            "hit_counts": {"knowledge": knowledge.get("total"),
                           "solutions": solutions.get("total")},
        })

    def _solution_search(self, query, *, limit: int = 20) -> dict:
        """Call the real WORK search read-model. A failure is typed, never an empty list.

        The audited bug was an adapter that asked for a ``solution_library.search``
        function that does not exist, threw it away, and reported
        ``unavailable`` over a result the store had already produced.
        ``store_view`` already returns a typed status; the honest move is to pass
        the query through and carry that status back.
        """
        from domains.work.control import solution_library
        try:
            view = solution_library.store_view(self.work.store, query=query or "", limit=limit)
        except Exception as exc:  # noqa: BLE001 - a read failure is reported, not swallowed
            return {"schemaVersion": solution_library.SEARCH_SCHEMA_VERSION,
                    "status": "READ_FAILED", "query": query,
                    "reason": "方案库读取抛出 " + type(exc).__name__ + "：" + str(exc)[:200],
                    "rows": [], "total": 0, "error_type": type(exc).__name__}
        rows = view.get("results") or []
        return {
            "schemaVersion": view.get("schemaVersion"),
            "status": view.get("status"),
            "reason": view.get("reason"),
            "query": view.get("query"),
            "rows": rows,
            "total": (view.get("summary") or {}).get("matched", len(rows)),
            "summary": view.get("summary"),
            "content_type": "work maintenance solution",
            "preserved_fields": ["solutionId", "revision", "status", "recommended", "source",
                                 "software", "versionHint", "matchedTerms", "score"],
        }

    def _v1_design_plans(self, handler, match):
        handler.guard()
        params = self._query_params(handler)
        project_id = params.get("project_id") or ""
        if len(project_id) != 32:
            _reject(400, "DESIGN_PROJECT_ID_REQUIRED")
            return
        try:
            plans = self._plans_factory(self.design_service).list(project_id)
        except ValueError as exc:
            raise RequestError(400, getattr(exc, "code", "DESIGN_PLANS_UNAVAILABLE")) from None
        return handler.send_json(200, plans)

    def _v1_design_plan_revision(self, handler, match):
        """Read one stored revision — the object a pinned pack answers."""
        handler.guard()
        plan_id = match[1]
        try:
            revision = int(match[2])
        except (TypeError, ValueError):
            _reject(400, "PLAN_REVISION_NUMBER_INVALID")
            return
        project_id = self._project_for_plan(plan_id)
        if project_id is None:
            _reject(404, "ASSISTANCE_PLAN_NOT_FOUND")
            return
        try:
            document = self._plans_factory(self.design_service).revision(project_id, plan_id,
                                                                        revision)
        except ValueError as exc:
            code = getattr(exc, "code", "ASSISTANCE_PLAN_REVISION_UNAVAILABLE")
            status = 404 if code.endswith("NOT_FOUND") else 409
            _reject(status, code)
            return
        return handler.send_json(200, document)

    def _project_for_plan(self, plan_id: str):
        for project in self.unified.list_projects():
            if project["source"] != "design":
                continue
            try:
                self._plans_factory(self.design_service).detail(project["root_path"], plan_id)
            except ValueError:
                continue
            return project["root_path"]
        return None

    def _v1_design_target_profiles(self, handler, match):
        handler.guard()
        params = self._query_params(handler)

        def number(name, default):
            raw = params.get(name)
            if raw is None or raw == "":
                return default
            try:
                return int(raw)
            except ValueError:
                raise RequestError(400, "TARGET_PROFILE_FILTER_MALFORMED") from None

        try:
            profiles = self._profiles_factory(self.design_service).list(
                offset=number("offset", 0), limit=number("limit", 20))
        except ValueError as exc:
            raise RequestError(400, getattr(exc, "code", "TARGET_PROFILES_UNAVAILABLE")) from None
        return handler.send_json(200, profiles)

    # -- WORK observer / control surfaces (audit F09) --------------------------
    def _query_params(self, handler) -> dict:
        """The request's query as a mapping -- with the refusal the old one-liner never made.

        ``dict(parse_qsl(...))`` keeps the last of ``?x=1&x=2``, so a caller that sent two values for
        one filter was answered about whichever one happened to sort last. N02 named that collapse for
        the task list (``TASK_FILTER_PROJECT_ID_DUPLICATE``); this is the same rule for every remaining
        GET surface, so the four parsers become one.
        """
        pairs = _query_pairs(handler)
        names = [name for name, _ in pairs]
        if any(names.count(name) > 1 for name in set(names)):
            _reject(400, "QUERY_PARAM_DUPLICATE")
        return dict(pairs)

    def _work_observer_health(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.observer_health(self, handler)

    def _work_observer_projection(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.observer_projection(self, handler)

    def _work_observer_snapshot(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.observer_snapshot(self, handler)

    def _work_observer_repair_packs(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.observer_repair_packs(self, handler)

    def _work_observer_solutions(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        params = self._query_params(handler)
        try:
            limit = int(params.get("limit") or 20)
        except ValueError:
            _reject(400, "SOLUTION_LIMIT_MALFORMED")
            return
        return work_surfaces.observer_solutions(self, handler, query=params.get("q") or "",
                                                software_id=params.get("softwareId") or "",
                                                limit=limit)

    def _work_observer_evidence_range(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        params = self._query_params(handler)
        try:
            offset = int(params["offset"]) if "offset" in params else 0
            limit = int(params["limit"]) if "limit" in params else 4096
        except ValueError:
            _reject(400, "EVIDENCE_RANGE_QUERY_MALFORMED")
            return
        # A declared empty digest stays empty instead of becoming "no digest": the reader
        # refuses a value that is not 64 hex characters, and an explicitly blank identity pin
        # must not be downgraded into an unpinned read. domains/work/control/sidecar.py already
        # forwards the raw value; the two surfaces of one reader now agree.
        return work_surfaces.observer_evidence_range(
            self, handler, handle=params.get("handle", ""), offset=offset, limit=limit,
            expected_digest=params.get("expectedDigest"))

    def _work_observer_events(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.observer_events(self, handler, match)

    def _work_observer_refusals(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.observer_refusals(self, handler)

    def _work_observer_write_refused(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.refuse_observer_write(self, handler, match)

    def _work_control_write_refused(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.refuse_observer_write(self, handler, match)

    def _work_surface_map(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.surface_map(self, handler)

    def _work_control_descriptor(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.control_descriptor(self, handler)

    def _work_control_receipts(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.control_receipts(self, handler, match)

    def _work_control_execute(self, handler, match):
        from backend.core import work_surfaces
        handler.guard()
        return work_surfaces.control_execute(self, handler)

    # -- probes (server-side only; never an HTTP write) -------------------------
    def run_startup_probes(self) -> None:
        """Record what this process can actually show right now.

        Called by the composition root, not by a request handler: a client must
        not be able to mint its own qualification. Read-only probes against the
        live stores are `live` origin; probes against a scratch fixture are
        `test` and therefore cannot grant a live qualification.
        """
        from backend.core import probes
        if self._probes_run:
            return
        self._probes_run = True
        probes.run_read_probes(api=self)


def actor_role_of(actor: str) -> str:
    """A simulated actor makes the row test data; that is the whole point of the label."""
    text = str(actor or "").strip().lower()
    if any(token in text for token in ("simul", "fixture", "test", "audit", "synthetic", "mock",
                                       "agent", "bot")):
        return "test"
    return "live"
