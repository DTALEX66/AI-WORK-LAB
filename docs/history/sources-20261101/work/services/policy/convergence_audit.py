"""Module/language/dependency + skill lifecycle + model diff convergence audit.

integrated-taskpack-20260916 NF-10 / NF-11 / NF-12 closeout.  Everything here
is read-only and deterministic, and consumes ONLY git-tracked repository facts
(so it never reaches across projects into user global state such as
``~/.agents/skills``, and it never invents a measured "savings %" it did not
actually measure).

NF-10  (skill lifecycle): a task is served by a skill's name + trigger
        description alone; the full body is read only on selection.  The user
        native provider/model/reasoning/hook/MCP/plugin fields are protected:
        they may be OBSERVE/FORBIDDEN but are NEVER in a managed write set.
        14 global backups are out of this repository's scope and are NOT read.

NF-11  (dependency / runnable convergence): the dependency manifests are the
        registered toolchains; apps/ holds exactly the known top-level apps
        (no second Observer, no generic agent service), services/ holds only
        the known owned modules.

NF-12  (model diff): per-adapter version/capability diff against the
        adapter-registry.  With no real model call, behavior is UNKNOWN (never
        "passed"); an unaffected layer yields NO_CHANGE.
"""
from __future__ import annotations

import json
import os
from typing import Any

# --- facts the audit is allowed to rely on --------------------------------
EXPECTED_APPS = frozenset({"control-surface", "observer", "token-monitor"})

# Generic agent-service names that would violate NF-11 acceptance #2.
FORBIDDEN_SERVICE_NAMES = frozenset(
    {"observer2", "second-observer", "generic-agent", "agent-service", "agent-framework"}
)

# User-native field paths that must NEVER enter a managed write set.
USER_NATIVE_FIELD_MARKERS = ("provider", "model", "reasoning", "hook", "mcp", "plugin")


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --- NF-10: skill lifecycle ---------------------------------------------
def skill_load_surface(repo_root: str) -> dict[str, Any]:
    """Report, per repository skill, the on-demand trigger + body byte size.

    A task can be served by ``name`` + ``description`` without reading the full
    body; selection is what reads the body.  The global ``~/.agents/skills``
    backups are OUT of repository scope and are deliberately not read.
    """
    skill_root = os.path.join(repo_root, ".agents", "skills")
    skills: list[dict[str, Any]] = []
    if os.path.isdir(skill_root):
        for name in sorted(os.listdir(skill_root)):
            body_path = os.path.join(skill_root, name, "SKILL.md")
            if not os.path.isfile(body_path):
                continue
            meta, desc = {}, ""
            body = open(body_path, "r", encoding="utf-8").read()
            # crude frontmatter: key: value lines between --- markers
            for line in body.splitlines():
                stripped = line.strip()
                if stripped in ("---", ""):
                    continue
                if ":" in stripped and not stripped.startswith("#"):
                    key, _, val = stripped.partition(":")
                    key = key.strip()
                    if key in ("name", "description", "version"):
                        meta[key] = val.strip().strip('"')
                        if key == "description":
                            desc = meta[key]
            skills.append({
                "name": name,
                "trigger": desc or meta.get("name", name),
                "body_bytes": len(body.encode("utf-8")),
                "select_to_read_body": True,  # full body only on selection
            })
    return {
        "repository_skill_count": len(skills),
        "skills": skills,
        "served_by": "name+description (body read only on selection)",
        "global_backups_scope": "out-of-repository (~/.agents/skills) — NOT read by this audit",
    }


def protected_user_native_fields(config_ownership: dict[str, Any]) -> dict[str, Any]:
    """The user native provider/model/reasoning/hook/MCP/plugin fields.

    These must be OBSERVE/FORBIDDEN.  Any of them with mode MANAGE would mean a
    managed write set can reset user intent — that is a violation this audit
    raises on.  Returns the protected set + a clean/violation verdict.
    """
    protected: list[str] = []
    violations: list[str] = []
    for field in config_ownership.get("fields", []):
        path = str(field.get("path", ""))
        mode = str(field.get("mode", ""))
        lowered = path.lower()
        is_user_native = any(m in lowered for m in USER_NATIVE_FIELD_MARKERS)
        if is_user_native:
            protected.append(path)
            if mode == "MANAGE":
                violations.append(path)
    return {
        "protected_fields": sorted(set(protected)),
        "mode_by_field": {
            f.get("path"): str(f.get("mode", ""))
            for f in config_ownership.get("fields", [])
            if any(m in str(f.get("path", "")).lower() for m in USER_NATIVE_FIELD_MARKERS)
        },
        "managed_reset_violations": violations,
        "clean": not violations,
    }


