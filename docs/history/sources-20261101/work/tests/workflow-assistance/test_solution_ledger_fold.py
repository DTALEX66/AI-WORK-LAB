"""CL-06 收尾：错误台账折进方案库时，生产者不许发明任何台账里没有的东西。

这一段守护的是"固化"这一步的可信度，而不是它的存在：

* **只有真 closed 的行才成为方案**，其余按具名原因跳过，并且 `eligible + skipped` 必须等于台账总行数
  ——一个只报"折入了 253 条"的计数器，读者无法知道另 36 条是被筛掉还是被丢掉。
* **折入的材料保持 UNVERIFIED**，走的是 `import_unverified`；伪造 VERIFIED 从这条通道进来必须被拒。
* **没有记录就不写**：软件版本、平台这些台账逐条没写的字段留空并带上 versionSource=UNKNOWN 的自带限制语，
  而不是补一个看起来完整的值。
* **dry run 永不写盘**，重复折入是 `UNCHANGED` 而不是第二份修订。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "packages" / "client-neutral-core" / "scripts",):
    sys.path.insert(0, str(entry))

import solution_library as library  # noqa: E402

LEDGER_REF = "taskpacks/current/error-ledger.json"


def row(error_id: str, status_after: str = "PASS", *, fix: str = "Renamed the field.",
        regression: str = "python tests/ci/test_x.py") -> dict:
    entry = {
        "error_id": error_id,
        "task_id": "WA-001",
        "phase": "LOCAL_IMPLEMENTATION",
        "classification": "contract_drift",
        "entrypoint": "packages/client-neutral-core/scripts/verify_core_schemas.py",
        "root_cause": "The budget field name collided with the denylist.",
        "remaining_boundary": "No live provider state was inspected.",
        "evidence_level": "local-focused",
        "status_after": status_after,
    }
    if fix:
        entry["fix"] = fix
    if regression:
        entry["regression_test"] = regression
    return entry


class CountingStore:
    """The only store shape the fold needs, with the write counted instead of performed."""

    def __init__(self) -> None:
        self.writes: list[dict] = []
        self.stored: set[str] = set()

    def save_solution(self, record):
        if record["solutionId"] in self.stored:
            return {"solutionId": record["solutionId"], "revision": record["revision"],
                    "title": record["title"], "status": record["status"],
                    "recommended": False, "changed": False}
        self.stored.add(record["solutionId"])
        self.writes.append(record)
        return {"solutionId": record["solutionId"], "revision": record["revision"],
                "title": record["title"], "status": record["status"],
                "recommended": False, "changed": True}


class ForbiddenStore(CountingStore):
    def save_solution(self, record):  # noqa: D102 - the point of the class
        raise AssertionError("a dry run must not reach the store")


class FoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = library.load_schema()

    def documents(self, errors):
        docs, skipped = library.documents_from_error_ledger(
            {"generated_at": "2026-10-25T00:00:00Z", "errors": errors}, ledger_ref=LEDGER_REF)
        return docs, skipped

    def test_only_closed_rows_fold_and_every_other_row_is_named(self) -> None:
        errors = [row("ERR-001"), row("ERR-002", "PARTIAL"), row("ERR-003", fix=""),
                  row("ERR-004", regression="")]
        docs, skipped = self.documents(errors)
        self.assertEqual([d["solutionId"] for d in docs], ["sol-err-001"])
        self.assertEqual(len(docs) + len(skipped), len(errors),
                         "every ledger row must land either in the fold or in a named skip")
        self.assertIn("no recorded fix", [s["reason"] for s in skipped])
        self.assertIn("no recorded regression_test", [s["reason"] for s in skipped])
        self.assertTrue(any(s["reason"].startswith("status_after=PARTIAL") for s in skipped))

    def test_a_folded_document_satisfies_the_solution_contract(self) -> None:
        docs, _ = self.documents([row("ERR-010")])
        problems = library.validate_solution(docs[0], schema=self.schema)
        self.assertEqual(problems, [], json.dumps(problems, ensure_ascii=False))

    def test_the_fold_invents_no_version_no_platform_and_no_repair_commit(self) -> None:
        docs, _ = self.documents([row("ERR-011")])
        document = docs[0]
        self.assertEqual(document["software"]["versionSource"], "UNKNOWN")
        self.assertEqual(document["software"]["softwareVersion"], "")
        self.assertEqual(document["software"]["platform"], "")
        self.assertEqual(document["status"], "UNVERIFIED")
        self.assertFalse(document["recommended"])
        self.assertIn(library.UNKNOWN_VERSION_LIMIT, document["limits"])
        self.assertTrue(any("fixedCommit" in line for line in document["limits"]),
                        "the missing repair commit has to travel with the recipe")
        self.assertEqual(document["steps"], ["Renamed the field."])
        self.assertEqual(document["verificationSteps"], ["python tests/ci/test_x.py"])

    def test_dry_run_reaches_no_store(self) -> None:
        ledger = ROOT / "taskpacks" / "current" / "error-ledger.json"
        summary = library.fold_error_ledger(ForbiddenStore(), ledger_path=ledger,
                                            dry_run=True, schema=self.schema)
        self.assertTrue(summary["dryRun"])
        self.assertEqual(summary["imported"], 0)
        self.assertEqual(summary["refused"], [])
        self.assertGreater(summary["eligible"], 0)

    def test_replay_is_unchanged_and_a_forged_verified_status_is_refused(self) -> None:
        docs, _ = self.documents([row("ERR-020")])
        store = CountingStore()
        first = library.import_unverified(store, docs[0], schema=self.schema)
        self.assertEqual(first["status"], "IMPORTED")
        replay = library.import_unverified(store, docs[0], schema=self.schema)
        self.assertEqual(replay["status"], "UNCHANGED")
        self.assertEqual(len(store.writes), 1, "a replay must not mint a second revision")
        forged = copy.deepcopy(docs[0])
        forged["status"] = "VERIFIED"
        with self.assertRaises(ValueError) as caught:
            library.import_unverified(store, forged, schema=self.schema)
        self.assertIn("SOLUTION_IMPORT_ONLY_UNVERIFIED", str(caught.exception))
        self.assertEqual(len(store.writes), 1, "the refused document must not have been stored")

    def test_the_shipped_ledger_folds_without_losing_a_row(self) -> None:
        ledger = json.loads((ROOT / "taskpacks" / "current" / "error-ledger.json").read_text(encoding="utf-8"))
        docs, skipped = library.documents_from_error_ledger(ledger, ledger_ref=LEDGER_REF)
        self.assertEqual(len(docs) + len(skipped), len(ledger["errors"]))
        self.assertEqual(len({d["solutionId"] for d in docs}), len(docs),
                         "two folded rows may not claim the same solutionId")
        for document in docs:
            self.assertEqual(library.validate_solution(document, schema=self.schema), [],
                             document["solutionId"])


if __name__ == "__main__":
    unittest.main()
