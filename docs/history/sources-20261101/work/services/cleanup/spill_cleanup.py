"""Spill cleanup decisions (WL-410 / ch 44 item 2 + the standing no-delete rule).

ch 44 says ``.project-local`` becomes WORK-LAB's local runtime root, and the
repo's own hygiene rules say: clean only what is proven useless or
regenerable, and ALWAYS keep runtime state, logs, sessions and recovery
backups.  WL-410 takes the spill rows the repo-slimming auditor produced
(ch 34's spill-report.json) and turns each one into a DECISION — it never
deletes.

Four dispositions, each with an explicit, reversible reason:

    KEEP_IN_PLACE    sanctioned runtime / session / recovery state — leave it
    MIGRATE          generated data that belongs under .project-local — move it
    REGENERATE_OK    proven build/dependency/cache output — safe to rebuild,
                     and only then remove the stale copy
    BLOCKED          touches a shared / unknown / credential-adjacent state —
                     stop, ask the user; do not act on it

A decision that would remove something not proven-regenerable, or that hits
a shared runtime root, is BLOCKED by construction, not "clean up later".
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class Disposition:
    KEEP_IN_PLACE = "keep_in_place"
    MIGRATE = "migrate"
    REGENERATE_OK = "regenerate_ok"
    BLOCKED = "blocked"

    ALL = (KEEP_IN_PLACE, MIGRATE, REGENERATE_OK, BLOCKED)
    _MEMBERS = frozenset(ALL)


@dataclass
class SpillDecision:
    path: str
    disposition: str
    reversible: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# patterns that mean "this is sanctioned local runtime root" — never touch
_SANCTIONED_PREFIXES = (".project-local/", ".hermes/")
# file names that are recovery / session state and must survive any cleanup
_KEEP_ALWAYS_EXT = (".sqlite", ".sqlite3", ".jsonl", ".log")
_KEEP_ALWAYS_NAMES = ("handoff-audit.jsonl", "state.db", "CURRENT_STATE.json")
# proven regenerable build/dependency outputs
_REGENERABLE_MARKERS = ("node_modules/", "venv/", ".venv/", "__pycache__/",
                       "*.egg-info", ".pytest_cache/", ".ruff_cache/")


class SpillGovernor:
    """Decides, for each spill row, what may happen to it — never executes a
    destructive step.  The caller owns any real move/delete and only for
    REGENERATE_OK after re-verification."""

    SCHEMA = "work-lab/spill-cleanup/v1"

    def __init__(self, sanctioned_roots: Optional[List[str]] = None,
                 user_authorized: Optional[List[str]] = None) -> None:
        self._sanctioned = [p.replace(os.sep, "/")
                           for p in (sanctioned_roots or [])] + list(_SANCTIONED_PREFIXES)
        # paths the user explicitly green-lit THIS request; only these may be
        # migrated / regenerated for real
        self._authorized = set(user_authorized or set())

    # -- the single decision ----------------------------------------------
    def decide(self, spill: Dict[str, Any]) -> SpillDecision:
        path = spill.get("path", "").replace(os.sep, "/")
        low = path.lower()
        in_sanitize = any(path.startswith(s) for s in self._sanctioned)

        # 1. FAIL-CLOSED FIRST: shared / credential state OUTSIDE the project's
        #    sanctioned roots is never auto-touched.  A global Hermes state.db,
        #    a shared toolchain root, or a credential file stops the cleanup.
        #    (in_sanitize is False here, so state.db / .env we see are the
        #    global ones, not the project-local copy the sanctioned-keep would
        #    otherwise protect.)
        if not in_sanitize and self._looks_shared_or_unknown(low):
            return SpillDecision(path, Disposition.BLOCKED, False,
                                 "shared or credential-adjacent state outside the "
                                 "project; stop and ask the user (no auto action)")

        # 2. sanctioned project runtime root -> keep, never touch
        if in_sanitize:
            return SpillDecision(path, Disposition.KEEP_IN_PLACE, True,
                                 "sanctioned local runtime root (.project-local / .hermes)")

        # 3. keep-always by name / extension (project-relative, not the global
        #    shared copies — those were already blocked above)
        name = path.rsplit("/", 1)[-1]
        if name in _KEEP_ALWAYS_NAMES:
            return SpillDecision(path, Disposition.KEEP_IN_PLACE, True,
                                 "recovery/session state; keep-always")
        if any(name.endswith(e) for e in _KEEP_ALWAYS_EXT):
            return SpillDecision(path, Disposition.KEEP_IN_PLACE, True,
                                 "log / session / state file; keep-always")

        # 4. proven regenerable build output
        if any(marker in path for marker in _REGENERABLE_MARKERS):
            if path in self._authorized:
                return SpillDecision(path, Disposition.REGENERATE_OK, True,
                                     "proven regenerable output, user-authorized")
            # not authorized this request: flag it, but do NOT auto-remove
            return SpillDecision(path, Disposition.MIGRATE, True,
                                 "regenerable; leave until a user authorizes "
                                 "the clean (safe to rebuild, not auto-deleted)")

        # 5. ordinary generated data that belongs under .project-local
        if path in self._authorized:
            return SpillDecision(path, Disposition.MIGRATE, True,
                                 "generated data; user-authorized to migrate to "
                                 ".project-local")
        return SpillDecision(path, Disposition.MIGRATE, True,
                             "generated data; recommend moving to .project-local "
                             "(no automatic move)")

    def _looks_shared_or_unknown(self, low: str) -> bool:
        # shared toolchain / global Hermes runtime roots
        shared_markers = ("appdata/local/hermes/state",
                         "appdata/local/hermes/profiles/",
                         "appdata/local/hermes/plugins/",
                         "toolchain", "shared-")
        if any(m in low for m in shared_markers):
            return True
        # credential-adjacent files.  We only ever reach this when the path is
        # OUTSIDE the sanctioned project roots, so state.db / .env / token here
        # are the global ones, not the project-local copy we must preserve.
        cred_markers = ("credential", "secret", ".env", "token",
                        "state.db", "session.db")
        if any(m in low for m in cred_markers):
            return True
        return False

    # -- batch + report ----------------------------------------------------
    def govern(self, spills: List[Dict[str, Any]]) -> Dict[str, Any]:
        decisions = [self.decide(s) for s in spills]
        summary: Dict[str, int] = {d: 0 for d in Disposition.ALL}
        for dec in decisions:
            summary[dec.disposition] += 1
        blocked = [d.path for d in decisions if d.disposition == Disposition.BLOCKED]
        return {
            "schema": self.SCHEMA,
            "decision_count": len(decisions),
            "summary": summary,
            "blocked": blocked,
            "decisions": [d.to_dict() for d in decisions],
        }

    @staticmethod
    def report_receipt_sha256(report: Dict[str, Any]) -> str:
        payload = json.dumps(report, sort_keys=True, ensure_ascii=False)
        import hashlib
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
