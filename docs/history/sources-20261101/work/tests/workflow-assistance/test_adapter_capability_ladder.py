"""Gate: the seven-layer capability ladder cannot be climbed from the top (P1-03 / F1).

The blueprint's ladder — Registered → Installed → Loaded/Connected → Qualified → Enabled for Task →
Native Projection → Observed in Execution — existed only as prose, so nothing stopped a UI from calling a
manifest entry "installed" or an adapter "native". This gate pins the projection and the validator
together, with the emphasis on the refusal cases, because a card that over-claims is the failure mode.

Sources are the real tracked files (``config/adapter-registry.json`` and
``config/capability-conformance.json``), so the declared half is measured, not asserted. The upper layers
stay NOT_PROBED because the adapter verbs still answer NOT_IMPLEMENTED (AG-06/G06) — that is the current
truth, and these tests fail if anyone promotes it without evidence.

Discovered dynamically by ``run_quality_gate.py governance``.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import adapter_capability_projection as acp  # noqa: E402
import snapshot_validator  # noqa: E402

GENERATED_AT = "2026-10-08T00:00:00Z"


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
    return {
        "schemaVersion": snapshot_validator.SNAPSHOT_SCHEMA_VERSION,
        "revision": 1,
        "generatedAt": GENERATED_AT,
        "projects": [],
        "adapterCapabilities": cards,
    }


class LiveSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry, cls.conformance, cls.matrix = acp.load_inputs(ROOT)

    def cards(self, software_rows=None):
        return acp.project_adapter_capabilities(
            registry=self.registry, conformance=self.conformance, matrix=self.matrix,
            software_rows=software_rows or [], observed_at=GENERATED_AT)

    def test_every_declared_adapter_gets_exactly_the_seven_layers_in_order(self) -> None:
        cards = self.cards()
        self.assertEqual(len(cards), len(self.registry["entries"]),
                         "a declared adapter without a card is a silent gap")
        for card_row in cards:
            with self.subTest(client=card_row["clientId"]):
                self.assertEqual([layer["layer"] for layer in card_row["layers"]], list(acp.LAYER_ORDER))

    def test_the_role_the_operator_declares_reaches_the_card_and_absence_is_unknown(self) -> None:
        cards = {row["clientId"]: row for row in self.cards()}
        # The case that started this: a provider router must be identifiable as one in the payload, or
        # every surface that lists clients has to guess — and it guessed wrong.
        self.assertEqual(cards["cc-switch"]["role"], "provider_router")
        self.assertEqual(cards["hermes"]["role"], "agent_runtime")
        # openhuman declares no role in the matrix, so the projection answers UNKNOWN instead of naming
        # a kind for software this repo cannot cite a source for.
        self.assertEqual(cards["openhuman"]["role"], "UNKNOWN")
        schema = json.loads((ROOT / "packages/contracts/schemas/workflow/snapshot-v3.schema.json")
                            .read_text(encoding="utf-8"))
        allowed = set(schema["properties"]["adapterCapabilities"]["items"]["properties"]["role"]["enum"])
        for client_id, row in cards.items():
            with self.subTest(client=client_id):
                self.assertIn(row["role"], allowed, "a role outside the declared enum breaks the contract")

    def test_only_registration_is_met_without_an_install_probe(self) -> None:
        cards = self.cards()
        for card_row in cards:
            with self.subTest(client=card_row["clientId"]):
                states = {layer["layer"]: layer["state"] for layer in card_row["layers"]}
                self.assertEqual(states["REGISTERED"], "MET")
                self.assertEqual(states["INSTALLED"], "NOT_PROBED",
                                 "INSTALLED must not follow from a registry version string")
                for layer in acp.LAYER_ORDER[2:]:
                    self.assertEqual(states[layer], "NOT_PROBED")
                    self.assertTrue(card_row["layers"][acp.LAYER_ORDER.index(layer)]["reason"].strip())

    def test_the_installed_layer_follows_the_install_identity_enum_not_a_version_string(self) -> None:
        """Each location_status means a different thing; conflating them is how a card lies."""
        verified = self.cards([{"softwareId": "hermes", "locationStatus": "SINGLE_VERIFIED",
                                "installRoot": "C:/synthetic/hermes"}])
        absent = self.cards([{"softwareId": "hermes", "locationStatus": "NOT_INSTALLED",
                              "installRoot": None}])
        drift = self.cards([{"softwareId": "hermes", "locationStatus": "LOCATION_DRIFT",
                             "installRoot": "C:/old/hermes"}])
        unknown = self.cards([{"softwareId": "hermes", "locationStatus": "UNKNOWN",
                               "installRoot": None}])
        missing = self.cards([])

        def installed(rows):
            card_row = next(row for row in rows if row["clientId"] == "hermes")
            return next(layer for layer in card_row["layers"] if layer["layer"] == "INSTALLED")

        verified_layer = installed(verified)
        self.assertEqual(verified_layer["state"], "MET")
        self.assertEqual(verified_layer["evidenceLevel"], "INTEGRATED")
        self.assertIn("SINGLE_VERIFIED", verified_layer["source"])

        absent_layer = installed(absent)
        self.assertEqual(absent_layer["state"], "NOT_SUPPORTED",
                         "a measured absence must not be reported as merely unprobed")
        self.assertEqual(absent_layer["evidenceLevel"], "INTEGRATED")

        for label, layer in (("LOCATION_DRIFT", installed(drift)), ("UNKNOWN", installed(unknown))):
            with self.subTest(status=label):
                self.assertEqual(layer["state"], "NOT_PROBED")
                self.assertIn(label, layer["reason"])

        missing_layer = installed(missing)
        self.assertEqual(missing_layer["state"], "NOT_PROBED")
        self.assertIsNone(missing_layer["source"])

    def test_the_registry_version_is_carried_as_a_readback_with_its_method_not_as_a_verification(self) -> None:
        hermes = next(row for row in self.cards() if row["clientId"] == "hermes")
        self.assertTrue(hermes["declaredVersion"])
        self.assertTrue(hermes["versionReadbackMethod"])
        # a version readback is not a hash check: the registry says UNVERIFIED and the card must repeat it
        self.assertEqual(hermes["detectionEvidenceState"], "UNVERIFIED")

    def test_per_client_governance_facts_come_from_the_capability_matrix(self) -> None:
        cards = {row["clientId"]: row for row in self.cards()}
        # cc-switch is LEGACY_OBSERVE by the project's own scope statement; a card that showed it as an
        # active writer would be a product lie, so the status is carried per client, not averaged.
        self.assertEqual(cards["cc-switch"]["registryStatus"], "legacy_observe")
        self.assertEqual(cards["hermes"]["registryStatus"], "active")
        self.assertEqual(cards["codex"]["registryStatus"], "quarantined")
        self.assertTrue(cards["hermes"]["writePolicy"])
        self.assertEqual(cards["hermes"]["configOwnershipDefault"]["mode"], "MANAGE")
        self.assertTrue(cards["hermes"]["configOwnershipDefault"]["preserve_unknown"])
        # the manifest-only clients carry no write policy and no risk in the matrix; the card says UNKNOWN
        # rather than inventing one, and their status is their own: blocked, not quarantined, not active
        for client_id in ("cursor", "claude-code", "workbuddy"):
            with self.subTest(client=client_id):
                self.assertEqual(cards[client_id]["registryStatus"], "blocked")
                self.assertEqual(cards[client_id]["writePolicy"], "UNKNOWN")
                self.assertEqual(cards[client_id]["risk"], "UNKNOWN")
        for client_id, row in cards.items():
            with self.subTest(client=client_id):
                self.assertIn(row["registryStatus"],
                              ("active", "quarantined", "legacy_observe", "blocked", "NOT_IN_MATRIX"))
                self.assertTrue(str(row["risk"]).strip())

    def test_protocol_conformance_is_attached_as_protocol_not_as_a_client_capability_list(self) -> None:
        cards = self.cards()
        for row in cards:
            self.assertEqual(set(row["protocolConformance"]), set(acp.CONFORMANCE_PROTOCOLS))
        acp_status = {row["protocolConformance"]["acp"] for row in cards}
        declared = {(entry.get("id"), (self.conformance.get("acp") or {}).get("status"))
                    for entry in (self.conformance.get("acp") or {}).get("entries") or []}
        self.assertTrue(acp_status)
        self.assertTrue(declared)
        # every card reports the same protocol verdicts: they belong to the protocol, not to a client
        self.assertTrue(all(row["protocolConformance"]["acp"] in {"STATIC_PASS", "STATIC_UNVERIFIED",
                                                                 "BLOCKED", "ABSENT"} for row in cards))

    def test_registry_and_matrix_verb_sets_are_both_shown_and_drift_is_named(self) -> None:
        for row in self.cards():
            drift_expected = bool(row["matrixOperations"]) and \
                row["declaredOperations"] != row["matrixOperations"]
            self.assertEqual(row["operationsDrift"], drift_expected,
                             f"{row['clientId']}: drift disagrees with the two listed verb sets")
            if drift_expected:
                self.assertNotEqual(row["declaredOperations"], row["matrixOperations"])

    def test_the_projected_snapshot_validates(self) -> None:
        verdict = snapshot_validator.validate_snapshot(snapshot_with(self.cards()))
        self.assertTrue(verdict["valid"], verdict["errors"][:3])

    def test_the_projection_never_promotes_native_status(self) -> None:
        for row in self.cards():
            self.assertEqual(row["nativeStatus"], "NOT_IMPLEMENTED")


    def test_a_live_entry_readback_is_a_fact_of_its_own_and_does_not_climb_the_ladder(self) -> None:
        """`executor_live_probe` proves an executable answered. That is Installed, not a live session."""
        rows, probed_at = acp.load_live_probe(ROOT)
        self.assertTrue(rows, "the tracked probe record should exist and be readable")
        cards = acp.project_adapter_capabilities(
            registry=self.registry, conformance=self.conformance, matrix=self.matrix,
            live_probe_rows=rows, live_probe_at=probed_at, observed_at=GENERATED_AT)
        by_id = {row["clientId"]: row for row in cards}

        hermes = by_id["hermes"]
        installed = next(layer for layer in hermes["layers"] if layer["layer"] == "INSTALLED")
        self.assertEqual(installed["state"], "MET")
        self.assertIn("executor_live_probe", installed["source"])
        self.assertEqual(hermes["entryProbe"]["status"], "LIVE_VERIFIED")
        self.assertEqual(hermes["entryProbe"]["exitCode"], 0)
        self.assertEqual(len(hermes["entryProbe"]["outputDigest"]), 64)
        self.assertFalse(hermes["versionDrift"])
        # the climb stops where the evidence stops
        loaded = next(layer for layer in hermes["layers"] if layer["layer"] == "LOADED_CONNECTED")
        self.assertEqual(loaded["state"], "NOT_PROBED")
        self.assertEqual(hermes["nativeStatus"], "NOT_IMPLEMENTED")

        codex = by_id["codex"]
        self.assertTrue(codex["versionDrift"], "the live answer differs from the claimed version")
        self.assertIn("observed=", str(codex["entryProbe"]["detail"]))
        self.assertIn("claimed=", str(codex["entryProbe"]["detail"]))
        self.assertEqual(next(layer for layer in codex["layers"] if layer["layer"] == "INSTALLED")["state"],
                         "MET", "a version move still proves the executable exists")

        dsh = by_id["deepseek-harness"]
        self.assertEqual(dsh["entryProbe"]["status"], "PROBE_TIMEOUT")
        self.assertFalse(dsh["versionDrift"])
        self.assertEqual(next(layer for layer in dsh["layers"] if layer["layer"] == "INSTALLED")["state"],
                         "NOT_PROBED", "a probe that timed out proves nothing")

    def test_no_card_is_invented_when_the_probe_record_is_absent(self) -> None:
        cards = acp.project_adapter_capabilities(
            registry=self.registry, conformance=self.conformance, matrix=self.matrix,
            live_probe_rows=[], observed_at=GENERATED_AT)
        self.assertTrue(all(row["entryProbe"] is None for row in cards))
        self.assertTrue(all(row["versionDrift"] is False for row in cards))

    def test_no_change_on_the_record_keeps_the_ladder_identical(self) -> None:
        """Guard against the probe quietly becoming a default: without rows nothing may be MET above
        REGISTERED+software identity."""
        without = acp.project_adapter_capabilities(registry=self.registry, conformance=self.conformance,
                                                  matrix=self.matrix, software_rows=[], observed_at=GENERATED_AT)
        states = {row["clientId"]: [layer["state"] for layer in row["layers"]] for row in without}
        self.assertTrue(all(states[client][1] == "NOT_PROBED" for client in states))


class ValidatorRefusalTests(unittest.TestCase):
    def reject(self, cards, fragment):
        verdict = snapshot_validator.validate_snapshot(snapshot_with(cards))
        self.assertFalse(verdict["valid"], f"accepted {json.dumps(cards, ensure_ascii=False)[:300]}")
        self.assertTrue(any(fragment in error for error in verdict["errors"]),
                        f"errors={verdict['errors']} did not name {fragment}")

    def test_a_card_must_name_a_client(self) -> None:
        self.reject([card(clientId="")], "clientId required")

    def test_a_met_layer_without_a_source_is_refused(self) -> None:
        layers = [dict(card()["layers"][0], source=None)]
        self.reject([card(layers=layers)], "claims MET without a named source")

    def test_a_met_layer_with_no_evidence_is_refused(self) -> None:
        layers = [dict(card()["layers"][0], evidenceLevel="NO_EVIDENCE")]
        self.reject([card(layers=layers)], "claims MET with NO_EVIDENCE")

    def test_an_unprobed_layer_must_say_why(self) -> None:
        layers = [dict(card()["layers"][1], reason="   ")]
        self.reject([card(layers=layers)], "must say what is missing")

    def test_evidence_levels_outside_the_fixed_vocabulary_are_refused(self) -> None:
        layers = [dict(card()["layers"][0], evidenceLevel="GOOD_ENOUGH")]
        self.reject([card(layers=layers)], "evidenceLevel must be one of")

    def test_layer_names_must_not_repeat(self) -> None:
        dup = [card()["layers"][0], dict(card()["layers"][0])]
        self.reject([card(layers=dup)], "repeats a layer name")

    def test_claiming_native_verification_without_execution_evidence_is_refused(self) -> None:
        """The anti-promotion rule: the ladder cannot be declared climbed from the top."""
        self.reject([card(nativeStatus="NATIVELY_VERIFIED")], "cannot be climbed from the top")

    def test_native_verification_is_accepted_when_execution_was_observed(self) -> None:
        # A complete ladder: this positive control used to pass with only two layers named
        # (REGISTERED + OBSERVED_IN_EXECUTION) and still validate, which is exactly the hole the
        # monotonicity rule now closes -- an absent lower layer is not a disproved one, it is an
        # unstated one. The assertion's meaning is unchanged: a full, evidenced ladder is accepted.
        order = ["REGISTERED", "INSTALLED", "LOADED_CONNECTED", "QUALIFIED",
                 "ENABLED_FOR_TASK", "NATIVE_PROJECTION", "OBSERVED_IN_EXECUTION"]
        layers = [card()["layers"][0]]
        layers += [{"layer": name, "state": "MET", "evidenceLevel": "REAL",
                    "source": "receipt:run-77 readback ok", "reason": "observed"}
                   for name in order[1:]]
        verdict = snapshot_validator.validate_snapshot(
            snapshot_with([card(layers=layers, nativeStatus="NATIVELY_VERIFIED")]))
        self.assertTrue(verdict["valid"], verdict["errors"])

    def test_a_ladder_climbed_from_the_top_is_refused(self) -> None:
        """OBSERVED_IN_EXECUTION=MET with the layers below it simply absent is not a verified client.

        The validator enforced "no NATIVELY_VERIFIED status without an observed layer" but never that the
        lower rungs hold, so a card listing only the top rung validated clean. Absent is not MET, and
        absent is not NOT_PROBED either -- it is unstated, which is the shape this rule refuses.
        """
        for layers in (
            [{"layer": "OBSERVED_IN_EXECUTION", "state": "MET", "evidenceLevel": "REAL",
              "source": "receipt:run-77", "reason": "observed"}],
            [{"layer": "QUALIFIED", "state": "MET", "evidenceLevel": "INTEGRATED",
              "source": "conformance run", "reason": "ok"}],
        ):
            with self.subTest(top=layers[0]["layer"]):
                verdict = snapshot_validator.validate_snapshot(snapshot_with([card(layers=layers)]))
                self.assertFalse(verdict["valid"])
                self.assertTrue(any("are not MET" in error for error in verdict["errors"]),
                                verdict["errors"])

    def test_a_layer_name_outside_the_ladder_is_refused(self) -> None:
        verdict = snapshot_validator.validate_snapshot(snapshot_with([card(layers=[
            {"layer": "REGISTERED", "state": "MET", "evidenceLevel": "REAL", "source": "registry",
             "reason": "ok"},
            {"layer": "TELEPORTED", "state": "MET", "evidenceLevel": "REAL", "source": "vibes",
             "reason": "ok"},
        ])]))
        self.assertFalse(verdict["valid"])
        self.assertTrue(any("outside the ladder" in error for error in verdict["errors"]),
                        verdict["errors"])

    def test_absent_adapter_capabilities_stay_absent(self) -> None:
        snapshot = {
            "schemaVersion": snapshot_validator.SNAPSHOT_SCHEMA_VERSION,
            "revision": 1, "generatedAt": GENERATED_AT, "projects": [],
        }
        self.assertTrue(snapshot_validator.validate_snapshot(snapshot)["valid"])


class ValidatorVerbRefusalTests(unittest.TestCase):
    """The snapshot gate refuses a malformed verb row independently of the projection that built it.

    A real snapshot reaches ``validate_snapshot`` straight from the read path; the projection validated
    these rows first, but the gate is defence in depth — a hand-edited or differently-produced card with a
    row that reads like proof but names nothing must not pass. The refusals are the same five the probe
    holds itself to, and the verb vocabulary is read from the tracked contract through the projection's own
    discovery helper, never restated here.
    """

    def verb(self, **over):
        row = {"verb": "detect", "state": "MET", "evidenceLevel": "INTEGRATED",
               "source": "read-only version readback: hermes.exe --version", "reason": None,
               "attempted": True}
        row.update(over)
        return row

    def reject(self, rows, fragment):
        card_row = card(verbEvidence=rows)
        verdict = snapshot_validator.validate_snapshot(snapshot_with([card_row]))
        self.assertFalse(verdict["valid"], f"accepted rows: {json.dumps(rows, ensure_ascii=False)}")
        self.assertTrue(any(fragment in error for error in verdict["errors"]),
                        f"errors={verdict['errors']} did not name {fragment!r}")

    def test_a_valid_verb_dimension_validates_clean(self) -> None:
        rows = [self.verb(),
                self.verb(verb="apply", state="NOT_PROBED", evidenceLevel="NO_EVIDENCE", source=None,
                          reason="拒绝尝试：apply 会写入真实用户配置。", attempted=False)]
        verdict = snapshot_validator.validate_snapshot(snapshot_with([card(verbEvidence=rows)]))
        self.assertTrue(verdict["valid"], verdict["errors"])

    def test_an_absent_verb_dimension_is_not_a_verb_error(self) -> None:
        verdict = snapshot_validator.validate_snapshot(snapshot_with([card()]))
        self.assertTrue(verdict["valid"], verdict["errors"])
        self.assertFalse(any("verbEvidence" in error for error in verdict["errors"]))

    def test_a_state_outside_the_verb_vocabulary_is_refused(self) -> None:
        self.reject([self.verb(state="PROBABLY")], "must be MET|NOT_PROBED|NOT_SUPPORTED")

    def test_a_met_verb_without_a_source_is_refused(self) -> None:
        self.reject([self.verb(source=None)], "claims MET without a named source")

    def test_a_not_probed_verb_without_a_reason_is_refused(self) -> None:
        self.reject([self.verb(state="NOT_PROBED", evidenceLevel="NO_EVIDENCE", source=None, reason=None)],
                    "must say why nothing was established")

    def test_a_repeated_verb_inside_one_card_is_refused(self) -> None:
        self.reject([self.verb(), self.verb()], "repeats verb")

    def test_a_verb_outside_the_contract_vocabulary_is_refused(self) -> None:
        # the refusal must come from the contract, not a list copied into the validator
        self.reject([self.verb(verb="teleport")], "not an adapter interface verb")

    def test_an_empty_verb_list_is_refused_rather_than_read_as_declares_nothing(self) -> None:
        card_row = card(verbEvidence=[])
        verdict = snapshot_validator.validate_snapshot(snapshot_with([card_row]))
        self.assertFalse(verdict["valid"])
        self.assertTrue(any("empty list" in error for error in verdict["errors"]), verdict["errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
