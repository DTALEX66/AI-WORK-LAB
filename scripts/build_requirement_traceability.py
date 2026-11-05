# SPDX-License-Identifier: MIT
"""Requirement traceability: every handoff-table row gets a *mechanically checked* disposition.

Why this exists
---------------
``AI-WORK-LAB_HANDOFF_20261029/`` ships four tables that together describe the whole
product promise -- 56 legacy UI entries (04), 30 capability families (05), 25 explicit
requirements and preferences (11) and 15 proposed API endpoints (08). The closure
documents only ever cited the 198 WORK gap rows and the per-file source coverage, so
those four tables had **no** reconciliation against the code: a reader could not tell
whether "PROPOSED_NOT_IMPLEMENTED" was still true, partly true, or simply stale.

This builder makes every row carry a verifiable disposition. It is fail-closed by
construction, not by wording:

* a ``file:line`` location is read from disk -- the path must exist, the line must
  exist, and the line must be non-blank;
* a route location must match a **live** entry imported from
  ``backend.v1.V1_ROUTES`` (75 routes, including the 49 WORK-surface routes) or
  ``design_lab.http_service.ROUTES`` (89 compatibility routes) -- never prose;
* a test citation resolves only when the file exists **and** declares that test name;
* an evidence citation resolves only when the JSON exists under
  ``.project-local/audit/20261030-qoder-ed9037/`` **and** the dotted key path is present;
* ``DEFERRED_P2``/``DEFERRED_P3`` must be backed by the row's own 分期 text or by a task
  id that ``09_任务分期与验收.json`` really records with that phase;
* ``EXCLUDED_BY_OWNER`` must quote, verbatim, a decision string that is present in the
  source row itself -- an exclusion invented by this script downgrades to ``GAP``;
* ``PARTIAL`` must name its missing part with the marker ``缺口：``, otherwise it is not
  a partial, it is a gap;
* ``IMPLEMENTED_VERIFIED`` is reachable only when the location *and* every evidence
  citation resolve. Code that exists but is not covered by a test/探测 stays
  ``IMPLEMENTED_UNVERIFIED``.

A status is therefore never inherited from a document saying "done": the docstring of
this file, ``docs/CODEX-AUDIT-ENTRY.md`` and the frozen handoff tables are all inputs to
be checked, never authorities to be copied.

The authored part is the judgement in ``basis`` (which anchor represents this promise,
what the cited test actually proves, what is still missing). The machine part is whether
those anchors resolve. Both are written into the same column so a reader can tell them
apart: ``[判定]`` prefixes the authored judgement, ``[机验]`` the resolved result.

Registers written (all four are NEW files; nothing existing is modified):
``migration/ui-entry-disposition.csv``,
``migration/capability-family-register.csv``,
``migration/requirement-traceability.csv``,
``migration/api-contract-check.json``.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from published_stamp import keeping_the_recorded_stamp  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF = REPO_ROOT / "AI-WORK-LAB_HANDOFF_20261029"
UI_TABLE = HANDOFF / "04_原界面入口映射.csv"
FAMILY_TABLE = HANDOFF / "05_能力族分期.csv"
REQUIREMENT_TABLE = HANDOFF / "11_需求追溯.csv"
PROTOCOL_TABLE = HANDOFF / "08_前后端交接约定.json"
PHASING_TABLE = HANDOFF / "09_任务分期与验收.json"
OUT_DIR = REPO_ROOT / "migration"
EVIDENCE_DIR = REPO_ROOT / ".project-local" / "audit" / "20261030-qoder-ed9037"

#: The closed status vocabulary. Nothing outside this tuple may be written.
STATUSES = (
    "IMPLEMENTED_VERIFIED",
    "IMPLEMENTED_UNVERIFIED",
    "PARTIAL",
    "GAP",
    "DEFERRED_P2",
    "DEFERRED_P3",
    "EXCLUDED_BY_OWNER",
)

#: Sentinels used inside the claim tables below.
ABSENT = "ABSENT"          # no implementation location exists for this promise
#: The nodes that replaced "本仓无 pytest 断言" in the rows below. Names live here once so a
#: renamed test has to be fixed in one place, and test_v16 resolves every one of them.
V03_TOOLS_TEST = "tests/unified/test_v03_work_loop.py::test_entry_work_tools_state_is_read_from_the_qualification_ledger"
V03_AUDIT_TEST = "tests/unified/test_v03_work_loop.py::test_entry_work_audit_integrity_names_the_tampered_result"
V03_EXECUTION_TEST = "tests/unified/test_v03_work_loop.py::test_entry_work_execution_detail_attempt_is_the_stored_row"
V03_RECORDS_TEST = "tests/unified/test_v03_work_loop.py::test_entry_design_records_plan_list_reads_back_created_plan"
V03_DELIVERABLES_TEST = "tests/unified/test_v03_work_loop.py::test_entry_design_deliverables_bundle_list_reads_back_registered_bundle"
V03_EVIDENCE_TEST = "tests/unified/test_v03_work_loop.py::test_entry_design_evidence_projection_refusal_names_the_absent_ledger"
V02_PROJECT_DETAIL_TEST = "tests/unified/test_v02_surface.py::test_project_detail_route_returns_the_one_project_written"
V02_ENVIRONMENT_TEST = "tests/unified/test_v02_surface.py::test_environment_projection_reads_the_paths_ledger_at_boot"
V02_USAGE_TEST = "tests/unified/test_v02_surface.py::test_observer_projection_usage_reports_what_the_store_holds"
V02_SOFTWARE_TEST = "tests/unified/test_v02_surface.py::test_software_projection_is_the_registry_read_now_not_a_copy"
V02_INTAKE_TEST = "tests/unified/test_v02_surface.py::test_intake_brief_goals_and_revisions_read_back"
V02_RESEARCH_TEST = "tests/unified/test_v02_surface.py::test_research_findings_read_back_only_what_was_filed"
V02_SETTINGS_TEST = "tests/unified/test_v02_surface.py::test_settings_read_set_answers_and_writes_nothing"
V18_USAGE_UNKOWN_TEST = ("tests/unified/test_v18_tools_connections.py::"
                         "test_usage_projection_never_renders_unknown_as_a_measured_zero")
V18_USAGE_SPLIT_TEST = ("tests/unified/test_v18_tools_connections.py::"
                        "test_usage_measured_and_estimated_costs_use_separate_keys")
V18_UNCLASSIFIED_TEST = ("tests/unified/test_v18_tools_connections.py::"
                         "test_unclassified_review_recomputes_from_the_mapping_population_not_from_its_own_words")


def _nodes(module: str, *names: str) -> str:
    """Semicolon-joined pytest node ids for one batch of tests, spelled out once.

    A row that cites six nodes would otherwise repeat the file path six times; test_v16 resolves
    every pointer in the published register, so a renamed test still lands here as a build error
    rather than a register that cites something no longer present.
    """
    return ";".join("tests/unified/%s::%s" % (module, name) for name in names)


#: 05#L8 -- the issue chain's own forward/backward link predicates and their falsifiers.
V11_CHAIN_NODES = _nodes("test_v11_audit_rework.py",
    "test_issue_chain_forward_references_resolve_to_real_rows_in_the_same_store",
    "test_issue_chain_broken_link_is_named_by_the_verdict",
    "test_issue_chain_reverse_trace_from_a_verdict_names_the_same_ids",
    "test_issue_chain_one_tampered_identifier_is_named_and_the_row_restores",
    "test_issue_chain_double_projection_is_byte_identical_except_one_named_field",
    "test_issue_chain_link_predicates_falsification")
#: 05#L11 -- the managed-adapter-registry read chain: follows the file, restores, writes nothing.
V02_CONFIG_NODES = _nodes("test_v02_surface.py",
    "test_local_profile_entry_restore_leaves_native_auth_and_global_environment",
    "test_no_write_entry_reaches_managed_config_native_auth_or_global_environment",
    "test_managed_config_restore_follows_the_file_and_lands_no_new_persistent_write",
    "test_machine_absolute_paths_travel_as_paths_not_as_verified_evidence")
#: 05#L16 -- source / date / probe / qualification as four separate axes of the model radar surface.
V09_RADAR_NODES = _nodes("test_v09_honesty.py",
    "test_radar_catalog_source_date_probe_qualification_are_four_separate_axes",
    "test_radar_catalog_absent_field_is_null_while_unknown_stays_unknown",
    "test_radar_catalog_source_and_date_equal_the_recorded_strings",
    "test_radar_catalog_follows_edited_registries_and_changes_nothing_else",
    "test_radar_qualification_cannot_be_minted_from_documentation_or_probe",
    "test_radar_weights_state_cannot_be_folded_back_onto_the_count",
    "test_radar_catalog_document_satisfies_the_published_schema")
#: 05#L21|design-domain and 05#L28|research -- the two rows that had no assertion at all.
V24_DOMAIN_NODES = _nodes("test_v24_capability_evidence.py",
    "test_domain_pack_projection_reports_the_disk_and_invents_no_verdict",
    "test_the_pack_verdict_is_the_checkers_and_an_unreadable_pack_is_never_dropped")
V24_RESEARCH_NODES = _nodes("test_v24_capability_evidence.py",
    "test_research_material_is_data_that_no_runtime_path_imports")
V24_RECON_NODES = _nodes("test_v24_capability_evidence.py",
    "test_rir_contract_is_one_document_in_three_places_and_refuses_what_it_must")
#: 05#L23 -- a real migrated RIR document, walked through the raster branch end to end.
V24_RASTER_NODES = _nodes("test_v24_capability_evidence.py",
    "test_a_migrated_rir_sample_passes_the_contract_with_a_raster_node",
    "test_relative_and_absolute_project_roots_reach_the_same_raster_verdict",
    "test_the_raster_path_reports_the_gates_a_real_document_actually_hits")
#: 05#L22 -- asset versions, byte-pinned references, the input/output split, no platform channel.
V04_ASSET_NODES = _nodes("test_v04_design_loop.py",
    "test_design_asset_versions_are_immutable_history_and_both_revisions_read_back",
    "test_design_asset_reference_pins_its_bytes_and_other_projects_are_refused",
    "test_design_input_material_and_output_artifact_stay_two_different_kinds",
    "test_design_asset_surface_offers_no_external_platform_channel")
#: 05#L18 -- the three prompt routes behind real HTTP: compose, list, review, plus the store guard.
V04_PROMPT_NODES = _nodes("test_v04_design_loop.py",
    "test_design_prompt_composition_is_not_an_artwork_row",
    "test_design_prompt_composition_refusals_are_named_and_store_nothing",
    "test_design_prompt_results_list_parses_its_own_query",
    "test_design_prompt_result_review_requires_a_named_human",
    "test_design_prompt_store_guard_answers_instead_of_a_quiet_201")
#: 05#L27 -- consumers, version compatibility, refused inputs and resource-path regressions.
V05_CONTRACT_NODES = _nodes("test_v05_rejections.py",
    "test_contracts_control_plane_reads_the_published_request_contract",
    "test_contracts_control_request_documents_accepted_and_refused_with_named_code",
    "test_contracts_control_result_envelope_matches_published_result_contract",
    "test_contracts_action_plan_product_generated_pack_satisfies_published_schema",
    "test_contracts_action_plan_published_examples_are_the_contract_test_docs",
    "test_contracts_action_plan_store_row_version_compat_and_solution_consumer_refusal",
    "test_contracts_solution_schema_consumer_accepts_and_refuses_with_named_code",
    "test_contracts_client_adapter_verb_vocabulary_agrees_across_schema_matrix_and_snapshot_consumer",
    "test_contracts_snapshot_v3_version_is_compared_not_rederived",
    "test_the_excerpt_bound_and_the_schema_max_length_are_the_same_number",
    "test_contracts_every_published_schema_ref_resolves_to_a_real_repo_file",
    "test_contracts_planted_broken_ref_makes_the_resource_predicate_red",
    "test_contracts_published_inventory_and_consumed_set_do_not_drift")

#: The sentence every software-projection row still owes: nothing was probed on this machine.
NOT_PROBED_SENTENCE = ("不声称任何真实软件在本机被探测、安装、授权或执行——那仍是 "
                       "DECLARED_NOT_PROBED / NOT_PROBED")

NO_EVIDENCE = "NONE"       # nothing measures this row
PARTIAL_MARKER = "缺口："   # a PARTIAL row must name what is missing
# Derived at build time, never hand-copied: the contracts row cites it, so a reader can
# see whether the published surface grew since the sentence was written.
CONTRACTS_PUBLISHED_JSON = len(list((REPO_ROOT / "packages" / "contracts").rglob("*.json")))

LOCATION_LINE_RE = re.compile(r"^(?P<path>.+):(?P<line>\d+)$")
#: A ``file::name`` location is the same claim with the offset removed: the cited construct is the
#: one called ``name``, and it resolves while the file grows above it. Uniqueness is the whole
#: contract -- a name the file defines twice says nothing, and ``find_definition``/``find_binding``
#: only emit this form when the name occurs once.
LOCATION_SYMBOL_RE = re.compile(r"^(?P<path>[^:]+)::(?P<name>[A-Za-z_][A-Za-z0-9_]*)$")
#: A ``file:line`` location must name a binding: a (possibly indented) ``def`` / ``class`` /
#: decorator, or a module-level assignment or annotated name. Anchors that only have to be
#: "non-empty" survive drift onto a dict entry, a closing brace or a comment, and the row
#: then claims a location that is not the implementation it describes.
ANCHOR_FORM_RE = re.compile(r"^(?:\s*(?:def\s|class\s|@)|[A-Za-z_][A-Za-z0-9_]*\s*[:=])")
PHASE_TASK_RE = re.compile(r"\bL(\d{2})\b")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# live route tables (imported, never grepped)
# --------------------------------------------------------------------------

_ROUTE_CACHE = None


def live_routes() -> dict[tuple[str, str], dict]:
    """{(method, pattern): {"table": ..., "handler": ...}} from the two live tables."""
    global _ROUTE_CACHE
    if _ROUTE_CACHE is None:
        for entry in (str(REPO_ROOT), str(REPO_ROOT / "domains" / "design")):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        from backend.v1 import V1_ROUTES
        from design_lab.http_service import ROUTES as COMPAT_ROUTES

        table: dict[tuple[str, str], dict] = {}
        for route in V1_ROUTES:
            table[(route.method, route.pattern)] = {
                "table": "backend.v1.V1_ROUTES", "handler": route.action}
        for route in COMPAT_ROUTES:
            table.setdefault((route.method, route.pattern), {
                "table": "design_lab.http_service.ROUTES", "handler": route.action})
        table[("__counts__", "__counts__")] = {
            "v1_routes": len(V1_ROUTES), "compat_routes": len(COMPAT_ROUTES)}
        _ROUTE_CACHE = table
    return _ROUTE_CACHE


def route_counts() -> tuple[int, int]:
    entry = live_routes()[("__counts__", "__counts__")]
    return int(entry["v1_routes"]), int(entry["compat_routes"])


def current_branch() -> str:
    """The checked-out branch, read live: naming it in a register otherwise rots the day the branch moves."""
    import subprocess
    out = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], capture_output=True,
                         cwd=str(REPO_ROOT)).stdout.decode("utf-8", errors="replace").strip()
    return out or "(detached HEAD)"


_PACK_CACHE: dict | None = None


def domain_pack_readback() -> dict:
    """The domain-pack qualification, read from the projection this route serves.

    This row used to assert that no pack had ever been checked. That sentence goes stale
    the moment the repository's own checker is present, and a stale "not done yet" reads
    as honest caution while it is actually false -- so every figure below is taken from
    ``domain_packs.build()`` at build time instead of being typed here.
    """
    global _PACK_CACHE
    if _PACK_CACHE is None:
        for entry in (str(REPO_ROOT), str(REPO_ROOT / "domains" / "design")):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        from design_lab import domain_packs

        document = domain_packs.build()
        by = document["counts"]["byValidation"]
        refused = sorted((entry for entry in document["packs"]
                          if entry["validation"] == domain_packs.INVALID),
                         key=lambda entry: str(entry["packId"]))
        _PACK_CACHE = {
            "checker": document["checker"]["state"],
            "packs": document["counts"]["packs"],
            "listed": len(document["packs"]),
            "validates": by.get(domain_packs.VALIDATES, 0),
            "invalid": by.get(domain_packs.INVALID, 0),
            "unreadable": by.get(domain_packs.UNREADABLE, 0),
            "not_checked": by.get(domain_packs.NOT_CHECKED, 0),
            "refused": "、".join(
                "%s（清单 %s，%s 条理由，首条「%s」）" % (
                    entry["packId"], entry["manifestSchemaVersion"],
                    entry["validationErrorCount"],
                    str((entry["validationErrors"] or [""])[0])[:64])
                for entry in refused) or "无",
        }
    return _PACK_CACHE


def find_definition(name: str, relative: str) -> str | None:
    """Where ``name`` is defined in ``relative`` -- ``file::name`` when that names one place.

    This used to answer ``file:line``, and the number was a claim about a file the project edits every
    round: folding two lines of ``backend/v1.py`` into one moved four of these cites in a single run
    (the register's own guard caught it and went red). A name is what the cite means -- *this route's
    handler is that def* -- and it cannot slide when somebody writes above it. The number stays when
    the name occurs more than once, because an anchor that could mean two places is worse than a
    moving one. Same rule as the coverage register's ``authority`` column (§15.40).
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    pattern = re.compile(r"^\s*(?:def|class)\s+%s\b" % re.escape(name))
    hits = [index for index, text in enumerate(lines, start=1) if pattern.search(text)]
    if not hits:
        return None
    return "%s::%s" % (relative, name) if len(hits) == 1 else "%s:%d" % (relative, hits[0])


def find_binding(name: str, relative: str) -> str | None:
    """``relative`` -> the module-level ``name = ...`` / ``name: T = ...`` line, named where unique.

    ``find_definition`` only walks ``def``/``class`` headers. A table that lives at module level
    (the route list is one) has no definition to name, and typing its line number reproduces the
    same drift this derives away for everything else -- so the binding gets ``file::name`` too, on
    the same uniqueness rule.
    """
    path = REPO_ROOT / relative
    if not path.is_file():
        return None
    pattern = re.compile(r"^%s\s*[:=]" % re.escape(name))
    hits = [index for index, text in enumerate(path.read_text(encoding="utf-8", errors="replace")
                                               .splitlines(), start=1) if pattern.match(text)]
    if not hits:
        return None
    return "%s::%s" % (relative, name) if len(hits) == 1 else "%s:%d" % (relative, hits[0])


# --------------------------------------------------------------------------
# verification primitives
# --------------------------------------------------------------------------

def check_repo_state(what: str) -> tuple[bool, str]:
    """Resolve a claim about this repository's own checkout state -- by asking git, not by reading bytes.

    ``repo:branch`` exists because U11 used to cite ``.git/HEAD:1`` as its 当前实现位置. That address is
    not auditable repository content (no clone can diff it, it is outside ``git ls-files``), and a
    detached checkout -- which is exactly how this project's clone-repro harness checks a commit out --
    stores a bare SHA there instead of ``ref: refs/heads/...``. The line still existed and was still
    non-empty, so the guard stayed green at the one moment the claim stopped being true. Asking git
    makes a detached HEAD a named refusal instead.
    """
    if what != "branch":
        return (False, "未知的 repo: 形态 repo:%s（本登记只认识 repo:branch）" % what)
    result = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=str(REPO_ROOT),
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    name = (result.stdout or "").strip()
    if result.returncode != 0 or not name:
        return (False, "HEAD 是分离的（detached），没有检出的分支，而本行声称的正是"
                       "「在检出的本地工作分支上执行」")
    return (True, "机验：`git symbolic-ref --short HEAD` 现读为 %s" % name)


def check_location(spec: str) -> tuple[bool, str]:
    """Resolve one 当前实现位置 claim. Never trusts the author."""
    if spec == ABSENT:
        return (False, "无实现位置（按声明）")
    repo_state = re.match(r"^repo:(?P<what>[\w-]+)$", spec)
    if repo_state:
        return check_repo_state(repo_state.group("what"))
    route = re.match(r"^(GET|POST|PUT|PATCH|DELETE) (/.*)$", spec)
    if route:
        key = (route.group(1), route.group(2))
        entry = live_routes().get(key)
        if entry is None:
            return (False, "路由 %s %s 不在实测路由表（V1_ROUTES 与兼容表）中" % key)
        return (True, "路由 %s %s 存在于 %s，handler=%s"
                % (key[0], key[1], entry["table"], entry["handler"]))
    symbol = LOCATION_SYMBOL_RE.match(spec)
    if symbol:
        path = REPO_ROOT / symbol.group("path")
        if not path.is_file():
            return (False, "文件不存在：%s" % symbol.group("path"))
        name = symbol.group("name")
        header = re.compile(r"^(?:\s*(?:def|class)\s+%s\b|%s\s*[:=])"
                            % (re.escape(name), re.escape(name)))
        hits = [text.strip() for text in path.read_text(encoding="utf-8", errors="replace")
                .splitlines() if header.match(text)]
        if not hits:
            return (False, "%s 里没有名为 %s 的定义或模块级绑定" % (symbol.group("path"), name))
        if len(hits) > 1:
            return (False, "%s 在 %s 出现 %d 次，锚点说不出是哪一个"
                            % (name, symbol.group("path"), len(hits)))
        return (True, "%s::%s 定义唯一：%s" % (symbol.group("path"), name, hits[0][:80]))
    match = LOCATION_LINE_RE.match(spec)
    if not match:
        return (False, "位置写法既不是 file::name、file:line，也不是「METHOD /pattern」，"
                       "也不是 repo:<形态>：%s" % spec)
    git_internal = match.group("path").replace("\\", "/")
    if git_internal.startswith(".git/") or "/.git/" in git_internal:
        # .git/ bytes are not auditable repository content: no clone can diff them, they are outside
        # `git ls-files`, and a detached checkout puts a bare SHA where a branch ref used to be -- so
        # the line keeps existing while the claim about it stops holding. Repository state is asked
        # of git itself, through repo:branch above.
        return (False, "实现位置不能指向 .git/ 内部的字节（%s）：那不是仓库内容，分离检出时"
                       "内容还会完全换一个意思；仓库自身状态请用 repo:branch" % match.group("path"))
    path = REPO_ROOT / match.group("path")
    wanted = int(match.group("line"))
    if not path.is_file():
        return (False, "文件不存在：%s" % match.group("path"))
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return (False, "文件不可读：%s（%s）" % (match.group("path"), type(exc).__name__))
    if wanted < 1 or wanted > len(lines):
        return (False, "%s 只有 %d 行，第 %d 行不存在" % (match.group("path"), len(lines), wanted))
    raw_line = lines[wanted - 1]
    stripped = raw_line.strip()
    if not stripped:
        return (False, "%s 第 %d 行为空行，不能作为实现位置" % (match.group("path"), wanted))
    if match.group("path").endswith(".py") and not ANCHOR_FORM_RE.match(raw_line):
        # A bare "non-empty line" test let an anchor drift onto a dict entry, a closing brace
        # or a comment as soon as anything above it grew -- the row then still read as
        # "位置已解析" while naming something that is not the implementation.
        return (False, "%s 第 %d 行不是定义行（def / class / 装饰器 / 模块级绑定），"
                       "锚点已随上方编辑漂移，须重新钉到定义处：%r"
                      % (match.group("path"), wanted, stripped[:60]))
    return (True, "%s:%d 存在且非空：%s"
            % (match.group("path"), wanted, stripped[:80]))


def check_evidence(spec: str) -> tuple[bool, str]:
    """Resolve one 验证证据 citation: pytest node id or an evidence-JSON key path."""
    if spec == NO_EVIDENCE:
        return (False, "无验证证据（NONE）")
    ok_all, notes = True, []
    for part in [piece.strip() for piece in spec.split(";") if piece.strip()]:
        resolved, note = _check_one_evidence(part)
        ok_all = ok_all and resolved
        notes.append(("✓" if resolved else "✗") + " " + note)
    return (ok_all, " ｜ ".join(notes))


def _check_one_evidence(part: str) -> tuple[bool, str]:
    if part.startswith("evidence:"):
        body = part[len("evidence:"):]
        file_name, _, dotted = body.partition("#")
        path = EVIDENCE_DIR / file_name
        if not path.is_file():
            return (False, "证据文件不存在：.project-local/audit/20261030-qoder-ed9037/" + file_name)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return (False, "证据 JSON 不可解析：%s（%s）" % (file_name, type(exc).__name__))
        if not dotted:
            return (True, "%s 可读" % file_name)
        cursor = document
        for step in dotted.split("."):
            if isinstance(cursor, dict) and step in cursor:
                cursor = cursor[step]
            elif isinstance(cursor, list) and step.isdigit() and int(step) < len(cursor):
                cursor = cursor[int(step)]
            else:
                return (False, "%s 中没有键路径 %s" % (file_name, dotted))
        return (True, "%s#%s 存在（值 %s）"
                % (file_name, dotted, json.dumps(cursor, ensure_ascii=True)[:60]))
    if "::" not in part:
        return (False, "证据写法既不是 tests/…py::test_* 也不是 evidence:…#key：" + part)
    file_part, _, remainder = part.partition("::")
    path = REPO_ROOT / file_part
    if not path.is_file():
        return (False, "测试文件不存在：" + file_part)
    collectible = collectible_node_ids(path)
    if remainder not in collectible:
        return (False, "%s::%s 不是 pytest 能收集的节点（该文件收集得到：%s）"
                % (file_part, remainder, ", ".join(sorted(collectible)[:6]) or "空"))
    return (True, "%s::%s 可被 pytest 收集" % (file_part, remainder))


# --------------------------------------------------------------------------
# the reconciliation itself
# --------------------------------------------------------------------------

def collectible_node_ids(path: Path) -> set[str]:
    """Every node id pytest could collect from one test file, spelled the way pytest spells it.

    Read off the file's own syntax tree, not off a grep for a ``def`` line: module-level ``test_*``
    functions are bare names, while methods of a ``unittest.TestCase`` class collect as
    ``Class::method``. A citation that leaves the class out matches nothing — measured, a legacy
    row's ``file.py::test_method`` answered "no tests ran" — so resolving a citation means
    matching the whole part after the file, and the four registers now carry the qualified spelling.
    """
    import ast as _ast

    tree = _ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, _ast.FunctionDef) and node.name.startswith("test_"):
            found.add(node.name)
        elif isinstance(node, _ast.ClassDef):
            for item in node.body:
                if isinstance(item, _ast.FunctionDef) and item.name.startswith("test_"):
                    found.add("%s::%s" % (node.name, item.name))
    return found


