"""NF-12-SYNC: software / model / protocol updates adapt only the affected
surface.

Proves the acceptance rows for AT-36 / AT-37 on the self-executable slice
(real plugin / venv updates stay user-authorization-gated and BLOCKED):
  * one version / capability change triggers ONLY the affected adaptation, and
    the other clients are NOT reinstalled;
  * two projects sharing an adapter keep a pre-upgrade handoff readable, and
    an unknown cost stays UNKNOWN;
  * no change is a legal NO_CHANGE — it is not proven by "more files".

Pure and deterministic: no real venv / plugin update, no forced user model
choice, no paid call.
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

import update_adaptation as ua  # noqa: E402


def _snap(version: str, caps: set, protocol: str = "v1",
          runtime: str = "native") -> ua.CapabilitySnapshot:
    return ua.CapabilitySnapshot(runtime=runtime, protocol=protocol,
                                 capabilities=caps, version=version)


class TestAffectedSurfaceOnly(unittest.TestCase):
    def test_one_change_adapts_only_its_surface_others_not_reinstalled(self):
        adapter = ua.UpdateAdapter()
        # two clients record their current snapshot
        adapter.record("client-a", _snap("1.0", {"read", "execute"}))
        adapter.record("client-b", _snap("2.0", {"read"}))
        # client-a upgrades protocol to v2 (an affected surface)
        res_a = adapter.adapt("client-a", _snap("1.1", {"read", "execute"}, protocol="v2"),
                              used_surfaces=("protocol", "fields"))
        self.assertEqual(res_a["verdict"], "ADAPTED")
        self.assertFalse(res_a["reinstall"])
        self.assertIn("protocol", res_a["minimal_patch"]["changed_surfaces"])
        # client-b is UNCHANGED -> NO_CHANGE, not reinstalled
        res_b = adapter.adapt("client-b", _snap("2.0", {"read"}),
                              used_surfaces=("protocol", "fields"))
        self.assertEqual(res_b["verdict"], "NO_CHANGE")
        self.assertFalse(res_b["reinstall"])
        self.assertIsNone(res_b["patch"])

    def test_unused_surface_is_not_checked(self):
        adapter = ua.UpdateAdapter()
        adapter.record("x", _snap("1.0", {"read"}))
        # a capability gain the system does not use: verdict is NO_CHANGE
        res = adapter.adapt("x", _snap("1.0", {"read", "new-cap"}),
                            used_surfaces=("fields",))
        self.assertEqual(res["verdict"], "NO_CHANGE")

    def test_incompatibility_yields_minimal_patch_and_rollback(self):
        adapter = ua.UpdateAdapter()
        adapter.record("y", _snap("1.0", {"read", "execute"}))
        # lost 'execute' is detected from the capability set (always checked)
        res = adapter.adapt("y", _snap("1.0", {"read"}),
                            used_surfaces=("fields",))
        self.assertEqual(res["verdict"], "ADAPTED")
        self.assertIn("execute", res["minimal_patch"]["lost_capabilities"])
        self.assertEqual(res["rollback_plan"]["revert_to_version"], "1.0")
        self.assertFalse(res["reinstall"])  # not a whole-package reinstall


class TestNoChangeLegal(unittest.TestCase):
    def test_no_change_is_legal_not_enlarged_files(self):
        adapter = ua.UpdateAdapter()
        adapter.record("z", _snap("3.0", {"read"}))
        res = adapter.adapt("z", _snap("3.0", {"read"}), used_surfaces=("fields",))
        self.assertEqual(res["verdict"], "NO_CHANGE")
        self.assertIn("NO_CHANGE", res["note"])
        self.assertIsNone(res["patch"])


class TestSharedAdapterUpgrade(unittest.TestCase):
    def test_old_handoff_still_readable_after_upgrade(self):
        up = ua.SharedAdapterUpgrade()
        up.register_readable_schema("workflow/federation-envelope/v1")
        up.register_readable_schema("workflow/federation-envelope/v2")
        self.assertTrue(up.old_handoff_still_readable(
            "workflow/federation-envelope/v1")["readable"])

    def test_unknown_schema_is_flagged_not_silently_dropped(self):
        up = ua.SharedAdapterUpgrade()
        up.register_readable_schema("workflow/federation-envelope/v2")
        res = up.old_handoff_still_readable("workflow/federation-envelope/v0")
        self.assertFalse(res["readable"])
        self.assertIn("unrecognised" if "unrecognised" in res["note"]
                      else "unreadable", res["note"])

    def test_unknown_cost_stays_unknown(self):
        up = ua.SharedAdapterUpgrade()
        self.assertEqual(up.cost_unknown_stays_unknown(None), "UNKNOWN")
        self.assertEqual(up.cost_unknown_stays_unknown(""), "UNKNOWN")
        self.assertEqual(up.cost_unknown_stays_unknown("$0.02"), "$0.02")

    def test_user_native_reasoning_is_not_forced(self):
        up = ua.SharedAdapterUpgrade()
        res = up.model_params_are_users_choice(
            user_reasoning="medium", offered_reasoning="high")
        self.assertFalse(res["forced"])
        self.assertEqual(res["applied_reasoning"], "medium")
        self.assertEqual(res["offered_but_not_applied"], "high")


class TestFailureIsolation(unittest.TestCase):
    def test_one_unapproved_maintenance_does_not_fail_the_whole_package(self):
        results = {
            "group-a": "passed",
            "group-b": "blocked_unapproved",
            "group-c": "passed",
        }
        res = ua.isolate_maintenance_failure(results)
        self.assertFalse(res["whole_package_failed"])
        self.assertIn("group-b", res["blocked_groups"])
        self.assertEqual(sorted(res["still_working"]), ["group-a", "group-c"])

    def test_a_real_failure_of_everything_does_fail_the_package(self):
        res = ua.isolate_maintenance_failure({"g": "failed"})
        self.assertTrue(res["whole_package_failed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
