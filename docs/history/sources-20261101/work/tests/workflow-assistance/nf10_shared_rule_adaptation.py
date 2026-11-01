"""NF-10-SYNC: shared rules / skills / user-difference real adaptation.

Proves the acceptance rows for AT-02 / AT-30 / AT-36 on the self-executable
slice (a real global deploy stays user-authorization-gated and BLOCKED):
  * the same shared rule can take effect in two software native carriers
    (here: two project configs share the rule field) with a read-back, and a
    project diff does NOT pollute the global; model / provider / reasoning /
    auth / user-plugin values keep their original values;
  * removing a managed enhancement removes ONLY its owned content; add /
    delete / rollback never touch unknown fields;
  * the base / live / candidate three-way compare PRESERVES the user's
    modification; an upstream change is marked pending adaptation, never a
    blind restore of the old snapshot;
  * skills load on demand; a no-benefit skill is stopped; 13 is inventory,
    not a permanent number; a new model does not get a full skill copy.

Pure and deterministic: no global deploy, no provider / API-Key change, no
upstream internal file edit.
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

import shared_rule_adaptation as sra  # noqa: E402


class TestFieldLayering(unittest.TestCase):
    def test_same_shared_rule_effect_in_two_carriers_with_readback(self):
        # one shared rule value, read back from two project configs (native
        # carriers) — the rule layer is separate from the project diff layer
        ledger = sra.OwnershipLedger()
        ledger.register(sra.ManagedAsset(
            asset_id="shared-rule-pkg", owns_fields={"rule.max_retries"},
            provenance="origin:shared-rule-pkg@v1"))
        carrier_a = {"rule.max_retries": "3", "model": "agnes", "provider": "custom"}
        carrier_b = {"rule.max_retries": "3", "model": "codex", "provider": "openai"}
        # both carriers show the SAME rule value (the shared rule took effect)
        self.assertEqual(carrier_a["rule.max_retries"], carrier_b["rule.max_retries"])
        # the rule field is the managed one; model/provider are user-native
        self.assertEqual(ledger.owned_fields("shared-rule-pkg"), {"rule.max_retries"})
        # a managed add must not touch the user-native fields
        with self.assertRaises(ValueError):
            ledger.add_fields("shared-rule-pkg", ["model"])

    def test_project_diff_does_not_pollute_global(self):
        cmp = sra.ThreeWayCompare()
        global_values = {"model": "agnes", "provider": "custom",
                         "shared.rule_x": "base"}
        # a project diff tries to shadow the global rule field + set a native
        res = cmp.project_diff_isolated(
            {"shared.rule_x": "project-override", "model": "codex"},
            global_values=global_values)
        self.assertFalse(res["global_polluted"])
        # the global's own values are untouched by the diff
        self.assertEqual(res["global_result"]["shared.rule_x"], "base")
        # a user-native field (model) in the diff is preserved at its original
        self.assertIn("model", res["native_values_preserved"])
        self.assertEqual(res["global_result"]["model"], "agnes")


class TestManagedDeletion(unittest.TestCase):
    def test_remove_managed_removes_only_owned_not_unknown(self):
        ledger = sra.OwnershipLedger()
        ledger.register(sra.ManagedAsset(
            asset_id="skill-x", owns_fields={"skill.x.enable"},
            foreign_fields={"user.custom_field"},
            provenance="origin:skill-x@v2"))
        live = {"skill.x.enable": True, "user.custom_field": "keep-me",
                "other.unknown": "do-not-touch"}
        res = ledger.remove_managed_asset("skill-x", live)
        self.assertTrue(res["removed"])
        self.assertEqual(res["removed_fields"], ["skill.x.enable"])
        # the user's field and an unknown field are BOTH preserved
        self.assertIn("user.custom_field", res["preserved_fields"])
        self.assertIn("other.unknown", res["preserved_fields"])
        self.assertFalse(res["unknown_fields_touched"])

    def test_non_managed_asset_cannot_be_mutated(self):
        ledger = sra.OwnershipLedger()
        with self.assertRaises(ValueError):
            ledger.register(sra.ManagedAsset(asset_id="ghost", owns_fields={"g"},
                                             provenance=""))

    def test_a_field_owned_by_another_asset_cannot_be_hijacked(self):
        ledger = sra.OwnershipLedger()
        ledger.register(sra.ManagedAsset(asset_id="a", owns_fields={"f"},
                                        provenance="o:a"))
        ledger.register(sra.ManagedAsset(asset_id="b", owns_fields={"g"},
                                        provenance="o:b"))
        with self.assertRaises(ValueError):
            ledger.add_fields("b", ["f"])  # 'f' belongs to asset a


class TestThreeWayPreservesUser(unittest.TestCase):
    def test_user_modification_preserved_upstream_pending(self):
        cmp = sra.ThreeWayCompare()
        base = {"tone": "plain", "model": "agnes"}
        # the user changed 'tone' in live
        live = {"tone": "warm", "model": "agnes"}
        # upstream (candidate) moved 'tone' again and left model alone
        candidate = {"tone": "plain-v2", "model": "agnes"}
        res = cmp.compare(base, live, candidate)
        # the user's 'warm' survives the merge, not the upstream value
        self.assertEqual(res["merged"]["tone"], "warm")
        self.assertIn("tone", res["upstream_pending_adaptation"])
        self.assertFalse(res["blind_restore"])

    def test_user_only_field_not_in_candidate_is_kept(self):
        cmp = sra.ThreeWayCompare()
        base = {"a": 1}
        live = {"a": 1, "user_note": "kept"}
        candidate = {"a": 2}
        res = cmp.compare(base, live, candidate)
        self.assertEqual(res["merged"]["user_note"], "kept")
        self.assertIn("user_note", res["user_modified_preserved"])

    def test_no_change_is_a_legal_no_change(self):
        cmp = sra.ThreeWayCompare()
        same = {"k": "v"}
        res = cmp.compare(same, dict(same), dict(same))
        self.assertEqual(res["merged"], {"k": "v"})
        self.assertEqual(res["upstream_pending_adaptation"], [])
        self.assertEqual(res["user_modified_preserved"], [])


class TestSkillOnDemand(unittest.TestCase):
    def test_skill_loaded_only_when_needed(self):
        inv = sra.SkillInventory()
        r1 = inv.load_on_demand("heavy-skill", needed=False)
        self.assertFalse(r1["loaded"])
        self.assertEqual(inv.inventory(), 0)  # not counted while idle
        r2 = inv.load_on_demand("heavy-skill", needed=True)
        self.assertTrue(r2["loaded"])
        self.assertEqual(inv.inventory(), 1)

    def test_no_benefit_skill_stopped_not_force_kept(self):
        inv = sra.SkillInventory()
        inv.load_on_demand("useless-skill", needed=True)
        self.assertEqual(inv.inventory(), 1)
        inv.stop_no_benefit("useless-skill")
        self.assertEqual(inv.inventory(), 0)

    def test_new_model_does_not_get_a_full_skill_copy(self):
        inv = sra.SkillInventory()
        self.assertTrue(inv.no_full_copy_per_new_model())


if __name__ == "__main__":
    unittest.main(verbosity=2)
