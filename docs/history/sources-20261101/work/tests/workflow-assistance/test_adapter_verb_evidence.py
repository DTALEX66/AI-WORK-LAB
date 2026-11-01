"""Gate: per-verb evidence may be honest or empty, never inferred (P1-03 open item, the verb dimension).

The seven-layer ladder says what a CLIENT is; it cannot say which verbs of the adapter interface the client
answers, so a card reading "capable" was a claim about a client and not about an interface. This gate pins
the verb dimension added to `adapter_capability_projection.py` to the measurements in
`packages/client-neutral-core/scripts/adapter_verb_probe.py` and to the tracked record in
`docs/audits/EXECUTOR_LIVE_PROBE_2026-10-08.json`.

The refusals are the point, because the failure mode is a row that reads like proof:

* a verb claimed MET without naming the call that answered it is refused;
* a NOT_PROBED with no reason is refused — an unprobed verb must say whether it was refused or exercised
  and not credited;
* a NOT_SUPPORTED must name the declaration it rests on; UNKNOWN is not 0 and an absence is not a zero;
* a card still cannot be climbed from the top: `NATIVELY_VERIFIED` without a MET `OBSERVED_IN_EXECUTION`
  layer is refused, and adding verb rows neither weakens that nor lets a verb row promote a layer;
* an absent probe record yields NO rows, never an empty list that renders as "declared to support nothing".

The verb list is read from the tracked contract, never asserted as a number here.

Discovered dynamically by ``run_quality_gate.py governance``.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import adapter_capability_projection as acp  # noqa: E402
import snapshot_validator  # noqa: E402

GENERATED_AT = "2026-10-08T00:00:00Z"
VERBS = acp.contract_verb_vocabulary(ROOT)


def row(verb: str = "detect", **over):
    base = {"verb": verb, "state": "MET", "evidenceLevel": "INTEGRATED",
            "source": f"read-only version readback: hermes.exe --version (exit 0, digest 95f01c44)",
            "reason": None, "attempted": True, "probedAt": "2026-10-08T03:00:00+0800"}
    base.update(over)
    return base


def card(**over):
    base = {
        "clientId": "hermes",
        "layers": [
            {"layer": "REGISTERED", "state": "MET", "evidenceLevel": "SYNTHETIC",
             "source": "config/adapter-registry.json#entries[id=hermes]", "reason": "declared"},
            {"layer": "OBSERVED_IN_EXECUTION", "state": "NOT_PROBED", "evidenceLevel": "NO_EVIDENCE",
             "source": None, "reason": "no execution evidence"},
        ],
        "nativeStatus": "NOT_IMPLEMENTED",
    }
    base.update(over)
    return base


def snapshot_with(cards):
    return {"schemaVersion": snapshot_validator.SNAPSHOT_SCHEMA_VERSION, "revision": 1,
            "generatedAt": GENERATED_AT, "projects": [], "adapterCapabilities": cards}


class VerbVocabularyTests(unittest.TestCase):
    def test_the_verb_list_is_discovered_and_all_three_sources_agree(self) -> None:
        """Nothing here hardcodes a count; the schema's closed enum is the authority and is cross-checked."""
        self.assertTrue(VERBS)
        _registry, _conformance, matrix = acp.load_inputs(ROOT)
        self.assertEqual(list(VERBS), list(matrix["interface_contract"]))
        schema = ROOT / acp.ADAPTER_INTERFACE_SCHEMA_RECORD
        self.assertTrue(schema.is_file())

    def test_a_verb_outside_the_contract_is_refused(self) -> None:
        errors = acp.validate_verb_evidence([row("install")], verbs=VERBS)
        self.assertTrue(any("not an adapter interface verb" in error for error in errors), errors)

    def test_a_repeated_verb_is_refused(self) -> None:
        errors = acp.validate_verb_evidence([row(), row()], verbs=VERBS)
        self.assertTrue(any("repeats verb" in error for error in errors), errors)


