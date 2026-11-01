"""NF-08-F: one on-demand entry point per software, minimal manual operation.

Proves the acceptance rows for AT-29 / AT-30:
  * two different hosts can serve a unified verb WITHOUT copying the task body,
    and one of them does not depend on Hermes;
  * inside a clearly authorized scope the same confirmation is not re-asked
    per card; only a NEW outbound / write triggers the corresponding
    authorization;
  * a standard resume does not load every project history and not the full
    skill texts.

Pure routing / policy: no network, no host process launch, no credentials.
"""
from __future__ import annotations

import os
import sys
import unittest

_PKG = os.path.abspath(os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "..", "..",
    "packages", "client-neutral-core", "scripts"))
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

import entry_semantics as es  # noqa: E402


def two_hosts() -> es.UnifiedEntryPoint:
    reg = es.UnifiedEntryPoint()
    # host 1: native CLI, no Hermes dependency; publishing needs new outbound
    reg.register_host(es.HostEntry(
        host_id="github-native",
        entries={"publish": "gh pr create", "view": "gh pr view",
                 "return": "gh issue comment"},
        depends_on_hermes=False,
        requires_outbound={"publish": True, "return": True},
    ))
    # host 2: Hermes-backed executor adapter; no outbound for resume/view
    reg.register_host(es.HostEntry(
        host_id="codex-native",
        entries={"resume": "codex resume", "view": "codex status",
                 "adjust": "codex send"},
        depends_on_hermes=True,
    ))
    return reg


class TestUnifiedRouting(unittest.TestCase):
    def test_user_sees_verb_not_directory(self):
        reg = two_hosts()
        r = reg.route("resume", "codex-native")
        self.assertTrue(r["routed"])
        self.assertEqual(r["verb"], "resume")
        self.assertEqual(r["native_entry"], "codex resume")
        self.assertFalse(r["body_copied"])

    def test_unknown_verb_rejected(self):
        reg = two_hosts()
        with self.assertRaises(ValueError):
            reg.route("teleport")

    def test_no_host_supports_is_not_invented(self):
        reg = two_hosts()
        # 'publish' is only on github-native; asking the codex host for it is refused
        r = reg.route("publish", "codex-native")
        self.assertFalse(r["routed"])

    def test_host_preference_avoids_hermes_when_both_can(self):
        # only one host supports 'publish', so it is chosen regardless
        reg = two_hosts()
        r = reg.route("publish")
        self.assertEqual(r["host_id"], "github-native")
        self.assertFalse(r["depends_on_hermes"])


class TestTwoHostsWithoutBodyCopy(unittest.TestCase):
    def test_two_hosts_one_without_hermes_no_body_copy(self):
        reg = two_hosts()
        res = reg.two_hosts_without_body_copy("resume")
        # resume is on codex-native; add a second resume-capable host to prove two
        reg.register_host(es.HostEntry(
            host_id="file-channel",
            entries={"resume": "open outbox/next.json"},
            depends_on_hermes=False,
        ))
        res = reg.two_hosts_without_body_copy("resume")
        self.assertTrue(res["two_hosts"])
        self.assertTrue(res["one_without_hermes"])
        self.assertFalse(res["body_copied"])
        self.assertIn("codex-native", res["hosts"])
        self.assertIn("file-channel", res["hosts"])


class TestAuthorizationScope(unittest.TestCase):
    def test_no_new_outbound_means_no_repeated_confirmation(self):
        reg = two_hosts()
        host = reg._hosts["codex-native"]
        scope = es.AuthorizationScope()
        # 'view' / 'resume' need no new outbound -> allowed, no trigger
        for verb in ("view", "resume"):
            r = scope.check(verb, host, scope_key="k1")
            self.assertTrue(r["confirmed"])
            self.assertFalse(r["triggered"])

    def test_new_outbound_triggers_authorization_once_then_not_reasked(self):
        reg = two_hosts()
        gh = reg._hosts["github-native"]
        scope = es.AuthorizationScope()
        # first 'publish' with no grant -> triggers
        first = scope.check("publish", gh, scope_key="publish:public")
        self.assertFalse(first["confirmed"])
        self.assertTrue(first["triggered"])
        # grant the scope; the NEXT identical publish is not re-asked per card
        scope.grant("publish:public")
        second = scope.check("publish", gh, scope_key="publish:public")
        self.assertTrue(second["confirmed"])
        self.assertFalse(second["triggered"])
        # the requests log shows exactly one triggered request
        triggered = [r for r in scope.requests_log() if r["triggered"]]
        self.assertEqual(len(triggered), 1)

    def test_different_scope_triggers_again(self):
        reg = two_hosts()
        gh = reg._hosts["github-native"]
        scope = es.AuthorizationScope()
        scope.grant("publish:private-A")
        r = scope.check("publish", gh, scope_key="publish:private-B")
        self.assertTrue(r["triggered"])  # a different scope still needs auth


class TestResumeContext(unittest.TestCase):
    def test_standard_resume_loads_only_needed_not_full_history_or_skills(self):
        rc = es.ResumeContext()
        available = {
            "checkpoint": "cp-1",
            "current_revision": "3",
            "open_items": "fix readback",
            "full_project_history": "very-large",
            "full_skill_texts": "very-large",
        }
        plan = rc.plan_resume("t-1", needed=["checkpoint", "current_revision", "open_items"],
                             available=available)
        self.assertEqual(set(plan["loaded"]),
                         {"checkpoint", "current_revision", "open_items"})
        # the heavy material is explicitly NOT loaded on a standard resume
        self.assertNotIn("full_project_history", plan["loaded"])
        self.assertNotIn("full_skill_texts", plan["loaded"])
        self.assertIn("full_project_history", plan["not_loaded_heavy"])
        self.assertFalse(plan["loads_full_project_history"])
        self.assertFalse(plan["loads_full_skill_texts"])

    def test_missing_needed_key_is_reported_not_fabricated(self):
        rc = es.ResumeContext()
        plan = rc.plan_resume("t-2", needed=["missing-thing"],
                              available={"checkpoint": "cp"})
        self.assertEqual(plan["excluded_missing"], ["missing-thing"])
        self.assertNotIn("missing-thing", plan["loaded"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
