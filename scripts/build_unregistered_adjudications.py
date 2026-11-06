"""Build ``config/unregistered-adjudications.json`` from the pending rows, verifying each cite.

The 32 ``OWNER_DECISION_PENDING`` rows are the only thing keeping L10#0 at REFUSED. Every earlier
round re-derived them with a one-off script, and the owner was handed a list with no evidence
attached -- so the decision cost more than the research. This writes the *evidence* half of that
job into a data file and leaves the *decision* half empty:

  * ``proposed_category`` is a claim gathered by an agent that read the in-repo files;
  * ``cite_checked`` records what this script could actually verify: the path exists, the line
    number is inside the file, and the line is not blank. Semantic equivalence -- "this in-repo
    file really carries the same contract" -- is NOT verified here and is not claimed anywhere;
  * ``decided_by`` stays null. Until a named person fills it, the adjudication ladder keeps
    answering ``OWNER_DECISION_PENDING`` and the readiness gate keeps refusing.

Run:  .venv/Scripts/python.exe -B -X utf8 scripts/build_unregistered_adjudications.py
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "config/unregistered-adjudications.json"
CATEGORIES = ("UNREGISTERED_TARGET_PATH_PRESENT", "UNREGISTERED_EXCLUDED_CAPABILITY",
              "UNREGISTERED_DEV_TOOLING")

#: (repo, source path) -> (proposed category, authority cite). Gathered by an agent that read
#: the cited files; see the section notes in the audit entry for what each cite is being asked to
#: support.
PROPOSALS = {
    ("design", "design-lab/core/__init__.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "packages/contracts/schemas-design/design-project-state.schema.json::#唯一权威设计项目状态"),
    ("design", "design-lab/core/commands.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "packages/contracts/schemas-design/design-command.schema.json::#对设计对象的显式命令"),
    ("design", "design-lab/core/project_state.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "packages/contracts/schemas-design/design-project-state.schema.json::#唯一权威设计项目状态"),
    ("design", "design-lab/core/providers.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/design/design_lab/creative/generative/workflow_provider.py::provider_declaration"),
    ("design", "design-lab/core/quality_gate.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "packages/contracts/schemas-design/quality-gate.schema.json::#质量门禁：分层评分"),
    ("design", "design-lab/core/user_modes.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        'packages/contracts/schemas-design/user-modes.schema.json::#"guided", "copilot", "director", "method", "production"'),
    ("design", "design-lab/scripts/effective_evidence.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/design/design_lab/readiness/__init__.py::#Module boundary:"),
    ("design", "design-lab/scripts/resolve_open_design_locator.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-design.csv::#design,design-lab/scripts/resolve_open_design_locator.py"),
    ("design", "scripts/amend_source_lock_presence.py"): (
        "UNREGISTERED_DEV_TOOLING", "AGENTS.md::#| 迁移脚本与台账 |"),
    ("design", "scripts/archive_records.py"): (
        "UNREGISTERED_DEV_TOOLING", "scripts/build_source_coverage.py::archive_ledger"),
    ("design", "scripts/collect_design_capability_candidates.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-design.csv::#design,scripts/collect_design_capability_candidates.py"),
    ("design", "scripts/deepseek_test_gate_report.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-design.csv::#design,scripts/deepseek_test_gate_report.py"),
    ("design", "scripts/generate_current_reports.py"): (
        "UNREGISTERED_DEV_TOOLING", "AGENTS.md::#- **数字不手抄。**"),
    ("design", "scripts/run_python_tests.py"): (
        "UNREGISTERED_DEV_TOOLING", "AGENTS.md::#| **任何一次删改测试** |"),
    ("work", "apps/observer/scripts/u19_webview_e2e.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-work.csv::#work,apps/observer/scripts/u19_webview_e2e.py"),
    ("work", "apps/observer/scripts/usage_rollup.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/work/workflow_core/canonical_store.py::#def projection(self)"),
    ("work", "apps/observer/scripts/write_artifact_receipt.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY", "INTEGRATION_POLICY.md::#| 云构建 / 远程 CI / 远程部署 / 发布 |"),
    ("work", "apps/observer/src/observer_evidence.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/work/control/evidence_range_reader.py::name_is_sensitive"),
    ("work", "apps/observer/src/observer_runtime.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT", "docs/CODEX-AUDIT-ENTRY.md::#| F09 Observer 独立入口靠偶然导入顺序 |"),
    ("work", "apps/observer/src/observer_state_classification.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT", "domains/work/control/sse_hub.py::LIVE"),
    ("work", "apps/observer/src/observer_store.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/work/workflow_core/canonical_store.py::CanonicalStore"),
    ("work", "integrations/archeaxis/contracts/open_design_client_seam.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY", "config/adapter-registry.json::#Client USER_GLOBAL desired state"),
    ("work", "integrations/archeaxis/contracts/promotion_contract.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY", "INTEGRATION_POLICY.md::#| AAOS、ASTRYN | 不在写入范围 |"),
    ("work", "scripts/audit/bundle_provenance.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "scripts/check_workbench_bundle_drift.py::main"),
    ("work", "scripts/audit/hud_strip_geometry_via_cdp.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY",
        "scripts/build_requirement_traceability.py::requirement_claims"),
    ("work", "scripts/audit/text_legibility_via_cdp.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-work.csv::#work,scripts/audit/text_legibility_via_cdp.py"),
    ("work", "scripts/audit/topbar_geometry_via_cdp.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-work.csv::#work,scripts/audit/topbar_geometry_via_cdp.py"),
    ("work", "scripts/maintenance/absorb_local_assets.py"): (
        "UNREGISTERED_DEV_TOOLING", "PROJECT_CURRENT.md::#与两个原仓的切割已完成"),
    ("work", "scripts/maintenance/converge_u02_runtime_paths.py"): (
        "UNREGISTERED_DEV_TOOLING", "PROJECT_CURRENT.md::#与两个原仓的切割已完成"),
    ("work", "scripts/maintenance/finish_tmp_tree_cleanup.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY",
        "scripts/build_f01_disposition.py::OUT_OF_SCOPE_RULES"),
    ("work", "scripts/maintenance/record_documentation_drifts.py"): (
        "UNREGISTERED_DEV_TOOLING", "AGENTS.md::#- **数字不手抄。**"),
    ("work", "services/policy/universal_agent_core.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY", "AGENTS.md::#`agents.md` 的 UNIVERSAL_AGENT_CORE"),
}


def check_cite(cite: str) -> dict:
    """Verify only what a cite can be verified for: it resolves to something that is there.

    Three forms are accepted and they are not interchangeable:

    * ``path:NNN`` -- "that line exists and is not blank". This is the weakest form and it rots
      silently: any edit above the line keeps it in range while pointing it at unrelated prose.
      Measured here the same day the register was first written -- editing one §五 bullet moved
      two ``PROJECT_CURRENT.md:212`` cites onto a different sentence, and the check still said ok.
    * ``path::name`` -- a top-level definition in a Python file; survives re-indentation.
    * ``path::#fragment`` -- the line must CONTAIN this text, and the cite reports the line it
      found. The anchor names its own content, so a moved line resolves to the same sentence and
      a reworded one stops resolving. Use this for prose and for rows inside generated registers,
      where a line number is a fact about the last build, not about the claim.
    """
    if "::" in cite:
        path_text, _, anchor = cite.rpartition("::")
        target = ROOT / path_text
        if anchor.startswith("#"):
            fragment = anchor[1:]
            record = {"path": path_text, "fragment": fragment,
                      "path_exists": target.is_file(), "anchor_found": False, "line": None,
                      "line_text": None}
            if record["path_exists"]:
                lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
                found = [index for index, text in enumerate(lines, start=1) if fragment in text]
                record["anchor_found"] = bool(found)
                if len(found) == 1:
                    record["line"] = found[0]
                    record["line_text"] = lines[found[0] - 1].strip()[:160]
                elif found:
                    # an anchor that matches several lines does not identify the evidence, so it
                    # is not treated as resolved: the row would look verified while pointing at
                    # any one of them
                    record["line_text"] = "%d lines contain the anchor" % len(found)
            return record
        record = {"path": path_text, "symbol": anchor, "path_exists": target.is_file(),
                  "symbol_defined": False, "line_text": None}
        if record["path_exists"]:
            import ast
            tree = ast.parse(target.read_text(encoding="utf-8"))
            names = set()
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(node.name)
                elif isinstance(node, ast.Assign):
                    names.update(t.id for t in node.targets if isinstance(t, ast.Name))
            record["symbol_defined"] = anchor in names
            record["line_text"] = "top-level definition %s" % anchor if anchor in names else None
        return record
    path_text, _, number = cite.rpartition(":")
    target = ROOT / path_text
    record = {"path": path_text, "line": int(number), "path_exists": target.is_file(),
              "line_in_range": False, "line_is_content": False, "line_text": None}
    if not target.is_file():
        return record
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    if 1 <= record["line"] <= len(lines):
        record["line_in_range"] = True
        text = lines[record["line"] - 1].strip()
        record["line_is_content"] = bool(text)
        record["line_text"] = text[:160]
    return record


def cite_resolves(record: dict) -> bool:
    if "fragment" in record:
        return record["path_exists"] and record["anchor_found"] and record["line"] is not None
    if "symbol" in record:
        return record["path_exists"] and record["symbol_defined"]
    return record["path_exists"] and record["line_in_range"] and record["line_is_content"]



def main(argv: list[str] | None = None) -> int:
    """`--check` compares and writes nothing; any other argument is refused, not ignored.

    The first version of this function took no arguments at all, so a caller that typed
    ``--check`` got a write and an rc of 0 -- the register looked verified while the mode nobody
    asked for rewrote it. A mode that does not exist must be an error.
    """
    arguments = list(sys.argv[1:] if argv is None else argv[1:])
    unknown = [item for item in arguments if item != "--check"]
    if unknown:
        print(json.dumps(dict(error="UNKNOWN_ARGUMENT", arguments=unknown), ensure_ascii=False))
        return 2
    check = "--check" in arguments
    register = json.loads((ROOT / "config/blocker-register.json").read_text(encoding="utf-8-sig"))
    item = next(i for i in register["items"] if i["id"] == "L10#0")
    pending = [(row["repo"], row["path"], row["source_sha256"]) for row in item["owner_queue"]]

    unproposed = [f"{repo}|{path}" for repo, path, _ in pending if (repo, path) not in PROPOSALS]
    stale = [f"{repo}|{path}" for repo, path in PROPOSALS
             if (repo, path) not in {(r, p) for r, p, _ in pending}]
    if unproposed or stale:
        print(json.dumps(dict(error="PROPOSAL_SET_DOES_NOT_MATCH_THE_PENDING_ROWS",
                              without_proposal=unproposed, no_longer_pending=stale),
                         ensure_ascii=False))
        return 1

    rows = []
    for repo, path, digest in pending:
        category, cite = PROPOSALS[(repo, path)]
        assert category in CATEGORIES, category
        rows.append(dict(repo=repo, path=path, source_sha256=digest,
                         proposed_category=category, authority=cite,
                         cite_check=check_cite(cite),
                         decided_by=None,
                         note="执行人提议 + 出处按锚现查（符号/片段锚，不靠行号）；"
                              "锚找到唯一一行不等于语义等价，那一步由具名真人判"))
    unresolved = [row["authority"] for row in rows if not cite_resolves(row["cite_check"])]
    document = dict(
        schema_version="awl/unregistered-adjudications/v1",
        rule="待判定行的证据通道：proposed_category 不是决定，decided_by 为 null 时判据一律回 "
             "OWNER_DECISION_PENDING；出处一律用能说出内容的锚：代码用 path::符号，散文与生成表用 "
             "path::#片段（锚本身写明它要指的那句话/那一行，句子改了锚就断，不再靠行号在不在范围内）；"
             "语义等价由具名真人判",
        rows=rows,
        counts=dict(rows=len(rows), unresolved_cites=len(unresolved),
                    decided=sum(1 for row in rows if row["decided_by"])),
        unresolved_cites=unresolved,
    )
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if check:
        tracked = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        print(json.dumps(dict(verdict="MATCHES" if tracked == text else "DRIFT",
                              rows=len(rows), unresolved=unresolved[:5],
                              unresolved_count=len(unresolved),
                              tracked_bytes=len(tracked.encode("utf-8")),
                              rebuilt_bytes=len(text.encode("utf-8"))), ensure_ascii=False))
        # an anchor that no longer resolves is a defect whether or not the bytes moved: the
        # register's whole claim is that each proposal carries evidence a person can go and read
        return 0 if tracked == text and not unresolved else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(dict(written=str(OUT), rows=len(rows), unresolved=unresolved[:5],
                          unresolved_count=len(unresolved)), ensure_ascii=False))
    return 0 if not unresolved else 1


if __name__ == "__main__":
    sys.exit(main())
