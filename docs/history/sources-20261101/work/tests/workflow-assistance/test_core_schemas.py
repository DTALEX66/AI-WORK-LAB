from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "packages" / "contracts" / "schemas" / "workflow"
VERIFY = ROOT / "packages/client-neutral-core/scripts" / "verify_core_schemas.py"
EXPECTED = {
    "client-adapter.schema.json",
    "adapter-registry.schema.json",
    "task-card.schema.json",
    "domain-pack.schema.json",
    "action-plan.schema.json",
    # 后端2 (2026-10-22): the repair-pack envelope. It wraps an action-plan body rather than replacing it,
    # and the envelope is camelCase because the producer that writes it is `repair_pack_projection.py` and
    # the executor-facing fields are the same ones the issue rows already use. Adding the file moves this
    # set -- that is the review this pin exists to force.
    "repair-pack.schema.json",
    # CL-06 (2026-10-23): one immutable revision of a reusable maintenance solution. The file is
    # camelCase like the other documents the workflow producer writes, and it is registered here because
    # this set is the review that makes a new cross-module contract an explicit decision.
    "solution.schema.json",
    # OD05 (2026-10-08): Quick Entry's field+permission contract. This set is an exact inventory of
    # the directory, so adding a legitimate schema moves it -- the pin defends "nothing appears in the
    # contract directory without being reviewed here", not a fixed number.
    "quick-entry-request.schema.json",
    # WUI-15 (2026-10-10): the read-only Observer snapshot joined the SSOT. This set is an exact inventory
    # of the directory, so the addition is the review record — the snapshot was the one cross-language
    # payload with no schema, which is what let ERR-225's producer/type drift pass unnoticed.
    "snapshot-v3.schema.json",
    "run-event.schema.json",
    "evidence-envelope.schema.json",
    "error.schema.json",
    "task-ledger.schema.json",
    "observer-event.schema.json",
    "rule-asset.schema.json",
    "skill-package.schema.json",
    "growth-candidate.schema.json",
    "project-profile.schema.json",
    "gate-registry.schema.json",
    "gate-plan.schema.json",
    "blocker.schema.json",
    "ci-observation.schema.json",
    "evidence-manifest.schema.json",
    "model-policy.schema.json",
    "memory-record.schema.json",
    "rule-drift.schema.json",
    "platform-identity.schema.json",
    "config-ownership.schema.json",
    "agent-runtime-adapter.schema.json",
    "model-asset.schema.json",
    "runtime-registry.schema.json",
    "model-invocation-plan.schema.json",
    "usage-observation.schema.json",
    "canonical-config-intent.schema.json",
    "cloud-event-envelope.schema.json",
    "context-capsule.schema.json",
    "global-agent-policy.schema.json",
    "policy-projection-contract.schema.json",
    "policy-projection-loss-report.schema.json",
    "software-installation-identity.schema.json",
    "software-update-preflight.schema.json",
    "execution-parallel-dispatch.schema.json",
    "software-update-postflight.schema.json",
    # P1-06 (2026-10-08): the Control Surface request/result pair. Registered here as well as in
    # .project/governance/contracts/contract-catalog.json — this set is the review gate that makes a new
    # cross-language contract an explicit decision instead of a file that appeared.
    "control-operation.schema.json",
    "control-operation-result.schema.json",
    # WUI-21 read models (2026-10-10). Added here as well as in
    # .project/governance/contracts/contract-catalog.json, because this set is the review gate that makes a
    # new cross-language contract an explicit decision rather than a file that appeared.
    "operation-progress.schema.json",
    "isolated-trial.schema.json",
}

# Schemas whose wire field is camelCase by producer fact, mapped to that field's name.
CAMEL_CASE_WIRE_SCHEMAS = {
    "snapshot-v3.schema.json": "schemaVersion",
    # The repair-pack envelope is camelCase on the wire like the issue rows it binds; its inner `plan`
    # keeps the action-plan contract's own snake_case fields, which is why the version field has to be
    # named rather than guessed from the file's neighbours.
    "repair-pack.schema.json": "schemaVersion",
    # The solution document is written by `solution_library.py` and read by the Observer's solution route;
    # its version field is `schemaVersion` for the same producer-fact reason.
    "solution.schema.json": "schemaVersion",
}


class CoreSchemaTests(unittest.TestCase):
    def test_core_schema_set_has_neutral_metadata_and_required_contracts(self) -> None:
        self.assertEqual({p.name for p in SCHEMA_DIR.glob("*.schema.json")}, EXPECTED)
        for name in sorted(EXPECTED):
            data = json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))
            self.assertEqual(data["type"], "object", name)
            self.assertIn("$id", data, name)
            # The rule is "the payload must carry a version field", not "the field must be spelled in
            # snake_case". workflow/snapshot/v3 is camelCase on the wire (`schemaVersion`, written by
            # snapshot_api.py and declared in apps/observer/frontend/src/types.ts), and renaming it to satisfy
            # a doc guard would change the contract instead of describing it. The exception is a named list,
            # so a schema cannot join it silently and a snake-named one still has to prove its field.
            if name in CAMEL_CASE_WIRE_SCHEMAS:
                self.assertIn(CAMEL_CASE_WIRE_SCHEMAS[name], data["required"], name)
                self.assertNotIn("schema_version", data["required"], name)
            else:
                self.assertIn("schema_version", data["required"], name)
            serialized = json.dumps(data, ensure_ascii=False)
            for forbidden in ("gpt-5.5", "gpt-5.6", "deepseek-chat", "kimi-k2"):
                self.assertNotIn(forbidden, serialized, name)

    def test_action_plan_is_approval_and_rollback_bounded(self) -> None:
        data = json.loads((SCHEMA_DIR / "action-plan.schema.json").read_text(encoding="utf-8"))
        self.assertIn("approval", data["required"])
        self.assertIn("rollback", data["required"])
        self.assertIn("approval_required", json.dumps(data))
        self.assertIn("WAITING_APPROVAL", json.dumps(data))

    def test_verifier_runs_without_client_runtime(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VERIFY), "--schema-dir", str(SCHEMA_DIR)],
            cwd=ROOT,
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CORE_SCHEMA_CONTRACT_PASS", result.stdout)
        self.assertIn("schemas=29", result.stdout)

    def test_verifier_rejects_schema_missing_required_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            temp = Path(raw)
            for path in SCHEMA_DIR.glob("*.schema.json"):
                (temp / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            broken = temp / "action-plan.schema.json"
            data = json.loads(broken.read_text(encoding="utf-8"))
            data["required"].remove("rollback")
            broken.write_text(json.dumps(data), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(VERIFY), "--schema-dir", str(temp)],
                cwd=ROOT,
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("rollback", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
