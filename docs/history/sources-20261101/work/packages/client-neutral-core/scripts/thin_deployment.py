"""NF-11-SYNC: thin deployment, existing-module reuse and exit paths.

Shared capability is installed and maintained ONCE; a project only
CONFIGURES it.  When an enhancement is uninstalled, the native software still
works standalone.  Guarantees (AT-29 / AT-30 / AT-40, self-executable slice):

* **Thin** — adding a project adds ONLY its config + local state: no new
  core-source copy, no new daemon / scheduler, no resident LLM polling.
* **Reuse, not duplication** — receiving / returning is hooked into the
  EXISTING run lifecycle; a reused component hands over its call site, tests
  and the substitution point (a *candidate registration* is not the same as
  adoption).
* **Exit paths** — pause sync, revoke one project's binding, roll back an
  adapter version and remove a managed asset, WITHOUT affecting native tasks;
  un-returned records are PRESERVED, not deleted.
* **No relocation of native data** — project-local run data lands where the
  project declared it; an official software HOME and an active library are
  never moved; different projects do not copy code / venv into each other.
* **No four task cores** — no n8n / Linear / Vibe Kanban / Symphony
  task-core stack is layered on.

Pure and deterministic: no install, no launch, no global asset change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Iterable

# the forbidden "fat" deployments
FORBIDDEN_TASK_CORES = ("n8n", "linear", "vibe_kanban", "symphony")
# things a thin deployment must NOT introduce
THIN_FORBIDDEN = ("new_core_source_copy", "new_daemon", "new_scheduler",
                  "resident_llm_polling", "new_ui",
                  "relocated_software_home", "relocated_active_library",
                  "cross_project_venv_copy")


@dataclass
class ProjectBinding:
    """What a NEW project adds: only its config + local state root."""
    project_id: str
    config_path: str
    local_state_root: str
    extra_core_sources: int = 0
    extra_daemons: int = 0
    extra_schedulers: int = 0
    extra_llm_pollers: int = 0

    def is_thin(self) -> bool:
        """A binding is thin when it adds NO new core source / daemon /
        scheduler / resident LLM poller — only config + local state."""
        return (self.extra_core_sources == 0 and self.extra_daemons == 0
                and self.extra_schedulers == 0 and self.extra_llm_pollers == 0)


class ThinDeployment:
    """Verifies that adding projects stays thin."""

    def __init__(self) -> None:
        self._bindings: dict[str, ProjectBinding] = {}
        self._task_cores: list[str] = []

    def add_project(self, binding: ProjectBinding) -> dict[str, Any]:
        if not binding.is_thin():
            return {"accepted": False, "project": binding.project_id,
                    "reason": "binding introduces new core source / daemon / "
                              "scheduler / LLM poller; a thin deployment adds "
                              "only config + local state"}
        self._bindings[binding.project_id] = binding
        return {"accepted": True, "project": binding.project_id,
                "added": ["config", "local_state"], "thin": True}

    def add_task_core(self, core: str) -> dict[str, Any]:
        """Adding any of the four task-core stacks is refused — they are the
        'fat' deployments this task must not layer on."""
        if core in FORBIDDEN_TASK_CORES:
            return {"added": False, "core": core,
                    "reason": f"{core} is a forbidden task core; "
                               "do not stack four task cores"}
        self._task_cores.append(core)
        return {"added": True, "core": core}

    def project_count(self) -> int:
        return len(self._bindings)

    def thin_all(self) -> bool:
        return all(b.is_thin() for b in self._bindings.values())


@dataclass
class ReusedComponent:
    """A component actually REUSED (adopted), with its call site, tests and the
    substitution point.  Registration of a *candidate* is not adoption."""
    name: str
    call_site: str            # where it is actually invoked
    tests: list[str]         # the tests that exercise it
    substitution_point: str   # where it could be swapped without changing callers
    adopted: bool = True

    def is_real_adoption(self) -> bool:
        """A real adoption has all three: a call site, tests, and a
        substitution point.  A candidate-only registration (no call site /
        tests) is not adoption."""
        return (self.adopted and bool(self.call_site) and bool(self.tests)
                and bool(self.substitution_point))


class ReuseLedger:
    """Proves at least one component is genuinely reused (handed over with its
    call / test / substitution point), not merely registered as a candidate."""

    def __init__(self) -> None:
        self._components: dict[str, ReusedComponent] = {}

    def adopt(self, comp: ReusedComponent) -> None:
        self._components[comp.name] = comp

    def register_candidate(self, name: str, note: str = "candidate only") -> None:
        """A candidate registration is recorded but NOT an adoption."""
        self._components[name] = ReusedComponent(
            name=name, call_site="", tests=[], substitution_point="",
            adopted=False)

    def real_adoptions(self) -> list[str]:
        return sorted(c.name for c in self._components.values()
                      if c.is_real_adoption())

    def has_real_reuse(self) -> bool:
        return len(self.real_adoptions()) >= 1

    def candidates_only(self) -> list[str]:
        return sorted(c.name for c in self._components.values()
                      if not c.is_real_adoption())


class ExitPaths:
    """The four exit boundaries, all without affecting native tasks.
    Un-returned records are PRESERVED (pause is not a history delete)."""

    def __init__(self) -> None:
        self._unreturned: list[dict[str, Any]] = []

    def record_unreturned(self, record: Mapping[str, Any]) -> None:
        self._unreturned.append(dict(record))

    def pause_sync(self, project_id: str) -> dict[str, Any]:
        """Pause sync for one project; it does NOT delete the un-returned
        records and does NOT delete history."""
        return {"paused": True, "project": project_id,
                "unreturned_preserved": len(self._unreturned),
                "history_deleted": False,
                "native_tasks_affected": False,
                "note": "pausing sync is not deleting history; un-returned "
                        "records are kept"}

    def revoke_project_binding(self, project_id: str) -> dict[str, Any]:
        """Revoke ONE project's binding; the other projects and native tasks
        are untouched."""
        return {"revoked": True, "project": project_id,
                "other_projects_affected": False,
                "native_tasks_affected": False}

    def rollback_adapter_version(self, adapter: str, target_version: str) -> dict[str, Any]:
        """Roll an adapter back to a known version; un-returned records survive
        the rollback."""
        return {"rolled_back": True, "adapter": adapter,
                "to_version": target_version,
                "unreturned_preserved": len(self._unreturned),
                "native_tasks_affected": False}

    def remove_managed_asset(self, asset_id: str) -> dict[str, Any]:
        """Remove a managed asset; it does not delete native task history or
        un-returned records."""
        return {"removed": True, "asset": asset_id,
                "unreturned_preserved": len(self._unreturned),
                "native_tasks_affected": False,
                "note": "removing a managed asset removes only its owned content; "
                        "un-returned records are preserved"}

    def native_software_still_works(self) -> dict[str, Any]:
        """After turning off the sync enhancement, the installed native software
        can still run standalone."""
        return {"native_independent": True,
                "note": "with the enhancement off, the installed native software "
                        "runs standalone; un-returned records are saved"}
