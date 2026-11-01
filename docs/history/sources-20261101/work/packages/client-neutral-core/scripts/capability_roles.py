"""NF-05-SYNC: client capabilities registered BY ROLE, reusing native probes.

The goal is "the same task format faces different software; adding software
is mainly a thin adapter, not a change to every project".  This module
registers capability ROLES against software, with capabilities driven by
*probes* — a capability is declared ONLY if the probe confirmed it.  The
capability vocabulary is deliberately NOT a fixed seven-item enum: it is a
dynamic table per software, so a software that only supports task-visibility
/ artifact import is PARTIAL, not falsely reported as full-feature.

Key semantics (acceptance AT-18/19/20)
---------------------------------------
* **Roles** separate planning/publishing, execution, review, storage and
  observation.  A planning / review software (e.g. a GitHub or CC Switch
  integration) is registered under its real role and is never presented as a
  code executor.
* **Probe-driven capabilities** — a software's capability set is whatever its
  probe confirmed (read/publish/execute/status/cancel/resume/observe/...), not
  a hardcoded list.  Unsupported capabilities are simply absent and reported
  as PARTIAL / UNSUPPORTED with the prerequisite that would close the gap.
* **Project-neutral adapter reuse** — the SAME adapter id is referenced by two
  projects; dispatch keys on the adapter id, never on a project name.
* **Decoupling** — removing one executor (e.g. Hermes) leaves the others
  usable; executor selection is by *capability*, not by a fixed dependency on
  any one software.

Pure and deterministic: no network, no process launch, no paid call, no
credential access.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Iterable

# Capability ROLES — a fixed semantic partition of who-does-what.  This is NOT
# the capability vocabulary (that is probe-driven and dynamic, see below).
ROLES = ("planner", "executor", "reviewer", "storage", "observer")

# A capability is a native operation the probe can confirm.  The set is open;
# any software declares the subset its probe confirmed.
PROBE_CAPABILITY_EXAMPLES = ("read", "publish", "execute", "status",
                              "cancel", "resume", "observe", "review",
                              "store", "cancel_session")


@dataclass
class SoftwareEntry:
    """One registered software under one or more roles with probed caps."""
    name: str
    roles: list[str]
    probed_capabilities: set[str]
    adapter_id: str            # shared across projects; never a project name
    prerequisites: dict[str, str] = field(default_factory=dict)  # cap -> what closes it

    def __post_init__(self) -> None:
        for r in self.roles:
            if r not in ROLES:
                raise ValueError(f"unknown role {r!r}; roles are {ROLES}")
        # capability table is the dynamic source of truth: no fixed 7-item enum.
        self.probed_capabilities = set(self.probed_capabilities)


class CapabilityRoleRegistry:
    """Registers software by role and answers capability / coverage queries.

    Dispatch and project binding are keyed on ``adapter_id`` (the shared
    adapter), never on a project name — that is the "two projects reuse the
    same adapter, no per-project branching" guarantee.
    """

    def __init__(self) -> None:
        self._software: dict[str, SoftwareEntry] = {}
        self._adapter: dict[str, str] = {}        # adapter_id -> software name
        self._projects: dict[str, dict[str, str]] = {}  # project -> {role: adapter_id}

    # ------------------------------------------------------------------
    # registration
    # ------------------------------------------------------------------
    def register_software(self, name: str, *, adapter_id: str,
                          roles: Iterable[str],
                          probed_capabilities: Iterable[str],
                          prerequisites: Mapping[str, str] | None = None) -> SoftwareEntry:
        entry = SoftwareEntry(
            name=name,
            roles=list(roles),
            probed_capabilities=set(probed_capabilities),
            adapter_id=adapter_id,
            prerequisites=dict(prerequisites or {}),
        )
        self._software[name] = entry
        # one adapter may serve many software, but the adapter->software map
        # records the primary owner; re-registration overwrites the owner.
        self._adapter[adapter_id] = name
        return entry

    def register_project_binding(self, project: str, role: str, adapter_id: str) -> None:
        """Bind a project's role need to a shared adapter.  Dispatch keys on
        adapter_id, so two projects on the same adapter share it with zero
        per-project branching in the code."""
        if adapter_id not in self._adapter:
            raise KeyError(f"adapter {adapter_id!r} not registered; a project "
                           "cannot bind to an unregistered adapter (fail-closed)")
        self._projects.setdefault(project, {})[role] = adapter_id

    # ------------------------------------------------------------------
    # capability queries
    # ------------------------------------------------------------------
    def has_capability(self, software: str, capability: str) -> bool:
        entry = self._software.get(software)
        return entry is not None and capability in entry.probed_capabilities

    def roles_with_capability(self, capability: str,
                               role: str | None = None) -> list[str]:
        """Software (optionally within one role) whose probe confirmed a cap."""
        out = []
        for name, entry in self._software.items():
            if capability not in entry.probed_capabilities:
                continue
            if role is not None and role not in entry.roles:
                continue
            out.append(name)
        return sorted(out)

    def executor_candidates(self, *, exclude: Iterable[str] = ()) -> list[str]:
        """Executors usable for a task = software with the 'executor' role AND
        a probed 'execute' capability.  Excluding one (e.g. a missing Hermes)
        leaves the others intact — decoupling guarantee."""
        excluded = set(exclude)
        return [
            name for name in sorted(self.roles_with_capability("execute", role="executor"))
            if name not in excluded
        ]

    def can_plan_publish(self, software: str) -> bool:
        return self.has_capability(software, "publish")

    # ------------------------------------------------------------------
    # role constraints
    # ------------------------------------------------------------------
    def role_constraint_report(self) -> dict[str, Any]:
        """A planning / reviewer / storage / observer software must NOT be
        usable as a code executor without a probed execute capability.  A
        software registered under 'executor' without 'execute' is flagged."""
        flags: dict[str, list[str]] = {}
        for name, entry in self._software.items():
            if "executor" in entry.roles and "execute" not in entry.probed_capabilities:
                flags.setdefault("executor_without_execute", []).append(name)
            # planning/publishing software that is also listed as executor and
            # has no execute is the classic 'GitHub pretends to be a coder' bug
            for r in ("planner", "reviewer", "storage", "observer"):
                if r in entry.roles and "execute" not in entry.probed_capabilities \
                        and "executor" not in entry.roles:
                    pass  # not claiming execution; nothing to flag
        return flags

    # ------------------------------------------------------------------
    # per-capability coverage matrix (AT-20: every used client has a row)
    # ------------------------------------------------------------------
    def coverage_matrix(self, software_names: Iterable[str] | None = None,
                        capabilities: Iterable[str] = PROBE_CAPABILITY_EXAMPLES) -> list[dict[str, Any]]:
        names = list(software_names) if software_names else sorted(self._software)
        caps = list(capabilities)
        rows = []
        for name in names:
            entry = self._software.get(name)
            if entry is None:
                rows.append({"software": name, "present": False})
                continue
            supported = sorted(entry.probed_capabilities & set(caps))
            missing = [c for c in caps if c not in entry.probed_capabilities]
            # PARTIAL: has at least one capability; UNSUPPORTED: none
            status = "FULL" if not missing else ("PARTIAL" if supported else "UNSUPPORTED")
            rows.append({
                "software": name,
                "present": True,
                "roles": list(entry.roles),
                "adapter_id": entry.adapter_id,
                "supported": supported,
                "missing": missing,
                "status": status,
                "prerequisites": dict(entry.prerequisites),
            })
        return rows

    def missing_capability_prerequisite(self, software: str, capability: str) -> dict[str, Any]:
        """What it takes to close a gap, or that it cannot be claimed done."""
        entry = self._software.get(software)
        if entry is None:
            return {"software": software, "capability": capability,
                    "state": "UNKNOWN", "note": "software not registered"}
        if capability in entry.probed_capabilities:
            return {"software": software, "capability": capability,
                    "state": "SUPPORTED", "note": "probe confirmed this capability"}
        prereq = entry.prerequisites.get(capability)
        return {"software": software, "capability": capability,
                "state": "GAP",
                "prerequisite": prereq,
                "note": ("missing supported interface; cannot be reported as "
                         "full-feature" if prereq is None
                         else f"gap closes when: {prereq}")}

    # ------------------------------------------------------------------
    # adapter reuse
    # ------------------------------------------------------------------
    def adapter_reused_by(self, adapter_id: str) -> dict[str, Any]:
        owner = self._adapter.get(adapter_id)
        if owner is None:
            return {"adapter_id": adapter_id, "owner": None, "projects": []}
        projects = [
            proj for proj, binding in self._projects.items()
            if adapter_id in binding.values()
        ]
        return {"adapter_id": adapter_id, "owner": owner, "projects": sorted(projects),
                "note": "shared adapter; dispatch keys on adapter_id, not project name"}
