"""Contract tests for the Codex enhancement responsibility boundary."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "config" / "codex-enhancement-boundary.json"
EXPECTED_SKILLS = {
    "skills/workflow-assistance-github-delivery",
    "skills/workflow-assistance-project-data-boundary",
    "skills/workflow-assistance-safe-project-execution",
    "skills/workflow-assistance-update-safety",
    "skills/workflow-assistance-windows-development",
}
EXPECTED_FIELDS = {
    "config.toml:approval_policy when absent",
    "config.toml:sandbox_mode when absent",
    "config.toml:project_doc_max_bytes when absent",
}


def test_codex_boundary_contract_is_machine_readable() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["module_id"] == "workflow-assistance.codex-global-enhancement"
    assert contract["status"] == "BOUNDARY_CONTRACT"
    assert set(contract["managed_surfaces"]["agent_home"]) == EXPECTED_SKILLS
    assert set(contract["managed_surfaces"]["codex_home"]) >= EXPECTED_FIELDS


def test_codex_boundary_preserves_private_and_project_surfaces() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    excluded = " ".join(contract["responsibility"]["does_not_own"]).lower()
    for term in ("provider", "authentication", "mcp", "plugins", "sessions", "project source"):
        assert term in excluded
    assert contract["capabilities"]["invoke"]["mode"] == "NOT_PROVIDED"
    assert contract["capabilities"]["apply"]["mode"] == "USER_APPROVAL_REQUIRED"
    assert contract["approval_policy"]["live_provider_or_external_project_write"] == "forbidden_by_this_module"
    assert "$codex_home/memories" in excluded


def test_codex_boundary_owns_only_read_only_execution_preflight() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    detected = " ".join(contract["capabilities"]["detect"]["allowed"])

    assert "execution_preflight.py" in detected
    assert "Git/Python/Markdown" in detected
    assert contract["capabilities"]["invoke"]["mode"] == "NOT_PROVIDED"


def test_codex_boundary_requires_redacted_idempotent_evidence() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    evidence = " ".join(contract["evidence_requirements"]).lower()
    assert "redacted" in evidence
    assert "idempotent" in evidence
    assert "credentials" in evidence
    assert contract["capabilities"]["rollback"]["mode"] == "OWNED_HASH_FENCED"
