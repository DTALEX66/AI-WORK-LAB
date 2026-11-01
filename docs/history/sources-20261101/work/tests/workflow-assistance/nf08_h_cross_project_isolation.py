"""NF-08-H: cross-project collaboration reference and isolation.

Proves the acceptance rows for AT-05 / AT-17 / AT-33 / AT-34:
  * A's network failure, A's rule change and A's task cancellation do not
    affect independent B;
  * an authorized A→B delivery completes; an unauthorized reference is refused
    and does NOT cross B's read boundary (a project name is not a grant);
  * a shared UI exposes only the coarse authorized-visible state — another
    project's summary body is never leaked.

Pure and deterministic: independent in-memory project roots; no network, no
cross-project write, no credentials.
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

import cross_project_isolation as xi  # noqa: E402


def _projects() -> dict:
    return {
        "A": xi.Project("A", rules={"max_retries": "3"}, tasks={"t-a": "RUNNING"},
                        network_ok=True),
        "B": xi.Project("B", rules={"max_retries": "5"}, tasks={"t-b": "QUEUED"},
                        network_ok=True),
    }


class TestIndependence(unittest.TestCase):
    def test_a_network_failure_does_not_touch_b(self):
        p = _projects()
        res = xi.simulate_failure(p["A"], p["B"], kind="network")
        self.assertFalse(p["A"].network_ok)
        self.assertTrue(res["b_network_ok"])
        self.assertTrue(res["independent"])

    def test_a_rule_change_does_not_touch_b(self):
        p = _projects()
        res = xi.simulate_failure(p["A"], p["B"], kind="rule_change")
        self.assertEqual(p["A"].rules["max_retries"], "1")
        self.assertNotEqual(p["B"].rules.get("max_retries"), "1")
        self.assertTrue(res["b_rules_untouched"])

    def test_a_cancellation_does_not_touch_b(self):
        p = _projects()
        res = xi.simulate_failure(p["A"], p["B"], kind="cancel")
        self.assertEqual(p["A"].tasks["t-a"], "CANCELLED")
        self.assertNotIn("t-a", p["B"].tasks)
        self.assertTrue(res["b_tasks_untouched"])

    def test_unknown_failure_kind_refused(self):
        p = _projects()
        with self.assertRaises(ValueError):
            xi.simulate_failure(p["A"], p["B"], kind="exploded")


class TestAuthorizedDelivery(unittest.TestCase):
    def test_authorized_a_to_b_delivery_completes(self):
        p = _projects()
        grants = xi.CrossProjectGrant()
        grants.grant("g1", from_project="A", to_project="B",
                     artifact="design-spec", scope="read-deliver")
        cx = xi.CrossProjectDelivery(grants, p)
        res = cx.deliver(grant_id="g1", from_project="A", to_project="B",
                         artifact="design-spec")
        self.assertTrue(res["delivered"])
        self.assertTrue(res["authorized"])
        # recorded in B's own namespace, not A's
        self.assertEqual(res["recorded_in"], "B")
        self.assertEqual(p["B"].tasks["delivery:design-spec"], "DELIVERED")
        self.assertNotIn("delivery:design-spec", p["A"].tasks)

    def test_unauthorized_reference_refused_not_crossing_b_boundary(self):
        p = _projects()
        grants = xi.CrossProjectGrant()
        cx = xi.CrossProjectDelivery(grants, p)
        # no grant at all -> refused, B's read boundary not bypassed
        res = cx.deliver(grant_id="nope", from_project="A", to_project="B",
                         artifact="design-spec")
        self.assertFalse(res["delivered"])
        self.assertFalse(res["authorized"])
        self.assertFalse(res["crossed_read_boundary"])
        self.assertIsNone(p["B"].tasks.get("delivery:design-spec"))
        self.assertTrue(cx.unauthorized_reference_is_refused(
            grant_id="nope", from_project="A", to_project="B",
            artifact="design-spec"))

    def test_grant_scoped_to_exact_projects_and_artifact(self):
        p = _projects()
        grants = xi.CrossProjectGrant()
        grants.grant("g1", from_project="A", to_project="B",
                     artifact="design-spec", scope="read-deliver")
        cx = xi.CrossProjectDelivery(grants, p)
        # a different artifact is NOT covered by this grant
        res = cx.deliver(grant_id="g1", from_project="A", to_project="B",
                         artifact="secrets")
        self.assertFalse(res["delivered"])
        self.assertFalse(res["authorized"])

    def test_revoked_grant_refused(self):
        p = _projects()
        grants = xi.CrossProjectGrant()
        grants.grant("g1", from_project="A", to_project="B",
                     artifact="design-spec", scope="read-deliver")
        grants.revoke("g1")
        cx = xi.CrossProjectDelivery(grants, p)
        res = cx.deliver(grant_id="g1", from_project="A", to_project="B",
                         artifact="design-spec")
        self.assertFalse(res["delivered"])

    def test_project_name_alone_is_not_a_grant(self):
        p = _projects()
        grants = xi.CrossProjectGrant()  # no grants registered
        cx = xi.CrossProjectDelivery(grants, p)
        res = cx.deliver(grant_id="A", from_project="A", to_project="B",
                         artifact="x")  # using the name as an id -> no match
        self.assertFalse(res["delivered"])


class TestSharedUINoLeak(unittest.TestCase):
    def test_coarse_state_shared_summary_never_leaked(self):
        vis = xi.VisibilityProjection()
        vis.publish_shared_state("A", "COMPLETED")
        vis.hide_summary("A", "internal details should not be exposed")
        view = vis.shared_view_for("A")
        self.assertEqual(view["shared_state"], "COMPLETED")
        self.assertFalse(view["summary_exposed"])
        self.assertTrue(vis.summary_never_in_shared_view("A"))
        self.assertNotIn("internal details", str(view))

    def test_private_summary_body_cannot_be_shared(self):
        vis = xi.VisibilityProjection()
        with self.assertRaises(ValueError):
            vis.publish_shared_state("A", "this is a private summary body")

    def test_missing_shared_state_is_none_not_guess(self):
        vis = xi.VisibilityProjection()
        view = vis.shared_view_for("B")
        self.assertIsNone(view["shared_state"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
