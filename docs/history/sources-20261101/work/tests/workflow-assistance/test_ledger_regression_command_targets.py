"""Gate: the error ledger must state, per record, whether its own proof can still be re-run.

`scripts/audit/ledger_regression_command_targets.py` re-points stale operands and stamps
`regressionTestVerifiability` on every record (213 at the 2026-10-08 count). This gate protects five claims:

1. coverage — no record is left without a label, and the shipped record's counts equal the ledger's own
   distribution (derived from the structure, not from a number I typed);
2. honesty of a re-point — a record may claim REPOINTED_20261007 only when the note claims it *and*
   every file operand in the written command resolves against `git ls-files`;
3. the map is not decorative — every re-point target is tracked and every re-point source is still
   absent, so the substitution moved something real;
4. the matcher knows the difference between a path, a pytest node id, a markdown-wrapped path, a
   directory fragment, a glob, a bare word and a live client home — each falsified with a fixture;
5. a re-publish cannot flatten a record's explanation — the tool writes one measured sentence per label,
   and the tool is re-run whenever a record is added (ERR-216).

Everything here reads tracked state only. The audit that found this class (ERR-142) failed CI because a
verdict answered from local disk, so a gate over a verdict must not do the same thing.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import collections
import importlib.util
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "ledger_regression_command_targets.py"
LEDGER = ROOT / "taskpacks/current/error-ledger.json"
AUDIT = ROOT / "docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json"

spec = importlib.util.spec_from_file_location("lrct", SCRIPT)
lrct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lrct)

INDEX = lrct.build_indexes()


class MatcherBehaviourTests(unittest.TestCase):
    """Each token shape the ledger actually contains, falsified individually."""

    def operands(self, cmd: str) -> list[str]:
        return lrct.operands(cmd)

    def kind(self, token: str) -> str:
        path_set, by_base, prefixes = INDEX
        return lrct.classify(token, path_set, by_base, prefixes)[0]

    def test_a_pytest_node_id_is_one_promise_about_one_file(self) -> None:
        ops = self.operands("python -m pytest tests/workflow-assistance/"
                            "test_recover_shared_root_original.py::UpstreamScannerGapTests::test_x")
        self.assertEqual(ops, ["tests/workflow-assistance/test_recover_shared_root_original.py"])
        self.assertEqual(self.kind(ops[0]), "RESOLVES")

    def test_a_markdown_wrapped_path_is_still_a_path(self) -> None:
        ops = self.operands("see the CI step's own `scripts/ci/generate_current_state.py --check-current`")
        self.assertIn("scripts/ci/generate_current_state.py", ops)
        self.assertEqual(self.kind("scripts/ci/generate_current_state.py"), "RESOLVES")

    def test_a_directory_fragment_is_not_a_lost_file(self) -> None:
        self.assertEqual(self.kind("frontend/src"), "DIR_NOT_FILE")
        self.assertEqual(self.kind("tests"), "DIR_NOT_FILE")

    def test_a_glob_a_bare_word_an_env_assignment_and_a_sentence_period_are_not_operands(self) -> None:
        self.assertEqual(self.operands("python -m unittest discover -s tests -p 'test_*.py'"), [])
        self.assertEqual(self.operands("PYTHONUTF8=1 python x.py").count("PYTHONUTF8=1"), 0)
        self.assertIn("x.py", self.operands("run x.py."))
        self.assertNotIn("run", self.operands("run x.py."))

    def test_a_live_client_home_is_declared_out_of_repo_not_missing(self) -> None:
        for token in (r"C:/Users/admin/.codex/config.toml", "CODEX_HOME/AGENTS.md",
                      "Hermes/config.yaml".replace("Hermes/", "HERMES_HOME/")):
            self.assertEqual(self.kind(token), "EXTERNAL", token)

    def test_a_stale_convergence_path_is_reported_moved_not_resolved(self) -> None:
        kind, cands = lrct.classify("scripts/workflow/verify_core_schemas.py", *INDEX)
        self.assertEqual(kind, "MOVED")
        self.assertEqual(cands, ["packages/client-neutral-core/scripts/verify_core_schemas.py"])

    def test_a_path_that_exists_nowhere_tracked_is_gone(self) -> None:
        self.assertEqual(self.kind("tests/test_observer_dashboard.py"), "GONE")


class LedgerLabelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.errors = cls.data["errors"]
        cls.audit = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_every_record_carries_a_declared_label(self) -> None:
        # the floor is a floor, not a frozen number: the ledger grows as records are added, and a gate
        # that fails on growth teaches nobody anything except to edit the gate
        self.assertGreaterEqual(len(self.errors), 140)
        self.assertEqual(self.audit["records"], len(self.errors),
                         "the audit was published against a different ledger than the one in the tree")
        missing = [e["error_id"] for e in self.errors
                   if str(e.get("regressionTestVerifiability") or "") not in lrct.STATES]
        self.assertEqual(missing, [], f"records without a valid label: {missing[:8]}")

    def test_the_shipped_counts_equal_the_ledger_own_distribution(self) -> None:
        actual = collections.Counter(str(e.get("regressionTestVerifiability")) for e in self.errors)
        self.assertEqual(self.audit["counts"], dict(actual),
                         "the audit's counts were typed or stale rather than derived")
        self.assertEqual(sum(self.audit["counts"].values()), len(self.errors))
        self.assertEqual(self.audit["records"], len(self.errors))

    def test_a_repoint_claim_requires_a_note_and_fully_resolving_operands(self) -> None:
        claimed = [e for e in self.errors
                   if e.get("regressionTestVerifiability") == "REPOINTED_20261007"]
        self.assertGreaterEqual(len(claimed), 25, "the re-point half of the gate would pass vacuously")
        for e in claimed:
            note = str(e.get("regressionRepointNote") or "")
            self.assertTrue(note, f"{e['error_id']} claims a re-point with no note")
            self.assertNotIn("still does not resolve", note,
                             f"{e['error_id']} disclaims its own re-point but keeps the label")
            kinds = [self.kind(op) for op in lrct.operands(str(e.get("regression_test") or ""))]
            # a re-pointed promise must contain no stale operand; a directory fragment or a live client
            # home inside the same sentence is context, not a broken pointer
            self.assertIn("RESOLVES", kinds, f"{e['error_id']}: nothing in the promise resolves")
            stale = [k for k in kinds if k in ("GONE", "MOVED", "AMBIGUOUS")]
            self.assertEqual(stale, [], f"{e['error_id']} claims a re-point but still carries {stale}")

    def kind(self, token: str) -> str:
        path_set, by_base, prefixes = INDEX
        return lrct.classify(token, path_set, by_base, prefixes)[0]

    def test_a_disclaimed_note_never_keeps_a_repoint_label(self) -> None:
        for e in self.errors:
            note = str(e.get("regressionRepointNote") or "")
            if "still does not resolve" in note:
                self.assertNotEqual(e.get("regressionTestVerifiability"), "REPOINTED_20261007",
                                    f"{e['error_id']} says no re-point happened, then claims one")

    def test_the_repoint_map_moves_real_paths(self) -> None:
        path_set = INDEX[0]
        repoint = self.audit["repointMap"]
        self.assertGreaterEqual(len(repoint), 25, "an empty map would make this test decorative")
        for stale, fresh in repoint.items():
            self.assertIn(fresh, path_set, f"{stale} -> {fresh}: the target is not tracked")
            self.assertNotIn(stale, path_set,
                             f"{stale} is still tracked, so re-pointing it was not a move")

    def test_every_hand_adjudication_states_a_reason_and_a_map_target(self) -> None:
        path_set = INDEX[0]
        hand = self.audit["handAdjudicated"]
        self.assertEqual(set(hand), set(lrct.ADJUDICATED), "the record hides or invents an adjudication")
        for eid, adj in hand.items():
            self.assertGreaterEqual(len(str(adj["reason"]).strip()), 60,
                                    f"{eid}: 'it is fine' is not a reason")
            self.assertIn(adj["state"], lrct.STATES, f"{eid} has an undeclared state")
        for eid, mapping in self.audit["handRepointMaps"].items():
            for stale, fresh in mapping.items():
                self.assertIn(fresh, path_set, f"{eid}: hand-chosen {fresh} is not tracked")
                self.assertNotIn(stale, path_set, f"{eid}: {stale} was never stale")

    def test_out_of_repo_labels_point_at_a_live_machine_path(self) -> None:
        for e in [x for x in self.errors
                  if x.get("regressionTestVerifiability") == "OUT_OF_REPO_TARGET"]:
            self.assertTrue(any(lrct.OUT_OF_REPO.match(op) or op.startswith("~")
                                for op in lrct.operands(str(e.get("regression_test") or "")))
                            or e["error_id"] in lrct.ADJUDICATED,
                            f"{e['error_id']} claims out-of-repo without an out-of-repo operand")

    def test_status_after_is_never_rewritten_by_the_labelling(self) -> None:
        allowed = {"NOT_RUN", "FAIL", "UNVERIFIED", "PASS", "PARTIAL", "BLOCKED"}
        leaked = {e["error_id"]: e["status_after"] for e in self.errors
                  if e.get("status_after") not in allowed}
        self.assertEqual(leaked, {}, "a verifiability label leaked into status_after")

    def test_the_path_gone_labels_are_reproducible_negative_claims(self) -> None:
        gone = [e for e in self.errors if e.get("regressionTestVerifiability") == "PATH_GONE"]
        self.assertGreaterEqual(len(gone), 20, "the honest-dirt half of the gate would pass vacuously")
        for e in gone:
            kinds = [self.kind(op) for op in lrct.operands(str(e.get("regression_test") or ""))]
            self.assertTrue("GONE" in kinds or e["error_id"] in lrct.ADJUDICATED,
                            f"{e['error_id']} is labelled PATH_GONE but nothing is gone: {kinds}")


class DeterminismTests(unittest.TestCase):
    def test_measuring_twice_produces_the_same_state_digest(self) -> None:
        first = json.loads(LEDGER.read_text(encoding="utf-8"))
        rows_a, *_ = lrct.measure(first["errors"])
        rows_b, *_ = lrct.measure(json.loads(LEDGER.read_text(encoding="utf-8"))["errors"])
        import hashlib
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))["errors"]
        claims = sorted((e["error_id"], str(e.get("regressionTestVerifiability") or ""))
                        for e in ledger)
        digest = hashlib.sha256(json.dumps(claims, ensure_ascii=False).encode("utf-8")).hexdigest()
        self.assertEqual(json.loads(AUDIT.read_text(encoding="utf-8"))["stateDigest"], digest,
                         "the shipped record's stateDigest does not reproduce from the ledger labels")
        self.assertEqual([r["state"] for r in rows_a], [r["state"] for r in rows_b],
                         "two measurements of the same tree disagreed")


class ReasonPreservationTests(unittest.TestCase):
    """A record's explanation survives a re-publish; only a label that moved gets the measured sentence.

    ERR-216: adding ERR-215 to the ledger and re-running the publisher with `--apply` rewrote three
    hand-authored `regressionTestVerifiabilityReason` strings into the one boilerplate the tool knows how
    to emit. The digest is keyed on (id, label) alone, so nothing downstream noticed -- the loss was
    silent, and the tool is re-run for every new record.
    """

    BOILERPLATE = "every operand resolves against git ls-files"

    def test_an_unchanged_label_keeps_the_sentence_that_explains_it(self) -> None:
        hand = "reads the schema, the catalogue, the code tuple and the module itself; no network"
        self.assertEqual(lrct.next_reason("RESOLVES", hand, "RESOLVES", self.BOILERPLATE), hand)

    def test_a_label_that_moved_loses_the_sentence_about_the_old_state(self) -> None:
        # Falsification: a blanket preserve would keep an explanation of a state the record no longer
        # claims, which is the opposite of the honesty this field exists to provide.
        self.assertEqual(
            lrct.next_reason("PATH_GONE", "no tracked file carries this basename", "RESOLVES", self.BOILERPLATE),
            self.BOILERPLATE,
        )

    def test_a_missing_or_blank_reason_is_filled_from_the_measurement(self) -> None:
        for previous in (None, "", "   "):
            self.assertEqual(lrct.next_reason("RESOLVES", previous, "RESOLVES", self.BOILERPLATE), self.BOILERPLATE,
                             f"reason={previous!r} was not filled")

    def test_the_ledger_really_carries_explanations_that_are_not_boilerplate(self) -> None:
        # Without this, the preservation above could be guarding nothing: measured 2026-10-08, 213 records
        # carry 14 distinct reasons and 11 of them belong to exactly one record.
        errors = json.loads(LEDGER.read_text(encoding="utf-8"))["errors"]
        reasons = [str(e.get("regressionTestVerifiabilityReason") or "") for e in errors]
        counts = collections.Counter(reasons)
        unique = [reason for reason in reasons if counts[reason] == 1 and reason != self.BOILERPLATE]
        self.assertGreaterEqual(
            len(unique), 10,
            f"only {len(unique)} records carry a reason nobody else uses; a re-publish has flattened them",
        )


    def test_the_rule_is_applied_at_the_call_site_not_only_in_the_helper(self) -> None:
        """`next_reason` is correct; the loop that calls it must not overwrite the label first.

        Measured 2026-10-10: a new record's authored label was RESOLVES while the operand set measured
        PATH_GONE, and the record kept the RESOLVES sentence, because the loop wrote the new label into
        the record and only then read it back as the previous state — so the comparison in
        `next_reason` always saw two equal values and the documented replacement never fired.
        """
        scratch = ROOT / ".project-local" / "runs" / "ledger_reason_callsite_probe.json"
        gone = "tests/workflow-assistance/test_a_promise_that_exists_nowhere_9a7c1f.py"
        hand = "reads the schema, the catalogue, the code tuple and the module itself; no network"
        data = {"errors": [
            {"error_id": "ERR-900001", "regression_test": gone,
             "regressionTestVerifiability": "RESOLVES",
             "regressionTestVerifiabilityReason": hand},
            {"error_id": "ERR-900002", "regression_test": gone,
             "regressionTestVerifiability": "PATH_GONE",
             "regressionTestVerifiabilityReason": "hand sentence for a label that has not moved"},
        ]}
        real = lrct.LEDGER
        scratch.parent.mkdir(parents=True, exist_ok=True)
        try:
            lrct.LEDGER = scratch
            scratch.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8", newline="\n")
            written, _applied = lrct.apply_labels({"errors": [dict(row) for row in data["errors"]]})
            rows = {row["error_id"]: row for row in written["errors"]}
            moved = rows["ERR-900001"]
            stayed = rows["ERR-900002"]
            self.assertEqual("PATH_GONE", moved["regressionTestVerifiability"])
            self.assertNotEqual(hand, moved["regressionTestVerifiabilityReason"],
                                "a record whose label moved kept the sentence about the old state")
            self.assertIn("basename", moved["regressionTestVerifiabilityReason"])
            self.assertEqual("hand sentence for a label that has not moved",
                             stayed["regressionTestVerifiabilityReason"],
                             "an unchanged label must not have its explanation flattened")
        finally:
            lrct.LEDGER = real
            scratch.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