def phasing_tasks() -> dict[str, str]:
    """task id -> declared phase, read from 09_任务分期与验收.json."""
    document = json.loads(PHASING_TABLE.read_text(encoding="utf-8"))
    return {item["id"]: item["phase"] for item in document["tasks"]}


def reconcile(kind: str, row_key: str, source_text: str, phase_text: str,
              claim: dict) -> dict:
    """Apply the closed vocabulary to one authored claim, downgrading what cannot resolve.

    ``source_text`` is the verbatim source row (used to prove an owner exclusion really
    is the owner's words); ``phase_text`` is that row's own 分期/运行实现分期 column.
    """
    location = claim["location"]
    evidence = claim["evidence"]
    authored = claim["status"]
    basis = claim["basis"].strip()
    downgrades: list[str] = []

    if authored not in STATUSES:
        raise SystemExit("STATUS_VOCABULARY_VIOLATION " + kind + " " + row_key)

    loc_ok, loc_note = check_location(location)
    ev_ok, ev_note = check_evidence(evidence)

    if authored in ("IMPLEMENTED_VERIFIED", "IMPLEMENTED_UNVERIFIED", "PARTIAL"):
        if not loc_ok:
            downgrades.append("位置未解析（%s）→ 降级 GAP" % loc_note)
            authored = "GAP"
        elif authored == "IMPLEMENTED_VERIFIED" and not ev_ok:
            downgrades.append("声明 VERIFIED 但证据未解析（%s）→ 降级 IMPLEMENTED_UNVERIFIED" % ev_note)
            authored = "IMPLEMENTED_UNVERIFIED"
        elif authored == "PARTIAL" and PARTIAL_MARKER not in basis:
            downgrades.append("声明 PARTIAL 但未用「%s」写明缺什么 → 降级 GAP" % PARTIAL_MARKER)
            authored = "GAP"
    elif authored in ("DEFERRED_P2", "DEFERRED_P3"):
        wanted = authored.split("_")[1]
        cited = [task for task in PHASE_TASK_RE.findall(basis)
                 if phasing_tasks().get("L" + task) == wanted]
        if wanted not in phase_text and not cited:
            downgrades.append("声明 %s 但该行分期文本无「%s」，且未引用 09 分期表中该期的任务 id → 降级 GAP"
                              % (authored, wanted))
            authored = "GAP"
        elif cited:
            ev_note = ("机验：引用的分期任务 %s 在 09_任务分期与验收.json 中确为 %s"
                       % ("、".join("L" + task for task in cited), wanted)) + " ｜ " + ev_note
    elif authored == "EXCLUDED_BY_OWNER":
        quoted = [token for token in claim.get("decision_quotes", []) if token in source_text]
        if not quoted:
            downgrades.append("声明 EXCLUDED_BY_OWNER 但引用的 owner 原话未逐字出现在来源行中 → 降级 GAP")
            authored = "GAP"
        else:
            ev_note = ("机验：排除决定逐字命中来源行——" + "、".join(quoted)) + " ｜ " + ev_note

    if authored == "GAP" and not basis:
        raise SystemExit("GAP_ROW_WITHOUT_REASON " + kind + " " + row_key)

    verdict = "[机验] 位置：%s ｜ 证据：%s" % (loc_note, ev_note)
    if downgrades:
        verdict += " ｜ [降级] " + "；".join(downgrades)
    return {
        "来源行标识": row_key,
        "要求原文": source_text,
        "当前实现位置": location if loc_ok or location == ABSENT else "GAP（原引用 %s 未能解析）" % location,
        "验证证据": evidence,
        "状态": authored,
        "依据说明": "[判定] " + basis + " " + verdict,
        "_authored_status": claim["status"],
        "_authored_location": location,
        "_authored_evidence": evidence,
        "_location_ok": loc_ok,
        "_evidence_ok": ev_ok,
        "_downgraded": bool(downgrades),
    }


