# SPDX-License-Identifier: MIT
"""DL-P0-160/161: C2PA-shaped provenance mapping and DeliveryReceipt V2 (E1 structural).

Every assertion here is structural. Nothing in this file signs, embeds, opens a
host or claims an E2+ result; ``test_signing_always_fails_closed`` pins that.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.interop import InteropError  # noqa: E402
from design_lab.interop import delivery_receipt as receipts  # noqa: E402
from design_lab.interop import provenance  # noqa: E402

C2PA_SCHEMA = ROOT / "design-lab/schemas/interop-c2pa-manifest.schema.json"
RECEIPT_SCHEMA = ROOT / "design-lab/schemas/interop-delivery-receipt-v2.schema.json"

A = "sha256:" + "aa" * 32
B = "sha256:" + "bb" * 32
C = "sha256:" + "cc" * 32


def delivery_record(**overrides) -> dict:
    record = {
        "deliverable_id": "dlv-0001",
        "artifact_sha256": A,
        "asset_kind": "raster",
        "producer": {"operation_id": "op-42", "provider_id": "provider-local", "model_id": "m-7"},
        "inputs": [
            {"version_id": "ver-1", "sha256": B, "relationship": "parentOf"},
            {"version_id": "ver-2", "sha256": C, "relationship": "componentOf"},
        ],
        "rights_profile": "all-rights-reserved",
        "actions": [
            {"action": "c2pa.created", "when": "2026-01-02T03:04:05+00:00",
             "software_agent": "DESIGN-LAB/test"},
            {"action": "c2pa.edited", "when": "2026-01-02T03:10:00+00:00"},
        ],
        "created_at": "2026-01-02T03:04:05+00:00",
    }
    record.update(overrides)
    return record


def receipt_delivery(**overrides) -> dict:
    record = {
        "job_id": "job-7",
        "created_at": "2026-01-02T04:00:00+00:00",
        "requirements": [{"req_id": "req-editability", "status": "UNVERIFIED"}],
        "rollback": {"backup_ref": "backup://job-7", "procedure": "restore the prior artifact version"},
        "deliverables": [
            {"deliverable_id": "dlv-0001", "artifact_sha256": A, "byte_size": 4096, "editable": True,
             "provenance_manifest": provenance.build_manifest(delivery_record())},
            {"deliverable_id": "dlv-0002", "artifact_sha256": B, "byte_size": 2048, "editable": False,
             "provenance_sha256": C},
        ],
    }
    record.update(overrides)
    return record


class ProvenanceFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = ROOT / ".project-local/task-runtime/interop-provenance-tests"
        parent.mkdir(parents=True, exist_ok=True)
        cls._temp = tempfile.TemporaryDirectory(dir=parent)
        cls.addClassCleanup(cls._temp.cleanup)
        cls.workdir = Path(cls._temp.name)


class C2PaManifestTest(ProvenanceFixture):
    def test_schema_is_repo_owned_draft_2020_12(self):
        schema = json.loads(C2PA_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"],
                         "https://dtalex66.local/schemas/interop-c2pa-manifest.schema.json")
        self.assertEqual(provenance.C2PA_SPEC_VERSION, "2.4")
        self.assertEqual(provenance.SIGNING_STATUS, "UNSIGNED_STRUCTURAL_ONLY")
        self.assertEqual(provenance.CLAIM_VERSION, "c2pa.claim.v2")
        self.assertEqual(provenance.SIGNATURE_ASSERTION, "c2pa.signature")
        self.assertEqual(schema["properties"]["c2pa_spec_version"]["const"], "2.4")
        self.assertEqual(schema["properties"]["claim_version"]["const"], "c2pa.claim.v2")
        self.assertEqual(schema["properties"]["signature"]["const"], "c2pa.signature")
        self.assertIn("claim_version", schema["required"])
        self.assertIn("signature", schema["required"])

    def test_manifest_carries_the_c2pa_2x_baseline_labels(self):
        manifest = provenance.build_manifest(delivery_record())
        self.assertEqual(manifest["claim_version"], "c2pa.claim.v2")
        self.assertEqual(manifest["signature"], "c2pa.signature")
        self.assertEqual(manifest["c2pa_spec_version"], "2.4")
        # The label is a declaration only: no signature material, no assertion.
        self.assertNotIn("c2pa.signature",
                         [assertion["label"] for assertion in manifest["assertions"]])
        report = provenance.validate_manifest(manifest)
        self.assertEqual(report["claim_version"], "c2pa.claim.v2")
        self.assertEqual(report["signature_assertion"], "c2pa.signature")
        self.assertFalse(report["signed"])

    def test_asset_graph_stays_the_source_of_truth_for_the_projection(self):
        manifest = provenance.build_manifest(delivery_record())
        self.assertEqual(manifest["design_lab"]["projection_of"], provenance.SOURCE_OF_TRUTH)
        self.assertEqual(provenance.SOURCE_OF_TRUTH, "design-lab-asset-graph")
        self.assertEqual(provenance.validate_manifest(manifest)["projection_of"],
                         provenance.SOURCE_OF_TRUTH)
        docstring = provenance.__doc__ or ""
        self.assertIn("source of truth", docstring)
        self.assertIn("projection", docstring)
        self.assertIn("Asset Graph", docstring)
        # The delivery record is an input, never an output: the module only reads it.
        delivery = delivery_record()
        snapshot = json.dumps(delivery, sort_keys=True)
        provenance.build_manifest(delivery)
        self.assertEqual(json.dumps(delivery, sort_keys=True), snapshot)

    def test_manifest_maps_inputs_to_one_ingredient_each(self):
        manifest = provenance.build_manifest(delivery_record())
        labels = [assertion["label"] for assertion in manifest["assertions"]]
        self.assertEqual(labels, ["c2pa.actions", "c2pa.ingredient", "c2pa.ingredient",
                                  "c2pa.creative-work", "c2pa.training-mining"])
        ingredients = [assertion["data"] for assertion in manifest["assertions"]
                       if assertion["label"] == "c2pa.ingredient"]
        self.assertEqual([item["instanceID"] for item in ingredients], ["ver-1", "ver-2"])
        self.assertEqual([item["relationship"] for item in ingredients],
                         ["parentOf", "componentOf"])
        self.assertEqual(ingredients[0]["sha256"], B)
        self.assertEqual(manifest["title"], "dlv-0001")
        self.assertEqual(manifest["format"], "raster")
        self.assertEqual(manifest["design_lab"]["input_count"], 2)

    def test_actions_are_mapped_with_a_software_agent_default(self):
        manifest = provenance.build_manifest(delivery_record())
        actions = manifest["assertions"][0]["data"]["actions"]
        self.assertEqual([action["action"] for action in actions], ["c2pa.created", "c2pa.edited"])
        self.assertEqual(actions[0]["softwareAgent"], "DESIGN-LAB/test")
        self.assertEqual(actions[1]["softwareAgent"], provenance.CLAIM_GENERATOR)

    def test_rights_profile_drives_creative_work_and_training_assertions(self):
        for profile, training_use in (("all-rights-reserved", "notAllowed"),
                                      ("open-license", "allowed"),
                                      ("attribution-required", "notAllowed"),
                                      ("internal-review-only", "notAllowed")):
            with self.subTest(profile):
                manifest = provenance.build_manifest(delivery_record(rights_profile=profile))
                labels = [assertion["label"] for assertion in manifest["assertions"]]
                self.assertIn("c2pa.creative-work", labels)
                self.assertIn("c2pa.training-mining", labels)
                entries = next(assertion["data"]["entries"] for assertion in manifest["assertions"]
                               if assertion["label"] == "c2pa.training-mining")
                self.assertEqual(len(entries), len(provenance.TRAINING_ENTRIES))
                self.assertTrue(all(payload["use"] == training_use for payload in entries.values()))

        silent = provenance.build_manifest(delivery_record(rights_profile="no-rights-declared"))
        labels = [assertion["label"] for assertion in silent["assertions"]]
        self.assertNotIn("c2pa.creative-work", labels)
        self.assertNotIn("c2pa.training-mining", labels)

    def test_explicit_rights_mapping_carries_author_and_copyright(self):
        manifest = provenance.build_manifest(delivery_record(rights_profile={
            "profile": "client-contract-2026",
            "creative_work": True,
            "copyright": "(c) 2026 Example Studio",
            "author": {"name": "Example Studio", "@type": "Organization"},
            "training": {"c2pa.ai_training": "constrained"},
        }))
        creative = next(assertion["data"] for assertion in manifest["assertions"]
                        if assertion["label"] == "c2pa.creative-work")
        self.assertEqual(creative["copyright"], "(c) 2026 Example Studio")
        self.assertEqual(creative["author"], [{"@type": "Organization", "name": "Example Studio"}])
        entries = next(assertion["data"]["entries"] for assertion in manifest["assertions"]
                       if assertion["label"] == "c2pa.training-mining")
        self.assertEqual(entries, {"c2pa.ai_training": {"use": "constrained"}})
        self.assertEqual(manifest["design_lab"]["rights_profile"], "client-contract-2026")

    def test_manifest_is_deterministic(self):
        first = provenance.build_manifest(delivery_record())
        second = provenance.build_manifest(delivery_record())
        self.assertEqual(first, second)
        self.assertEqual(provenance.manifest_digest(first), provenance.manifest_digest(second))

    def test_digest_is_order_independent(self):
        manifest = provenance.build_manifest(delivery_record())
        reordered = dict(reversed(list(manifest.items())))
        self.assertEqual(provenance.manifest_digest(manifest), provenance.manifest_digest(reordered))

    def test_validation_reports_ingredient_coverage(self):
        manifest = provenance.build_manifest(delivery_record())
        report = provenance.validate_manifest(manifest, expected_inputs=delivery_record()["inputs"])
        self.assertFalse(report["signed"])
        self.assertEqual(report["signing_status"], provenance.SIGNING_STATUS)
        self.assertEqual(report["ingredient_count"], 2)
        self.assertEqual(report["ingredient_versions"], ["ver-1", "ver-2"])
        self.assertEqual(report["creative_work_assertions"], 1)
        self.assertEqual(report["training_entries"], 4)
        self.assertEqual(report["manifest_sha256"], provenance.manifest_digest(manifest))

    def test_missing_or_extra_ingredients_fail_closed(self):
        manifest = provenance.build_manifest(delivery_record())
        with self.assertRaises(InteropError) as caught:
            provenance.validate_manifest(manifest, expected_inputs=["ver-1"])
        self.assertIn("unexpected: ['ver-2']", str(caught.exception))
        with self.assertRaises(InteropError) as caught:
            provenance.validate_manifest(manifest, expected_inputs=["ver-1", "ver-2", "ver-3"])
        self.assertIn("missing: ['ver-3']", str(caught.exception))

    def test_duplicate_ingredient_for_one_version_fails_closed(self):
        manifest = provenance.build_manifest(delivery_record())
        manifest["assertions"].append(json.loads(json.dumps(manifest["assertions"][1])))
        with self.assertRaises(InteropError) as caught:
            provenance.validate_manifest(manifest)
        self.assertIn("more than one ingredient assertion", str(caught.exception))

    def test_delivery_inputs_are_validated(self):
        cases = {
            "duplicate version": {"inputs": [
                {"version_id": "ver-1", "sha256": B, "relationship": "parentOf"},
                {"version_id": "ver-1", "sha256": C, "relationship": "inputTo"}]},
            "bad relationship": {"inputs": [
                {"version_id": "ver-1", "sha256": B, "relationship": "derivedFrom"}]},
            "zero digest": {"inputs": [
                {"version_id": "ver-1", "sha256": "sha256:" + "0" * 64,
                 "relationship": "inputTo"}]},
            "empty actions": {"actions": []},
            "bad action": {"actions": [{"action": "c2pa.published", "when": "2026-01-02T00:00:00+00:00"}]},
            "naive timestamp": {"actions": [{"action": "c2pa.created", "when": "yesterday"}]},
            "unknown rights profile": {"rights_profile": "whatever"},
            "rights without a decision": {"rights_profile": {"profile": "x"}},
            "missing producer": {"producer": {"operation_id": "op"}},
        }
        for label, override in cases.items():
            with self.subTest(label):
                with self.assertRaises(InteropError):
                    provenance.build_manifest(delivery_record(**override))

    def test_manifest_validation_rejects_tampering(self):
        manifest = provenance.build_manifest(delivery_record())
        broken = json.loads(json.dumps(manifest))
        broken["assertions"][0]["data"]["actions"][0]["action"] = "c2pa.published"
        with self.assertRaises(InteropError) as caught:
            provenance.validate_manifest(broken)
        self.assertIn("c2pa.published", str(caught.exception))

        broken = json.loads(json.dumps(manifest))
        broken["assertions"][1]["data"]["sha256"] = "sha256:" + "0" * 64
        with self.assertRaises(InteropError):
            provenance.validate_manifest(broken)

        broken = json.loads(json.dumps(manifest))
        broken["assertions"][1]["data"]["relationship"] = "derivedFrom"
        with self.assertRaises(InteropError) as caught:
            provenance.validate_manifest(broken)
        self.assertIn("relationship", str(caught.exception))

    def test_signing_always_fails_closed(self):
        manifest = provenance.build_manifest(delivery_record())
        with self.assertRaises(InteropError) as caught:
            provenance.sign(manifest)
        message = str(caught.exception)
        for fragment in ("c2pa / c2patool", "certificate chain", "private key",
                         provenance.SIGNING_STATUS):
            self.assertIn(fragment, message)

    def test_unsigned_guard_rejects_any_signing_claim(self):
        manifest = provenance.build_manifest(delivery_record())
        self.assertIs(provenance.assert_not_a_signed_asset(manifest), manifest)
        for broken in ({"signing_status": "SIGNED"},
                       {"signing_status": None},
                       {"signature": {"alg": "ES256"}},
                       {"signature": "signed-by-release-pipeline"},
                       {"signature_info": {"issuer": "x"}},
                       {"claim_signature": "..."},
                       {"x5chain": ["..."]}):
            with self.subTest(broken):
                tampered = {**json.loads(json.dumps(manifest)), **broken}
                with self.assertRaises(InteropError):
                    provenance.assert_not_a_signed_asset(tampered)

        # A real c2pa.signature assertion would be the signature block of a signed
        # manifest, so it fails closed too.
        signed = json.loads(json.dumps(manifest))
        signed["assertions"].append({"label": "c2pa.signature",
                                     "data": {"alg": "ES256", "x5chain": ["..."]}})
        with self.assertRaises(InteropError) as caught:
            provenance.assert_not_a_signed_asset(signed)
        self.assertIn("c2pa.signature", str(caught.exception))
        with self.assertRaises(InteropError):
            provenance.validate_manifest(signed)


class ReceiptTest(ProvenanceFixture):
    def test_schema_is_repo_owned_draft_2020_12(self):
        schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"],
                         "https://dtalex66.local/schemas/interop-delivery-receipt-v2.schema.json")
        self.assertEqual(receipts.SCHEMA_VERSION, "design-lab/delivery-receipt/v2")

    def test_receipt_records_digests_not_the_provenance_structure(self):
        receipt = receipts.build_receipt(receipt_delivery())
        first, second = receipt["deliverables"]
        self.assertEqual([entry["deliverable_id"] for entry in receipt["deliverables"]],
                         ["dlv-0001", "dlv-0002"])
        self.assertEqual(first["provenance"],
                         provenance.manifest_digest(provenance.build_manifest(delivery_record())))
        self.assertEqual(second["provenance"], C)
        self.assertNotIn("assertions", json.dumps(receipt))
        self.assertEqual(first["byte_size"], 4096)
        self.assertTrue(first["editable"])
        self.assertFalse(second["editable"])
        self.assertEqual(first["rollback"]["backup_ref"], "backup://job-7")
        self.assertEqual(first["requirements"], [{"req_id": "req-editability", "status": "UNVERIFIED"}])

    def test_receipt_without_readback_is_partial(self):
        receipt = receipts.build_receipt(receipt_delivery())
        self.assertEqual(receipt["axes"], {"delivery": "PARTIAL"})
        self.assertIsNone(receipt["deliverables"][0]["host_readback"])
        self.assertIsNone(receipt["deliverables"][0]["readback_matches_artifact"])
        report = receipts.verify_receipt(receipt)
        self.assertTrue(report["verified"])
        self.assertEqual(report["readback_count"], 0)
        claims = "\n".join(report["unsupported_claims"])
        self.assertIn("no host readback was recorded", claims)
        self.assertIn(provenance.SIGNING_STATUS, claims)

    def test_full_readback_raises_the_delivery_axis(self):
        readback = {
            "dlv-0001": {"host_id": "photoshop", "host_version": "26.0",
                         "readback_sha256": A, "opened_at": "2026-01-02T05:00:00+00:00"},
            "dlv-0002": {"host_id": "illustrator", "host_version": "29.0",
                         "readback_sha256": C, "opened_at": "2026-01-02T05:05:00+00:00"},
        }
        receipt = receipts.build_receipt(receipt_delivery(), host_readback=readback)
        self.assertEqual(receipt["axes"], {"delivery": "PASS"})
        self.assertTrue(receipt["deliverables"][0]["readback_matches_artifact"])
        self.assertFalse(receipt["deliverables"][1]["readback_matches_artifact"])
        self.assertEqual(receipt["deliverables"][0]["host_readback"]["host_id"], "photoshop")
        claims = "\n".join(receipts.unsupported_claims(receipt))
        self.assertIn("differs from the artifact digest", claims)

    def test_partial_readback_and_failing_requirement_stay_partial(self):
        partial = receipts.build_receipt(receipt_delivery(), host_readback=[
            {"deliverable_id": "dlv-0001", "host_id": "photoshop", "host_version": "26.0",
             "readback_sha256": A, "opened_at": "2026-01-02T05:00:00+00:00"}])
        self.assertEqual(partial["axes"], {"delivery": "PARTIAL"})

        failing = receipt_delivery()
        failing["requirements"] = [{"req_id": "req-editability", "status": "FAIL"}]
        full_readback = {
            "dlv-0001": {"host_id": "photoshop", "host_version": "26.0", "readback_sha256": A,
                         "opened_at": "2026-01-02T05:00:00+00:00"},
            "dlv-0002": {"host_id": "illustrator", "host_version": "29.0", "readback_sha256": C,
                         "opened_at": "2026-01-02T05:05:00+00:00"},
        }
        receipt = receipts.build_receipt(failing, host_readback=full_readback)
        self.assertEqual(receipt["axes"], {"delivery": "PARTIAL"})
        self.assertIn("req-editability", "\n".join(receipts.unsupported_claims(receipt)))

    def test_receipt_build_fails_closed_on_missing_evidence(self):
        cases = {
            "unknown readback deliverable": {"host_readback": {
                "dlv-9999": {"host_id": "x", "host_version": "1", "readback_sha256": A,
                             "opened_at": "2026-01-02T05:00:00+00:00"}}},
            "no provenance": {"delivery": {"deliverables": [
                {"deliverable_id": "d", "artifact_sha256": A, "byte_size": 1, "editable": True}]}},
            "both provenance forms": {"delivery": {"deliverables": [
                {"deliverable_id": "d", "artifact_sha256": A, "byte_size": 1, "editable": True,
                 "provenance_sha256": B}]}},
            "unknown requirement status": {"delivery": {"requirements": [{"req_id": "r", "status": "MAYBE"}]}},
            "no requirements": {"delivery": {"requirements": None}},
            "no rollback": {"delivery": {"rollback": None}},
            "zero digest": {"delivery": {"deliverables": [
                {"deliverable_id": "d", "artifact_sha256": "sha256:" + "0" * 64, "byte_size": 1,
                 "editable": True, "provenance_sha256": B}]}},
        }
        for label, kwargs in cases.items():
            with self.subTest(label):
                delivery = receipt_delivery()
                if label == "both provenance forms":
                    delivery["deliverables"][1]["provenance_manifest"] = provenance.build_manifest(
                        delivery_record(deliverable_id="dlv-0002"))
                if label == "unknown requirement status":
                    delivery["requirements"] = [{"req_id": "r", "status": "MAYBE"}]
                if label == "no requirements":
                    delivery["requirements"] = None
                    for entry in delivery["deliverables"]:
                        entry.pop("requirements", None)
                if label == "no rollback":
                    delivery["rollback"] = None
                    for entry in delivery["deliverables"]:
                        entry.pop("rollback", None)
                if label in ("no provenance", "zero digest"):
                    delivery = {"job_id": "job-7", **kwargs["delivery"]}
                with self.assertRaises(InteropError):
                    receipts.build_receipt(delivery, host_readback=kwargs.get("host_readback"))

    def test_receipt_is_deterministic_and_clock_free(self):
        first = receipts.build_receipt(receipt_delivery())
        second = receipts.build_receipt(receipt_delivery())
        self.assertEqual(first, second)
        self.assertEqual(first["receipt_id"], second["receipt_id"])
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        without_time = receipt_delivery()
        del without_time["created_at"]
        self.assertNotIn("created_at", receipts.build_receipt(without_time))

    def test_dumps_loads_reproduce_the_same_hash(self):
        receipt = receipts.build_receipt(receipt_delivery())
        text = receipts.dumps(receipt)
        target = self.workdir / "receipt.json"
        target.write_text(text, encoding="utf-8")
        reloaded = receipts.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(reloaded, receipt)
        self.assertEqual(receipts.receipt_sha256(reloaded), receipt["receipt_sha256"])
        self.assertEqual(receipts.dumps(reloaded), text)

    def test_loads_rejects_non_canonical_text(self):
        receipt = receipts.build_receipt(receipt_delivery())
        pretty = json.dumps(receipt, indent=2)
        with self.assertRaises(InteropError) as caught:
            receipts.loads(pretty)
        self.assertIn("canonical form", str(caught.exception))

    def test_verify_rejects_a_receipt_claiming_more_than_its_evidence(self):
        receipt = receipts.build_receipt(receipt_delivery())
        overclaim = {**receipt, "axes": {"delivery": "PASS"}}
        overclaim = receipts.rebuild_identity(overclaim)
        self.assertEqual(overclaim["axes"], {"delivery": "PASS"})
        self.assertNotEqual(overclaim["receipt_id"], receipt["receipt_id"])
        with self.assertRaises(InteropError) as caught:
            receipts.verify_receipt(overclaim)
        self.assertIn("must not claim PASS", str(caught.exception))

    def test_verify_rejects_tampering_and_bad_digests(self):
        receipt = receipts.build_receipt(receipt_delivery())
        tampered = json.loads(json.dumps(receipt))
        tampered["deliverables"][0]["byte_size"] = 8192
        with self.assertRaises(InteropError) as caught:
            receipts.verify_receipt(tampered)
        self.assertIn("does not match the canonical body", str(caught.exception))

        zeroed = json.loads(json.dumps(receipt))
        zeroed["deliverables"][0]["artifact_sha256"] = "sha256:" + "0" * 64
        zeroed = receipts.rebuild_identity(zeroed)
        with self.assertRaises(InteropError) as caught:
            receipts.verify_receipt(zeroed)
        self.assertIn("nonzero SHA-256", str(caught.exception))

        unknown = json.loads(json.dumps(receipt))
        unknown["extra"] = "field"
        with self.assertRaises(InteropError) as caught:
            receipts.verify_receipt(unknown)
        self.assertIn("interop-delivery-receipt-v2.schema.json", str(caught.exception))

    def test_unsupported_claims_never_claim_a_host_result(self):
        receipt = receipts.build_receipt(receipt_delivery())
        claims = receipts.unsupported_claims(receipt)
        self.assertTrue(claims)
        self.assertTrue(all(isinstance(claim, str) and claim for claim in claims))
        joined = " ".join(claims)
        self.assertIn("no E2+ host/runtime result", joined)
        self.assertIn("not independently verified", joined)


if __name__ == "__main__":
    unittest.main(verbosity=2)
