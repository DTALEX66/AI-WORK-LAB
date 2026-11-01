"""Gate: `projects[].lastStrongEvidenceAt` is a real observation, or it is null — never a made-up time.

Owner readback 2026-10-27: 「现在界面上登记记录的内容 都是假的啊 都给我接入进来啊 我要真实的啊」. The daily
shell's project card answered 最近变化 待确认 / 更新：UNKNOWN for every project. That string is not hardcoded
in the front: `apps/observer/frontend/src/daily/dailyData.ts::projectCardOf` falls back to 待确认 when
`p.lastStrongEvidenceAt` is null, `snapshot_api._project_projection` copies the key out of the project row,
and `composition_root._project_rows` — the producer of that row — did not produce the key at all. The card
was therefore structurally incapable of anything but 待确认.

What this file pins:

* the value comes from the project's OWN strong `source_quality` rows (`collectors.py` writes
  `quality = "EXACT_SOURCE"` only when it read the source exactly), passed through verbatim;
* weak rows are not evidence: the newest row in the table may be an `UNKNOWN` row, and then the answer is
  the older strong stamp, not the newest stamp;
* no strong row is null. Null is asserted against the specific fabrications this codebase forbids — 0, the
  snapshot's own `generatedAt`, an epoch stamp, and a "just now" string;
* a project with no evidence of its own does not borrow another project's (WL-L01, same field, different
  column);
* the emitted snapshot still validates against `packages/contracts/schemas/workflow/snapshot-v3.schema.json`,
  which requires the key — an absent key is not an option either.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

import snapshot_validator  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from composition_root import _project_rows, _strong_evidence_map, build_v3_snapshot, load_approved_index  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402
from project_temp import fixture_dir, force_release  # noqa: E402

SCHEMA_PATH = ROOT / "packages/contracts/schemas/workflow/snapshot-v3.schema.json"

T_OLD = "2026-10-27T09:00:00.000000Z"
T_MID = "2026-10-27T11:30:00.500000Z"
T_NEW = "2026-10-27T14:53:24.153046Z"


def quality_row(project_id: str, scope: str, quality: str, observed_at: str) -> dict[str, Any]:
    """One `source_quality` record in the shape `collectors.py` writes."""
    return {
        "row_id": f"{scope}-{project_id}-{observed_at}",
        "project_id": project_id,
        "scope": scope,
        "quality": quality,
        "coverage": "PARTIAL",
        "freshness": "STALE",
        "observed_at": observed_at,
        "last_good_at": observed_at,
        "head_sha": "769345d21fb9df9d0acafe13f953e41597658b80" if scope == "git" else None,
        "branch": "main" if scope == "git" else None,
        "dirty_count": 0 if scope == "git" else None,
        "sourceRef": "git-rev-parse" if scope == "git" else "source-scan",
    }


class StrongEvidenceProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = fixture_dir(prefix="strong-evidence-")
        self.store = CanonicalStore(self.dir / "canonical.sqlite")
        self.store.register_project("work-lab", str(ROOT), display_name="WORK-LAB")
        self.store.register_project("design-lab", str(self.dir / "other"), display_name="DESIGN-LAB")

    def tearDown(self) -> None:
        self.store.close()
        force_release(self.dir)

    def rows(self) -> dict[str, dict[str, Any]]:
        return {row["projectId"]: row for row in _project_rows(self.store, load_approved_index(self.store))}

    def test_strong_rows_produce_the_newest_observed_at_verbatim(self) -> None:
        self.store.append_quality(quality_row("work-lab", "git", "EXACT_SOURCE", T_OLD))
        self.store.append_quality(quality_row("work-lab", "source", "EXACT_SOURCE", T_NEW))
        self.assertEqual(self.rows()["work-lab"]["lastStrongEvidenceAt"], T_NEW,
                         "lastStrongEvidenceAt must be the store's own string, not a reformatted one")

    def test_a_newer_weak_row_does_not_move_the_answer(self) -> None:
        """Strongest wins is not the same as newest wins: an UNKNOWN row is not evidence."""
        self.store.append_quality(quality_row("work-lab", "git", "EXACT_SOURCE", T_MID))
        self.store.append_quality(quality_row("work-lab", "source", "UNKNOWN", T_NEW))
        self.assertEqual(self.rows()["work-lab"]["lastStrongEvidenceAt"], T_MID,
                         "a row the collector itself labelled UNKNOWN was treated as strong evidence")

    def test_no_strong_row_answers_null_not_zero_not_now(self) -> None:
        self.store.append_quality(quality_row("work-lab", "git", "UNKNOWN", T_NEW))
        value = self.rows()["work-lab"]["lastStrongEvidenceAt"]
        self.assertIsNone(value, f"a project with no strong evidence must read null, got {value!r}")
        for fabrication in (0, "", "UNKNOWN", "刚刚", "待确认", "1970-01-01T00:00:00Z"):
            self.assertNotEqual(value, fabrication)

    def test_null_is_also_the_answer_when_the_evidence_table_is_empty(self) -> None:
        value = self.rows()["work-lab"]["lastStrongEvidenceAt"]
        self.assertIsNone(value)

    def test_a_project_without_its_own_evidence_does_not_borrow_one(self) -> None:
        """WL-L01 in a new column: WORK-LAB's observation printed under DESIGN-LAB's name."""
        self.store.append_quality(quality_row("work-lab", "git", "EXACT_SOURCE", T_NEW))
        rows = self.rows()
        self.assertEqual(rows["work-lab"]["lastStrongEvidenceAt"], T_NEW)
        self.assertIsNone(rows["design-lab"]["lastStrongEvidenceAt"],
                          "design-lab has no source_quality row of its own and must not inherit one")

    def test_the_map_only_holds_projects_with_strong_rows(self) -> None:
        self.store.append_quality(quality_row("design-lab", "source", "EXACT_SOURCE", T_OLD))
        self.assertEqual(_strong_evidence_map(self.store), {"design-lab": T_OLD})

    def test_an_unreadable_evidence_table_is_no_evidence_not_a_time(self) -> None:
        class ExplodingStore:
            def list_source_quality(self) -> list[dict[str, Any]]:
                raise OSError("table gone")

        self.assertEqual(_strong_evidence_map(ExplodingStore()), {})  # type: ignore[arg-type]


class SnapshotEndToEndTests(unittest.TestCase):
    def test_the_produced_snapshot_validates_and_carries_the_key(self) -> None:
        root = fixture_dir(prefix="strong-evidence-snapshot-")
        store = CanonicalStore(root / "canonical.sqlite")
        try:
            store.register_project("work-lab", str(ROOT), display_name="WORK-LAB")
            store.append_quality(quality_row("work-lab", "git", "EXACT_SOURCE", T_NEW))
            snapshot = build_v3_snapshot(store, load_approved_index(store), revision=1)
        finally:
            store.close()
        try:
            self.assertTrue(snapshot_validator.validate_snapshot(snapshot)["valid"])
            schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
            errors = list(Draft202012Validator(schema).iter_errors(snapshot))
            self.assertEqual([], [error.message for error in errors],
                             "the produced snapshot no longer satisfies its own contract")
            project = snapshot["projects"][0]
            self.assertEqual(project["lastStrongEvidenceAt"], T_NEW)
            # The key is required by the contract, so the no-evidence branch has to answer with null
            # rather than by omitting the field.
            self.assertIn("lastStrongEvidenceAt", project)
            self.assertNotEqual(project["lastStrongEvidenceAt"], snapshot["generatedAt"],
                                "the card must not be dated by the moment we woke up")
        finally:
            force_release(root)


if __name__ == "__main__":
    unittest.main()