def join_verbatim(fields: list[str]) -> str:
    return " | ".join(field.strip() for field in fields)


# --------------------------------------------------------------------------
# authored judgements (input to the machine; never the other way round)
# --------------------------------------------------------------------------

def ui_claims() -> dict[str, dict]:
    """One judgement per 04 row, keyed ``来源仓:原入口ID``.

    Semantics used here for this table (stated in each row's 依据说明 as well):
    IMPLEMENTED_VERIFIED needs BOTH a real fused landing spot (the shipped workbench
    navigation) AND a test in this repo over the endpoint that spot reads; the fused
    product shell is STITCH's deliverable and is recorded NOT_RUN, so the 31 WORK
    entries — which have no navigation in this repo at all — can at best be PARTIAL
    (backend surface verified, fused UI missing) or GAP (no surface either).
    """
    manual = "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart"
    projection = "tests/unified/test_v11_audit_rework.py::test_f01_unified_service_serves_the_migrated_work_projection"
    f09 = "tests/unified/test_v11_audit_rework.py::test_f09_observer_reads_answer_and_control_gate_is_enforced"
    f09w = "tests/unified/test_v11_audit_rework.py::test_f09_observer_writes_are_refused_and_recorded"
    caps = "tests/unified/test_v02_surface.py::test_capabilities_are_honest_and_derived"
    projects = "tests/unified/test_v02_surface.py::test_projects_register_and_read_back_both_sources"
    conn = "tests/unified/test_v09_honesty.py::test_connections_never_claim_connected_without_a_probe"
    knowledge = "tests/unified/test_v06_knowledge.py::test_create_search_short_queries_and_no_result"
    unified_search = "tests/unified/test_v06_knowledge.py::test_unified_search_endpoint_merges_both_libraries"
    handoff_guard = "tests/unified/test_v05_rejections.py::test_external_receipt_claim_is_not_declarable"
    import_guard = "tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused"
    stale_guard = "tests/unified/test_v05_rejections.py::test_stale_result_refused"
    dispatch_guard = "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch"
    f10 = "tests/unified/test_v11_audit_rework.py::test_f10_qualification_needs_a_probe_bound_to_this_candidate"
    improvements = "tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only"

    def partial(basis: str) -> dict:
        return {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "PARTIAL",
                "basis": basis}

    no_ui = "融合后的统一桌面壳（总览/工具/任务/知识/设置 五组导航）由 STITCH 前端交付，本轮实测登记为 NOT_RUN（evidence:delivery-summary.json#outstanding 含 FRONTEND_STITCH）；"

    work = {
        "work:work": {"location": "GET /api/work/observer/projection", "evidence": projection,
                      "status": "PARTIAL",
                      "basis": no_ui + "缺口：新产品的「总览/当前工作」视图未生成；WORK 侧当前工作的只读投影已在统一内核挂载并有断言。"},
        "work:agents": {"location": "GET /api/v1/connections", "evidence": conn,
                        "status": "PARTIAL",
                        "basis": "该行分期为「P1 投影；P2真实接线」：P1 投影已有（连接态只会是未连接，客户端不能自证 CONNECTED）。" + no_ui
                                 + "缺口：P2 真实执行器接线未做（09 的 L21 单个执行器适配为 P2 条件项；a01-a10-results.json#results.P2_native_hosts 记 NOT_RUN）。"},
        "work:projects": {"location": "GET /api/v1/projects", "evidence": projects,
                          "status": "PARTIAL",
                          "basis": "两域项目在同一端点注册并读回（work/design 同表）。" + no_ui + "缺口：「项目/列表」视图未生成。"},
        "work:project-detail": {"location": "GET /api/projects/([0-9a-f]{32})",
                                "evidence": V02_PROJECT_DETAIL_TEST, "status": "PARTIAL",
                                "basis": "DESIGN 兼容面已有单项目读取路由，且详情逐字段等于存储里的那一行、"
                                         "两个项目不互顶、未写入时 404（具名断言 + 植入反证）；" + no_ui
                                         + "缺口：WORK 项目详情视图未生成。"},
        "work:environment": {"location": "GET /api/environment",
                             "evidence": V02_ENVIRONMENT_TEST, "status": "PARTIAL",
                             "basis": "本机环境读面在兼容路由中，且条目来自启动前那份 .project/paths.json 台账、"
                                      "改一条路径只影响 shared_inputs/tools 两处（具名断言 + 植入反证）；" + no_ui
                                      + "缺口：任何软件是否真的存在仍未探测（一律 DECLARED_NOT_PROBED），视图未生成。"},
        "work:capabilities": {"location": "GET /api/v1/capabilities", "evidence": caps + ";" + f10,
                              "status": "PARTIAL",
                              "basis": "能力目录由实现/资格/依赖/连接/授权/策略派生，不可用带原因，资格只认绑定当前候选版本的探测记录；"
                                       + no_ui + "缺口：「工具/能力目录」视图未生成。"},
        "work:usage": {"location": "GET /api/work/observer/projection",
                       "evidence": projection + ";" + V02_USAGE_TEST, "status": "PARTIAL",
                       "basis": "投影响应内含 usage_summary 字段并由该测试读回；分组、数字与覆盖词都等于存储里"
                                "现写的样本，未知组保持 null 而非 0（具名断言 + 植入反证）；" + no_ui
                                + "缺口：「项目/用量」视图未生成，真实计费链路未跑过。"},
        "work:rules-adaptation": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                                  "basis": "两张实测路由表中不存在任何规则适配端点，backend/ 与 domains/ 下亦无对应读写面；来源侧的两个 HTTP 服务逐一列举过自己的端点（WORK-LAB 的 services/control/control_service.py:1148 = /api/control/descriptor、/api/control/operations、/health；与 services/orchestration/sidecar.py:714 = /api/projection、/api/v1/snapshot、/repair-packs、/solutions、/evidence-range、/events），里面都没有这一项：所以这是「从未有后端面」而不是「融合时丢了后端面」。这一层要不要新建，属 owner 的产品范围决定，不由本批擅自补端点。"},
        "work:privacy": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                         "basis": "「隐私与采集」在产品边界上成立（私有正文限制、原始任务内容与遥测分离写在 08 的 invariants 与 INTEGRATION_POLICY §5），但没有实现该设置的读写面与开关，故是缺口而不是半成品。来源侧的两个 HTTP 服务逐一列举过自己的端点（WORK-LAB 的 services/control/control_service.py:1148 = /api/control/descriptor、/api/control/operations、/health；与 services/orchestration/sidecar.py:714 = /api/projection、/api/v1/snapshot、/repair-packs、/solutions、/evidence-range、/events），里面都没有这一项：所以这是「从未有后端面」而不是「融合时丢了后端面」。来源侧它只作为设置区的一部分出现（WORK-LAB apps/observer/frontend/src/lib/legacyRoutes.ts:184 的 evidence 指向 apps/observer/frontend/src/views/settingsPrivacy.contract.test.tsx），属前端交付面。"},
        "work:executions": {"location": "GET /api/v1/tasks/([0-9a-f]{32})", "evidence": manual,
                            "status": "PARTIAL",
                            "basis": "执行记录以 Attempt 形式随任务读回；" + no_ui + "缺口：「任务/执行记录」视图未生成。"},
        "work:models": {"location": "GET /api/models", "evidence": NO_EVIDENCE, "status": "PARTIAL",
                        "basis": "该行分期为「P1档案；P2真实连接」：模型档案面已在兼容路由，模型目录不做锁定、默认 fail-closed；"
                                 + no_ui + "缺口：P2 真实连接与「工具/模型与入口」视图未生成，本仓无 pytest 断言 /api/models 口径。"},
        "work:memory": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                        "basis": "该行自身约束「不复制原生私有记忆」，因此保留的是接缝而不是实现——"
                                "接缝点名登记在 migration/deferral-register.json 的 "
                                "work.session_continuity 条目（生成器要求接缝文件真实存在）；"
                                "统一后端无会话/记忆端点，「知识/上下文与经验」视图也未生成。"},
        "work:tools": {"location": "GET /api/v1/tools",
                       "evidence": V03_TOOLS_TEST, "status": "PARTIAL",
                       "basis": "工具台账端点真实存在，且每项 state 从资格台账现读、无记录时是 NOT_PROBED 而非已连接"
                                "（具名断言 + 植入反证）；" + no_ui + "缺口：「工具/我的工具」视图未生成。"},
        "work:monitoring": {"location": "GET /api/work/observer/snapshot", "evidence": f09,
                            "status": "PARTIAL",
                            "basis": "运行观察快照经同一内核读同一 CanonicalStore，采集器健康行写一条读一条"
                                     "（具名断言 + 植入反证）；" + no_ui
                                     + "缺口：持续 watcher/SSE 推送仍在独立 sidecar（docs/CODEX-AUDIT-ENTRY.md §7），「项目/运行状态」视图未生成。"},
        "work:delivery": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                          "basis": "WORK 侧「任务/交付」没有端点：交付面（bundles/receipt）只存在于 DESIGN 兼容路由，未与统一任务信封接通，也没有 WORK 交付台账。来源侧的两个 HTTP 服务逐一列举过自己的端点（WORK-LAB 的 services/control/control_service.py:1148 = /api/control/descriptor、/api/control/operations、/health；与 services/orchestration/sidecar.py:714 = /api/projection、/api/v1/snapshot、/repair-packs、/solutions、/evidence-range、/events），里面都没有这一项：所以这是「从未有后端面」而不是「融合时丢了后端面」。来源前端路由表里也没有独立的 /delivery 项。"},
        "work:trust": {"location": "GET /api/v1/tasks/([0-9a-f]{32})/completion", "evidence": stale_guard,
                       "status": "PARTIAL",
                       "basis": "核验与可信详情由 completion 计算 + 结果时效（stale 拒绝）支撑；" + no_ui + "缺口：「任务/核验与可信详情」视图未生成。"},
        "work:software": {"location": find_definition("classify_installation", "domains/work/orchestration/software_installation_identity.py"),
                          "evidence": V02_SOFTWARE_TEST, "status": "PARTIAL",
                          "basis": "安装身份分类逻辑已迁入（classify_installation），software[] 由台账现读、"
                                   "不落第二副本：改台账即改读回、缺值保持 null、台账读不到时该键整个缺席"
                                   "（缺失不等于空数组；具名断言 + 植入反证）；" + no_ui
                                   + "缺口：任何软件被安装/探测/授权/可执行均未证明，视图未生成。"},
        "work:settings": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                          "basis": "「设置」作为总入口没有对应的统一读写面：/api/v1/health 与 /api/environment 只回答服务与本机构环境，规则/隐私/审批策略的持久化设置在两表中均无端点。来源侧的两个 HTTP 服务逐一列举过自己的端点（WORK-LAB 的 services/control/control_service.py:1148 = /api/control/descriptor、/api/control/operations、/health；与 services/orchestration/sidecar.py:714 = /api/projection、/api/v1/snapshot、/repair-packs、/solutions、/evidence-range、/events），里面都没有这一项：所以这是「从未有后端面」而不是「融合时丢了后端面」。来源侧它是前端路由（WORK-LAB .ui-reference/WORK-LAB/07_B07_前端开发规范_L7/routes/routes.ts:13 path=/settings）。"},
        "work:rules-policy": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                              "basis": "同 work:rules-adaptation：实测路由表中无规则策略端点，domains/ 下无策略账本读写实现。来源侧的两个 HTTP 服务逐一列举过自己的端点（WORK-LAB 的 services/control/control_service.py:1148 = /api/control/descriptor、/api/control/operations、/health；与 services/orchestration/sidecar.py:714 = /api/projection、/api/v1/snapshot、/repair-packs、/solutions、/evidence-range、/events），里面都没有这一项：所以这是「从未有后端面」而不是「融合时丢了后端面」。来源侧同样是前端路由（.ui-reference/WORK-LAB/07_B07_前端开发规范_L7/routes/routes.ts:8 path=/policies, id=rules-policy）。"},
        "work:audit": {"location": "GET /api/v1/integrity",
                       "evidence": V03_AUDIT_TEST, "status": "PARTIAL",
                       "basis": "完整性/诊断读面存在（integrity），且篡改一条结果摘要会被点名为 "
                                "RESULT_DIGEST_MISMATCH 并带上被改的那条 result_id（具名断言 + 植入反证）；" + no_ui
                                + "缺口：「设置/诊断与审计」视图未生成。"},
        "work:approvals": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/approval",
                           "evidence": "tests/unified/test_v10_gate.py::test_gate_accepts_backed_completions;" + f09w,
                           "status": "PARTIAL",
                           "basis": "审批写面 + 真人门（本地 Human Gate 账本，拒绝 Agent 身份冒名）已实现并有断言；"
                                    + no_ui + "缺口：「任务/待确认与权限抽屉」视图未生成，权限抽屉无实现。"},
        "work:integrations": {"location": "GET /api/v1/connections", "evidence": conn, "status": "PARTIAL",
                              "basis": "该行分期「P1档案；P2真实连接」：连接档案与探测态可读；" + no_ui
                                       + "缺口：MCP/集成真实连接属 P2（09 的 L21），未接线，视图未生成。"},
        "work:task-packs": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/pack",
                            "evidence": manual + ";" + handoff_guard, "status": "PARTIAL",
                            "basis": "人工任务包生成/声明/导入/核验全链路有测试；生成本身不声明交接。" + no_ui
                                     + "缺口：「任务/人工任务包」视图未生成。"},
        "work:workflows": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                           "basis": "该行写「P1保留既有」，但本仓没有任何工作流模板/流程端点：workflow_core 只有 repair pack 状态机与投影。来源侧的两个 HTTP 服务逐一列举过自己的端点（WORK-LAB 的 services/control/control_service.py:1148 = /api/control/descriptor、/api/control/operations、/health；与 services/orchestration/sidecar.py:714 = /api/projection、/api/v1/snapshot、/repair-packs、/solutions、/evidence-range、/events），里面都没有这一项：所以这是「从未有后端面」而不是「融合时丢了后端面」。来源侧 workflows 是前端路由与视图（.ui-reference/WORK-LAB/07_B07_前端开发规范_L7/routes/routes.ts:3 的 /workflows 与 :4 的 /workflows/:id；apps/observer/frontend/src/lib/legacyRoutes.ts:163 的 seedId=workflows 是 compat-lane），没有可「保留」的后端读写面——「P1保留既有」对这行指的是入口，不是端点。"},
        "work:workflow-editor": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "DEFERRED_P3",
                                 "basis": "该行分期「P1保留既有；P3复杂新增」：高级流程编辑器属复杂新增，按 09 分期表 L30/L31（P3）延期，来源与接缝保留，本行不声称已实现。"},
        "work:observer": {"location": "GET /api/work/observer/snapshot", "evidence": f09,
                          "status": "PARTIAL",
                          "basis": "该行要求 P1 只读：Observer 读面只读、写请求被拒并落拒绝记录（GET /api/work/observer/refusals）；" + no_ui
                                   + "缺口：「项目/运行观察详情」视图未生成。"},
        "work:execution-detail": {"location": "GET /api/v1/attempts/([0-9a-f]{32})",
                                  "evidence": V03_EXECUTION_TEST, "status": "PARTIAL",
                                  "basis": "单 Attempt 读取路由存在，且回读的就是存储里那一行（两个并发 Attempt "
                                           "各回各自的指纹、导入的结果 id 与重算摘要逐一对上；具名断言 + 植入反证）；"
                                   + no_ui + "缺口：「任务/执行详情」视图未生成。"},
        "work:evidence": {"location": "GET /api/work/observer/evidence-range", "evidence": f09,
                          "status": "PARTIAL",
                          "basis": "证据区间读面存在且经同一内核；" + no_ui + "缺口：「任务/证据抽屉」视图未生成。"},
        "work:trial-plan": {"location": find_definition("run_read_probes", "backend/core/probes.py"),
                            "evidence": f10 + ";" + conn, "status": "PARTIAL",
                            "basis": "受控探测试（run_read_probes）与资格派生分离实现，探测与执行分开写在 08 的 invariants；" + no_ui
                                     + "缺口：「工具/受控试用/方案」视图未生成，试用方案的编排面未接入自动路径。"},
        "work:trial-failure": {"location": find_definition("derive", "backend/core/qualifications.py"), "evidence": f10,
                               "status": "PARTIAL",
                               "basis": "失败/过期/外来候选记录不授予资格由 derive() 判定并有断言；" + no_ui + "缺口：「工具/受控试用/失败」视图未生成。"},
        "work:trial-readback": {"location": find_definition("loopback_http_probe", "backend/core/qualifications.py"), "evidence": f10,
                                "status": "PARTIAL",
                                "basis": "loopback 读回探测存在且只绑定当前候选版本；" + no_ui + "缺口：「工具/受控试用/读回」视图未生成。"},
    }

    def design_row(nav_line: int, status: str, basis: str, evidence: str = NO_EVIDENCE,
                   location: str | None = None) -> dict:
        return {"location": location or ("apps/workbench/shell.ts:%d" % nav_line),
                "evidence": evidence, "status": status,
                "basis": "[判定] 入口已落在 apps/workbench/shell.ts 的导航表内（该行的 view id 与来源表 04 的原入口ID 同名）"
                         + basis
                         + "（导航表的派生关系有断言存在于 apps/workbench/tests/appshell.mjs——"
                           "那是 node 门、不由 pytest 运行，所以本行缺的是视图侧的数据断言，"
                           "不是「这个仓里什么都没有」）"}

    plan_test = "tests/legacy/design/test_assistance_plan.py::AssistancePlanTests::test_a_plan_is_saved_with_its_basis_and_reads_back_after_a_restart"
    revision_test = "tests/legacy/design/test_assistance_plan.py::AssistancePlanTests::test_a_stale_revision_is_refused_with_the_actual_number"
    knowledge_test = "tests/legacy/design/test_knowledge_library.py::KnowledgeLibraryTests::test_every_minimum_field_is_stored_and_a_silent_field_is_unknown"
    target_test = "tests/legacy/design/test_target_profile.py::TargetProfileTests::test_seeded_profiles_are_served_from_the_tracked_config_with_no_database_copy"
    design_read = "tests/unified/test_v02_surface.py::test_design_domain_read_routes_answer_real_data"
    design_loop = "tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending"

    design = {
        "design:workbench": design_row(346, "IMPLEMENTED_UNVERIFIED",
                                        "；默认视图真实存在，但本仓 pytest 不断言工作台渲染，故不标 VERIFIED。"),
        "design:assistant": design_row(349, "IMPLEMENTED_VERIFIED",
                                       "；其后端合同（辅助方案存/读回/修订）由具名测试断言。", plan_test),
        "design:dashboard": design_row(350, "IMPLEMENTED_UNVERIFIED",
                                       "；「总览/设计摘要」无专门聚合端点，本仓无对应断言。"),
        "design:intake": design_row(351, "PARTIAL",
                                    "；briefs 读写路由在兼容面存在，且写入/回读/修订三份一致、旧版被标记 "
                                    "superseded_by、另一项目仍为空（具名断言 + 植入反证）" + PARTIAL_MARKER
                                    + "「#/intake」渲染与专业质量/rights 判定未证明。",
                                    V02_INTAKE_TEST),
        "design:analysis": design_row(352, "IMPLEMENTED_VERIFIED",
                                      "；分析与方案的修订冲突按真实数字拒绝，由具名测试断言。", revision_test),
        "design:prompt-intelligence": design_row(353, "PARTIAL",
                                                 "；该行分期「P1既有；P3复杂新增」，入口与既有提示词面在，" + PARTIAL_MARKER
                                                 + "P3 复杂新增（模型执行）未做（09 分期表 L32 为 P3）；提示词路由在本仓无 pytest 断言。",
                                                 NO_EVIDENCE),
        "design:research": design_row(354, "PARTIAL",
                                      "；该行分期「P1保留；外部检索本批不调用」，" + PARTIAL_MARKER
                                      + "外部检索按 INTEGRATION_POLICY §1 与 00 §四 的本地执行边界不调用；"
                                        "读写路由有本仓断言：只回读我提交的那条、提交者不替人署名、"
                                        "supersedes 链与逐字节一致性都现算（植入反证已咬住），"
                                        "但 research_verdict 恒为 null 是有意的（不据本地台账下判断）。",
                                      V02_RESEARCH_TEST),
        "design:capabilities": design_row(355, "IMPLEMENTED_VERIFIED",
                                          "；「工具/能力目录/设计筛选」读的是已实测的能力目录端点，诚实性与派生由具名测试断言。",
                                          caps),
        "design:design-domains": design_row(356, "IMPLEMENTED_UNVERIFIED",
                                            "；/api/domains 路由在，本仓无 pytest 断言 13 领域包可加载。"),
        "design:brand-systems": design_row(357, "IMPLEMENTED_UNVERIFIED",
                                           "；设计系统与 tokens 读写路由在，本仓无对应断言（P1保留既有）。"),
        "design:creative-tools": design_row(358, "PARTIAL",
                                            "；该行分期「P1档案；P2真实调用」，" + PARTIAL_MARKER
                                            + "P2 真实宿主调用-保存-重开-读回仍 BLOCKED（需逐次 Human Gate，见 docs/CODEX-AUDIT-ENTRY.md §5；09 分期表 L20 为 P2）。",
                                            "tests/unified/test_v14_registers.py::test_host_bridge_script_is_reachable_where_the_adapter_probes"),
        "design:knowledge": design_row(360, "IMPLEMENTED_VERIFIED",
                                       "；「知识/设计知识与提示词」的条目存读、修订与索引重建均有本仓断言。",
                                       knowledge_test + ";" + knowledge + ";" + unified_search),
        "design:projects": design_row(362, "IMPLEMENTED_VERIFIED",
                                      "；「项目/设计筛选」读的是统一项目端点，两域来源同表注册并读回由具名测试断言。", projects),
        "design:plan": design_row(363, "IMPLEMENTED_VERIFIED",
                                  "；「设计/目标生成包与任务关联」走统一设计闭环，专业验收在真人门前保持 pending 由具名测试断言。",
                                  design_loop + ";" + design_read),
        "design:records": design_row(365, "PARTIAL",
                                     "；「设计/我的方案与任务记录」入口在，聚合读面复用方案列表路由，"
                                     "该路由现已被断言：空表 total=0，创建后 total=1 且 plan_id/objective/"
                                     "revision 就是我创建的那条，统一聚合面读到同一 id（具名断言 + 植入反证）"
                                     + PARTIAL_MARKER + "记录视图本身的渲染与筛选未证明。",
                                     V03_RECORDS_TEST),
        "design:deliverables": design_row(366, "PARTIAL",
                                         "；交付路由（bundles/receipt/preflight）在兼容面存在，bundle 列表已被断言："
                                         "空表到登记一条后 id/version_id/sha256/byte_size 全等于写入值，"
                                         "同 kind 的非 bundle 前缀被正确排除（具名断言 + 植入反证）"
                                         + PARTIAL_MARKER + "宿主真实导出（Human Gate 与冻结范围）未证明。",
                                         V03_DELIVERABLES_TEST),
        "design:evidence": design_row(367, "PARTIAL",
                                      "；证据投影路由在，其缺席拒绝已被断言为点名缺失账本路径的 409 "
                                      "EVIDENCE_LEDGER_ABSENT 且不携带 receipts（具名断言 + 植入反证）"
                                      + PARTIAL_MARKER + "有账本时的 receipts 读回无法经此路由证明——"
                                      "融合检出有意不带该账本，属 owner 的打包决定；视图渲染同样未证明。",
                                      V03_EVIDENCE_TEST),
        "design:preflight-qa": design_row(368, "PARTIAL",
                                          "；该行分期「P1保留既有；P2宿主；P3复杂新增」，" + PARTIAL_MARKER
                                          + "宿主 preflight 的真调用属 P2（09 分期表 L20），复杂 Jury 属 P3（L31）；预检路由无本仓断言。",
                                          NO_EVIDENCE),
        "design:settings": design_row(370, "PARTIAL",
                                      "；设置视图入口在，其实际读取的三个端点已被断言：模型 counts 与逐行字段"
                                       "等于按产品路径重读的两份台账、知识索引 0→1 就是我写的那条、"
                                       "POST→404 与 PUT/PATCH/DELETE→405 之后三份读回逐字段不变（写面确实不写；"
                                       "具名断言 + 植入反证）" + PARTIAL_MARKER
                                      + "模型被加载/运行/许可裁定未证明，#/settings 渲染未证明。",
                                      V02_SETTINGS_TEST),
        "design:model-selection": design_row(374, "PARTIAL",
                                             "；该行分期「P1档案；P2真实连接」：模型选择档案与 choose 记录在（选择不等于连接和执行），"
                                             + PARTIAL_MARKER + "P2 真实连接未接线；用户显式选择只记录动作、不改合格状态。",
                                             NO_EVIDENCE),
        "design:target-profiles": design_row(378, "IMPLEMENTED_VERIFIED",
                                             "；「设计/目标组合」的软件×模型×入口种子由具名测试断言（无数据库副本、逐轴原因保留）。",
                                             target_test),
        "design:automation-connectors": design_row(381, "PARTIAL",
                                                   "；该行分期「P1档案；P2真实连接」，连接器档案路由在，" + PARTIAL_MARKER
                                                   + "P2 真实连接未接线，本仓无该路由断言。", NO_EVIDENCE),
        "design:collaboration": {"location": "apps/workbench/shell.ts:382", "evidence": NO_EVIDENCE,
                                 "status": "EXCLUDED_BY_OWNER",
                                 "decision_quotes": ["企业团队不进入主导航"],
                                 "basis": "owner 在本行的分期列写明「范围复核：个人评审归设计；企业团队不进入主导航」，并与 11_需求追溯.csv 的 P06"
                                          "「个人使用，不扩手机或企业团队平台」一致：企业团队协作平台是被明确排除的范围，不是缺口也不是待办。"
                                          "注意：该行原入口仍留在 workbench 导航里（来源保留），本登记只裁范围，不声称该能力已交付。"},
        "design:ui-states": design_row(383, "IMPLEMENTED_UNVERIFIED",
                                       "；该行分期「P1工程交接」：界面状态规范作为交接文档在 workbench 内，本仓无自动断言（人工交接物，不算运行能力）。"),
        "design:ui-components": design_row(384, "IMPLEMENTED_UNVERIFIED",
                                           "；同上，组件规范是工程交接物，本仓无自动断言。"),
    }
    claims = {}
    claims.update(work)
    claims.update(design)
    return claims


