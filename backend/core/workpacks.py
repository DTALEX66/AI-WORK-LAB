# SPDX-License-Identifier: MIT
"""Adapter over the migrated WORK-LAB repair-pack machinery.

This module owns no second state machine. The lifecycle truth lives in
``domains/work/workflow_core`` (repair_pack_projection / repair_state /
repair_verification) on the migrated WORK-LAB CanonicalStore; this adapter only
shapes calls between the unified attempt envelope and that machinery:

* issues and their fingerprints come from the migrated issue projection
  (``load_issues`` on the work store) — never recomputed here;
* the pack is built by ``build_repair_pack(manual=True)`` and recorded with
  ``record_pack`` (a draft, never a decision);
* approval resolves a grant in the trusted grants record (fail closed);
* handoff declarations are user statements only;
* the technical verdict is ``verify_repair_record`` re-reading the store now.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
if str(TARGET_ROOT) not in sys.path:
    sys.path.insert(0, str(TARGET_ROOT))

from domains.work.workflow_core import repair_pack_projection as pack_projection
from domains.work.workflow_core import repair_state
from domains.work.workflow_core import repair_verification
from domains.work.workflow_core.canonical_store import CanonicalStore
from domains.work.workflow_core.issue_projection import load_issues

WORK_GATE_RELATIVE_PATH = pack_projection.OWN_GATE_RELATIVE_PATH


class WorkPackError(ValueError):
    """A pack operation the WORK-LAB machinery refused (message carries its reason)."""


class WorkPacks:
    """The work-side pack lifecycle bound to one CanonicalStore + grants path."""

    def __init__(self, store_path: Path, grants_path: Path | None):
        self.store = CanonicalStore(Path(store_path))
        self.grants_path = grants_path

    def close(self) -> None:
        self.store.close()

    # -- issues --------------------------------------------------------------
    def issues_now(self):
        """(issues, summary, absent_reason) straight from the migrated projection."""
        return load_issues(self.store)

    # -- build & record --------------------------------------------------------
    def build_and_record_pack(self, *, project_id: str, project_root: str) -> dict:
        """Build the manual pack for one project's open issues and record the draft."""
        issues, _summary, absent_reason = self.issues_now()
        if issues is None:
            raise WorkPackError("WORK_ISSUE_SOURCE_ABSENT " + repr(absent_reason))
        open_rows = [row for row in issues if row.get("status") == "OPEN"]
        if not open_rows:
            raise WorkPackError("WORK_NO_OPEN_ISSUES")
        pack, reason = pack_projection.build_repair_pack(
            adapter=None, project_id=project_id, bound_rows=open_rows,
            projects=[{"projectId": project_id, "root_path": project_root}],
            registry=None, generated_at=repair_state._now_string(), manual=True)
        if pack is None:
            raise WorkPackError("WORK_PACK_NOT_BUILT " + repr(reason))
        try:
            record = repair_state.record_pack(self.store, pack)
        except ValueError as conflict:
            # the pack id is content-addressed: identical issues + executor mean the
            # SAME durable row — a retry reuses it instead of minting a duplicate
            existing = self.store.read_action_plan(str(pack.get("packId") or ""))
            if existing is None:
                raise
            record = existing
        return {"pack": pack, "record": record,
                "handoff_text": pack_projection.render_handoff_text(pack)}

    def read_record(self, plan_id: str) -> dict | None:
        return repair_state.read_record(self.store, plan_id)

    # -- lifecycle ---------------------------------------------------------------
    def approve(self, plan_id: str, *, authorization_ref: str, expected_version: int) -> dict:
        grants, _state = repair_state.load_grants(self.grants_path)
        if not grants:
            raise WorkPackError("WORK_GRANTS_ABSENT approval without a resolvable grant is self-grant")
        return repair_state.approve_pack(self.store, plan_id,
                                         authorization_ref=authorization_ref,
                                         grants=grants, expected_version=expected_version)

    def declare_handoff(self, plan_id: str, *, claim: str, expected_version: int,
                        target_version: str | None = None, channel: str | None = None,
                        claimed_recipient: str | None = None) -> dict:
        return repair_state.declare_handoff(
            self.store, plan_id, claim=claim, expected_version=expected_version,
            target_version=target_version, channel=channel,
            claimed_recipient=claimed_recipient)

    def record_outcome(self, plan_id: str, *, outcome: str, evidence_level: str,
                       evidence_refs: list, expected_version: int,
                       detail: str | None = None) -> dict:
        return repair_state.record_outcome(
            self.store, plan_id, outcome=outcome, evidence_level=evidence_level,
            evidence_refs=evidence_refs, expected_version=expected_version, detail=detail)

    # -- verification ---------------------------------------------------------
    def verify(self, pack: dict) -> dict:
        """Independent technical verdict: the projection is re-read right now."""
        issues, summary, absent_reason = self.issues_now()
        return repair_verification.verify_repair_record(
            pack=pack, issues_now=issues, summary_now=summary,
            absent_reason=absent_reason, verified_at=repair_state._now_string())
