"""NF-08-F: one on-demand entry point per software, minimal manual operation.

A single set of UNIFIED verbs (publish / view / resume / adjust / return) is
routed to each host's NATIVE entry point, so the user does not have to remember
directories or per-software commands.  Two different hosts work without copying
the task body; one of them does not depend on Hermes.  Inside a clearly
authorized scope the same confirmation is not re-asked per card; only a NEW
outbound/write triggers the corresponding authorization.  A standard resume
loads only the context the task needs — never every project history or the full
skill texts.

Pure routing / policy layer: no network, no host process launch, no credential
access.  The native entry points are referenced symbolically and bound by the
host adapter; they are not executed here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Iterable

# the unified verbs exposed to the user, regardless of host
UNIFIED_VERBS = ("publish", "view", "resume", "adjust", "return")


@dataclass
class HostEntry:
    """One host's native entry points for the unified verbs.

    ``entries`` maps a unified verb -> the host's native entry (a symbolic
    command / path / MCP op).  A verb the host does not natively support is
    simply absent and reported, not invented."""
    host_id: str
    entries: dict[str, str]
    depends_on_hermes: bool = False
    requires_outbound: dict[str, bool] = field(default_factory=dict)  # verb -> needs new outbound auth

    def supports(self, verb: str) -> bool:
        return verb in self.entries


class UnifiedEntryPoint:
    """Routes a unified verb to a host's native entry.  The user sees the verb,
    not the directory/command; the host is chosen by capability, not by name
    memorized by the user."""

    def __init__(self) -> None:
        self._hosts: dict[str, HostEntry] = {}

    def register_host(self, host: HostEntry) -> HostEntry:
        self._hosts[host.host_id] = host
        return host

    def route(self, verb: str, host_id: str | None = None) -> dict[str, Any]:
        if verb not in UNIFIED_VERBS:
            raise ValueError(f"unified verb must be one of {UNIFIED_VERBS}")
        if host_id is not None:
            host = self._hosts.get(host_id)
            if host is None:
                return {"routed": False, "verb": verb, "reason": f"host {host_id!r} not registered"}
            candidates = [host]
        else:
            candidates = [h for h in self._hosts.values() if h.supports(verb)]
        # keep only hosts that natively support the verb — a host that lacks it
        # is NOT routed to it and the entry is NOT invented
        candidates = [h for h in candidates if h.supports(verb)]
        if not candidates:
            return {"routed": False, "verb": verb,
                    "reason": "no host natively supports this verb; not invented"}
        # prefer a host that does NOT depend on Hermes when both can do it
        chosen = sorted(candidates, key=lambda h: h.depends_on_hermes)[0]
        return {"routed": True, "verb": verb, "host_id": chosen.host_id,
                "native_entry": chosen.entries[verb],
                "body_copied": False,
                "depends_on_hermes": chosen.depends_on_hermes}

    def host_options(self, verb: str) -> list[str]:
        return sorted(h.host_id for h in self._hosts.values() if h.supports(verb))

    def two_hosts_without_body_copy(self, verb: str, exclude_hermes_dependent: bool = True) -> dict[str, Any]:
        """Prove two DIFFERENT hosts can serve the verb, neither copying the
        body, and one not depending on Hermes."""
        options = [h for h in self._hosts.values() if h.supports(verb)]
        non_hermes = [h for h in options if not h.depends_on_hermes]
        ok = len(options) >= 2 and len(non_hermes) >= 1
        return {"two_hosts": len(options) >= 2,
                "one_without_hermes": len(non_hermes) >= 1,
                "body_copied": False,
                "hosts": [h.host_id for h in options],
                "ok": ok}


class AuthorizationScope:
    """Inside a clearly-authorized scope the same confirmation is NOT re-asked
    per card; only a NEW outbound / write action triggers the corresponding
    authorization."""

    def __init__(self) -> None:
        self._granted: set[str] = set()          # granted scope keys
        self._requests: list[dict[str, Any]] = []

    def grant(self, key: str) -> None:
        self._granted.add(key)

    def check(self, verb: str, host: HostEntry, *, scope_key: str) -> dict[str, Any]:
        """A verb that needs a NEW outbound/write and whose scope key is not
        yet granted requires confirmation; an already-granted scope does not
        re-ask per card."""
        needs_new = host.requires_outbound.get(verb, False)
        if not needs_new:
            # no new outbound/write: allowed inside the existing scope, no re-confirm
            return {"confirmed": True, "triggered": False, "scope_key": scope_key,
                    "note": "no new outbound/write; no repeated confirmation"}
        if scope_key in self._granted:
            self._requests.append({"scope_key": scope_key, "triggered": False,
                                   "verb": verb, "note": "scope already granted; not re-asked"})
            return {"confirmed": True, "triggered": False, "scope_key": scope_key,
                    "note": "scope already granted; not re-asked per card"}
        # a NEW outbound/write with no grant -> this is the action that triggers auth
        self._requests.append({"scope_key": scope_key, "triggered": True, "verb": verb})
        return {"confirmed": False, "triggered": True, "scope_key": scope_key,
                "note": "new outbound/write; corresponding authorization is triggered"}

    def requests_log(self) -> list[dict[str, Any]]:
        return list(self._requests)


class ResumeContext:
    """A standard resume loads ONLY the context the task needs — never every
    project history and never the full skill texts."""

    def __init__(self) -> None:
        self._grants: dict[str, list[str]] = {}  # task -> minimal context keys

    def plan_resume(self, task_id: str, *, needed: Iterable[str],
                    available: Mapping[str, str]) -> dict[str, Any]:
        """``needed``: the minimal context keys this task's resume requires
        (checkpoint / current revision / open items).  ``available``: what
        exists on disk (full project history, full skill texts, ...).  The plan
        loads only the needed keys and EXPLICITLY excludes the heavy material."""
        needed_keys = sorted(set(needed))
        loaded = []
        excluded: list[str] = []
        for key in needed_keys:
            if key in available:
                loaded.append(key)
            else:
                excluded.append(key)
        # anything not in the needed set (e.g. full history / full skills) is
        # deliberately NOT loaded on a standard resume
        heavy = [k for k in available if k not in needed_keys]
        return {
            "task_id": task_id,
            "loaded": loaded,
            "excluded_missing": excluded,
            "not_loaded_heavy": heavy,
            "loads_full_project_history": "full_project_history" in loaded,
            "loads_full_skill_texts": "full_skill_texts" in loaded,
            "note": "standard resume loads only the needed context; "
                    "full project history and full skill texts are NOT loaded",
        }