def family_claims() -> dict[str, dict]:
    manual = "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart"
    namespace = "tests/unified/test_v12_data_migration.py::test_cross_domain_same_id_is_namespaced_not_merged"
    projection = "tests/unified/test_v11_audit_rework.py::test_f01_unified_service_serves_the_migrated_work_projection"
    read_path = "tests/unified/test_v11_audit_rework.py::test_f01_read_path_starts_no_collector_and_opens_no_socket"
    f09 = "tests/unified/test_v11_audit_rework.py::test_f09_observer_reads_answer_and_control_gate_is_enforced"
    caps = "tests/unified/test_v02_surface.py::test_capabilities_are_honest_and_derived"
    return {
        "project": {"location": "POST /api/v1/tasks",
                    "evidence": "tests/unified/test_v02_surface.py::test_projects_register_and_read_back_both_sources;" + namespace,
                    "status": "IMPLEMENTED_VERIFIED",
                    "basis": "项目/工作单元与任务在同一统一存储中登记并跨域命名空间隔离，验收的「项目ID、来源路径、关联任务可读回，无跨项目污染」有直接断言。"},
        "task": {"location": "POST /api/v1/tasks", "evidence": manual + ";" + "tests/unified/test_v05_rejections.py::test_duplicate_result_refused_on_second_attempt",
                 "status": "IMPLEMENTED_VERIFIED",
                 "basis": "幂等键 (task_id, idempotency_key) 唯一、重启读回、重复结果拒绝均有具名断言；人工交接与结果核验见 04 work:task-packs。"},
        "execution": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/handoff-declarations",
                      "evidence": "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch;" + "tests/unified/test_v05_rejections.py::test_external_receipt_claim_is_not_declarable",
                      "status": "PARTIAL",
                      "basis": PARTIAL_MARKER + "P2 单个真实执行器连接、P3 多 Agent 未接线（09 分期表 L21/L30）；本轮只有 P1 人工闭环，"
                              "且一个会话一个拥有者、取消与结果不伪造只到「声明与拒绝」层，没有真实执行器可对账。"},
        "permissions": {"location": find_definition("PermissionGate", "domains/work/control/permission_gate.py"),
                        "evidence": "tests/unified/test_v02_surface.py::test_write_boundary_unknown_project_and_kind;" + f09,
                        "status": "PARTIAL",
                        "basis": "Observer 只读（写请求 405 并落拒绝记录）与 Control 写入门控有断言；" + PARTIAL_MARKER
                                + "验收的「写入校验范围与状态」只覆盖已挂载的操作面；独立授权账本在本仓不存在——新建一层授权账本是 owner 的产品范围决定，不由本批顺手补一个看起来像账本的文件。"},
        "telemetry": {"location": find_definition("observer_projection", "backend/core/work_surfaces.py"), "evidence": read_path,
                      "status": "PARTIAL",
                      "basis": "真实投影走同一 CanonicalStore，且读路径不启动采集器、不开套接字（该测试正是证明这一点）；" + PARTIAL_MARKER
                              + "持续采集/watcher 仍在独立 sidecar，统一内核只提供有界帧（docs/CODEX-AUDIT-ENTRY.md §7）。"},
        "usage": {"location": find_definition("projection", "domains/work/workflow_core/canonical_store.py"),
                  "evidence": V18_USAGE_UNKOWN_TEST + ";" + V18_USAGE_SPLIT_TEST,
                  "status": "IMPLEMENTED_VERIFIED",
                  "basis": "「实测与估计分开、未知不填 0」两侧现在都有具名断言，并且投影本身被改成能回答这句话："
                          "每组带 quality_samples / tokens_by_quality / cost_coverage，token 与钱各按精度词分档，"
                          "未知保持 null、词表外的精度词进 OTHER 而不消失（两种植入反证都会变红：把 UNKNOWN 补成 0、"
                          "把估计钱并进实测钱）。" + NOT_PROBED_SENTENCE},
        "issues": {
                   "location": find_definition("load_issues", "domains/work/workflow_core/issue_projection.py"),
                   "evidence": f09 + ";" + V11_CHAIN_NODES,
                   "status": "IMPLEMENTED_VERIFIED",
                   "basis": "问题投影与修复包读面真实存在并被读回（F09 那条断言的是这一面的读通与 Control 写入门被拒，"
                           "链的完整性由后面六条负责）；「问题、修复、尝试和证据链可追溯」这一句现在按链本身"
                           "现读断言：问题行的出处引用解析回采集器健康、遥测事件、执行实例与任务四种真实行，"
                           "包到尝试、尝试到结果、结果到验收判定每一跳正向可达，再从判定反向追回同一组 id；"
                           "包快照与存储行的绑定集合、尝试与包的互相引用、结果与任务及尝试的归属都各有具名缺陷码，"
                           "三处标识篡改分别被点名并在整行逐字段相等后复绿；固定时钟下两次投影除显式点名的耗时字段外"
                           "逐字节相同，重试不铸第二行也不前进版本。"
                           "断裂检测已从测试谓词搬进产品自己的一致性报告（本轮 I-b）："
                           "`integrity_report()` 现在接受一个 plan 读面并逐条把 "
                           "`attempts.pack_plan_id` 与 `action_plans` 的行对照：包行不存在报 "
                           "ATTEMPT_ORPHAN_PACK_PLAN，包行存在但属于别的项目报 ATTEMPT_PACK_PROJECT_SPLIT"
                           "（「解析得到」不等于「是对的哪一条」），两种都带上尝试 id 与那个包 id；"
                           "路由把 work 库的读面交给它，而没有读面时报告自报 pack_plan_check=NOT_RUN——"
                           "「没查」不再长得像「查过且干净」，跨库那一跳也不必被复制进第二座账本。"
                           "判定侧同类的错位归因也已在本轮修掉：先前 `read_record` 落空时调用方把空 pack "
                           "交给投影，于是 BLOCKED 的理由写成「the pack bound no fingerprint to re-check」，"
                           "把「包行读不到」说成「没绑指纹」且不出现那个包 id；现在调用方直接说它看到的"
                           "事实——detail 点名那个包 id、checks.pack_record_absent 为真、"
                           "issue_projection_reread 为假、evidence 为空（没发生过的读回不能挂成凭据），"
                           "由 test_issue_chain_broken_link_is_named_by_the_verdict 钉住"
                           "（旧文本出现即红）。"
                           "仍然成立的限制：判定一旦写下就没有补偿动作——跨项目误读产生的那条 PASS 与"
                           "据此 COMPLETED 的任务会留在存储里，报表点名它而不撤销它；"
                           "真实宿主产生的证据与真人专业验收不在本行声称范围内。"},
        "solutions": {"location": "GET /api/work/observer/solutions",
                      "evidence": "tests/unified/test_v11_audit_rework.py::test_f05_unified_search_returns_work_solutions;" + "tests/unified/test_v11_audit_rework.py::test_f05_solution_revision_conflict_and_restart_readback",
                      "status": "IMPLEMENTED_VERIFIED",
                      "basis": "中文检索命中真实 WORK 方案、修订冲突与重启读回都有具名断言（F05 返工项）。"},
        "software": {"location": find_definition("classify_installation", "domains/work/orchestration/software_installation_identity.py"),
                     "evidence": ("tests/unified/test_v18_tools_connections.py::test_software_installation_identity_records_the_five_sides_apart;"
                                  "tests/unified/test_v18_tools_connections.py::test_software_installation_identity_blank_path_is_not_a_recorded_location;"
                                  "tests/unified/test_v18_tools_connections.py::test_unauthorized_software_installation_probe_records_nothing"),
                     "status": "IMPLEMENTED_VERIFIED",
                     "basis": "安装身份分类与 config/software-registry.json 已迁入；「安装、版本、探测、授权、"
                             "可执行」五个侧面各用自己的键、缺值保持 null 并以 NOT_PROBED 记「没看」，"
                             "未授权时探测一项也不写——由上面三个具名测试断言（含植入反证）。"
                             "本行不声称任何真实安装在本机被探测过：路径、版本、可执行文件仍是 NOT_PROBED。"},
        "configuration": {
                          "location": find_definition("load_inputs", "domains/work/orchestration/adapter_capability_projection.py"),
                          "evidence": caps + ";" + V02_CONFIG_NODES,
                          "status": "PARTIAL",
                          "basis": "「局部配置可恢复」的读侧按台账真正的读链断言：同一进程内四轮换掉受管台账"
                                  "（逐字节照抄、改一个条目并删一个、原样抄回、只动另一个条目），答复随文件变、"
                                  "换回原文件即回到基线，卡片里除被改那格外其余逐字段不变；恢复过程对工作区"
                                  "（含台账与规范存储文件）和真实配置目录做逐文件摘要对照，一个字都不动，"
                                  "即恢复不落新的持久写入；装一个「第一次读就记住」的第二副本会让"
                                  "「跟着文件变」当场变红。「不覆盖原生认证和全局环境」按现状成立：写面上"
                                  "配置的 apply、readback、rollback 三项 implemented=False 且各带具名拒绝码"
                                  "（TARGET_NOT_AUTHORISED / NO_WRITE_TO_READ_BACK / NO_RECOVERY_HANDLE，"
                                  "domains/work/control/control_service.py:238-249），唯一实现的 diff 只出计划、"
                                  "written 为 false，且配置前缀被门拒、认证名需要人工门、越界目标被拒；"
                                  "认证描述符与环境答复各被读两次比对——描述符比的是授权记录、操作集、证据上限与"
                                  "传输四个子字段（观测时刻除外），环境答复是整份相等，两者都不是四轮的那条断言。"
                                  + PARTIAL_MARKER
                                  + "恢复只测了读侧一致性——写入与回滚在产品里没有实现分支，谈不上回滚验收；"
                                  "登记原先写的 backend/core/capabilities.py:97 并不打开这份台账，能力目录换台账后"
                                  "一个字不动（该事实现由节点钉成断言，卡片集来自快照面）；"
                                  "环境基线文件没有产品运行时读者，只有测试读它。"},
        "evidence": {"location": "POST /api/v1/results/([0-9a-f]{32})/verifications",
                     "evidence": "tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused;tests/unified/test_v10_gate.py::test_gate_refuses_forged_result_and_verdict",
                     "status": "IMPLEMENTED_VERIFIED",
                     "basis": "验收「拒绝错任务、错版本、重复和假回执」逐条对应到具名反例测试（错项目/错包、stale、重复、伪造回执与伪 PASS）。"},
        "session": {"location": find_definition("link_session", "domains/design/design_lab/creative/session_link.py"),
                    "evidence": NO_EVIDENCE,
                    "status": "PARTIAL",
                    "basis": "会话引用与任务不同表：它落在独立的写一次关联表 worklab_session_link 上，"
                            "session_ref 必须是不透明 id（路径与载荷被拒），见 session_link.py 的 "
                            "link_session 与 assert_correlation_only；本树没有任何名为 native_session_ref "
                            "的字段（backend/ 与 domains/ 全文无该串），原判定文字借用了来源仓的叫法，"
                            "task 侧真正存在的只有 current_attempt_id。" + PARTIAL_MARKER
                            + "该行运行实现分期「P1保留既有；P2协议接续」的 P2 接续未做，「不复制私人会话」是执行策略约束而非被测行为。"},
        "candidate": {"location": "GET /api/projects/([0-9a-f]{32})/knowledge-candidates",
                      "evidence": ("tests/unified/test_v04_design_loop.py::test_knowledge_candidate_readback_is_a_read_and_never_a_send;"
                                   "tests/unified/test_v04_design_loop.py::test_knowledge_candidate_creation_refusals_leave_no_row_and_no_approval"),
                      "status": "IMPLEMENTED_VERIFIED",
                      "basis": "候选与导出的读写合同保留（RETAIN_CONTRACT），P3 深度 AAOS 明确延期且 AAOS 不是依赖；"
                              "「读回不是发送」现由上面两个具名测试断言：导出可以本地合同合格、可以组装出字节，"
                              "读回的 outbound 仍是 NOT_CONNECTED / sent_count 0 / last_attempt_at null，"
                              "未批准的候选导出被 409 拒、非法入参不留半行、也没有任何入参能造出 APPROVED。"
                              "权利判定与真人审阅人是夹具 supplied 的字段，本行不声称它们已被证真。"},
        "cleanup": {"location": find_definition("prune_report", "scripts/migrate_sources.py"),
                    "evidence": "tests/unified/test_v07_migration.py::test_prune_reports_only_paths_this_tool_recorded",
                    "status": "PARTIAL",
                    "basis": "已有的是迁移工具的 prune——只报告本工具登记过的路径、默认不删；" + PARTIAL_MARKER
                            + "面向运行产品的「清单范围清理与恢复可读回」未实现，不删除用户作品目前靠不实现删除来保证。"},
        "radar": {
                  "location": find_definition("catalog", "domains/design/design_lab/model_catalog.py"),
                  "evidence": V09_RADAR_NODES,
                  "status": "IMPLEMENTED_VERIFIED",
                  "basis": "模型与情报目录从 readiness/model-radar.json 及提供方台账现读，"
                          "「信息来源、日期、探测与资格有区别」按四个轴分别钉住，且每种「不知道」各自有唯一的答复："
                          "出处引用 source_ref、证据引用 evidence_ref、本机状态 machine_state 与雷达状态 radar_state"
                          "是四个互不相同的字段且各在自己的词表里；权重按三态报告——`weights_sha256` 字段缺席答 "
                          "UNSTATED、登记为空列表答 REGISTERED_NONE、确有摘要答 RECORDED，"
                          "计数 weights_recorded / weights_unstated / weights_registered_none 三格独立；"
                          "把三态塌回一个计数会让「没说明」冒充「登记为空」，一个 monkeypatch 植入的折叠实现"
                          "在本节点里被证明为红（折叠后所有条目同态、台账反而多出 weights_state 键）；"
                          "`_model` 现原样透传 hash_source 与 qualified_by，「摘要从哪来」「由谁判定合格」不再在投影里消失，"
                          "而无人署名的 QUALIFIED_LOCAL 由台账装载器拒（readiness/model_radar.py:114）；"
                          "目录文档本身用已发布的 model-catalog-v1.schema.json 现校验（Draft202012Validator），"
                          "三份合同副本逐字节相同，所以字段区别不只是测试里的说法，发布合同与产品答复同增同减；"
                          "逐条改台账里的出处、日期或本机状态，答复只有被改那一格移动、条目数与其余字段不动；"
                          "资格词不可由文档措辞或一次探测铸造（默认启用数不超过合格本地数）。"
                          "限制（不是缺口）：本轮实测的产品台账里每一条都把权重列表登记为空，"
                          "hash_source 与 qualified_by 在全部条目为 null，故三态在真实人口上目前只走出一格，"
                          "UNSTATED 与 RECORDED 由合成夹具人口证明；文档级观测时刻只从台账带出，条目行没有自己的日期；"
                          "source_ref 是 github/huggingface 的外部地址，本机不联网也不校验其字节。"
                          "本行不声称本机任何模型真被装载、探测或授权。"},
        "design-knowledge": {"location": find_definition("KnowledgeLibrary", "domains/design/design_lab/knowledge_library.py"),
                             "evidence": "tests/unified/test_v06_knowledge.py::test_create_search_short_queries_and_no_result;tests/unified/test_v06_knowledge.py::test_revision_conflict_and_index_rebuild",
                             "status": "IMPLEMENTED_VERIFIED",
                             "basis": "内容/来源/修订、中文短词与无结果、索引重建与重启读回都有具名断言。"},
        "design-prompt": {"location": find_definition("PromptIntelligence", "domains/design/design_lab/prompt_intelligence.py"),
                          "evidence": V04_PROMPT_NODES + ";" +
                                  "tests/legacy/design/test_assistance_plan.py::AssistancePlanTests::"
                                  "test_a_linked_asset_is_reported_linked_only_until_a_reversal_exists",
                          "status": "PARTIAL",
                          "basis": "生成与反推的既有实现按「P1迁既有」迁入。四条提示词路由现在都有走真实 HTTP 的"
                                  "具名断言：生成只多一行 prompt_result——两个素材面（`/assets` 与 "
                                  "`/native-assets`）的 id 集合在生成前后逐字相同，读回的 `executed` 恒为 "
                                  "False，同一请求重打得到同一行，这就是「提示词导出不算作品生成」从约定变成"
                                  "断言；列表面自己解析 query，畸形数字得到具名 400 而不是 404，计数在切片"
                                  "之前；签收要具名真人，`reviewer_kind` 非 human 被具名拒绝，真人签名后"
                                  "`content_sha256` 等于台账里那份文档的摘要；存储守卫被注入打穿时路由答具名"
                                  "拒绝而不是闷声 201。反推路由的覆盖在旧只读套件里（上面那个具名节点）。"
                                  + PARTIAL_MARKER + "「P3新增模型执行」未做（09 分期表 L32）：本机没有合格模型，"
                                  "真实推理按边界停在 NOT_RUN，本节不拿文档生成冒充推理；并发窗口里的两个 409"
                                  "（`PROMPT_RESULT_CONCURRENT_UPDATE` / "
                                  "`PROMPT_REVIEW_CONCURRENT_UPDATE`）在单连接串行的 HTTP 面上构造不出，"
                                  "归 store 层，未由本节证明。"},
        "design-plan": {"location": find_definition("AssistancePlanError", "domains/design/design_lab/assistance_plan.py"),
                        "evidence": "tests/legacy/design/test_assistance_plan.py::AssistancePlanTests::test_a_plan_is_saved_with_its_basis_and_reads_back_after_a_restart;tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending",
                        "status": "IMPLEMENTED_VERIFIED",
                        "basis": "方案修订不可变、旧修订按自身读回、与任务信封关联后专业验收保持 pending，均由具名测试断言；旧只读合同兼容。"},
        "design-target": {"location": find_definition("TargetProfiles", "domains/design/design_lab/target_profile.py"),
                          "evidence": "tests/legacy/design/test_target_profile.py::TargetProfileTests::test_seeded_profiles_are_served_from_the_tracked_config_with_no_database_copy;tests/unified/test_v04_design_loop.py::test_target_profile_reference_must_address_a_real_profile",
                          "status": "IMPLEMENTED_VERIFIED",
                          "basis": "软件×模型×入口档案从受管配置现读且不落第二副本；引用必须指向真实档案——「选择不等于连接和执行」由资格层断言。"},
        "design-domain": {"location": find_definition("build", "domains/design/design_lab/domain_packs.py"),
                          "evidence": V24_DOMAIN_NODES, "status": "PARTIAL",
                          "basis": ("领域包投影的目录数、身份字段与资格合计都由这一次调用现算，并被两个具名"
                                    "节点钉住：列出的 {listed} 条与盘面上的包目录逐一对齐（既不漏也不凭空多），"
                                    "`counts.packs`={packs} 与 `byValidation` 各类相加等于该长度，manifest 里"
                                    "没有的字段答 null 而不是被默认成字符串（v1 包不许冒充 v2 身份）。"
                                    "仓库自带的那个校验脚本本轮按逐字节复制迁入打包资源根：来源覆盖登记里这一行"
                                    "由 TOOL_OR_SCRIPT 转为 COPIED_VERIFIED，`migration/copies.json` 记下复制时的"
                                    "摘要，`checker.state` 从 UNAVAILABLE 变成 {checker}。于是「资格分别标记」第一次"
                                    "真的有分别——{validates} 个 VALIDATES、{invalid} 个 INVALID、{unreadable} 个 "
                                    "UNREADABLE，NOT_CHECKED 归 {not_checked}；词表里那一格仍然被声明，因为词表是"
                                    "能力而不是本次读数。被拒的那些点名到这里："
                                    "{refused}。").format(**domain_pack_readback())
                                  + PARTIAL_MARKER
                                  + "VALIDATES 只是 E1 结构陈述：它说的是这个仓里的文件是否齐到能过 schema，"
                                    "不是宿主跑过、不是设计质量判定、不是被接受的领域能力，更不是真人 E4 验收；"
                                    "被拒的包一个字节都没由我改动——让它在读回里保持 INVALID 是校验器在尽责，"
                                    "补它的清单是 owner 的设计工作，不是登记可以替它做的事。UNREADABLE 那一格"
                                    "由植入校验器的节点证明：读不到清单的包不被丢弃，而是带着名字出现，"
                                    "投影也没有把任何一种结论写死。"},
        "design-assets": {
                          "location": "GET /api/projects/([0-9a-f]{32})/assets(?:/(img-[0-9a-f]{64})/content)?",
                          "evidence": V04_ASSET_NODES,
                          "status": "IMPLEMENTED_VERIFIED",
                          "basis": "「输入、输出、版本、引用可恢复，不扩素材平台」四件事各有具名断言："
                                  "版本是只增历史——同一素材第二次登记得到新的版本 id，当前版按路由读回"
                                  "（列表里同一资产只出现一行，内容读出来的字节等于当初登记的字节），"
                                  "历史版由素材层自己的校验读取与磁盘摘要确认（旧记录的摘要与大小不被顶替，"
                                  "两版字节不同；兼容面的路由本身按构造只回当前版，本行不把它说成历史版可经路由读回）；"
                                  "引用按摘要钉住，内容被换后取回返回摘要不符，同一 id 跨项目寻址返回不存在、改写归属直接被拒；"
                                  "输入面只列 img- 前缀的栅格、输出面只列 native- 前缀并另带类别、版本号与核验字段，"
                                  "两套字段集合互不相等、彼此寻不到，把两侧折成一条不分类别的大列表的植入立刻变红；"
                                  "路由面两个人口分别钉住：pattern 含 /assets 的条目与测试里登记的那一组构成集合等式"
                                  "（方法限于 GET/POST，模式与动作里不含平台词根），整张路由表按 upload/sync/remote/"
                                  "fetch/pull/push/download/platform/cdn/proxy/webhook 这份清单搜索结果为空——它是载荷侧"
                                  "那份更长的词表的一个子集，两端各自为政；入参递一个 remote_url、sync_target 或 "
                                  "upload_to 都停在 400 具名错误，两处权利位保持 NOT_REVIEWED。"
                                  "读回的「换一次」是同一进程里换一个服务实例（新数据库连接、新 HTTP 端口）从磁盘重读，"
                                  "不是操作系统进程重启，也不主张断电语义；本行也不声称宿主真能打开产物——"
                                  "输出字节是合成的，这一面只哈希不解析，真实宿主产生输出的链路仍按人工门逐次进行。"},
        "design-reconstruction": {"location": find_definition("validate_rir", "packages/capabilities/reconstruction/contracts.py"),
                                  "evidence": V24_RECON_NODES + ";" + V24_RASTER_NODES,
                                  "status": "PARTIAL",
                                  "basis": "RIR 合同由 native_plan 与 plan_to_rir 真实调用（它们以 "
                                          "`design_lab.reconstruction` 的名字导入，而实现只有一份："
                                          "`contracts.__file__` 落在 packages/capabilities/reconstruction 下，"
                                          "包路径是别名不是复制）；合同的三份副本（来源仓、打包资源、对外发布）"
                                          "逐字节相同；安装态不给项目根就拒、缺必填字段按 schema 自己声明的字段名"
                                          "拒、非有限数在任何字段检查前拒，路径政策的绝对/穿越/反斜杠/URI/空串"
                                          "各有具名拒绝，而干净的相对路径确实落在根内。本行现在还有一份**真的**"
                                          "合法文档：来源仓 20 份 git 跟踪的 RIR 样本全部过本仓的 validate_rir，"
                                          "其中唯一带 raster 节点的那份逐字节迁入 "
                                          "tests/fixtures/reconstruction/uikit-conformance-2026-09-28/input.rir.json"
                                          "（摘要记在迁移台账，测试断言它此后没被改过），栅格字节用来源仓自己"
                                          "带 .license 的 flat-64.png 夹具。链路按产品的三个函数走到底并逐段现测："
                                          "样本原样交给 build_photoshop_job 得到 "
                                          "「rounded or parameterized rect unsupported」（它先在一个带参数的 rect 上"
                                          "被拒，所以本行不说「撞的是 raster 门」）；收成只含 raster 节点的派生文档"
                                          "得到「raster remapping/alpha requires explicit preprocessed asset」；再把 "
                                          "sourceMappings 清掉、crop 物成 PNG 实际尺寸、把栅格放进 run root 之内，"
                                          "构建被接受并产出 asset-texture-chip——这一句就是原先说「未被端到端演示」的"
                                          "那一半。同一轮修掉两处路径政策里的实话问题：`project_root` 传相对写法时"
                                          "任何合法 raster.path 都被判「reparse resolution escapes outside the "
                                          "project」（根没 resolve，绝对候选永远不比它更内），而这句理由描述的是没"
                                          "发生的越界；`.` 与空段被 PurePosixPath 归一化吃掉而静默通过，消息却声称"
                                          "禁止——现在按调用方真正传来的字面分段判。"
                                          + PARTIAL_MARKER
                                          + "「结构与视觉规格分开验收」需要真人判断，本仓不替人签这个字；"
                                          "样本 raster.path 声明的那张原件 PNG 从不在来源仓的 Git 里（本行用的是"
                                          "来源仓自带的授权夹具，不谎称原件）；lowering 产出的是文档，宿主一次也"
                                          "没被拉起；含制表符的文件名今天仍然通过策略——本行把它当实测事实记着，"
                                          "不声称覆盖控制字符。"},
        "design-quality": {"location": find_definition("assert_not_agent_signed", "domains/design/design_lab/assurance/human_jury.py"),
                           "evidence": "tests/unified/test_v11_audit_rework.py::test_f08_agent_and_unresolved_verifiers_cannot_satisfy_professional",
                           "status": "IMPLEMENTED_VERIFIED",
                           "basis": "验收「技术核验与专业人工验收分开」有直接反例断言：Agent 引用与未解析 verifier 不能充当真人验收。"},
        "design-tools": {"location": find_definition("quiesce", "domains/design/design_lab/adapters/photoshop_com.py"),
                         "evidence": "tests/unified/test_v14_registers.py::test_host_bridge_script_is_reachable_where_the_adapter_probes",
                         "status": "PARTIAL",
                         "basis": "桥接脚本在适配层实际探测的包内路径且与真值逐字节一致（漂移由守卫拦截）；" + PARTIAL_MARKER
                                 + "P2「已可用宿主的真调用/保存/重开/读回」仍 BLOCKED（需逐次 Human Gate），P3 多宿主未做（09 分期表 L20/L31）——登记不算连接。"},
        "desktop": {"location": "apps/workbench/shell.ts:346", "evidence": NO_EVIDENCE,
                    "status": "PARTIAL",
                    "basis": "现有 workbench 导航与逐视图读回渲染在（未重画 UI，符合「不默认重画」）；" + PARTIAL_MARKER
                            + "「56 旧入口有去向」这一验收由本次生成的 ui-entry-disposition.csv 满足；"
                            "统一桌面壳与合成首页属 STITCH 前端，本轮实测登记为 NOT_RUN（evidence:delivery-summary.json#outstanding）。"},
        "contracts": {
                      "location": "packages/contracts/schemas/workflow/action-plan.schema.json:4",
                      "evidence": V05_CONTRACT_NODES, "status": "IMPLEMENTED_VERIFIED",
                      "basis": "「现有消费者与版本兼容、错误输入与资源路径回归」三件事各有具名断言："
                              "控制面按发布出去的请求合同校验（枚举双向相等、拒绝项带具名 code、结果信封字段集合"
                              "与发布合同对齐）；方案消费者按发布合同接受合法文档并以具名 code 拒绝非法文档；"
                              "动作计划的存储行钉的是修订冲突（CAS）与重复投递不铸第二版、且不把计划喂给方案消费者，"
                              "本行不把它说成「旧 schema 版本行按自身版本读回」；快照版本号是比对不是重导，"
                              "投影截断上限与同一字段的长度上限钉成同一个数；资源路径面把目录里每个 JSON 文件里"
                              "键名为 $ref 的引用逐条解析到真实文件（引用条数由该节点现数，本行不复述一个自己不再检查的数字；"
                              "$dynamicRef 等其它关键字不在其内），"
                              "标识符唯一性一并钉住，三份植入的断引用（文档内指针、跨文件引用、相对路径）分别被点名，"
                              "且发布清单与登记副本表按路径尾段与字节双向对账"
                              "（台账把目标写成跑迁移那一份检出的绝对路径，克隆里只能按尾段与字节比，"
                              "这一口径在节点里写明）：每个已发布合同要么等于迁移记录写下的摘要，"
                              "要么等于声明修复出具回执的那份摘要（走这一格的是哪几份由该节点逐名列出），"
                              "两者都对不上才算未解释的改动；"
                              "能力台账声明的输入逐个存在且可解析。"
                              "真实范围说清楚：运行期被产品代码打开的只有控制面请求合同、方案合同与适配器接口合同这三个"
                              "具名文件，这一集合由「装读句柄、跑三个真实消费者、再比集合」的双向等式钉住，"
                              "多一个或少一个都变红；动作计划与修复包的合同是由本节点把发布文件注入产品校验分支的，"
                              "产品调用方 repair_state.py:115 自己调用时不注入 schema——这正是「其余目录随包发布而无运行期读者」"
                              "的样子。发布目录整体纳入打包由 pyproject.toml:65/:136/:213 的声明钉住（合同节点不构建 wheel，"
                              "安装态是否真带上是 A08/F06 隔离安装那条实测的范围，不算在本行）。"
                              "本节现算而非抄旧数：packages/contracts 目录下 JSON 文件 %d 份。"
                              % CONTRACTS_PUBLISHED_JSON},
        "research": {"location": "research/candidates/CANDIDATE-TAXONOMY.json:2",
                     "evidence": V24_RESEARCH_NODES, "status": "IMPLEMENTED_VERIFIED",
                     "basis": "「资料不是运行事实」与「不新增在线采集依赖」两条都可查，且由具名节点查过："
                             "research/ 下的跟踪文件全是 JSON（本树实测没有任何 .py，因此运行时不可能从它 "
                             "import 到模块）；全仓跟踪的 .py 里没有一条 import 语句指向顶层 research 包"
                             "——该谓词本身用植入导入与 `from .assurance import research_store` 这种"
                             "同名不同物的写法两边都验过，避免误报与漏报；候选分类学能解析、条目非空、"
                             "条目键集合一致，条目数由这次读取现算而不是抄登记；pyproject 声明的依赖名里"
                             "没有 requests/httpx/aiohttp/urllib3/selenium/playwright 这类在线采集客户端。"
                             "本行不声称已具备联网检索能力（09 分期表 L30 的 P3 检索未做），"
                             "也不声称资料内容的正确性（那是人审范围）。"},
        "evolution": {"location": "GET /api/v1/improvements", "evidence": "tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only;" + caps,
                      "status": "PARTIAL",
                      "basis": "改进面诚实回答 CONTRACT_ONLY / activation_state=UNAVAILABLE，能力目录把 core.evolution 标为 DECLARED 且 can_invoke=false；" + PARTIAL_MARKER
                              + "「P3 完整执行链」——技能/插件/前后端修改分开、独立验收与回退——未实现（09 分期表 L32）。"},
        "build-test": {"location": find_definition("record", "scripts/verify_isolated_install.py"),
                       "evidence": "evidence:a01-a10-results.json#results.A08;tests/unified/test_v14_registers.py::test_coverage_register_accounts_for_every_source_file",
                       "status": "IMPLEMENTED_VERIFIED",
                       "basis": "wheel 离线构建并安装到隔离目录、安装态 __file__ 全部指向安装树（A08 实测记录），真实 loopback HTTP 与持久化由本仓回归覆盖；未继承旧 CI 绿。"},
        "unclassified": {"location": "migration/review/unclassified-review.json:4",
                         "evidence": V18_UNCLASSIFIED_TEST, "status": "IMPLEMENTED_VERIFIED",
                         "basis": "复核登记的 8/8 不再靠它自己的话：条数、族名词表、理由唯一性与处置一致性全部"
                                 "从 migration/mapping.csv 与能力族登记表现算，人口双向对齐（既不会漏第 9 条，"
                                 "也不会多出无主复核）；四组文件内植入加一次人口植入都会把断言变红。"
                                 "归属判断在语义上是否恰当仍是人的判断，本行不声称已被证明。"},
    }


