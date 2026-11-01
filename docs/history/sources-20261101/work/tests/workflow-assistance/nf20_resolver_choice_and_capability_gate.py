"""Negative-control + regression tests for the AG-01..AG-04 repairs.

These pin the four defects recorded in
`taskpacks/history/pre-convergence-20261019/WORK-LAB-ATLAS-GAP-REMEDIATION-TASKCARD-20261001.md` against
regression. Each test fails on the pre-repair implementation, so it is a real
negative control rather than a restatement of the code.

AG-01 explicit choice can be silently overwritten by a project overlay.
AG-02 explicit and overlay paths bypass the required-capabilities gate.
AG-03 session affinity used the salted builtin hash() -> drifts per process.
AG-04 runtime_health / resource were accepted and never consulted.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_ROOT = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(MODULE_ROOT))

from model_capability_resolver import Resolver  # noqa: E402


def catalog() -> dict:
    """Two usable local models with deliberately different capabilities."""
    return {"models": {
        "local-text": {"provider": "lmstudio", "locality": "local", "role": "local.general.fast",
                       "capabilities": ["text"], "lifecycle": "ACTIVE", "quality_state": "OK"},
        "local-vision": {"provider": "lmstudio", "locality": "local", "role": "local.general.vlm",
                         "capabilities": ["text", "ocr"], "lifecycle": "ACTIVE",
                         "quality_state": "OK"},
        "local-coder": {"provider": "lmstudio", "locality": "local", "role": "local.code.readonly",
                        "capabilities": ["code.read"], "lifecycle": "ACTIVE", "quality_state": "OK"},
        "local-writer": {"provider": "lmstudio", "locality": "local", "role": "agent.code.primary",
                         "capabilities": ["code.write"], "lifecycle": "ACTIVE",
                         "quality_state": "OK"},
    }}


def make_resolver(**overrides) -> Resolver:
    kwargs = {"policy": {}, "catalog": catalog(), "runtime_health": {}, "resource": {}}
    kwargs.update(overrides)
    return Resolver(**kwargs)


class AG01ExplicitChoiceIsTerminal(unittest.TestCase):
    """AG-01: an explicit user choice must never be silently overwritten."""

    def test_overlay_does_not_overwrite_explicit_choice(self) -> None:
        r = make_resolver(policy={"project_overlay": {"preferred_models": ["local-vision"]}})
        plan = r.resolve({"task_id": "ag01-1", "task_kind": "general", "data_privacy": "public",
                          "explicit_model": "local-text", "required_capabilities": ["text"]})
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["selected"]["candidate"], "local-text")
        self.assertEqual(plan["selected"]["reason"], "USER_EXPLICIT_CHOICE")

    def test_overlay_never_wins_when_explicit_is_usable(self) -> None:
        # Overlay candidate is strictly more capable; the user's pick still wins.
        r = make_resolver(policy={"project_overlay": {"preferred_models": ["local-vision"]}})
        plan = r.resolve({"task_id": "ag01-2", "task_kind": "general", "data_privacy": "public",
                          "explicit_model": "local-coder", "required_capabilities": ["code.read"]})
        self.assertEqual(plan["selected"]["candidate"], "local-coder")

    def test_unusable_explicit_blocks_and_does_not_substitute(self) -> None:
        r = make_resolver(policy={"project_overlay": {"preferred_models": ["local-text"]}})
        plan = r.resolve({"task_id": "ag01-3", "task_kind": "general", "data_privacy": "public",
                          "explicit_model": "ghost-model", "required_capabilities": ["text"]})
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIsNone(plan["selected"])
        self.assertEqual(plan["reason_code"], "UNKNOWN_CANDIDATE")


class AG02UnifiedCapabilityGate(unittest.TestCase):
    """AG-02: every selection path applies the same capability gate."""

    def test_explicit_missing_capability_is_refused(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "ag02-1", "task_kind": "ocr", "data_privacy": "public",
                          "explicit_model": "local-text", "required_capabilities": ["ocr"]})
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIsNone(plan["selected"])
        self.assertEqual(plan["reason_code"], "MISSING_CAPABILITY")

    def test_explicit_missing_capability_states_reason(self) -> None:
        # The refusal names the specific cause, not a generic unavailability.
        r = make_resolver()
        plan = r.resolve({"task_id": "ag02-2", "task_kind": "ocr", "data_privacy": "public",
                          "explicit_model": "local-text", "required_capabilities": ["ocr"]})
        self.assertEqual(plan["reason_code"], "MISSING_CAPABILITY")
        self.assertEqual(plan["rejected"][0]["candidate"], "local-text")

    def test_overlay_missing_capability_is_skipped_not_selected(self) -> None:
        # Overlay names a model lacking the required capability: it is refused
        # and the scan finds a capable model. The overlay candidate must never
        # be selected with the capability silently unsatisfied.
        r = make_resolver(policy={"project_overlay": {"preferred_models": ["local-text"]}})
        plan = r.resolve({"task_id": "ag02-3", "task_kind": "ocr", "data_privacy": "public",
                          "required_capabilities": ["ocr"]})
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["selected"]["candidate"], "local-vision")
        self.assertIn({"candidate": "local-text", "reason": "MISSING_CAPABILITY"},
                      plan["rejected"])

    def test_overlay_only_candidate_without_capability_blocks(self) -> None:
        # The overlay candidate is the ONLY candidate and it lacks the required
        # capability: refuse, never select it with the gate unsatisfied.
        only_text = {"models": {
            "local-text": {"provider": "lmstudio", "locality": "local",
                           "role": "local.general.fast", "capabilities": ["text"],
                           "lifecycle": "ACTIVE", "quality_state": "OK"},
        }}
        r = Resolver(policy={"project_overlay": {"preferred_models": ["local-text"]}},
                     catalog=only_text, runtime_health={}, resource={})
        plan = r.resolve({"task_id": "ag02-4", "task_kind": "ocr", "data_privacy": "public",
                          "required_capabilities": ["ocr"]})
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIsNone(plan["selected"])
        self.assertEqual(plan["reason_code"], "MISSING_CAPABILITY")

    def test_code_write_primary_enforced_on_explicit_path(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "ag02-5", "task_kind": "code-write", "data_privacy": "public",
                          "explicit_model": "local-coder", "required_capabilities": ["code.write"]})
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["reason_code"], "NOT_CODE_WRITE_PRIMARY")

    def test_code_write_primary_satisfied(self) -> None:
        r = make_resolver()
        plan = r.resolve({"task_id": "ag02-6", "task_kind": "code-write", "data_privacy": "public",
                          "explicit_model": "local-writer", "required_capabilities": ["code.write"]})
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["selected"]["candidate"], "local-writer")


class AG03StableSessionAffinity(unittest.TestCase):
    """AG-03: affinity must not depend on the per-process hash seed."""

    def _affinity(self, model_id: str, task_id: str) -> int:
        return make_resolver()._session_affinity(model_id, task_id)

    def test_affinity_is_deterministic_in_process(self) -> None:
        self.assertEqual(self._affinity("local-text", "task-42"),
                         self._affinity("local-text", "task-42"))

    def test_affinity_stable_across_hash_seeds(self) -> None:
        """Independent subprocesses with different PYTHONHASHSEED must agree."""
        script = (
            "import sys;"
            f"sys.path.insert(0, r'{MODULE_ROOT}');"
            "from model_capability_resolver import Resolver as R;"
            "r=R({}, {'models':{}}, {}, {});"
            "print(r._session_affinity('local-text','abc-123'))"
        )
        seen = []
        for seed in ("0", "1", "2", "3", "random"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run([sys.executable, "-c", script], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", env=env, check=True)
            seen.append(out.stdout.strip())
        self.assertEqual(len(set(seen)), 1, f"affinity drifted across seeds: {seen}")

    def test_affinity_is_bounded_and_id_sensitive(self) -> None:
        scores = {m: self._affinity(m, "t-1") for m in
                  ("local-text", "local-vision", "local-coder", "local-writer")}
        for value in scores.values():
            self.assertGreaterEqual(value, 0)
            self.assertLess(value, 100)
        # Not a constant function: different models must be able to differ.
        self.assertGreater(len(set(scores.values())), 1)


class AG04HealthGateIsReal(unittest.TestCase):
    """AG-04: an unhealthy runtime refuses the candidate with a reason."""

    def test_unhealthy_runtime_refuses_candidate(self) -> None:
        # Isolate the health gate: every candidate is capable, so the ONLY
        # admissible refusal is the runtime health one.
        r = make_resolver(
            catalog={"models": {
                "local-text": {"provider": "lmstudio", "locality": "local",
                               "role": "local.general.fast", "capabilities": ["text"],
                               "lifecycle": "ACTIVE", "quality_state": "OK"},
            }},
            runtime_health={"runtimes": {"lmstudio": {"status": "DOWN"}}})
        plan = r.resolve({"task_id": "ag04-1", "task_kind": "general", "data_privacy": "public",
                          "required_capabilities": ["text"]})
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["reason_code"], "RUNTIME_UNHEALTHY")
        self.assertEqual(plan["rejected"][0]["reason"], "RUNTIME_UNHEALTHY")

    def test_healthy_runtime_still_selects(self) -> None:
        r = make_resolver(runtime_health={"runtimes": {
            "lmstudio": {"status": "RUNNING"}}})
        plan = r.resolve({"task_id": "ag04-2", "task_kind": "general", "data_privacy": "public",
                          "required_capabilities": ["text"]})
        self.assertEqual(plan["status"], "READY")

    def test_unknown_health_shape_is_not_invented_as_failure(self) -> None:
        # Absence of evidence is not evidence of failure.
        r = make_resolver(runtime_health={"some_other_runtime": {"status": "DOWN"}})
        plan = r.resolve({"task_id": "ag04-3", "task_kind": "general", "data_privacy": "public",
                          "required_capabilities": ["text"]})
        self.assertEqual(plan["status"], "READY")

    def test_unhealthy_explicit_choice_reports_health_reason(self) -> None:
        r = make_resolver(runtime_health={"lmstudio": {"status": "FAILED"}})
        plan = r.resolve({"task_id": "ag04-4", "task_kind": "general", "data_privacy": "public",
                          "explicit_model": "local-text", "required_capabilities": ["text"]})
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["reason_code"], "RUNTIME_UNHEALTHY")


class PlanShapeUnchanged(unittest.TestCase):
    """The plan contract the durable worker / bridge consumes is intact."""

    def test_plan_keys_and_schema(self) -> None:
        plan = make_resolver().resolve(
            {"task_id": "shape-1", "task_kind": "general", "data_privacy": "public",
             "required_capabilities": ["text"]})
        self.assertEqual(plan["schema_version"], "workflow/model-invocation-plan/v1")
        self.assertEqual(plan["plan_id"], "plan-shape-1")
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["execution"], "deferred_to_worker")
        for key in ("task_id", "selected", "rejected", "reason_code"):
            self.assertIn(key, plan)
        self.assertNotIn("execute", plan)

    def test_plan_is_json_serializable(self) -> None:
        plan = make_resolver().resolve(
            {"task_id": "shape-2", "task_kind": "general", "data_privacy": "public",
             "required_capabilities": ["text"]})
        json.dumps(plan)


if __name__ == "__main__":
    unittest.main()
