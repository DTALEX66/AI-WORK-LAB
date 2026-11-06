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
        "packages/contracts/schemas-design/design-project-state.schema.json:5"),
    ("design", "design-lab/core/commands.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "packages/contracts/schemas-design/design-command.schema.json:5"),
    ("design", "design-lab/core/project_state.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "packages/contracts/schemas-design/design-project-state.schema.json:5"),
    ("design", "design-lab/core/providers.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/design/design_lab/creative/generative/workflow_provider.py::provider_declaration"),
    ("design", "design-lab/core/quality_gate.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "packages/contracts/schemas-design/quality-gate.schema.json:5"),
    ("design", "design-lab/core/user_modes.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "packages/contracts/schemas-design/user-modes.schema.json:22"),
    ("design", "design-lab/scripts/effective_evidence.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/design/design_lab/readiness/__init__.py:4"),
    ("design", "design-lab/scripts/resolve_open_design_locator.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-design.csv:1455"),
    ("design", "scripts/amend_source_lock_presence.py"): (
        "UNREGISTERED_DEV_TOOLING", "AGENTS.md:80"),
    ("design", "scripts/archive_records.py"): (
        "UNREGISTERED_DEV_TOOLING", "scripts/build_source_coverage.py::archive_ledger"),
    ("design", "scripts/collect_design_capability_candidates.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-design.csv:4246"),
    ("design", "scripts/deepseek_test_gate_report.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-design.csv:4297"),
    ("design", "scripts/generate_current_reports.py"): (
        "UNREGISTERED_DEV_TOOLING", "AGENTS.md:62"),
    ("design", "scripts/run_python_tests.py"): (
        "UNREGISTERED_DEV_TOOLING", "AGENTS.md:83"),
    ("work", "apps/observer/scripts/u19_webview_e2e.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-work.csv:315"),
    ("work", "apps/observer/scripts/usage_rollup.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/work/workflow_core/canonical_store.py:1374"),
    ("work", "apps/observer/scripts/write_artifact_receipt.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY", "INTEGRATION_POLICY.md:12"),
    ("work", "apps/observer/src/observer_evidence.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/work/control/evidence_range_reader.py:95"),
    ("work", "apps/observer/src/observer_runtime.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT", "docs/CODEX-AUDIT-ENTRY.md:34"),
    ("work", "apps/observer/src/observer_state_classification.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT", "domains/work/control/sse_hub.py:25"),
    ("work", "apps/observer/src/observer_store.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "domains/work/workflow_core/canonical_store.py:139"),
    ("work", "integrations/archeaxis/contracts/open_design_client_seam.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY", "config/adapter-registry.json:494"),
    ("work", "integrations/archeaxis/contracts/promotion_contract.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY", "INTEGRATION_POLICY.md:21"),
    ("work", "scripts/audit/bundle_provenance.py"): (
        "UNREGISTERED_TARGET_PATH_PRESENT",
        "scripts/check_workbench_bundle_drift.py::main"),
    ("work", "scripts/audit/hud_strip_geometry_via_cdp.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY",
        "scripts/build_requirement_traceability.py::requirement_claims"),
    ("work", "scripts/audit/text_legibility_via_cdp.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-work.csv:1983"),
    ("work", "scripts/audit/topbar_geometry_via_cdp.py"): (
        "UNREGISTERED_DEV_TOOLING", "migration/source-coverage-work.csv:1947"),
    ("work", "scripts/maintenance/absorb_local_assets.py"): (
        "UNREGISTERED_DEV_TOOLING", "PROJECT_CURRENT.md:212"),
    ("work", "scripts/maintenance/converge_u02_runtime_paths.py"): (
        "UNREGISTERED_DEV_TOOLING", "PROJECT_CURRENT.md:212"),
    ("work", "scripts/maintenance/finish_tmp_tree_cleanup.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY",
        "scripts/build_f01_disposition.py::OUT_OF_SCOPE_RULES"),
    ("work", "scripts/maintenance/record_documentation_drifts.py"): (
        "UNREGISTERED_DEV_TOOLING", "AGENTS.md:62"),
    ("work", "services/policy/universal_agent_core.py"): (
        "UNREGISTERED_EXCLUDED_CAPABILITY", "AGENTS.md:4"),
}


def check_cite(cite: str) -> dict:
    """Verify only what a cite can be verified for: it resolves to something that is there.

    Two forms are accepted, and the difference is not cosmetic. ``path:NNN`` is checked as
    "that line exists and is not blank" -- which rots the moment the cited file grows, as an
    earlier batch measured. ``path::name`` is checked against the file's own definitions, so it
    survives re-indentation; a code target should use it.
    """
    if "::" in cite:
        path_text, _, name = cite.rpartition("::")
        target = ROOT / path_text
        record = {"path": path_text, "symbol": name, "path_exists": target.is_file(),
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
            record["symbol_defined"] = name in names
            record["line_text"] = "top-level definition %s" % name if name in names else None
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
    if "symbol" in record:
        return record["path_exists"] and record["symbol_defined"]
    return record["path_exists"] and record["line_in_range"] and record["line_is_content"]



def main() -> int:
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
                         note="执行人提议 + 出处已核到「该行确实存在且非空白」；语义等价与否由 owner 判"))
    unresolved = [row["authority"] for row in rows if not cite_resolves(row["cite_check"])]
    document = dict(
        schema_version="awl/unregistered-adjudications/v1",
        rule="待判定行的证据通道：proposed_category 不是决定，decided_by 为 null 时判据一律回 "
             "OWNER_DECISION_PENDING；出处只核到「路径存在、行号在范围内、该行非空白」，"
             "语义等价由具名真人判",
        rows=rows,
        counts=dict(rows=len(rows), unresolved_cites=len(unresolved),
                    decided=sum(1 for row in rows if row["decided_by"])),
        unresolved_cites=unresolved,
    )
    OUT.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8", newline="\n")
    print(json.dumps(dict(written=str(OUT), rows=len(rows), unresolved=unresolved[:5],
                          unresolved_count=len(unresolved)), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