def requirement_claims() -> dict[str, dict]:
    manual = "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart"
    caps = "tests/unified/test_v02_surface.py::test_capabilities_are_honest_and_derived"
    projects = "tests/unified/test_v02_surface.py::test_projects_register_and_read_back_both_sources"
    return {
        "U01": {"location": "POST /api/v1/projects", "evidence": projects, "status": "PARTIAL",
                "basis": "两域已在同一后端、同一任务/数据入口上共同读写（work 与 design 同表注册并读回）；" + PARTIAL_MARKER
                        + "「单壳」尚未交付——统一桌面壳属 STITCH 前端，本轮登记为 NOT_RUN（evidence:delivery-summary.json#outstanding）。"},
        "U02": {"location": "migration/source-coverage-work.csv:2",
                "evidence": "tests/unified/test_v14_registers.py::test_coverage_register_accounts_for_every_source_file;" + "tests/unified/test_v12_data_migration.py::test_migration_preserves_revisions_digests_and_references",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "四个维度各自有面：源文件=逐文件覆盖登记（类别之和=行数由测试现算），语义=mapping.csv 与逐条去向登记，"
                        "行为=tests/unified 回归，数据=test_v12 受控迁移（含幂等/回滚/命名空间）。去重按 EQUIVALENT_MERGED/PRESENT_IN_TARGET 逐条判定。"},
        "U03": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/pack", "evidence": manual,
                "status": "PARTIAL",
                "basis": "确定流程直调工具（人工任务包/迁移工具/CLI）不依赖 Agent 即可闭环，且有测试；" + PARTIAL_MARKER
                        + "「成熟能力优先复用」目前只有迁入清单与去向判定支撑，没有复用度指标可测。"},
        "U04": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/handoff-declarations",
                "evidence": "evidence:a01-a10-results.json#results.P3_multi_agent;" + "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch",
                "status": "DEFERRED_P2",
                "basis": "本行交付原文即「本批保留合同，真实接线按条件分期」：合同（Attempt/执行模式枚举/拒绝外部回执冒充）已保留并有测试，"
                        "真实多 Agent 派发按 09 分期表 L21（P2 单个执行器）与 L30（P3 多 Agent）分期，实测登记 P3_multi_agent 未运行。"},
        "U05": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/handoff-declarations",
                "evidence": "tests/unified/test_v05_rejections.py::test_import_before_declared_handoff_refused;" + "tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "P1 两域人工闭环：WORK 侧生成包→人工声明交接→导入结果→核验；DESIGN 侧同链路且专业验收在真人门前保持 pending。"
                        "生成本身不产生交接声明、外部回执不可声明，均为具名反例断言。"},
        "U06": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "DEFERRED_P3",
                "basis": "BOT 是交互/消息入口，本行交付原文「渠道后置，不新建重复总控」：统一后端没有第二总控（只有一个 CanonicalStore 与一张路由表），"
                        "BOT 渠道本身按 09 分期表 L30（P3 复杂多Agent/BOT/跨机协作）延期，本行不声称已实现。"},
        "U07": {"location": "pyproject.toml:27", "evidence": NO_EVIDENCE, "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "「局部机制适配，不默认整仓换底」在技术上成立：产品仍是迁移过来的 Python 标准库后端 + Vanilla TypeScript/Vite 前端，"
                        "未引入参考项目的底座；但这是结构事实而非被测行为，本仓无断言，故不标 VERIFIED。参考资料的登记在 research/candidates 与 vendor/。"},
        "U08": {"location": "GET /api/v1/improvements", "evidence": "tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only",
                "status": "PARTIAL",
                "basis": "候选合同、独立验收门（拒绝伪 PASS）与升级/恢复的数据合同在；" + PARTIAL_MARKER
                        + "本行交付原文把执行划为 P3（09 分期表 L32 完整自改写激活与回退未实现）。"},
        "U09": {"location": ABSENT, "evidence": "evidence:a01-a10-results.json#results.FRONTEND_STITCH", "status": "GAP",
                "basis": "提示词文件只在只读任务包内（01_STITCH_完整前端提示词.txt），其交付物——前端设计稿与实现——本轮未产生，实测登记 FRONTEND_STITCH 为未运行；"
                        "F01-F10 帧与 J1-J9 在本仓没有任何对应实现或断言，本行是缺口而不是延期项（09 分期表把它列为必做波次的交接物）。"},
        "U10": {"location": find_binding("V1_ROUTES", "backend/v1.py"), "evidence": "tests/unified/test_v02_surface.py::test_health_is_real_service_metadata;" + manual,
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "后端闭环按 P0/P1 落实：路由条数在构建时从两张活动表现读——"
                        "V1_ROUTES %d 条、兼容表 %d 条，本行不复述手抄数字；"
                        "真实 loopback HTTP + 持久化 + 重启读回由具名测试断言。"
                        % route_counts()},
        "U11": {"location": "repo:branch", "evidence": "evidence:delivery-summary.json#git",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "本仓在检出的本地工作分支上执行，分支名由 `git symbolic-ref --short HEAD` 现读"
                        "（现为 %s；2026-11-02 仓库规范化时主线定为 main，那条融合批次分支已退掉，"
                        "恢复点就是 main 的尖端）——写死分支名会让登记在改名后变成假话。位置以前写的是 "
                        "`.git/HEAD:1`，那不是一个可复核的实现位置：`.git/` 里的字节不在 `git ls-files` 人群里、"
                        "克隆之间没法 diff，而本仓的克隆复跑是按 SHA 分离检出的，那时该文件存的是一枚裸 SHA，"
                        "行号仍「存在且非空」，于是这一行恰好在声称的事不成立时还亮着绿。现在改为 `repo:branch`，"
                        "由 git 现答，分离头具名拒绝并按既有规则降级。增量保全由 "
                        "delivery-summary.json#git 与 snapshot-before/after 逐文件摘要证明；"
                        "该行记录的是 2026-10-29 交接当时的保全证据，那时 HEAD 尚未产生任何提交，"
                        "现在已有提交，本行不据此声称内容已同步到远端。"
                        % current_branch()},
        "U12": {"location": find_definition("derive_catalog", "backend/core/capabilities.py"), "evidence": caps + ";" + "tests/unified/test_v11_audit_rework.py::test_f01_registered_gap_paths_all_have_a_real_disposition",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "两条都可测：延期面在能力目录里保持 DECLARED/DEFERRED 并带 phase、can_invoke=false（不降级冒充）；"
                        "来源与接缝的保留由逐条去向登记（migration/work-gap-disposition.csv，行数与报告现算对账）+ 逐文件覆盖登记断言，延期不等于删除。"},
        "U13": {"location": find_definition("_v1_build_pack", "backend/v1.py"),
                "evidence": "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch;" + "tests/unified/test_v09_honesty.py::test_connections_never_claim_connected_without_a_probe",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "运行面上没有任何可把项目/数据推向远端的入口：外部派发在 pack 处直接 400 拒绝，"
                        "且不存在把连接改成 CONNECTED 的路由（POST /api/v1/connections 实测 404）。"
                        "本行只声称代码层不被绕过；系统级出站隔离未被证明（INTEGRATION_POLICY §2），2026-10-31 的首次上传是 owner 单独放行的例外（§6），不改变本行的禁止面。"},
        "U14": {"location": find_definition("_v1_build_pack", "backend/v1.py"), "evidence": "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch;" + "evidence:a01-a10-results.json#results.A08",
                "status": "PARTIAL",
                "basis": "全部构建/测试/安装都在本地：A08 是离线隔离安装实测，工具与模型方式已在 INTEGRATION_POLICY §4 逐条核实；" + PARTIAL_MARKER
                        + "「禁止云构建/远程派发/自动同步」在代码与流程上成立，但系统级出站隔离未被证明，且执行本任务的模型本身是云端会话模型（§2 如实登记）。"},
        "U15": {"location": "docs/CODEX-AUDIT-ENTRY.md:1",
                "evidence": "evidence:a01-a10-results.json#results;" + "evidence:f01-f10-closure.json#items",
                "status": "PARTIAL",
                "basis": "我方一侧的交付齐了可被独立审的东西：候选摘要、原始日志、逐条反例与重跑记录；" + PARTIAL_MARKER
                        + "「由本地 Codex 审计」这一步在 owner 侧执行，其结论不由本仓生成也无法本仓自证，所以不能标 VERIFIED。"
                        "位置列只给出审计入口文件，不作为完成依据。"},
        "U16": {"location": "AI-WORK-LAB_HANDOFF_20261029/00_阅读顺序与需求确认.txt:1",
                "evidence": "evidence:delivery-summary.json#outstanding",
                "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "共同约定文本已随任务包只读留存并在 08 与三份提示词中成形，本登记把它拆成 25 条逐行可对账的要求；"
                        "但「确认理解」是人的动作，无自动断言，故不标 VERIFIED。"},
        "P01": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                "basis": "本行引用 STITCH 帧 F01/F02 与 SCREEN_12 画板，属前端交付；本轮前端 NOT_RUN，"
                        "且 SCREEN_12 未进入本仓（只读任务包内亦无位图证据），紧凑层级无从对照，故记缺口不记完成。"},
        "P02": {"location": "GET /api/v1/design/plans",
                "evidence": "tests/legacy/design/test_assistance_plan.py::AssistancePlanTests::test_a_plan_is_saved_with_its_basis_and_reads_back_after_a_restart;" + "tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending",
                "status": "PARTIAL",
                "basis": "后端连续状态可测：方案存/读回/修订、目标组合引用、专业验收 pending 均有断言，D01/D02/D04 所需的数据合同在；" + PARTIAL_MARKER
                        + "「自由切换、修订与目标组合」的画面按 F04 属前端，未交付。"},
        "P03": {"location": "apps/workbench/style.css:1", "evidence": NO_EVIDENCE,
                "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "共用 token 与深色/冷色布局在迁入的 workbench 样式内延续，未改成暖色；"
                        "这是视觉判断，需人审，本仓无 token 断言，故不标 VERIFIED。"},
        "P04": {"location": "apps/workbench/shell.ts:346", "evidence": NO_EVIDENCE,
                "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "导航是「入口 + 按需详情」的紧凑结构，未新增巨大流程仪表盘；"
                        "同样属视觉/信息密度判断，无自动断言，需人审，故不标 VERIFIED。"},
        "P05": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                "basis": "HUD（F10 轻量浮层不替代主界面）在本仓不存在：apps/workbench 全部源文件中检索不到 hud 相关实现，"
                        "后端也无 HUD 状态面；本行记缺口，不以前端提示词的存在充当实现。"},
        "P06": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "EXCLUDED_BY_OWNER",
                "decision_quotes": ["不扩手机或企业团队平台"],
                "basis": "本行本身就是 owner 的范围裁定：「个人使用，不扩手机或企业团队平台」，交付原文只要求「保留来源、解释范围，避免新平台」。"
                        "04 表 design:collaboration 行的「企业团队不进入主导航」与之呼应；本登记满足其「解释范围」部分。"
                        "排除不是缺口也不是待办，解除只认 owner 新的明确授权。"},
        "P07": {"location": "GET /api/projects/([0-9a-f]{32})/knowledge-candidates",
                "evidence": "evidence:a01-a10-results.json#results.A06_real_user_data;" + manual,
                "status": "PARTIAL",
                "basis": "「当前独立可运行」是可机验的：统一后端在没有 AAOS 的情况下跑通闭环（WORK 人工闭环测试全程不引用任何外部知识系统），"
                        "两张实测路由表中也不存在 AAOS 端点，保留的接缝是版本化的 KnowledgeCandidate 读面；真实用户数据迁移按 A06_real_user_data"
                        "登记为未运行，没有把未来接缝写成本轮依赖。" + PARTIAL_MARKER
                        + "「未来接缝」目前只有路由与合同：候选出口的读回与拒绝已由 05 candidate 行点名的两条具名断言覆盖，"                        "但真实用户数据迁移（A06_real_user_data）与 AAOS 侧合同联调仍未运行，故不能标 VERIFIED。"},
        "E01": {"location": "AI-WORK-LAB_HANDOFF_20261029/12_来源基线.json:6",
                "evidence": "evidence:a01-a10-results.json#results.F01",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "本机增量已按 INTEGRATION_POLICY §4 重新核实（来源多于云端锚点 → 以本地现状为迁移来源，锚点仅作研究参照，不回退），"
                        "并落成逐文件覆盖登记 + 逐条去向登记 + F01 迁移注册表三条实测记录；来源基线是研究锚点而不是完成清单这一口径由该断言守住。"},
        "E02": {"location": "docs/CODEX-AUDIT-ENTRY.md:1", "evidence": "evidence:delivery-summary.json#conclusion",
                "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "原型/实现/构建/运行/部署五态在本登记与 delivery-summary 中被分开记录（例如 U11 明写 HEAD unborn、"
                        "design-tools 明写登记不算连接、U15 明写审计在 owner 侧）；但「全交付状态和限制一致」需要跨文档一致性检查，"
                        "本仓无自动比对，故不标 VERIFIED，只把口径写死在每一行的依据里。"},
    }


