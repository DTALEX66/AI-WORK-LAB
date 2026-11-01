"""NF-01-SYNC rule semantics: what may legally transfer vs. what stays forbidden.

Proves that a *user-published business artifact* (audit / task document the
user explicitly selected to ship) may flow to an authorized target material
space, while *private session libraries, telemetry bodies, and credentials*
are NEVER auto-mirrored — even when an ``authorized`` flag is set.

Also proves that a project-scoped temporary model preference does not leak
to another project.

Loaded by file path per the NF-02 convention (no ``from services`` hard
import).  No network, no native private store, no paid call.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
AFP = os.path.join(
    ROOT, "packages", "client-neutral-core", "scripts", "artifact_flow_policy.py"
)


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


AFP_MOD = _load("nf01_afp", AFP)


class ClassifyFlowTests(unittest.TestCase):
    """Each decision path of classify_flow."""

    def test_forbidden_class_rejects_even_when_authorized(self):
        for kind in ("private_session", "conversation_log", "telemetry_body", "credential"):
            r = AFP_MOD.classify_flow({"artifact_kind": kind}, authorized=True)
            self.assertEqual(r["decision"], "REJECT", kind)

    def test_unknown_kind_is_pending_authorization(self):
        r = AFP_MOD.classify_flow({"artifact_kind": "something_new"}, authorized=True)
        self.assertEqual(r["decision"], "PENDING_AUTHORIZATION")

    def test_authorized_business_artifact_allows(self):
        for kind in ("user_published_task", "user_published_audit",
                     "immutable_task_package_ref", "receipt_ref"):
            r = AFP_MOD.classify_flow({"artifact_kind": kind, "task_id": "T-1"}, authorized=True)
            self.assertEqual(r["decision"], "ALLOW", kind)

    def test_unauthorized_business_artifact_is_pending(self):
        r = AFP_MOD.classify_flow({"artifact_kind": "user_published_task"}, authorized=False)
        self.assertEqual(r["decision"], "PENDING_AUTHORIZATION")

    def test_nested_secret_in_goal_field_is_isolated(self):
        # secret as a standalone high-entropy value in a whitelisted field
        payload = {"artifact_kind": "user_published_task",
                   "goal": "sk-" + "a" * 60,   # standalone token value
                   "next_step": "push"}
        r = AFP_MOD.classify_flow(payload, authorized=True)
        self.assertEqual(r["decision"], "ISOLATE")
        self.assertTrue(any("goal" in k for k in r.get("leaked_keys", [])))

    def test_nested_secret_by_key_name_is_isolated(self):
        payload = {"artifact_kind": "user_published_task",
                   "goal": "ok", "api_key": "SECRET", "next_step": "push"}
        r = AFP_MOD.classify_flow(payload, authorized=True)
        self.assertEqual(r["decision"], "ISOLATE")
        self.assertIn("api_key", r.get("leaked_keys", []))

    def test_secret_buried_in_nested_dict_is_caught(self):
        payload = {"artifact_kind": "user_published_task",
                   "goal": "ok",
                   "evidence": {"nested": {"auth_token": "abc"}}}
        r = AFP_MOD.classify_flow(payload, authorized=True)
        self.assertEqual(r["decision"], "ISOLATE")
        self.assertTrue(any("auth_token" in k for k in r.get("leaked_keys", [])))

    def test_clean_authorized_artifact_has_no_leak(self):
        payload = {"artifact_kind": "user_published_task",
                   "task_id": "T-2", "goal": "fix test", "next_step": "push"}
        r = AFP_MOD.classify_flow(payload, authorized=True)
        self.assertEqual(r["decision"], "ALLOW")
        self.assertNotIn("leaked_keys", r)


class ProjectPrefScopingTests(unittest.TestCase):
    """Project-scoped temporary preferences must not leak to other projects."""

    def test_project_pref_does_not_reach_other_project(self):
        pref_a = {"scope": "project", "project_id": "A", "model_preference": "offline"}
        self.assertEqual(AFP_MOD.effective_for_project(pref_a, "B"), {})
        self.assertFalse(AFP_MOD.does_project_pref_leak(pref_a, "B"))

    def test_task_pref_does_not_reach_other_project(self):
        pref_t = {"scope": "task", "project_id": "A", "model_preference": "fast"}
        self.assertEqual(AFP_MOD.effective_for_project(pref_t, "B"), {})

    def test_deliberate_global_pref_reaches_other_project(self):
        pref_g = {"global": True, "project_id": "A", "model_preference": "cheap"}
        eff = AFP_MOD.effective_for_project(pref_g, "B")
        self.assertIn("model_preference", eff)
        self.assertTrue(AFP_MOD.does_project_pref_leak(pref_g, "B"))

    def test_own_project_pref_applies(self):
        pref_a = {"scope": "project", "project_id": "A", "model_preference": "offline"}
        self.assertEqual(AFP_MOD.effective_for_project(pref_a, "A")["model_preference"], "offline")

    def test_is_project_scoped_helper(self):
        self.assertTrue(AFP_MOD.is_project_scoped({"scope": "project", "project_id": "A"}))
        self.assertTrue(AFP_MOD.is_project_scoped({"scope": "task", "project_id": "A"}))
        self.assertFalse(AFP_MOD.is_project_scoped({"scope": "global", "project_id": "A"}))


class NestedSecretDetectorTests(unittest.TestCase):
    """find_nested_secrets catches secrets anywhere in the tree, not just top-level."""

    def test_top_level_key(self):
        hits = AFP_MOD.find_nested_secrets({"api_key": "x", "task_id": "T-1"})
        self.assertIn("api_key", hits)

    def test_nested_dict_key(self):
        hits = AFP_MOD.find_nested_secrets({"outer": {"auth_token": "x"}})
        self.assertTrue(any("auth_token" in h for h in hits))

    def test_list_element_key(self):
        hits = AFP_MOD.find_nested_secrets({"items": [{"password": "p"}, {"ok": "v"}]})
        self.assertTrue(any("password" in h for h in hits))

    def test_high_entropy_value_embedded_in_free_text(self):
        """An embedded key is still a key: the whole-string anchor used to let it through."""
        secret_val = "sk-" + "a" * 60
        hits = AFP_MOD.find_nested_secrets({"goal": f"use {secret_val} to run"})
        self.assertTrue(any("goal" in h for h in hits))
        hits2 = AFP_MOD.find_nested_secrets({"bearer": secret_val})
        self.assertTrue(any("bearer" in h for h in hits2))

    def test_clean_payload_has_no_hits(self):
        self.assertEqual(AFP_MOD.find_nested_secrets({"task_id": "T-1", "goal": "ok"}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
