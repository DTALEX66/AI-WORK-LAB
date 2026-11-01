# SPDX-License-Identifier: MIT
"""V12: controlled business-data migration with failure recovery.

The 2026-10-30 independent audit refused A06/V07 as a *data* migration: what had
been proven was that source FILES copy repeatably, while "数据库内容迁移、ID/修订/
引用及中断恢复没有可运行入口和受控数据对账". This suite drives the tool that closes
that gap (``scripts/migrate_business_data.py``) over synthetic databases built to
the REAL schemas by the owning modules themselves — ``CanonicalStore``,
``UnifiedStore``, ``KnowledgeLibrary``, ``AssistancePlans``, ``TargetProfiles`` —
and asserts only on rows read back from disk (or through a brand-new store
object), never on what some function returned.

Nothing here touches ``workspace/.project-local/ai-work-lab/``, the two source
repositories, or any real user database: the refusal paths are part of the
acceptance, so a fixture that "succeeded" by writing into a live store would be a
failure of this test, not of the tool. Scratch databases live under
``.project-local/runs/v12-data-migration/`` (the project-owned runtime root).
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import uuid
from pathlib import Path

import pytest
from design_lab.assistance_plan import AssistancePlans
from design_lab.knowledge_library import KnowledgeLibrary
from design_lab.runtime import asset_store
from design_lab.service import ProjectService
from design_lab.target_profile import TargetProfiles

from backend.core import binding as binding_rules
from backend.core.unified_store import UnifiedStore, result_digest
from domains.work.workflow_core.canonical_store import CanonicalStore
from scripts.migrate_business_data import data_types, row_digest

TARGET_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = TARGET_ROOT / ".venv" / "Scripts" / "python.exe"
SCRIPT = TARGET_ROOT / "scripts" / "migrate_business_data.py"
LIVE_STORES = TARGET_ROOT / "workspace" / ".project-local" / "ai-work-lab"
SCRATCH = TARGET_ROOT / ".project-local" / "runs" / "v12-data-migration"

# The DESIGN plan contract pins project_id to ^[0-9a-f]{32}$, so the shared identity has
# to be a valid one on the design side; the WORK store accepts any text. Using the SAME
# value on both sides is the point: it is what makes an un-namespaced merge impossible.
SHARED_PROJECT_ID = hashlib.sha256(b"ai-work-lab-v12-shared-project").hexdigest()[:32]
WORK_PROJECT_ID = SHARED_PROJECT_ID
WORK_PROJECT_2 = "wl-proj-2"
DESIGN_PROJECT_ID = SHARED_PROJECT_ID
KNOWLEDGE_TERM = "缓存穿透"

SOURCE_TABLES = {
    "work.projects": ("work", "projects"),
    "work.action_plans": ("work", "action_plans"),
    "work.solutions": ("work", "solutions"),
    "work.collector_health": ("work", "collector_health"),
    "design.project": ("design", "project"),
    "design.assistance_plan": ("design", "assistance_plan"),
    "design.assistance_plan_revision": ("design", "assistance_plan_revision"),
    "design.assistance_plan_choice": ("design", "assistance_plan_choice"),
    "design.knowledge_entry": ("design", "knowledge_entry"),
    "design.knowledge_entry_revision": ("design", "knowledge_entry_revision"),
    "design.knowledge_judgement": ("design", "knowledge_judgement"),
    "design.target_profile_draft": ("design", "target_profile_draft"),
    "unified.projects": ("unified", "projects"),
    "unified.tasks": ("unified", "tasks"),
    "unified.attempts": ("unified", "attempts"),
    "unified.results": ("unified", "results"),
    "unified.verifications": ("unified", "verifications"),
}
SPEC_BY_KEY = {spec["key"]: spec for spec in data_types()}


# ---------------------------------------------------------------------------
# real-schema fixture builders
# ---------------------------------------------------------------------------

class Roots:
    """Source + destination workspace roots and their database paths."""

    def __init__(self, base: Path):
        self.base = base
        self.source = base / "src-workspace"
        self.target = base / "dst-workspace"
        for root in (self.source, self.target):
            (root / ".project-local" / "migration").mkdir(parents=True, exist_ok=True)
            (root / "AGENTS.md").write_text("# fixture workspace for V12\n", encoding="utf-8")
        self.source_dbs = {role: self.source / ".project-local" / "migration" / f"{role}.db"
                           for role in ("work", "design", "unified")}
        self.target_dbs = {role: self.target / ".project-local" / "migration" / f"{role}.db"
                           for role in ("work", "design", "unified")}
        self.ids: dict = {}

    def command(self, *extra: str) -> list[str]:
        argv = ["--source-root", str(self.source),
                "--source-work", str(self.source_dbs["work"]),
                "--source-design", str(self.source_dbs["design"]),
                "--source-unified", str(self.source_dbs["unified"]),
                "--target-root", str(self.target),
                "--target-work", str(self.target_dbs["work"]),
                "--target-design", str(self.target_dbs["design"]),
                "--target-unified", str(self.target_dbs["unified"]),
                "--allow-root", str(self.base)]
        return argv + list(extra)

    def report_path(self, name: str) -> Path:
        return self.base / "reports" / f"{name}.json"

    def alt_target(self, name: str) -> Path:
        """A second, empty destination workspace sharing these sources.

        Comparing a recovered run against a clean run of the SAME sources is the only
        honest way to say "the retry reached the completed state": a second fixture would
        carry its own minting timestamps and prove nothing.
        """
        root = self.base / name
        (root / ".project-local" / "migration").mkdir(parents=True, exist_ok=True)
        (root / "AGENTS.md").write_text("# fixture workspace for V12\n", encoding="utf-8")
        return root

    def command_into(self, root: Path, *extra: str) -> list[str]:
        dbs = {role: root / ".project-local" / "migration" / f"{role}.db"
               for role in ("work", "design", "unified")}
        return self.command("--target-root", str(root),
                            "--target-work", str(dbs["work"]),
                            "--target-design", str(dbs["design"]),
                            "--target-unified", str(dbs["unified"]), *extra)

    def alt_dbs(self, root: Path) -> dict:
        return {role: root / ".project-local" / "migration" / f"{role}.db"
                for role in ("work", "design", "unified")}


def _run(roots: Roots, argv: list[str], name: str) -> tuple[int, dict, str]:
    """One real CLI invocation: (exit code, machine report, stderr)."""
    out = roots.report_path(name)
    completed = subprocess.run(
        [str(VENV_PYTHON), "-B", "-X", "utf8", str(SCRIPT)] + argv + ["--json-out", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(TARGET_ROOT), timeout=900)
    report = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}
    return completed.returncode, report, completed.stderr


def _knowledge_body(title: str, summary: str, body: str, **overrides) -> dict:
    source = {"sourceId": "owner-note", "origin": "UNKNOWN", "author": "林岚",
              "license": "UNKNOWN", "licenseStatus": "unknown", "allowedUsage": "UNKNOWN",
              "citationScope": "UNKNOWN", "version": "1", "observedAt": "2026-10-30T00:00:00Z",
              "contentHash": "UNKNOWN", "verification": "UNVERIFIED"}
    value = {"entry_type": "METHOD", "title": title, "summary": summary,
             "domain_tags": ["film"], "task_tags": ["storyboard"], "target_tools": ["ps"],
             "body": body, "applicability": "适合短片前置。", "limits": "不适用于口型对位。",
             "source": dict(source), "related_capability_ids": [], "recommended": True,
             "created_by": "林岚", "supersedes": None}
    value.update(overrides)
    return value


def _plan_body(objective: str, entry_id: str, **overrides) -> dict:
    value = {"objective": objective, "output_type": "STORYBOARD",
             "neutral_creative": "三段式镜头推进，保留呼吸感",
             "brand_constraints": ["主色不超过三个"], "role_constraints": [],
             "lens": "35mm", "sound": "环境声为主",
             "shots": [{"index": 1, "duration_s": 3.5, "purpose": "建立空间"},
                       {"index": 2, "duration_s": 2.0, "purpose": "给出产品"}],
             "references": [{"kind": "KNOWLEDGE", "id": entry_id}],
             "external_steps": [{"step": "在外部工具里排版", "tool": "PS",
                                 "job_id": "UNUSED", "operation_id": "UNUSED"}],
             "known_gaps": ["缺尾镜"], "limits": ["未运行任何模型"],
             "created_by": "林岚"}
    value.update(overrides)
    return value


def _design_service(root: Path, db: Path):
    service = ProjectService(str(root))
    service.database = service.paths.database_path(str(db))
    return service


def build_sources(roots: Roots) -> Roots:
    """Populate the three source stores through the modules that own them."""
    # ---- DESIGN ---------------------------------------------------------
    design_db = roots.source_dbs["design"]
    conn = asset_store.connect(str(design_db), project_root=str(roots.source))
    asset_store.create_project(conn, DESIGN_PROJECT_ID, "融合前的设计项目")
    asset_store.create_project(conn, "dproj-2", "另一个设计项目")
    conn.commit()
    conn.close()

    service = _design_service(roots.source, design_db)
    library = KnowledgeLibrary(service)
    cache = library.create(_knowledge_body(
        "缓存穿透防护配方", "用布隆过滤器挡住穿透查询，再给空结果设短 TTL。",
        "先确认键空间，再选布隆过滤器参数；空结果缓存时间要短。"))["entry"]
    storyboard = library.create(_knowledge_body(
        "分镜拆解三步法", "把一段脚本拆成镜头表。", "第一步切节拍，第二步选景别，第三步标转场。"))["entry"]
    cache_id = cache["knowledge_entry_id"]

    plans = AssistancePlans(service)
    # the plan is written while the entry is still at revision 1: its pin must keep
    # pointing at revision 1 after the entry moves, before AND after the migration
    created = plans.create(DESIGN_PROJECT_ID, _plan_body("给新品做 30 秒短片分镜", cache_id))
    plan_id = created["plan"]["plan_id"]
    plans.revise(DESIGN_PROJECT_ID, plan_id,
                 _plan_body("给新品做 45 秒短片分镜", cache_id, expected_revision=1))
    plans.choose(DESIGN_PROJECT_ID, plan_id, {"revision": 1, "actor": "林岚",
                                              "actor_kind": "human"})
    revised = library.revise(cache_id, _knowledge_body(
        "缓存穿透防护配方（修订）", "用布隆过滤器挡住穿透查询，并把命中率写进观测。",
        "修订只在原文之上补一句命中率口径。", recommended=False,
        expected_revision=cache["revision"]))["entry"]
    library.record_judgement(cache_id, {
        "kind": "RECOMMENDATION", "revision": 1, "value": "RECOMMENDED",
        "reason": "修订补的是口径，不是配方本身", "recorded_by": "林岚",
        "recorded_by_kind": "HUMAN"})
    profiles = TargetProfiles(service)
    draft = profiles.create({"software": "Blender", "agent": "local", "model": None,
                             "provider": None, "version": "4.2", "entry": "DESKTOP_CLIENT",
                             "task_mode": "3D 资产", "actor": "林岚", "source_ref": "UNUSED",
                             "fields": {}})
    roots.ids.update({
        "design_project": DESIGN_PROJECT_ID, "plan_id": plan_id, "cache_entry": cache_id,
        "cache_revision_1": cache["content_sha256"], "cache_revision_2": revised["content_sha256"],
        "storyboard_entry": storyboard["knowledge_entry_id"],
        "profile_id": draft["profile"]["profile_id"],
        "profile_digest": draft["profile"]["content_sha256"],
        "plan_revision_1_digest": created["plan"]["content_sha256"]})

    # ---- WORK -----------------------------------------------------------
    work = CanonicalStore(roots.source_dbs["work"])
    work.register_project(WORK_PROJECT_ID, str(roots.source), "融合前的运行台账项目")
    work.register_project(WORK_PROJECT_2, str(roots.source), "第二个项目")
    work.save_action_plan({"planId": "AP-01", "projectId": WORK_PROJECT_ID,
                           "status": "APPROVED",
                           "payload": {"steps": ["核对台账", "执行修复"], "scope": "collector"}})
    work.save_action_plan({"planId": "AP-01", "projectId": WORK_PROJECT_ID,
                           "status": "IN_PROGRESS",
                           "payload": {"steps": ["核对台账", "执行修复", "补读回"],
                                       "scope": "collector"}}, expected_version=1)
    work.save_solution({"solutionId": "sol-cache", "revision": 1, "title": "缓存穿透防护",
                        "status": "ACTIVE", "softwareId": "redis", "softwareVersion": "7",
                        "platform": "windows", "keywords": ["缓存", "穿透"],
                        "payload": {"steps": ["装布隆过滤器"]}})
    work.save_solution({"solutionId": "sol-cache", "revision": 2, "title": "缓存穿透防护",
                        "status": "ACTIVE", "softwareId": "redis", "softwareVersion": "7",
                        "platform": "windows", "keywords": ["缓存", "穿透"],
                        "payload": {"steps": ["装布隆过滤器", "空结果短 TTL"],
                                    "supersedes": {"solutionId": "sol-cache", "revision": 1}}})
    work.recommend_solution("sol-cache", 2)
    work.upsert_collector_health({"name": "demo-collector", "totalRuns": 7,
                                  "consecutiveFailures": 2, "refusedRows": 1,
                                  "lastRunAt": "2026-10-30T08:00:00Z"})
    work.close()

    # ---- unified envelope -----------------------------------------------
    unified = UnifiedStore(roots.source_dbs["unified"])
    envelope_project = unified.register_project(source="work", display_name="信封项目",
                                                 root_path=str(roots.source))
    second_project = unified.register_project(source="design", display_name="信封二项目")
    task = unified.create_task(project_id=envelope_project["project_id"], kind="work",
                               title="台账核对", input_refs=[design_db.as_posix()],
                               acceptance={"text": "逐行读回"}, data_origin="test")
    attempt, _ = unified.create_attempt(task["task_id"], idempotency_key="attempt-1",
                                        execution_mode="LOCAL_TOOL", data_origin="test")
    unified.update_attempt(attempt["attempt_id"], expected_revision=attempt["revision"],
                           execution_state="RESULT_RECEIVED")
    raw = {"producedAt": "2026-10-30T09:00:00Z", "lines": ["step one", "step two"]}
    digest = binding_rules.canonical_digest(raw)
    result = unified.record_result(task_id=task["task_id"], attempt_id=attempt["attempt_id"],
                                   pack_id="AP-01", subject_fingerprint="fixture-fingerprint",
                                   artifact_refs=[".project-local/migration/out.json"],
                                   content_sha256=digest, raw=raw, data_origin="test")
    unified.record_verification(result_id=result["result_id"], axis="technical", outcome="PASS",
                                subject_fingerprint=digest, data_origin="test",
                                evidence_refs=[".project-local/migration/out.json"],
                                command_ref="scripts/migrate_business_data.py --dry-run",
                                verifier_ref="pytest-v12")
    unified.set_task_lifecycle(task["task_id"], "ACTIVE", current_attempt_id=attempt["attempt_id"])
    unified.set_task_lifecycle(task["task_id"], "COMPLETED")
    retry_task = unified.create_task(project_id=second_project["project_id"], kind="design",
                                     title="提示词反推", input_refs=[], acceptance={},
                                     professional_required=False, data_origin="test")
    second_attempt, _ = unified.create_attempt(retry_task["task_id"], idempotency_key="attempt-2",
                                               execution_mode="MANUAL_COPY", data_origin="test")
    unified.update_attempt(second_attempt["attempt_id"],
                           expected_revision=second_attempt["revision"],
                           execution_state="FAILED", finished_at="2026-10-30T09:05:00Z")
    unified.close()
    roots.ids.update({"envelope_project": envelope_project["project_id"],
                      "task_id": task["task_id"], "attempt_id": attempt["attempt_id"],
                      "result_id": result["result_id"], "digest": digest})
    return roots


@pytest.fixture()
def make_roots():
    """A fresh, uniquely named scratch pair of workspace roots with real-schema data."""
    created: list[Path] = []

    def _make(name: str) -> Roots:
        base = SCRATCH / f"{name}-{uuid.uuid4().hex[:8]}"
        base.mkdir(parents=True, exist_ok=True)
        created.append(base)
        return build_sources(Roots(base))

    _make.created = created  # type: ignore[attr-defined]
    return _make


@pytest.fixture()
def roots(make_roots) -> Roots:
    return make_roots("fixture")


# ---------------------------------------------------------------------------
# independent row readers (assertions never trust the tool's own numbers)
# ---------------------------------------------------------------------------

def _rows(db: Path, table: str) -> list[dict]:
    if not db.is_file():
        return []
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                           (table,)).fetchone():
            return []
        return [dict(row) for row in conn.execute(f"SELECT * FROM {table}")]
    except sqlite3.Error:
        return []
    finally:
        conn.close()


def _source_rows(roots: Roots, key: str) -> list[dict]:
    role, table = SOURCE_TABLES[key]
    return _rows(roots.source_dbs[role], table)


def _target_dbs(entity) -> dict:
    """Accepts a Roots or a bare {role: path} mapping."""
    return getattr(entity, "target_dbs", entity)


def _target_rows(entity, key: str) -> list[dict]:
    role, table = SOURCE_TABLES[key]
    return _rows(_target_dbs(entity)[role], table)


def _pk(key: str, row: dict) -> tuple:
    return tuple(str(row[column]) for column in SPEC_BY_KEY[key]["primary_key"])


def _digest_row(key: str, row: dict) -> str:
    return row_digest({column: row[column] for column in SPEC_BY_KEY[key]["columns"]
                       if column in row})


def _witness(roots: Roots, side: str) -> dict[str, list[tuple]]:
    reader = _source_rows if side == "source" else _target_rows
    return {key: sorted((_pk(key, row), _digest_row(key, row)) for row in reader(roots, key))
            for key in SOURCE_TABLES}


def _keyset(rows: list[dict], columns: list[str]) -> set[tuple]:
    return {tuple(str(row[column]) for column in columns) for row in rows}


def _raw_write(db: Path, statements: list[tuple[str, tuple]]) -> None:
    conn = sqlite3.connect(str(db))
    for sql, params in statements:
        conn.execute(sql, params)
    conn.commit()
    conn.close()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "ABSENT"


# ---------------------------------------------------------------------------
# 1. the contract is machine readable and says what this batch owns
# ---------------------------------------------------------------------------

def test_describe_contract_is_machine_readable():
    completed = subprocess.run([str(VENV_PYTHON), "-B", "-X", "utf8", str(SCRIPT), "--describe"],
                               capture_output=True, text=True, encoding="utf-8",
                               cwd=str(TARGET_ROOT), timeout=300)
    assert completed.returncode == 0, completed.stderr[-3000:]
    contract = json.loads(completed.stdout)
    required = set(SOURCE_TABLES) | {"unified.projects.registry_from_work",
                                      "unified.projects.registry_from_design"}
    listed = {spec["key"] for spec in contract["data_types"]}
    assert required <= listed, sorted(required - listed)
    for spec in contract["data_types"]:
        assert spec["authority"] and spec["relations"] and spec["counts_as"]
        assert spec["id_namespace_note"]
        # every type names a digest rule; a row with no published digest falls back to the
        # canonical row digest rather than being reported as "nothing to check"
        assert contract["digest_rules"][spec["key"]]
        assert set(spec["required"]) <= set(spec["columns"])
    assert contract["source_schema_versions"]["work"]["required_schema_migrations"] == [2, 3, 4, 5, 6]
    assert "v2-canonical-compact" in contract["source_schema_versions"]["unified"]["digest_vocabulary"]
    assert contract["source_schema_versions"]["design"]["resource_names"]
    assert contract["id_namespaces"]["unified.projects.registry_from_work"] == "work:"
    assert contract["id_namespaces"]["unified.projects.registry_from_design"] == "design:"
    assert "NOT_RUN" in contract["scope"]["real_user_data_migration"]
    assert set(contract["exit_codes"]) >= {"0", "2", "3", "4", "5", "6", "7"}
    assert any("SYNTHETIC FIXTURES" in line for line in contract["limitations"])
    assert "knowledge_entry_fts" in json.dumps(contract["not_migrated"], ensure_ascii=False)


# ---------------------------------------------------------------------------
# 2. the migration itself: revisions, digests, references, counts
# ---------------------------------------------------------------------------

def test_migration_preserves_revisions_digests_and_references(roots: Roots):
    before = {key: _source_rows(roots, key) for key in SOURCE_TABLES}
    code, report, stderr = _run(roots, roots.command("--init-targets"), "clean")
    assert code == 0, (code, report.get("refusal"), stderr[-3000:])
    assert report["outcome"] == "MIGRATED_AND_READ_BACK", report["outcome"]
    assert report["restart_readback"]["problems"] == []

    # the machine report is self-describing: contract, before/after per table, and the
    # sentence that says this was a fixture run, not a real user migration
    assert report["contract"]["data_types"], "the report must carry the contract it ran under"
    assert report["targets_before"] and report["targets_after"]
    assert all(entry["rows"] == 0 for entry in report["targets_before"].values())
    assert any("合成夹具" in line for line in report["limitations"])
    assert report["real_data_migration"]["status"] == "NOT_RUN"

    # ---- DESIGN: every stored revision keeps its own row and its own digest
    source_revisions = before["design.assistance_plan_revision"]
    target_revisions = _target_rows(roots, "design.assistance_plan_revision")
    assert len(source_revisions) == 2
    assert len(target_revisions) == 2
    assert _keyset(target_revisions, ["plan_id", "revision", "content_sha256"]) == \
        _keyset(source_revisions, ["plan_id", "revision", "content_sha256"])
    assert len(_target_rows(roots, "design.assistance_plan")) == 1
    assert len(_target_rows(roots, "design.assistance_plan_choice")) == 1
    # two entries, three stored revisions (the cache recipe was corrected once)
    assert len(_target_rows(roots, "design.knowledge_entry")) == 2
    assert len(_target_rows(roots, "design.knowledge_entry_revision")) == 3
    assert len(_target_rows(roots, "design.knowledge_judgement")) == 1
    assert len(_target_rows(roots, "design.target_profile_draft")) == 1
    assert len(_target_rows(roots, "design.project")) == 2

    # read back through brand-new product objects over the TARGET store
    service = _design_service(roots.target, roots.target_dbs["design"])
    detail = AssistancePlans(service).detail(DESIGN_PROJECT_ID, roots.ids["plan_id"])
    assert detail["latest_revision"] == 2, detail["revisions"]
    # a person adopted revision 1 while revision 2 is current: the migration must not
    # have written the old revision as the current one
    assert detail["choice"]["chosen"] is True
    assert detail["choice"]["revision"] == 1
    assert detail["choice"]["is_latest"] is False
    old = AssistancePlans(service).revision(DESIGN_PROJECT_ID, roots.ids["plan_id"], 1)
    assert old["content_sha256"] == roots.ids["plan_revision_1_digest"]
    assert old["is_latest"] is False and old["is_chosen"] is True
    pinned = next(item for item in detail["reference_status"] if item["id"] == roots.ids["cache_entry"])
    assert pinned["recorded_revision"] == 1
    assert pinned["recorded_sha256"] == roots.ids["cache_revision_1"]
    assert pinned["state"] == "CHANGED", "the entry moved to revision 2; the plan's pin must not"
    entry = KnowledgeLibrary(service).detail(roots.ids["cache_entry"])
    assert entry["latest_revision"] == 2
    assert entry["recommended_revision"] == 1          # the recorded judgement travelled too
    assert entry["recommendation_basis"] == "recorded-judgement"
    assert entry["judgements"][0]["recorded_by"] == "林岚"
    digests = {item["revision"]: item["content_sha256"] for item in entry["revisions"]}
    assert digests[1] == roots.ids["cache_revision_1"]
    assert digests[2] == roots.ids["cache_revision_2"]
    profile = TargetProfiles(service).detail(roots.ids["profile_id"])
    assert profile["content_sha256"] == roots.ids["profile_digest"]
    assert profile["support_state"] == "USER_DRAFT" and profile["executable"] is False

    # ---- WORK: ledger version, immutable revisions, recommendation pointer
    work = CanonicalStore(roots.target_dbs["work"], readonly=True)
    try:
        plan = work.read_action_plan("AP-01")
        assert plan is not None and plan["version"] == 2, plan
        assert plan["status"] == "IN_PROGRESS"
        source_plan = next(row for row in before["work.action_plans"] if row["plan_id"] == "AP-01")
        assert plan["payloadDigest"] == hashlib.sha256(
            source_plan["payload"].encode("utf-8")).hexdigest()
        assert work.read_solution("sol-cache", 1) is not None, "the cited old revision is gone"
        assert work.read_solution("sol-cache", 1)["recommended"] is False
        assert work.read_solution("sol-cache", 2)["recommended"] is True
        health = next(row for row in work.list_collector_health() if row["name"] == "demo-collector")
        assert health["total_runs"] == 7 and health["consecutive_failures"] == 2
        assert health["refused_rows"] == 1
        assert len(work.list_projects()) == len(before["work.projects"])
    finally:
        work.close()

    # ---- unified envelope: relations, CAS counters and the verdict chain
    unified = UnifiedStore.open_readonly(roots.target_dbs["unified"])
    try:
        task = unified.get_task(roots.ids["task_id"])
        assert task is not None
        source_task = next(row for row in before["unified.tasks"]
                           if row["task_id"] == roots.ids["task_id"])
        assert task["revision"] == source_task["revision"]
        assert task["lifecycle"] == "COMPLETED"
        assert task["current_attempt_id"] == roots.ids["attempt_id"]
        assert len(task["attempts"]) == 1 and len(task["results"]) == 1
        support = unified.completion_support(roots.ids["task_id"])
        assert support["supported"] is True, support["problems"]
        result = unified.get_result(roots.ids["result_id"])
        assert result["content_sha256"] == roots.ids["digest"]
        assert result_digest(result["raw"], result["digest_vocabulary"]) == result["content_sha256"]
        assert len(result["verifications"]) == 1
        verdict = result["verifications"][0]
        assert (verdict["axis"], verdict["outcome"]) == ("technical", "PASS")
        assert verdict["evidence_refs"]
        integrity = unified.integrity_report()
        assert integrity["problems"] == [], integrity["problems"]
        assert integrity["counts"] == {"tasks": len(before["unified.tasks"]),
                                       "attempts": len(before["unified.attempts"]),
                                       "results": len(before["unified.results"]),
                                       "attempts_with_pack_plan": 0,
                                       "pack_plan_check": "NOT_RUN"}
        # 现测：迁移后的统一库里没有任何一条尝试带 pack_plan_id（这座目标库被本节点按只读打开，
        # 那正是 V12 要证明的一部分，所以不能在这里植入绑定）。这一跳的规则本身在 test_v11 里
        # 由产品路径检验（两条链、断链与跨项目各有具名问题）；这里只断言迁移人口与读管线的现状。
        bound = [row["attempt_id"] for row in unified.conn.execute(
            "SELECT attempt_id FROM attempts "
            "WHERE pack_plan_id IS NOT NULL AND pack_plan_id != ''")]
        assert bound == [], bound
        hop = unified.integrity_report(plan_reader=work.read_action_plan)
        assert hop["counts"]["pack_plan_check"] == "RUN", hop["counts"]
        assert hop["counts"]["attempts_with_pack_plan"] == 0, hop["counts"]
        assert not [p for p in hop["problems"] if p["kind"] in (
            "ATTEMPT_ORPHAN_PACK_PLAN", "ATTEMPT_PACK_PROJECT_SPLIT")], hop["problems"]
    finally:
        unified.close()

    # every migrated table holds exactly the source population (registry rows aside)
    for key in SOURCE_TABLES:
        if key == "unified.projects":
            continue
        assert len(_target_rows(roots, key)) == len(before[key]), key
    registry = len(before["work.projects"]) + len(before["design.project"])
    assert len(_target_rows(roots, "unified.projects")) == len(before["unified.projects"]) + registry
    assert report["index_after_migration"]["indexed_entries"] == 2


# ---------------------------------------------------------------------------
# 3. rerun idempotence: same counts, same per-row digests, no new records
# ---------------------------------------------------------------------------

def test_rerun_is_idempotent_and_adds_no_records(roots: Roots):
    code, first, stderr = _run(roots, roots.command("--init-targets"), "idem-1")
    assert code == 0, (first.get("refusal"), stderr[-2000:])
    snapshot = _witness(roots, "target")
    counts = {key: len(snapshot[key]) for key in SOURCE_TABLES}

    code, second, stderr = _run(roots, roots.command("--resume"), "idem-2")
    assert code == 0, (second.get("refusal"), stderr[-2000:])
    assert second["preflight"]["foreign_target_rows"] == {}, second["preflight"]
    assert second["commit"]["rows_identical_skipped"] > 0, second["commit"]
    after = _witness(roots, "target")
    for key in SOURCE_TABLES:
        assert len(after[key]) == counts[key], f"{key} grew on a rerun"
        assert after[key] == snapshot[key], f"{key} changed on a rerun"
    for name, entry in second["targets_after"].items():
        assert entry["fingerprint"] == first["targets_after"][name]["fingerprint"], name
        assert entry["per_row"] == first["targets_after"][name]["per_row"], name


# ---------------------------------------------------------------------------
# 4. interruption: rollback, and the retry that reaches the completed state
# ---------------------------------------------------------------------------

def test_injected_exception_rolls_back_every_target_then_retry_completes(roots: Roots):
    expected = _witness(roots, "source")
    code, report, stderr = _run(roots, roots.command("--init-targets",
                                                    "--fail-at", "unified:verifications:1"),
                                "inject")
    assert code == 4, (code, report.get("refusal"), stderr[-2000:])
    assert report["outcome"] == "ROLLED_BACK_TO_PRE_MIGRATION_STATE"
    assert sorted(report["failure_injection"]["rolled_back_stores"]) == ["design", "unified", "work"]
    assert report["failure_injection"]["already_committed_stores"] == []
    assert report["failure_injection"]["rows_attempted_before_failure"] >= 1
    # the rollback is a fact about the files, not a claim inside the report
    witness = _witness(roots, "target")
    for key in SOURCE_TABLES:
        assert witness[key] == [], f"{key} still holds rows after the injected failure"

    code, retry, stderr = _run(roots, roots.command(), "after-inject")
    assert code == 0, (retry.get("refusal"), stderr[-2000:])
    assert retry["outcome"] == "MIGRATED_AND_READ_BACK"
    witness = _witness(roots, "target")
    for key in SOURCE_TABLES:
        if key == "unified.projects":
            continue
        assert [pk for pk, _ in witness[key]] == [pk for pk, _ in expected[key]], key
    assert witness["unified.verifications"], "the injected table stayed empty"


def test_killed_process_mid_transaction_leaves_no_committed_rows(roots: Roots):
    code, report, stderr = _run(roots, roots.command("--init-targets",
                                                    "--fail-at",
                                                    "design:knowledge_entry_revision:1:kill"),
                                "kill")
    assert code == 9, (code, report, stderr[-2000:])
    # os._exit skipped both the rollback call and the report write; SQLite must undo it
    assert report.get("outcome") in (None, "NOT_STARTED"), report.get("outcome")
    for key in SOURCE_TABLES:
        assert _target_rows(roots, key) == [], f"{key} survived a mid-transaction kill"

    code, retry, stderr = _run(roots, roots.command(), "after-kill")
    assert code == 0, (retry.get("refusal"), stderr[-2000:])
    assert len(_target_rows(roots, "design.knowledge_entry_revision")) == 3
    assert len(_target_rows(roots, "unified.tasks")) == 2


# ---------------------------------------------------------------------------
# 5. a crash between the stores is recovered by retry, not by undo
# ---------------------------------------------------------------------------

def test_partial_ordered_commit_is_completed_by_a_retry(roots: Roots):
    code, report, stderr = _run(roots, roots.command("--init-targets", "--commit-in-order",
                                                    "--fail-at", "commit:design"), "partial")
    assert code == 5, (code, report.get("refusal"), stderr[-2000:])
    assert report["outcome"] == "COMMITTED_STORES_KEPT_REST_ROLLED_BACK"
    assert report["failure_injection"]["already_committed_stores"] == ["work", "design"]
    assert report["failure_injection"]["rolled_back_stores"] == ["unified"]
    # genuinely partial, and read as such: the committed stores hold their rows, the third does not
    assert _target_rows(roots, "work.action_plans")
    assert len(_target_rows(roots, "design.knowledge_entry_revision")) == 3
    assert _target_rows(roots, "unified.tasks") == []
    assert _target_rows(roots, "unified.projects") == []

    code, retry, stderr = _run(roots, roots.command("--resume"), "after-partial")
    assert code == 0, (retry.get("refusal"), stderr[-2000:])
    assert _target_rows(roots, "unified.tasks")
    assert len(_target_rows(roots, "design.knowledge_entry_revision")) == 3, "retry duplicated rows"
    assert len(_target_rows(roots, "work.action_plans")) == 1

    # the recovered state matches a clean single run of the SAME sources, row for row
    alt = roots.alt_target("clean-reference")
    code, clean, stderr = _run(roots, roots.command_into(alt, "--init-targets"), "reference")
    assert code == 0, (clean.get("refusal"), stderr[-2000:])
    left, right = _witness(roots, "target"), _witness(roots.alt_dbs(alt), "target")
    assert set(left) == set(right)
    for key in SOURCE_TABLES:
        assert left[key] == right[key], key
    # and the recovered stores still answer through their own objects
    work = CanonicalStore(roots.target_dbs["work"], readonly=True)
    try:
        assert work.read_solution("sol-cache", 1)["payloadDigest"]
        assert work.read_action_plan("AP-01")["version"] == 2
    finally:
        work.close()


# ---------------------------------------------------------------------------
# 6. ID namespaces: the same id in two domains must not merge
# ---------------------------------------------------------------------------

def test_cross_domain_same_id_is_namespaced_not_merged(roots: Roots):
    code, report, stderr = _run(roots, roots.command("--init-targets"), "namespace")
    assert code == 0, (report.get("refusal"), stderr[-2000:])
    projects = _target_rows(roots, "unified.projects")
    ids = {row["project_id"] for row in projects}
    # this bare id exists in BOTH domain stores; neither copy may claim it alone
    assert SHARED_PROJECT_ID not in ids
    assert {f"work:{SHARED_PROJECT_ID}", f"design:{SHARED_PROJECT_ID}"} <= ids
    work_row = next(row for row in projects if row["project_id"] == f"work:{SHARED_PROJECT_ID}")
    design_row = next(row for row in projects if row["project_id"] == f"design:{SHARED_PROJECT_ID}")
    assert (work_row["source"], design_row["source"]) == ("work", "design")
    assert work_row["display_name"] != design_row["display_name"]
    assert len(projects) == 2 + 2 + 2   # 2 envelope + 2 work + 2 design
    for row in (work_row, design_row):
        assert row["data_origin"] == "test", "a minted registry row may not claim live origin"
    # the authoritative rows stayed in their own stores under their own ids
    assert _keyset(_target_rows(roots, "work.projects"), ["project_id"]) == {
        (WORK_PROJECT_ID,), (WORK_PROJECT_2,)}
    assert _keyset(_target_rows(roots, "design.project"), ["project_id"]) == {
        (DESIGN_PROJECT_ID,), ("dproj-2",)}
    # and both are individually addressable through the store object
    unified = UnifiedStore.open_readonly(roots.target_dbs["unified"])
    try:
        assert unified.get_project(f"work:{SHARED_PROJECT_ID}")["source"] == "work"
        assert unified.get_project(f"design:{SHARED_PROJECT_ID}")["source"] == "design"
    finally:
        unified.close()


def test_ambiguous_project_reference_is_refused_then_resolved_on_an_explicit_choice(roots: Roots):
    _raw_write(roots.source_dbs["unified"], [(
        "INSERT INTO tasks(task_id, project_id, kind, lifecycle, title, input_refs, acceptance,"
        " professional_required, revision, data_origin, origin_provenance, created_at, updated_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("task-foreign", SHARED_PROJECT_ID, "work", "DRAFT", "引用了两个域的同名项目", "[]", "{}",
         0, 1, "test", "ENFORCED_CHAIN", "2026-10-30T09:00:00Z", "2026-10-30T09:00:00Z"))])

    code, report, _ = _run(roots, roots.command("--init-targets"), "ambiguous-refuse")
    assert code == 2, (code, report.get("refusal"))
    assert report["refusal"]["code"] == "ID_NAMESPACE_AMBIGUOUS"
    assert _target_rows(roots, "unified.tasks") == []

    code, report, _ = _run(roots, roots.command("--allow-existing", "--on-dangling", "assign"),
                           "ambiguous-still-refuse")
    assert code == 2 and report["refusal"]["code"] == "ID_NAMESPACE_AMBIGUOUS", report["refusal"]

    code, report, stderr = _run(roots, roots.command("--allow-existing", "--on-dangling", "assign",
                                                   "--project-namespace", "design"),
                               "ambiguous-resolved")
    assert code == 0, (report.get("refusal"), stderr[-2000:])
    foreign = next(row for row in _target_rows(roots, "unified.tasks")
                   if row["task_id"] == "task-foreign")
    assert foreign["project_id"] == f"design:{SHARED_PROJECT_ID}"
    recorded = [item for item in report["commit"]["namespace_assigned"]
                if item["from"] == SHARED_PROJECT_ID]
    assert recorded and recorded[0]["to"] == f"design:{SHARED_PROJECT_ID}"
    assert foreign["revision"] == 1, "the CAS counter of a rewritten row still says 1"


def test_reserved_namespace_squat_is_refused_without_writing(roots: Roots):
    _raw_write(roots.source_dbs["unified"], [(
        "INSERT INTO projects(project_id, source, display_name, root_path, data_origin,"
        " origin_provenance, registered_at) VALUES (?,?,?,?,?,?,?)",
        (f"work:{WORK_PROJECT_ID}", "work", "冒名占用 work: 命名空间", "X", "test",
         "ENFORCED_CHAIN", "2026-10-30T09:00:00Z"))])
    code, report, _ = _run(roots, roots.command("--init-targets"), "squat")
    assert code == 2, (code, report.get("refusal"))
    assert report["refusal"]["code"] == "ID_NAMESPACE_CONFLICT"
    assert report["preflight"]["passed"] is False
    for key in SOURCE_TABLES:
        assert _target_rows(roots, key) == [], f"{key} was written although preflight refused"


# ---------------------------------------------------------------------------
# 7. dangling references and drifted digests
# ---------------------------------------------------------------------------

def test_dangling_reference_refused_then_dropped_only_when_authorised(roots: Roots):
    _raw_write(roots.source_dbs["unified"], [(
        "INSERT INTO verifications(verification_id, result_id, axis, outcome,"
        " subject_fingerprint, evidence_refs, data_origin, observed_at) VALUES (?,?,?,?,?,?,?,?)",
        ("verif-orphan", "result-that-does-not-exist", "technical", "PASS", "x", "[]",
         "test", "2026-10-30T09:00:00Z"))])
    code, report, _ = _run(roots, roots.command("--init-targets"), "dangling-refuse")
    assert code == 2 and report["refusal"]["code"] == "DANGLING_REFERENCE", report.get("refusal")
    assert "result-that-does-not-exist" in report["refusal"]["detail"]
    assert _target_rows(roots, "unified.verifications") == []

    code, report, stderr = _run(roots, roots.command("--init-targets", "--allow-existing",
                                                   "--on-dangling", "drop"), "dangling-drop")
    assert code == 0, (report.get("refusal"), stderr[-2000:])
    dropped = [item for item in report["preflight"]["findings"]
               if item["code"] == "DANGLING_REFERENCE_DROPPED"]
    assert dropped, report["preflight"]["findings"]
    assert any(row["pk"] == ["verif-orphan"] for item in dropped for row in item["dropped"])
    ids = {row["verification_id"] for row in _target_rows(roots, "unified.verifications")}
    assert "verif-orphan" not in ids
    assert ids == {row["verification_id"] for row in _source_rows(roots, "unified.verifications")} \
        - {"verif-orphan"}
    assert roots.ids["result_id"] in {row["result_id"]
                                      for row in _target_rows(roots, "unified.results")}


def test_drifted_source_digest_is_refused(roots: Roots):
    # the audit's counterexample databases under .project-local/audit are evidence, not
    # production stores; the same defect is reproduced here on a fixture row
    _raw_write(roots.source_dbs["unified"], [(
        "UPDATE results SET raw = ? WHERE result_id = ?",
        (json.dumps({"producedAt": "2026-10-30T09:00:00Z", "lines": ["tampered"]}),
         roots.ids["result_id"]))])
    code, report, _ = _run(roots, roots.command("--init-targets"), "digest")
    assert code == 2 and report["refusal"]["code"] == "SOURCE_DIGEST_MISMATCH", report.get("refusal")
    assert _target_rows(roots, "unified.results") == []
    assert _target_rows(roots, "design.knowledge_entry") == []


# ---------------------------------------------------------------------------
# 8. preflight refusals about the target itself
# ---------------------------------------------------------------------------

def test_non_empty_target_refused_then_resume_and_allow_existing_differ(roots: Roots):
    code, first, stderr = _run(roots, roots.command("--init-targets"), "first")
    assert code == 0, stderr[-2000:]
    snapshot = _witness(roots, "target")

    # a plain rerun onto the store it just filled is refused: a production database is
    # never a default target, and "the tool would have written these rows" is not obvious
    code, report, _ = _run(roots, roots.command(), "second-no-flag")
    assert code == 2 and report["refusal"]["code"] == "TARGET_NOT_EMPTY", report.get("refusal")
    assert "work.projects" in report["refusal"]["detail"]
    assert _witness(roots, "target") == snapshot, "the refused run changed the filled target"

    # --resume is the retry path: it accepts only the rows this batch would have written
    code, report, stderr = _run(roots, roots.command("--resume"), "third-resume")
    assert code == 0, (report.get("refusal"), stderr[-2000:])
    assert report["preflight"]["foreign_target_rows"] == {}
    assert _witness(roots, "target") == snapshot

    # ...and it stops the moment somebody else's row is in there
    _raw_write(roots.target_dbs["work"], [(
        "INSERT INTO projects(project_id, root_path, display_name, registered_at, status)"
        " VALUES (?,?,?,?,?)",
        ("someone-elses-row", "X", "不属于本批次", "2026-10-31T00:00:00Z", "REGISTERED"))])
    foreign = _witness(roots, "target")
    code, report, _ = _run(roots, roots.command("--resume"), "fourth-resume-foreign")
    assert code == 2 and report["refusal"]["code"] == "RESUME_FOREIGN_ROWS", report.get("refusal")
    assert "work.projects" in report["refusal"]["detail"]
    assert _witness(roots, "target") == foreign, "the refused resume rewrote the target"

    # merging into it is possible, but only as an explicitly authorised overlay
    code, report, stderr = _run(roots, roots.command("--allow-existing"), "fifth-allowed")
    assert code == 0, (report.get("refusal"), stderr[-2000:])
    assert any(item["code"] == "TARGET_OVERLAY_AUTHORISED"
               for item in report["preflight"]["warnings"]), report["preflight"]["warnings"]
    # the foreign row is still there, untouched: an overlay never deletes what it did not write
    assert "someone-elses-row" in {row["project_id"] for row in
                                   _target_rows(roots, "work.projects")}
    assert len(_target_rows(roots, "unified.projects")) == 6


def test_incompatible_unified_target_schema_is_refused_and_never_self_migrated(roots: Roots):
    legacy = roots.target / ".project-local" / "migration" / "legacy-unified.db"
    conn = sqlite3.connect(str(legacy))
    conn.executescript(
        """
        CREATE TABLE projects(project_id TEXT PRIMARY KEY, source TEXT NOT NULL,
                              display_name TEXT NOT NULL, root_path TEXT,
                              registered_at TEXT NOT NULL);
        CREATE TABLE tasks(task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,
                           lifecycle TEXT NOT NULL DEFAULT 'DRAFT', title TEXT NOT NULL,
                           input_refs TEXT NOT NULL DEFAULT '[]',
                           acceptance TEXT NOT NULL DEFAULT '{}',
                           professional_required INTEGER NOT NULL DEFAULT 0,
                           current_attempt_id TEXT, revision INTEGER NOT NULL DEFAULT 1,
                           created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        INSERT INTO projects(project_id, source, display_name, registered_at)
          VALUES ('legacy-1','work','旧库','2026-01-01T00:00:00Z');
        """)
    conn.commit()
    conn.close()
    before = _rows(legacy, "projects")
    code, report, _ = _run(roots, roots.command("--init-targets",
                                               "--target-unified", str(legacy)), "legacy")
    assert code == 2, (code, report.get("refusal"))
    assert report["refusal"]["code"] in ("TARGET_SCHEMA_VERSION_MISMATCH",
                                        "TARGET_SCHEMA_MISSING_COLUMNS"), report["refusal"]
    assert "origin_provenance" in report["refusal"]["detail"]
    assert _rows(legacy, "projects") == before, "the tool altered the store it was auditing"
    assert "origin_provenance" not in before[0]


def test_incompatible_work_target_version_is_refused(roots: Roots):
    legacy = roots.target / ".project-local" / "migration" / "legacy-work.db"
    store = CanonicalStore(legacy)
    store.close()
    conn = sqlite3.connect(str(legacy))
    conn.execute("DELETE FROM schema_migrations WHERE version >= 6")
    conn.commit()
    versions = sorted(row[0] for row in conn.execute("SELECT version FROM schema_migrations"))
    conn.close()
    code, report, _ = _run(roots, roots.command("--init-targets",
                                               "--target-work", str(legacy)), "legacy-work")
    assert code == 2, (code, report.get("refusal"))
    assert report["refusal"]["code"] == "TARGET_SCHEMA_VERSION_MISMATCH", report["refusal"]
    assert "schema_migrations" in report["refusal"]["detail"]
    conn = sqlite3.connect(str(legacy))
    after = sorted(row[0] for row in conn.execute("SELECT version FROM schema_migrations"))
    rows = conn.execute("SELECT COUNT(*) FROM action_plans").fetchone()[0]
    conn.close()
    assert after == versions, "the refusal must not run the store's own migration"
    assert rows == 0


def test_protected_and_escaping_paths_are_refused(roots: Roots):
    live = LIVE_STORES / "unified.sqlite3"
    digest_before = _file_sha256(live)
    code, report, _ = _run(roots, roots.command("--target-unified", str(live)), "protected")
    assert code == 2 and report["refusal"]["code"] == "PATH_PROTECTED", report.get("refusal")
    assert "ai-work-lab" in report["refusal"]["detail"]
    assert _file_sha256(live) == digest_before, "a refusal must not touch the live store"

    code, report, _ = _run(roots, roots.command("--allow-root", str(TARGET_ROOT)), "allow-root")
    assert code == 2 and report["refusal"]["code"] == "ALLOW_ROOT_PROTECTED", report.get("refusal")

    escaping = roots.target / ".project-local" / "migration" / ".." / ".." / "escape.db"
    code, report, _ = _run(roots, roots.command("--target-work", str(escaping)), "dotdot")
    assert code == 2 and report["refusal"]["code"] == "PATH_HAS_PARENT_TRAVEL", report.get("refusal")
    assert not (roots.target / ".project-local" / "escape.db").exists()

    outside = roots.base / "outside.db"
    code, report, _ = _run(roots, roots.command("--target-work", str(outside)), "outside")
    assert code == 2 and report["refusal"]["code"] == "PATH_OUTSIDE_ALLOWED_ROOT", report.get("refusal")


def test_real_private_source_root_is_blocked_with_the_authorization_text(roots: Roots):
    private = Path.home() / ".hermes"
    argv = ["--source-root", str(private),
            "--source-work", str(private / "work.db"),
            "--source-design", str(private / "design.db"),
            "--source-unified", str(private / "unified.db"),
            "--target-root", str(roots.target),
            "--target-work", str(roots.target_dbs["work"]),
            "--target-design", str(roots.target_dbs["design"]),
            "--target-unified", str(roots.target_dbs["unified"]),
            "--allow-root", str(roots.base)]
    code, report, stderr = _run(roots, argv, "private")
    assert code == 3, (code, report.get("refusal"), stderr[-2000:])
    assert report["refusal"]["code"] == "SOURCE_ROOT_PRIVATE"
    assert "owner decision" in report["refusal"]["detail"].lower()
    assert report["real_data_migration"]["status"] == "NOT_RUN"
    for key in SOURCE_TABLES:
        assert _target_rows(roots, key) == [], f"{key} was written from a blocked source"


# ---------------------------------------------------------------------------
# 9. derived index and dry run
# ---------------------------------------------------------------------------

def test_fts_index_drops_and_rebuilds_after_migration_with_identical_hits(roots: Roots):
    code, report, stderr = _run(roots, roots.command("--init-targets", "--verify-index",
                                                   "--search-term", KNOWLEDGE_TERM), "index")
    assert code == 0, (report.get("refusal"), stderr[-3000:])
    cycle = report["index_cycle"]
    assert cycle["equal_to_source"] is True
    assert cycle["equal_to_post_migration"] is True
    assert cycle["hits_after_migration"][KNOWLEDGE_TERM], "an empty hit set would make this vacuous"
    assert cycle["index_state_after_delete"]["indexed_entries"] == 0
    rebuilt = cycle["index_state_after_rebuild"]
    assert rebuilt["indexed_entries"] == rebuilt["revision_rows_covering_entries"] == 2
    assert cycle["hits_after_rebuild"][KNOWLEDGE_TERM] == cycle["hits_after_migration"][KNOWLEDGE_TERM]
    assert cycle["product_search_after_rebuild"][KNOWLEDGE_TERM]["strategy"] == "TRIGRAM"
    # no canonical row was lost while the index was gone
    assert len(_target_rows(roots, "design.knowledge_entry_revision")) == 3
    entries = {row["entry_id"] for row in _target_rows(roots, "design.knowledge_entry")}
    assert entries == {row["entry_id"] for row in _source_rows(roots, "design.knowledge_entry")}
    conn = sqlite3.connect(f"file:{roots.target_dbs['design'].as_posix()}?mode=ro", uri=True)
    try:
        indexed = {row[0] for row in conn.execute("SELECT DISTINCT entry_id FROM knowledge_entry_fts")}
    finally:
        conn.close()
    assert indexed == entries


def _make_directory_link(target: Path, link: Path) -> bool:
    """Try an unprivileged symlink first, then an NTFS junction (both are reparse points)."""
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        pass
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                            capture_output=True, text=True, errors="replace")
    return result.returncode == 0 and link.is_junction()


def test_reparse_point_in_the_target_path_is_refused(roots: Roots):
    """A link or junction inside the allowed root is still a refusal.

    realpath() alone would resolve an inside-the-root junction to a perfectly legal path and
    the write would land somewhere nobody reviewed; the chain is therefore checked both as
    the caller wrote it and as the filesystem resolves it.
    """
    real = roots.base / "v12-real"
    real.mkdir(parents=True, exist_ok=True)
    link = roots.base / "v12-link"
    if not _make_directory_link(real, link):
        pytest.skip("this host grants neither symlink nor junction creation to an "
                    "unprivileged process; the guard stays unexercised here")
    try:
        code, report, _ = _run(roots, roots.command("--target-work",
                                                   str(link / "work.db")), "reparse")
        assert code == 2, (code, report.get("refusal"))
        assert report["refusal"]["code"] in ("PATH_TRAVERSES_LINK", "PATH_OUTSIDE_ALLOWED_ROOT",
                                            "PATH_PROTECTED"), report["refusal"]
        assert list(real.iterdir()) == [], "the refused run wrote inside the linked directory"
        for key in SOURCE_TABLES:
            assert _target_rows(roots, key) == [], key
    finally:
        try:
            os.rmdir(str(link))
            real.rmdir()
        except OSError:
            pass


def test_sources_are_never_written_by_a_migration(roots: Roots):
    source_before = _witness(roots, "source")
    digests = {role: _file_sha256(db) for role, db in roots.source_dbs.items()}
    code, report, stderr = _run(roots, roots.command("--init-targets", "--verify-index",
                                                   "--search-term", KNOWLEDGE_TERM), "readonly-src")
    assert code == 0, (report.get("refusal"), stderr[-2000:])
    assert _witness(roots, "source") == source_before
    assert {role: _file_sha256(db) for role, db in roots.source_dbs.items()} == digests, \
        "a migration opened a source store for writing"


def test_sqlite_constraint_refusal_is_reported_and_rolled_back(roots: Roots):
    """A constraint the preflight does not name still cannot leave a half-written target.

    Here the destination carries a uniqueness rule of its own (a local index somebody added
    to the WORK store) that the source data violates. The tool cannot have known that, so
    SQLite is the one that refuses — and the point of this test is what happens next: the
    staged stores roll back, the refusal is in the report with the statement that produced
    it, and a retry after the source is repaired lands the same rows.
    """
    # a second WORK project sharing a display name with an existing one
    _raw_write(roots.source_dbs["work"], [(
        "INSERT INTO projects(project_id, root_path, display_name, registered_at, status)"
        " VALUES (?,?,?,?,?)",
        ("wl-dup", str(roots.source), "第二个项目", "2026-10-30T08:00:00Z", "REGISTERED"))])
    # the destination pre-created with its own uniqueness rule, so the run does not init it
    CanonicalStore(roots.target_dbs["work"]).close()
    _raw_write(roots.target_dbs["work"], [(
        "CREATE UNIQUE INDEX projects_display_name ON projects(display_name)", ())])
    UnifiedStore(roots.target_dbs["unified"]).close()
    from design_lab.knowledge_library import KnowledgeLibrary  # noqa: F401  owns the DDL below
    from scripts.migrate_business_data import init_target_design
    init_target_design(roots.target_dbs["design"], roots.target)

    code, report, stderr = _run(roots, roots.command(), "constraint")
    assert code == 7, (code, report.get("refusal"), stderr[-2000:])
    assert report["refusal"]["code"] == "SQL_WRITE_REFUSED", report["refusal"]
    assert "UNIQUE constraint failed" in report["sql_failure"]["error"]
    assert report["sql_failure"]["already_committed_stores"] == []
    assert sorted(report["sql_failure"]["rolled_back_stores"]) == ["design", "unified", "work"]
    for key in SOURCE_TABLES:
        assert _target_rows(roots, key) == [], f"{key} survived a refused statement"

    # repair the source, retry, and the same batch lands intact
    _raw_write(roots.source_dbs["work"], [(
        "DELETE FROM projects WHERE project_id = ?", ("wl-dup",))])
    code, report, stderr = _run(roots, roots.command("--resume"), "constraint-retry")
    assert code == 0, (report.get("refusal"), stderr[-2000:])
    assert len(_target_rows(roots, "work.projects")) == 2
    assert len(_target_rows(roots, "unified.tasks")) == 2


def test_dry_run_writes_no_rows(roots: Roots):
    code, report, stderr = _run(roots, roots.command("--init-targets", "--dry-run"), "dry")
    assert code == 0, (report.get("refusal"), stderr[-2000:])
    assert report["outcome"] == "PREFLIGHT_ONLY_ZERO_WRITES"
    assert report["preflight"]["passed"] is True
    assert report["preflight"]["types"]["design.knowledge_entry_revision"]["source_rows"] == 3
    assert report["preflight"]["types"]["unified.tasks"]["source_rows"] == 2
    for key in SOURCE_TABLES:
        assert _target_rows(roots, key) == [], key