# --------------------------------------------------------------------------
# row assembly
# --------------------------------------------------------------------------

def read_table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_ui_rows() -> list[dict]:
    claims = ui_claims()
    rows, missing = [], []
    for index, row in enumerate(read_table(UI_TABLE), start=2):
        key = "%s:%s" % (row["来源仓"], row["原入口ID"])
        claim = claims.get(key)
        source_text = join_verbatim([row["原名称"], "→ " + row["拟融合位置"], "分期 " + row["分期"]])
        if claim is None:
            missing.append(key)
            claim = {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                     "basis": "生成器未对该行给出判定（不应发生：行数守卫会失败）"}
        result = reconcile("ui-entry", "04#L%d|%s" % (index, key), source_text, row["分期"], claim)
        result["来源仓"] = row["来源仓"]
        result["原入口ID"] = row["原入口ID"]
        result["原名称"] = row["原名称"]
        result["拟融合位置"] = row["拟融合位置"]
        result["分期"] = row["分期"]
        result["来源表状态"] = row["状态"]
        rows.append(result)
    if missing:
        raise SystemExit("UNAUTHORED_UI_ROWS " + ",".join(missing))
    if len(rows) != len(claims):
        raise SystemExit("AUTHORED_KEYS_DO_NOT_MATCH_TABLE %d!=%d" % (len(rows), len(claims)))
    return rows