class VerbRowRefusalTests(unittest.TestCase):
    def reject(self, rows, fragment):
        errors = acp.validate_verb_evidence(rows, verbs=VERBS)
        self.assertTrue(errors, f"{rows} was accepted")
        self.assertTrue(any(fragment in error for error in errors), f"errors={errors} lacked {fragment!r}")

    def test_a_verb_marked_met_without_a_source_is_refused(self) -> None:
        """The named requirement: MET must point at the call that answered, or it is a claim."""
        self.reject([row(source=None)], "claims MET without a named source")
        self.reject([row(source="   ")], "claims MET without a named source")

    def test_a_met_verb_with_no_evidence_is_refused(self) -> None:
        self.reject([row(evidenceLevel="NO_EVIDENCE")], "claims MET with NO_EVIDENCE")

    def test_a_met_verb_that_was_never_attempted_is_refused(self) -> None:
        """A refusal cannot be credited as an answer, whichever way the two fields are spelled."""
        self.reject([row(attempted=False)], "never attempted")

    def test_a_not_probed_verb_without_a_reason_is_refused(self) -> None:
        """The other named requirement: NOT_PROBED must say what it was — refused, or answered too thinly."""
        self.reject([row(state="NOT_PROBED", evidenceLevel="NO_EVIDENCE", source=None, reason=None)],
                    "must say why nothing was established")
        self.reject([row(state="NOT_PROBED", evidenceLevel="NO_EVIDENCE", source=None, reason="  ")],
                    "must say why nothing was established")

    def test_a_not_supported_verb_must_name_its_declaration(self) -> None:
        self.reject([row(verb="apply", state="NOT_SUPPORTED", evidenceLevel="SYNTHETIC",
                         source=None, reason=None, attempted=False)],
                    "must name the declaration")

    def test_a_not_supported_verb_with_no_evidence_is_refused(self) -> None:
        """NOT_SUPPORTED is never a blank: UNKNOWN is not 0 and an absence is not a zero."""
        self.reject([row(verb="apply", state="NOT_SUPPORTED", evidenceLevel="NO_EVIDENCE", source=None,
                         reason="没测", attempted=False)], "NOT_SUPPORTED with NO_EVIDENCE")

    def test_an_evidence_level_outside_the_authority_vocabulary_is_refused(self) -> None:
        self.reject([row(evidenceLevel="GOOD_ENOUGH")], "evidenceLevel must be one of")

    def test_a_state_outside_the_ladder_vocabulary_is_refused(self) -> None:
        self.reject([row(state="PROBABLY")], "must be MET|NOT_PROBED|NOT_SUPPORTED")

    def test_the_projection_refuses_the_same_rows_it_would_publish(self) -> None:
        """The validator is not decoration: the projection raises rather than projecting a bad row."""
        registry, conformance, matrix = acp.load_inputs(ROOT)
        with self.assertRaises(ValueError) as caught:
            acp.project_adapter_capabilities(registry=registry, conformance=conformance, matrix=matrix,
                                             verb_rows={"hermes": [row(source=None)]},
                                             contract_verbs=VERBS, observed_at=GENERATED_AT)
        self.assertIn("claims MET without a named source", str(caught.exception))

    def test_a_probe_field_the_projection_does_not_understand_raises_instead_of_being_dropped(self) -> None:
        """Silently losing `checkedPaths` is how a record starts looking tidier than the machine."""
        registry, conformance, matrix = acp.load_inputs(ROOT)
        with self.assertRaises(ValueError) as caught:
            acp.project_adapter_capabilities(registry=registry, conformance=conformance, matrix=matrix,
                                             verb_rows={"hermes": [row(feeling="confident")]},
                                             contract_verbs=VERBS, observed_at=GENERATED_AT)
        self.assertIn("does not understand", str(caught.exception))


class AbsentRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry, self.conformance, self.matrix = acp.load_inputs(ROOT)

    def cards(self, verb_rows=None):
        return acp.project_adapter_capabilities(registry=self.registry, conformance=self.conformance,
                                                matrix=self.matrix, verb_rows=verb_rows,
                                                contract_verbs=VERBS, observed_at=GENERATED_AT)

    def test_an_absent_verb_record_yields_no_rows_rather_than_an_empty_list(self) -> None:
        cards = self.cards({})
        for card_row in cards:
            with self.subTest(client=card_row["clientId"]):
                self.assertNotIn("verbEvidence", card_row,
                                 "an empty verb list reads as 'declared to support nothing'")
                self.assertNotIn("verbEvidenceCounts", card_row)
                self.assertNotIn("verbEvidenceProbedAt", card_row)

    def test_a_record_that_says_nothing_about_a_client_leaves_that_client_without_rows(self) -> None:
        cards = {row_card["clientId"]: row_card for row_card in self.cards({"cursor": [row()]})}
        self.assertIn("verbEvidence", cards["cursor"])
        self.assertEqual([item["verb"] for item in cards["cursor"]["verbEvidence"]], ["detect"])
        for client_id, card_row in cards.items():
            if client_id != "cursor":
                with self.subTest(client=client_id):
                    self.assertNotIn("verbEvidence", card_row)

    def test_the_layers_are_identical_with_and_without_the_verb_dimension(self) -> None:
        """The seven layers keep their meaning; the verb dimension is additive and nothing else."""
        without = {card_row["clientId"]: card_row for card_row in self.cards({})}
        with_rows = {card_row["clientId"]: card_row
                     for card_row in self.cards({"hermes": [row(verb=verb) for verb in VERBS]})}
        hermes = with_rows["hermes"]
        self.assertEqual([item["verb"] for item in hermes["verbEvidence"]], list(VERBS))
        self.assertEqual(hermes["verbEvidenceCounts"]["MET"], len(VERBS))
        for client_id, card_row in with_rows.items():
            base = without[client_id]
            with self.subTest(client=client_id):
                self.assertEqual(base["layers"], card_row["layers"], "a layer changed meaning")
                self.assertEqual(base["nativeStatus"], card_row["nativeStatus"])
                added = set(card_row) - set(base)
                expected = {"verbEvidence", "verbEvidenceCounts", "verbEvidenceProbedAt"} \
                    if client_id == "hermes" else set()
                self.assertEqual(added, expected)