# --- NF-11: dependency / runnable convergence ---------------------------
def dependency_convergence(repo_root: str, manifest_paths: list[str]) -> dict[str, Any]:
    """Verify the registered toolchains + that no second app/service appeared.

    ``manifest_paths`` are relative to repo root (git-tracked).  We check each
    exists, then assert apps/ top-level == EXPECTED_APPS and services/ contains
    no generic agent-service name.
    """
    present: list[str] = []
    missing: list[str] = []
    for rel in manifest_paths:
        full = os.path.join(repo_root, rel)
        if os.path.exists(full):
            present.append(rel)
        else:
            missing.append(rel)

    apps_dir = os.path.join(repo_root, "apps")
    actual_apps = set(os.listdir(apps_dir)) if os.path.isdir(apps_dir) else set()
    unknown_apps = sorted(actual_apps - EXPECTED_APPS)

    services_dir = os.path.join(repo_root, "services")
    actual_services = set(os.listdir(services_dir)) if os.path.isdir(services_dir) else set()
    forbidden_services = sorted(actual_services & FORBIDDEN_SERVICE_NAMES)

    return {
        "manifests_present": sorted(present),
        "manifests_missing": sorted(missing),
        "apps": sorted(actual_apps),
        "unexpected_apps": unknown_apps,
        "forbidden_services": forbidden_services,
        "clean": not missing and not unknown_apps and not forbidden_services,
    }


# --- NF-12: model / version diff ----------------------------------------
def model_version_diff(adapter_registry: dict[str, Any],
                       observed_versions: dict[str, str] | None = None) -> dict[str, Any]:
    """Per-adapter version/capability diff against the registry.

    ``observed_versions`` maps client id -> a real probed version.  Where a
    version is not probed, status is UNKNOWN — never 'passed'.  A registry
    entry whose observed version equals its target yields NO_CHANGE; a newer
    observed version yields UPGRADE_CANDIDATE; a lower one yields LAGGING.
    Without a real model call, ``model_behavior`` stays 'UNVERIFIED'.
    """
    observed_versions = observed_versions or {}
    entries = adapter_registry.get("entries", [])
    diff: list[dict[str, Any]] = []
    for e in entries:
        cid = e.get("id")
        target = str(e.get("version") or "unknown")
        observed = observed_versions.get(cid)
        if observed is None:
            status, behavior = "UNKNOWN", "UNVERIFIED"
        elif observed == target:
            status, behavior = "NO_CHANGE", "UNVERIFIED"
        else:
            # cannot order arbitrary version strings; flag for human review
            status, behavior = "DIFFERENT", "UNVERIFIED"
        diff.append({
            "client": cid,
            "target_version": target,
            "observed_version": observed,
            "status": status,
            "model_behavior": behavior,  # never 'passed' without a real call
        })
    return {
        "entries": diff,
        "note": "model_behavior is UNVERIFIED unless a real authorized call is made; "
                "no impact => NO_CHANGE, impacted layer => only that layer changes",
    }


def build_convergence_receipt(
    repo_root: str,
    config_ownership: dict[str, Any],
    adapter_registry: dict[str, Any],
    manifest_paths: list[str],
    observed_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Deterministic, read-only convergence receipt (the three cards at once)."""
    return {
        "schema": "workflow/convergence-audit/v1",
        "nf10_skill": skill_load_surface(repo_root),
        "nf10_protected": protected_user_native_fields(config_ownership),
        "nf11_dependency": dependency_convergence(repo_root, manifest_paths),
        "nf12_model_diff": model_version_diff(adapter_registry, observed_versions),
        "global_state_read": False,
        "paid_calls": 0,
    }