def build_family_rows() -> list[dict]:
    claims = family_claims()
    rows, missing = [], []
    for index, row in enumerate(read_table(FAMILY_TABLE), start=2):
        key = row["能力族ID"]
        claim = claims.get(key)
        source_text = join_verbatim([row["名称"], row["原拟处理"], row["拟模块边界"],
                                     "运行实现分期 " + row["运行实现分期"], "核心验收 " + row["核心验收"]])
        if claim is None:
            missing.append(key)
            claim = {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                     "basis": "生成器未对该能力族给出判定（不应发生：行数守卫会失败）"}
        result = reconcile("capability-family", "05#L%d|%s" % (index, key), source_text,
                           row["运行实现分期"] + " " + row["保全批次"], claim)
        result["能力族ID"] = key
        result["名称"] = row["名称"]
        result["原拟处理"] = row["原拟处理"]
        result["拟模块边界"] = row["拟模块边界"]
        result["运行实现分期"] = row["运行实现分期"]
        result["核心验收"] = row["核心验收"]
        result["来源表状态"] = row["状态"]
        rows.append(result)
    if missing:
        raise SystemExit("UNAUTHORED_FAMILY_ROWS " + ",".join(missing))
    if len(rows) != len(claims):
        raise SystemExit("AUTHORED_KEYS_DO_NOT_MATCH_TABLE %d!=%d" % (len(rows), len(claims)))
    return rows