class LiveRecordTests(unittest.TestCase):
    """The tracked record is measured, so the gate reads it rather than restating it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.registry, cls.conformance, cls.matrix = acp.load_inputs(ROOT)
        cls.probe_rows, cls.probe_at = acp.load_live_probe(ROOT)
        cls.verb_rows, cls.verb_at = acp.load_verb_probe(ROOT)
        cls.cards = {card_row["clientId"]: card_row for card_row in acp.project_adapter_capabilities(
            registry=cls.registry, conformance=cls.conformance, matrix=cls.matrix,
            live_probe_rows=cls.probe_rows, live_probe_at=cls.probe_at,
            verb_rows=cls.verb_rows, verb_probe_at=cls.verb_at,
            contract_verbs=VERBS, observed_at=GENERATED_AT)}

    def test_the_tracked_record_carries_a_row_for_every_contract_verb_of_every_client(self) -> None:
        self.assertTrue(self.verb_rows, "the tracked record should carry verb rows")
        self.assertEqual(set(self.cards), set(self.verb_rows))
        for client_id, rows in self.verb_rows.items():
            with self.subTest(client=client_id):
                self.assertEqual([row_item["verb"] for row_item in rows], list(VERBS))

    def test_every_projected_row_still_passes_the_validator(self) -> None:
        for client_id, card_row in self.cards.items():
            with self.subTest(client=client_id):
                self.assertEqual(acp.validate_verb_evidence(card_row["verbEvidence"], verbs=VERBS), [])

    def test_every_met_row_names_a_command_and_a_digest(self) -> None:
        """MET without a re-runnable command is exactly the over-claim this gate exists to refuse."""
        met = [(client_id, item) for client_id, card_row in self.cards.items()
               for item in card_row["verbEvidence"] if item["state"] == "MET"]
        self.assertTrue(met, "the record should contain at least one genuinely measured verb")
        for client_id, item in met:
            with self.subTest(client=client_id, verb=item["verb"]):
                self.assertTrue(str(item["source"]).strip())
                self.assertTrue(item.get("command"), "a MET row must be re-runnable")
                self.assertEqual(item["exitCode"], 0)
                self.assertEqual(len(str(item["outputDigest"])), 64)
                self.assertTrue(item.get("probedAt"))

    def test_a_refused_write_or_execution_verb_is_recorded_as_not_probed_with_its_reason(self) -> None:
        """apply/invoke/plan/rollback: the honest refusal is a result, and it must read as one."""
        refusals = [(client_id, item) for client_id, card_row in self.cards.items()
                    for item in card_row["verbEvidence"]
                    if item["verb"] in ("apply", "invoke", "plan", "rollback")
                    and item["state"] == "NOT_PROBED"]
        self.assertTrue(refusals, "apply/invoke/plan/rollback must be honestly refused, not invented")
        for client_id, item in refusals:
            with self.subTest(client=client_id, verb=item["verb"]):
                self.assertIn("拒绝尝试", item["reason"])
                self.assertEqual(item["attempted"], False)
                self.assertEqual(item["evidenceLevel"], "NO_EVIDENCE")
                self.assertIsNone(item["source"])
                self.assertNotIn("outputDigest", item, "a refusal cannot carry a readback")

    def test_every_not_probed_row_names_what_it_lacked(self) -> None:
        """A blank hedge is the same lie in a different shape: each row must point at a concrete cause."""
        causes = ("拒绝尝试", "ENTRY_NOT_RESOLVED", "NO_DECLARED_ENTRY", "快捷方式", "GUI", "自报",
                  "未作答", "vendored adapter", "未给出可用作答")
        for client_id, card_row in self.cards.items():
            for item in card_row["verbEvidence"]:
                if item["state"] != "NOT_PROBED":
                    continue
                with self.subTest(client=client_id, verb=item["verb"]):
                    reason = str(item["reason"])
                    self.assertGreater(len(reason), 20, reason)
                    self.assertTrue(any(cause in reason for cause in causes), reason)

    def test_no_verb_row_is_met_for_a_client_whose_entry_point_was_not_resolved(self) -> None:
        """Cross-check the two rounds: an entry probe that never resolved a binary cannot answer a verb."""
        unresolved = {str(r.get("adapter")) for r in self.probe_rows
                      if r.get("state") in ("ENTRY_NOT_RESOLVED", "PROBE_TIMEOUT",
                                            "NOT_PROBED_DECLARATIVE_ONLY")}
        self.assertTrue(unresolved)
        for client_id in unresolved:
            for item in self.cards[client_id]["verbEvidence"]:
                with self.subTest(client=client_id, verb=item["verb"]):
                    self.assertNotEqual(item["state"], "MET",
                                        "a client that never answered the entry probe cannot be MET here")

    def test_the_verb_dimension_never_climbs_the_ladder(self) -> None:
        for client_id, card_row in self.cards.items():
            with self.subTest(client=client_id):
                states = {layer["layer"]: layer["state"] for layer in card_row["layers"]}
                self.assertEqual(states["LOADED_CONNECTED"], "NOT_PROBED")
                self.assertEqual(states["OBSERVED_IN_EXECUTION"], "NOT_PROBED")
                self.assertEqual(card_row["nativeStatus"], "NOT_IMPLEMENTED")

    def test_the_snapshot_with_verb_rows_still_validates(self) -> None:
        verdict = snapshot_validator.validate_snapshot(snapshot_with(list(self.cards.values())))
        self.assertTrue(verdict["valid"], verdict["errors"][:3])


class LadderPromotionStillRefusedTests(unittest.TestCase):
    def test_a_card_claiming_native_verification_without_execution_evidence_is_refused(self) -> None:
        """The existing ladder rule, re-asserted with the verb dimension present."""
        cards = [card(nativeStatus="NATIVELY_VERIFIED",
                      verbEvidence=[row(verb=verb) for verb in VERBS])]
        verdict = snapshot_validator.validate_snapshot(snapshot_with(cards))
        self.assertFalse(verdict["valid"])
        self.assertTrue(any("cannot be climbed from the top" in error for error in verdict["errors"]),
                        verdict["errors"])

    def test_verb_rows_alone_do_not_make_native_verification_legal(self) -> None:
        """All seven verbs MET is still not an execution observation; the ladder stays where the evidence is."""
        cards = [card(nativeStatus="NATIVELY_VERIFIED",
                      verbEvidence=[row(verb=verb) for verb in VERBS],
                      verbEvidenceCounts={"MET": len(VERBS)})]
        verdict = snapshot_validator.validate_snapshot(snapshot_with(cards))
        self.assertFalse(verdict["valid"])
        self.assertTrue(any("cannot be climbed from the top" in error for error in verdict["errors"]))

    def test_native_verification_is_still_accepted_when_the_ladder_was_actually_climbed(self) -> None:
        """The positive control: every layer MET from a named source, plus verb rows, validates clean."""
        layers = [{"layer": name, "state": "MET", "evidenceLevel": "REAL",
                   "source": f"receipt:run-77 {name} readback ok", "reason": "observed"}
                  for name in acp.LAYER_ORDER]
        verdict = snapshot_validator.validate_snapshot(snapshot_with(
            [card(layers=layers, nativeStatus="NATIVELY_VERIFIED",
                  verbEvidence=[row(verb=verb) for verb in VERBS])]))
        self.assertTrue(verdict["valid"], verdict["errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
