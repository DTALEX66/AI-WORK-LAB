# SPDX-License-Identifier: MIT
"""V01–V10 reconciliation: every frozen acceptance id points at something real.

``AI-WORK-LAB_HANDOFF_20261029/09_任务分期与验收.json`` freezes the acceptance ids
``V01`` … ``V10``. Until 2026-10-31 nothing mapped them: the test directory happens
to contain files named ``test_v02`` … ``test_v14``, which looks like coverage while
answering nothing — a renamed test, a deleted assertion, or an id with no file at
all (``V01``, ``V08`` had none) would not have failed any check, and file names are
not executables.

This file holds the mapping and can fail in three ways:

* an id in the frozen list is missing from the register, or the register invents one;
* a named ``module::test_name`` does not actually exist as a callable test function
  in that file (checked with ``importlib`` + ``getattr``, not by reading text);
* an id covered only by a **script** claims pytest status, or its script evidence
  disappeared. Those ids are recorded as ``SCRIPT_COVERED`` and must carry no
  ``pytest_targets`` at all — a subprocess check is not a pytest node.

Vocabulary: this proves the mapping is real and executable. It is not evidence that
the acceptance *clause* is satisfied — that judgement belongs to the assertions in
the named tests, and where the named coverage is a script, to that script's verdict.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_SOURCE = (TARGET_ROOT / "AI-WORK-LAB_HANDOFF_20261029"
                     / "09_任务分期与验收.json")
UNIFIED_DIR = Path(__file__).resolve().parent

#: Ids whose coverage is a subprocess-driven script rather than a pytest node.
#: ``verify_isolated_install.py`` runs the old suite twice (installed vs source) and
#: opens packaged resources from the install tree; that is real coverage for V08 and
#: it is not something this file should pretend to be.
SCRIPT_COVERED = {
    "V08": {
        "script": "scripts/verify_isolated_install.py",
        "script_functions": ["run_regression"],
        "recorded_checks": ["legacy-regression", "resource-readback",
                            "isolated-install-present"],
        "note": "隔离安装下的旧回归与包内资源读回由脚本产生 verdict；"
                "记录在 .project-local/build/*/verify-report.json，"
                "不是本目录的 pytest 节点，也不得写成 pytest 覆盖",
    },
}

#: V-id -> the tests that execute it. Every entry is a real, named test function.
PYTEST_COVERED = {
    "V01": {
        "clause": "来源清单、当前增量、迁移映射无未解释遗漏；重复项与延期有理由。",
        "pytest_targets": [
            "test_v14_registers.py::test_coverage_register_accounts_for_every_source_file",
            "test_v14_registers.py::test_coverage_register_leaves_no_row_undecided",
            "test_v14_registers.py::test_coverage_gap_rows_match_the_f01_register",
            "test_v14_registers.py::test_registered_non_python_gaps_state_where_the_file_actually_is",
            "test_v14_registers.py::test_f01_register_separates_wired_from_merely_present",
            "test_v14_registers.py::test_duplicate_candidates_are_recomputable_and_deferrals_carry_a_reason",
            "test_v07_migration.py::test_migrated_file_digests_match_their_sources",
            "test_v07_migration.py::test_mapping_rerun_is_idempotent",
        ],
    },
    "V02": {
        "clause": "新统一后端真实启动，loopback HTTP 返回健康、项目、能力和两域代表数据。",
        "pytest_targets": [
            "test_v02_surface.py::test_health_is_real_service_metadata",
            "test_v02_surface.py::test_projects_register_and_read_back_both_sources",
            "test_v02_surface.py::test_capabilities_are_honest_and_derived",
            "test_v02_surface.py::test_design_domain_read_routes_answer_real_data",
            "test_v02_surface.py::test_kernel_guards_apply_to_v1_routes",
        ],
    },
    "V03": {
        "clause": "维护人工任务包从创建到独立核验、重启读回通过。",
        "pytest_targets": [
            "test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart",
            "test_v11_audit_rework.py::test_f01_unified_service_serves_the_migrated_work_projection",
        ],
    },
    "V04": {
        "clause": "设计方案修订/目标组合进入同一任务包，导入结果仍区分技术与专业验收；重启读回。",
        "pytest_targets": [
            "test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending",
            "test_v04_design_loop.py::test_target_profile_reference_must_address_a_real_profile",
            "test_v11_audit_rework.py::test_f03_separation_of_stages",
            "test_v11_audit_rework.py::test_f03_pinned_revision_that_moved_is_blocked_not_pass",
        ],
    },
    "V05": {
        "clause": "错任务、错尝试、旧版本、重复结果、篡改内容、越界路径与危险导入实际被拒。",
        "pytest_targets": [
            "test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused",
            "test_v05_rejections.py::test_stale_result_refused",
            "test_v05_rejections.py::test_duplicate_result_refused_on_second_attempt",
            "test_v05_rejections.py::test_import_before_declared_handoff_refused",
            "test_v05_rejections.py::test_external_receipt_claim_is_not_declarable",
            "test_v05_rejections.py::test_work_project_root_must_exist",
            "test_v11_audit_rework.py::test_f02_design_result_with_wrong_bindings_and_dangerous_refs_is_refused",
            "test_v11_audit_rework.py::test_f02_attachment_is_never_executed_or_imported",
        ],
    },
    "V06": {
        "clause": "知识/方案搜索含 1 字、2 字、无结果，修订与并发冲突、索引重建后数据不丢。",
        "pytest_targets": [
            "test_v06_knowledge.py::test_create_search_short_queries_and_no_result",
            "test_v06_knowledge.py::test_revision_conflict_and_index_rebuild",
            "test_v06_knowledge.py::test_unified_search_endpoint_merges_both_libraries",
            "test_v11_audit_rework.py::test_v06_upgrade_unified_search_asserts_real_hits_not_field_presence",
            "test_v11_audit_rework.py::test_f05_short_queries_no_match_and_both_domains_hit",
            "test_v11_audit_rework.py::test_f05_solution_revision_conflict_and_restart_readback",
        ],
    },
    "V07": {
        "clause": "迁移重复执行不复制记录，注入失败后可恢复；原源文件与受控输入保持完整。",
        "pytest_targets": [
            "test_v07_migration.py::test_isolated_rehearsal_apply_is_idempotent",
            "test_v07_migration.py::test_injected_interruption_leaves_previous_bytes_and_a_retry_completes",
            "test_v07_migration.py::test_sources_are_byte_identical_before_and_after_a_rerun",
            "test_v07_migration.py::test_prune_reports_only_paths_this_tool_recorded",
            "test_v12_data_migration.py::test_rerun_is_idempotent_and_adds_no_records",
            "test_v12_data_migration.py::test_injected_exception_rolls_back_every_target_then_retry_completes",
        ],
    },
    "V09": {
        "clause": "不可用执行器、宿主、延期能力返回诚实状态；模拟连接成功不赋予真实运行资格。",
        "pytest_targets": [
            "test_v09_honesty.py::test_connections_never_claim_connected_without_a_probe",
            "test_v09_honesty.py::test_unavailable_capabilities_carry_reasons",
            "test_v09_honesty.py::test_demo_data_origin_cannot_grant_live_qualification",
            "test_v11_audit_rework.py::test_f07_origin_chain_is_inherited_and_cannot_be_promoted",
            "test_v11_audit_rework.py::test_f10_qualification_needs_a_probe_bound_to_this_candidate",
        ],
    },
    "V10": {
        "clause": "验收门拒绝“仅填 VERIFIED、伪回执、无效证据或只改文档”的完成声明。",
        "pytest_targets": [
            "test_v10_gate.py::test_gate_accepts_backed_completions",
            "test_v10_gate.py::test_gate_refuses_doc_only_completion",
            "test_v10_gate.py::test_gate_refuses_forged_result_and_verdict",
            "test_v10_gate.py::test_store_api_refuses_to_mint_the_forgery",
            "test_v11_audit_rework.py::test_f10_stale_and_foreign_candidate_records_grant_nothing",
            "test_v11_audit_rework.py::test_f10_unknown_enums_and_missing_dependency_fail_closed",
        ],
    },
}

#: The ids this register claims coverage for, in frozen order.
COVERED_IDS = sorted(set(PYTEST_COVERED) | set(SCRIPT_COVERED))


def _frozen_acceptance_ids() -> list[str]:
    document = json.loads(ACCEPTANCE_SOURCE.read_text(encoding="utf-8"))
    return list(document["acceptance_ids"])


def _load(module_file: str):
    spec = importlib.util.spec_from_file_location(
        "v_register_" + module_file.replace(".py", ""), UNIFIED_DIR / module_file)
    assert spec and spec.loader, module_file
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def modules() -> dict:
    loaded: dict = {}
    for entry in PYTEST_COVERED.values():
        for target in entry["pytest_targets"]:
            name = target.split("::")[0]
            loaded.setdefault(name, _load(name))
    return loaded


def test_register_covers_exactly_the_frozen_acceptance_ids():
    frozen = _frozen_acceptance_ids()
    assert frozen == ["V01", "V02", "V03", "V04", "V05", "V06", "V07", "V08", "V09", "V10"]
    assert COVERED_IDS == frozen, (sorted(set(frozen) - set(COVERED_IDS)),
                                   sorted(set(COVERED_IDS) - set(frozen)))
    # an id may not be covered twice under two kinds: that is how a script claim
    # gets laundered into a pytest one
    assert not set(PYTEST_COVERED) & set(SCRIPT_COVERED)
    for identifier, entry in PYTEST_COVERED.items():
        assert entry["clause"], identifier
        assert entry["pytest_targets"], identifier


def test_every_named_pytest_target_actually_exists(modules):
    checked = 0
    for identifier, entry in PYTEST_COVERED.items():
        for target in entry["pytest_targets"]:
            module_file, _, function = target.partition("::")
            assert module_file in modules, target
            assert function.startswith("test_"), target
            resolved = getattr(modules[module_file], function, None)
            assert resolved is not None, identifier + " names a missing test: " + target
            assert callable(resolved), target
            # defined in that file, not re-exported from somewhere else
            assert getattr(resolved, "__module__", "").endswith(module_file[:-3]), (
                target, getattr(resolved, "__module__", ""))
            checked += 1
    assert checked == sum(len(e["pytest_targets"]) for e in PYTEST_COVERED.values())


def test_script_covered_ids_are_not_claimed_as_pytest(modules):
    for identifier, entry in SCRIPT_COVERED.items():
        assert identifier not in PYTEST_COVERED, identifier
        assert "pytest_targets" not in entry, identifier
        script = TARGET_ROOT / entry["script"]
        assert script.is_file(), str(script)
        spec = importlib.util.spec_from_file_location("isolated_install_under_register", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for name in entry["script_functions"]:
            assert callable(getattr(module, name, None)), (identifier, name)
        text = script.read_text(encoding="utf-8")
        for check in entry["recorded_checks"]:
            assert re.search(r'record\(\s*"' + re.escape(check) + r'"', text), (identifier, check)


def test_script_covered_verdicts_exist_as_local_evidence():
    """SCRIPT_COVERED is only honest while the script's own record is on disk.

    ``.project-local`` is not in Git, so on a machine that never ran the isolated
    install this fails with a named reason instead of the id quietly reading as
    covered. That is the intended behaviour: V08 is not a pytest claim.
    """
    reports = sorted((TARGET_ROOT / ".project-local" / "build").glob("*/verify-report.json"))
    assert reports, ("no verify-report.json under .project-local/build: the V08 coverage is "
                     "produced by scripts/verify_isolated_install.py and must be re-run here")
    for identifier, entry in SCRIPT_COVERED.items():
        found: dict[str, str] = {}
        for path in reports:
            document = json.loads(path.read_text(encoding="utf-8"))
            for check in document.get("checks", []):
                if check.get("id") in entry["recorded_checks"]:
                    found.setdefault(check["id"], check["verdict"])
        for check in entry["recorded_checks"]:
            assert check in found, (identifier, check, sorted(found))
        assert found, identifier


def test_no_unified_test_file_is_claimed_that_the_directory_does_not_have(modules):
    """The register must not drift into naming files the suite no longer contains."""
    on_disk = {path.name for path in UNIFIED_DIR.glob("test_*.py")}
    for entry in PYTEST_COVERED.values():
        for target in entry["pytest_targets"]:
            assert target.split("::")[0] in on_disk, target
    # every frozen id has exactly one kind of coverage recorded, and V08 is the only
    # one whose pytest node count is zero
    assert set(_frozen_acceptance_ids()) == set(COVERED_IDS)
    script_only = {identifier for identifier in COVERED_IDS if identifier in SCRIPT_COVERED}
    assert script_only == {"V08"}, script_only