def build_requirement_rows() -> list[dict]:
    claims = requirement_claims()
    rows, missing = [], []
    for index, row in enumerate(read_table(REQUIREMENT_TABLE), start=2):
        key = row["需求ID"]
        claim = claims.get(key)
        source_text = join_verbatim([row["来源性质"], row["需求"], "交付或验收 " + row["交付或验收"]])
        if claim is None:
            missing.append(key)
            claim = {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                     "basis": "生成器未对该需求给出判定（不应发生：行数守卫会失败）"}
        result = reconcile("requirement", "11#L%d|%s" % (index, key), source_text, "", claim)
        result["需求ID"] = key
        result["来源性质"] = row["来源性质"]
        result["需求"] = row["需求"]
        result["交付或验收"] = row["交付或验收"]
        rows.append(result)
    if missing:
        raise SystemExit("UNAUTHORED_REQUIREMENT_ROWS " + ",".join(missing))
    if len(rows) != len(claims):
        raise SystemExit("AUTHORED_KEYS_DO_NOT_MATCH_TABLE %d!=%d" % (len(rows), len(claims)))
    return rows


#: ``08_前后端交接约定.json`` spells identifiers as ``{task_id}``/``{attempt_id}``/
#: ``{result_id}`` while the live tables compile them as 32-hex capture groups. The
#: contract itself demands this be recorded rather than ignored ("实际路径有差异需记录兼容
#: 表"), so the check normalises the placeholder and requires the normalised pattern to
#: resolve in a live table -- and writes which form matched into the register. A proposal
#: that resolves only after normalisation is still a real route, but the difference is
#: reported instead of being silently smoothed over.
ID_PLACEHOLDER = re.compile(r"\{[A-Za-z_]+\}")
ID_CAPTURE_GROUP = "([0-9a-f]{32})"


def build_api_checks() -> list[dict]:
    document = json.loads(PROTOCOL_TABLE.read_text(encoding="utf-8"))
    proposals = document["api_proposals"]
    rows = []
    for index, proposal in enumerate(proposals, start=1):
        method, pattern, purpose = proposal[0], proposal[1], proposal[2]
        entry = live_routes().get((method, pattern))
        matched_via = "合同路径与实测路由逐字相同"
        live_pattern = pattern
        if entry is None and ID_PLACEHOLDER.search(pattern):
            normalized = ID_PLACEHOLDER.sub(ID_CAPTURE_GROUP, pattern)
            entry = live_routes().get((method, normalized))
            if entry is not None:
                live_pattern = normalized
                matched_via = ("占位符归一后命中：%s → %s（差异按合同要求记录，不视为无差异）"
                               % (pattern, normalized))
        handler = entry["handler"] if entry else None
        table = entry["table"] if entry else None
        handler_location = None
        if handler:
            handler_location = (find_definition(handler, "backend/v1.py")
                                or find_definition(handler, "backend/core/work_surfaces.py"))
        evidence = API_EVIDENCE.get("%s %s" % (method, pattern), NO_EVIDENCE)
        #: 当前实现位置 must be a *live* route, so the normalised pattern is what gets
        #: cited; the contract's own spelling stays in 路径 and the gap between the two
        #: stays in 匹配方式. Nothing here silently pretends the two are the same string.
        claim = {"location": "%s %s" % (method, live_pattern), "evidence": evidence,
                 "status": "IMPLEMENTED_VERIFIED" if entry and handler_location else "GAP",
                 "basis": ("合同条目在实测路由表中存在（%s），handler %s 定义在 %s；%s。匹配方式：%s"
                           % (table, handler, handler_location, purpose, matched_via))
                          if entry and handler_location else
                          ("%s %s 不在实测路由表中（含占位符归一后仍未命中），合同条目未落实"
                           % (method, pattern))}
        result = reconcile("api-contract", "08#api_proposals[%d]" % (index - 1),
                           join_verbatim([method, pattern, purpose]), "", claim)
        result["提案序号"] = index
        result["方法"] = method
        result["路径"] = pattern
        result["实测路由pattern"] = live_pattern
        result["匹配方式"] = matched_via if entry else "未命中"
        result["合同意图"] = purpose
        result["实测路由表"] = table or ""
        result["handler"] = handler or ""
        result["handler位置"] = handler_location or ""
        rows.append(result)
    return rows


#: Which in-repo test measures each proposed endpoint. Every entry is checked by the
#: builder: a name that does not resolve downgrades that row out of IMPLEMENTED_VERIFIED.
API_EVIDENCE = {
    "GET /api/v1/health": "tests/unified/test_v02_surface.py::test_health_is_real_service_metadata",
    "GET /api/v1/projects": "tests/unified/test_v02_surface.py::test_projects_register_and_read_back_both_sources",
    "GET /api/v1/capabilities": "tests/unified/test_v02_surface.py::test_capabilities_are_honest_and_derived;tests/unified/test_v09_honesty.py::test_unavailable_capabilities_carry_reasons",
    "GET /api/v1/connections": "tests/unified/test_v09_honesty.py::test_connections_never_claim_connected_without_a_probe",
    "POST /api/v1/tasks": "tests/unified/test_v02_surface.py::test_write_boundary_unknown_project_and_kind",
    "GET /api/v1/tasks/{task_id}": "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart",
    "POST /api/v1/tasks/{task_id}/attempts": "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart;tests/unified/test_v05_rejections.py::test_stale_result_refused",
    "POST /api/v1/attempts/{attempt_id}/pack": "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart;tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused",
    "POST /api/v1/attempts/{attempt_id}/handoff-declarations": "tests/unified/test_v05_rejections.py::test_import_before_declared_handoff_refused;tests/unified/test_v05_rejections.py::test_external_receipt_claim_is_not_declarable",
    "POST /api/v1/attempts/{attempt_id}/results": "tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused;tests/unified/test_v11_audit_rework.py::test_f02_design_result_with_wrong_bindings_and_dangerous_refs_is_refused",
    "POST /api/v1/results/{result_id}/verifications": "tests/unified/test_v11_audit_rework.py::test_f03_pinned_revision_that_moved_is_blocked_not_pass;tests/unified/test_v10_gate.py::test_gate_refuses_forged_result_and_verdict",
    "GET /api/v1/knowledge/search": "tests/unified/test_v06_knowledge.py::test_create_search_short_queries_and_no_result",
    "GET /api/v1/design/plans": "tests/unified/test_v02_surface.py::test_design_domain_read_routes_answer_real_data;tests/unified/test_v11_audit_rework.py::test_f03_separation_of_stages",
    "GET /api/v1/design/target-profiles": "tests/unified/test_v04_design_loop.py::test_target_profile_reference_must_address_a_real_profile",
    "GET /api/v1/improvements": "tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only",
}


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------

#: Column order of the three registers: identity, then source, then verdict.
CSV_COLUMNS = ["来源行标识", "要求原文", "当前实现位置", "验证证据", "状态", "依据说明"]


def write_csv(rows: list[dict], path: Path, extra_columns: list[str]) -> None:
    fieldnames = ["来源行标识"] + extra_columns + ["要求原文", "当前实现位置", "验证证据",
                                                   "状态", "依据说明"]
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def histogram(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["状态"]] = counts.get(row["状态"], 0) + 1
    return counts


#: ``验证证据`` means "something measured this row". An ``evidence:<file>#<key>`` pointer into
#: the A01-A10 / F01-F10 result records proves the *opposite* on a row that already admits it is
#: unverified -- that record is the log of non-execution. Left in the evidence column it reads as
#: coverage, so on non-VERIFIED rows it moves into 依据说明 where it can only be a statement
#: about what has not run.
NON_VERIFIED_STATUSES = ("PARTIAL", "GAP", "DEFERRED_P2", "DEFERRED_P3",
                         "IMPLEMENTED_UNVERIFIED", "EXCLUDED_BY_OWNER", "NOT_RUN")
NOT_RUN_POINTER = "（这里引用的不是验证证据，而是未运行记录本身："


def relocate_non_evidence_citations(rows: list[dict]) -> int:
    """Move result-record pointers out of the evidence column on rows that do not verify.

    Returns how many rows changed, so the generator can refuse to pretend the pass ran on an
    empty population.
    """
    changed = 0
    for row in rows:
        if row["状态"] not in NON_VERIFIED_STATUSES:
            continue
        pieces = [piece.strip() for piece in row["验证证据"].split(";") if piece.strip()]
        pointers = [piece for piece in pieces if piece.startswith("evidence:")]
        if not pointers:
            continue
        kept = ";".join(piece for piece in pieces if not piece.startswith("evidence:"))
        row["验证证据"] = kept or NO_EVIDENCE
        row["依据说明"] = (row["依据说明"] + NOT_RUN_POINTER
                        + "；".join(sorted(pointers)) + "）")
        changed += 1
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    ui_rows = build_ui_rows()
    family_rows = build_family_rows()
    requirement_rows = build_requirement_rows()
    api_rows = build_api_checks()
    relocated = 0
    for rows in (ui_rows, family_rows, requirement_rows, api_rows):
        assert rows, "one of the four authored tables came back empty"
        relocated += relocate_non_evidence_citations(rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(ui_rows, args.out_dir / "ui-entry-disposition.csv",
              ["来源仓", "原入口ID", "原名称", "拟融合位置", "分期", "来源表状态"])
    write_csv(family_rows, args.out_dir / "capability-family-register.csv",
              ["能力族ID", "名称", "原拟处理", "拟模块边界", "运行实现分期", "核心验收", "来源表状态"])
    write_csv(requirement_rows, args.out_dir / "requirement-traceability.csv",
              ["需求ID", "来源性质", "需求", "交付或验收"])

    document = json.loads(PROTOCOL_TABLE.read_text(encoding="utf-8"))
    v1_count, compat_count = route_counts()
    api_payload = {
        "schema": "ai-work-lab/api-contract-check/v1",
        "generated_at": now(),
        "source": "AI-WORK-LAB_HANDOFF_20261029/08_前后端交接约定.json",
        "protocol": document["protocol"],
        "source_status": document["status"],
        "method": "逐条与实测路由表比对（backend.v1.V1_ROUTES / design_lab.http_service.ROUTES），"
                  "再解析 handler 定义位置与具名测试；比对对象是路由表，不是文档叙述。",
        "live_route_counts": {"v1_routes": v1_count, "compat_routes": compat_count},
        "api_proposals_total": len(document["api_proposals"]),
        "path_differences": [
            {"提案": row["来源行标识"], "合同路径": row["路径"], "实测pattern": row["实测路由pattern"],
             "匹配方式": row["匹配方式"]}
            for row in api_rows if row["匹配方式"] != "合同路径与实测路由逐字相同"],
        "status_counts": histogram(api_rows),
        "checks": [{key: value for key, value in row.items() if not key.startswith("_")}
                   for row in api_rows],
    }
    api_payload = keeping_the_recorded_stamp(
        args.out_dir / "api-contract-check.json", api_payload)
    (args.out_dir / "api-contract-check.json").write_text(
        json.dumps(api_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    registers = {
        "ui-entry-disposition.csv": ui_rows,
        "capability-family-register.csv": family_rows,
        "requirement-traceability.csv": requirement_rows,
        "api-contract-check.json": api_rows,
    }
    source_totals = {
        "ui-entry-disposition.csv": len(read_table(UI_TABLE)),
        "capability-family-register.csv": len(read_table(FAMILY_TABLE)),
        "requirement-traceability.csv": len(read_table(REQUIREMENT_TABLE)),
        "api-contract-check.json": len(document["api_proposals"]),
    }
    downgraded = [{"register": name, "row": row["来源行标识"],
                   "from": row["_authored_status"], "to": row["状态"]}
                  for name, rows in registers.items() for row in rows if row["_downgraded"]]
    summary = {
        "schemaVersion": "ai-work-lab/requirement-traceability/v1",
        "generated_at": now(),
        "live_route_counts": {"v1_routes": v1_count, "compat_routes": compat_count},
        "registers": {name: {"rows": len(rows), "source_rows": source_totals[name],
                             "reconciles": len(rows) == source_totals[name],
                             "status_counts": histogram(rows)}
                      for name, rows in registers.items()},
        "downgraded_rows": downgraded,
        "downgrade_count": len(downgraded),
        "evidence_pointers_relocated": relocated,
        "unverified_claims": {
            "implemented_unverified": [row["来源行标识"]
                                       for rows in registers.values() for row in rows
                                       if row["状态"] == "IMPLEMENTED_UNVERIFIED"],
        },
        "note": "状态由位置/证据/分期/排除四项机验决定，文档叙述不参与；"
                "IMPLEMENTED_VERIFIED 只可能出现在锚点全部解析成功的行上。",
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    ok = all(item["reconciles"] for item in summary["registers"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
