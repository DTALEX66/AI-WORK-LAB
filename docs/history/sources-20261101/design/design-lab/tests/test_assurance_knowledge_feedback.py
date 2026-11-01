# SPDX-License-Identifier: MIT
"""DL-P1-180 knowledge feedback candidate: rights, human approval, export, revocation."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import jsonschema  # noqa: E402

from design_lab.assurance import AssuranceError  # noqa: E402
from design_lab.assurance import knowledge_feedback as kf  # noqa: E402

SHA = "sha256:" + "e" * 64
ZERO = "sha256:" + "0" * 64
DESIGN_LAB_SHA = "9f34b53e7eff5707e087c35bced57bb17b856ab8"
REVIEWED_AT = "2026-09-12T10:00:00Z"


def source(**overrides):
    base = {
        "design_lab_sha": DESIGN_LAB_SHA,
        "job_id": "job-1",
        "operation_id": "op-1",
        "evidence_sha256": SHA,
    }
    base.update(overrides)
    return base


def rights(**overrides):
    base = {
        "license_id": "MIT",
        "rights_gate_state": "CHECKED",
        "contains_client_asset": False,
        "contains_third_party_asset": False,
        "redaction_note": None,
    }
    base.update(overrides)
    return base


def payload(**overrides):
    base = {
        "title": "Lock every colour to a named token before layout",
        "statement": "Layout was reworked twice because raw hex values were introduced mid-file.",
        "applies_to": ["brand", "layout"],
        "steps": ["collect the palette into tokens", "reject any new literal colour"],
    }
    base.update(overrides)
    return base


def build(**overrides):
    arguments = {
        "candidate_id": "kb-1",
        "candidate_type": "METHOD",
        "source": source(),
        "rights": rights(),
        "payload": payload(),
    }
    arguments.update(overrides)
    return kf.build_candidate(**arguments)


def approved(*, note=None, **overrides):
    return kf.approve(
        build(**overrides),
        reviewer_id="dtalex66",
        reviewer_kind="human",
        reviewed_at=REVIEWED_AT,
        note=note,
    )


class KnowledgeCandidateBuildTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".project-local/task-runtime/assurance-knowledge-tests"
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)

    def test_build_can_only_produce_a_pending_candidate(self):
        document = build()
        self.assertEqual("PENDING_HUMAN_APPROVAL", document["review"]["state"])
        self.assertIsNone(document["review"]["reviewer_id"])
        self.assertIsNone(document["review"]["reviewer_kind"])
        self.assertIsNone(document["review"]["reviewed_at"])
        self.assertEqual(kf.DEFAULT_REVOCATION_ENTRYPOINT, document["revocation"]["entrypoint"])
        self.assertTrue(document["revocation"]["revocable"])
        self.assertEqual("ACTIVE", document["revocation"]["state"])
        self.assertEqual(kf.request_hash(payload()), document["payload_sha256"])
        jsonschema.validate(instance=document, schema=kf.schema())
        path = self.tmp / "candidate.json"
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        self.assertEqual(document, json.loads(path.read_text(encoding="utf-8")))

    def test_there_is_no_argument_that_can_pre_approve_a_candidate(self):
        with self.assertRaises(TypeError):
            kf.build_candidate(
                candidate_id="kb-1", candidate_type="METHOD", source=source(),
                rights=rights(), payload=payload(),
                review={"state": "APPROVED", "reviewer_id": "agent"},
            )

    def test_every_candidate_type_builds(self):
        for candidate_type in kf.CANDIDATE_TYPES:
            document = build(candidate_type=candidate_type)
            self.assertEqual(candidate_type, document["candidate_type"])
            self.assertEqual("PENDING_HUMAN_APPROVAL", document["review"]["state"])

    def test_build_refuses_unverifiable_provenance(self):
        with self.assertRaises(AssuranceError) as caught:
            build(source=source(evidence_sha256=ZERO))
        self.assertIn("nonzero", str(caught.exception))
        with self.assertRaises(AssuranceError):
            build(source=source(evidence_sha256="sha256:short"))
        with self.assertRaises(AssuranceError):
            build(source=source(design_lab_sha="0" * 40))
        with self.assertRaises(AssuranceError):
            build(source=source(design_lab_sha="not-a-revision"))
        with self.assertRaises(AssuranceError):
            build(source=source(job_id="  "))
        with self.assertRaises(AssuranceError):
            build(candidate_type="TUTORIAL")

    def test_client_material_requires_a_redaction_note(self):
        with self.assertRaises(AssuranceError) as caught:
            build(rights=rights(contains_client_asset=True))
        self.assertIn("redaction_note", str(caught.exception))
        with self.assertRaises(AssuranceError):
            build(rights=rights(contains_client_asset=True, redaction_note="   "))
        redacted = build(rights=rights(
            contains_client_asset=True,
            redaction_note="client logo and the 12 referenced assets were replaced by neutral shapes",
        ))
        self.assertTrue(redacted["rights"]["contains_client_asset"])

    def test_private_material_is_refused_at_build_time(self):
        with self.assertRaises(AssuranceError) as caught:
            build(payload=payload(client_brief="the client asked for a bolder hero"))
        self.assertIn("must not leave this project", str(caught.exception))
        with self.assertRaises(AssuranceError):
            build(payload=payload(statement="see D:\\clients\\acme\\brief.docx"))
        with self.assertRaises(AssuranceError):
            build(payload=payload(statement="contact the brand lead at lead@acme.example"))
        with self.assertRaises(AssuranceError):
            build(payload=payload(applies_to=[]))

    def test_supersedes_chain_cannot_self_reference(self):
        self.assertEqual("kb-0", build(supersedes="kb-0")["supersedes"])
        with self.assertRaises(AssuranceError):
            build(supersedes="kb-1")

    def test_schema_closes_the_payload_and_the_root(self):
        validator = jsonschema.Draft202012Validator(kf.schema())
        widened = build()
        widened["payload"]["raw_transcript"] = ["user: make it pop"]
        self.assertTrue(list(validator.iter_errors(widened)))
        widened_root = build()
        widened_root["client_brief"] = {"text": "secret"}
        self.assertTrue(list(validator.iter_errors(widened_root)))


class KnowledgeApprovalTests(unittest.TestCase):
    def test_only_a_named_human_can_approve(self):
        for kind in ("agent", "model", "AGENT", "system", "", None):
            with self.assertRaises(AssuranceError) as caught:
                kf.approve(build(), reviewer_id="agent-1", reviewer_kind=kind,
                           reviewed_at=REVIEWED_AT)
            self.assertIn("an agent cannot approve an export to ArcheAxis",
                          str(caught.exception))
        with self.assertRaises(AssuranceError):
            kf.approve(build(), reviewer_id="  ", reviewer_kind="human", reviewed_at=REVIEWED_AT)
        with self.assertRaises(AssuranceError):
            kf.approve(build(), reviewer_id="dtalex66", reviewer_kind="human",
                       reviewed_at="2026-09-12")

    def test_the_schema_cannot_represent_an_agent_approval(self):
        validator = jsonschema.Draft202012Validator(kf.schema())
        forged = build()
        forged["review"] = {
            "state": "APPROVED",
            "reviewer_id": "design-lab/agent",
            "reviewer_kind": "agent",
            "reviewed_at": REVIEWED_AT,
            "note": "looks good to me",
        }
        self.assertTrue(list(validator.iter_errors(forged)),
                        "an agent-signed approval must be structurally unrepresentable")
        unsigned = build()
        unsigned["review"] = {
            "state": "APPROVED", "reviewer_id": None, "reviewer_kind": None,
            "reviewed_at": None, "note": None,
        }
        self.assertTrue(list(validator.iter_errors(unsigned)))

    def test_approval_refuses_an_unchecked_rights_gate(self):
        for state in ("UNCHECKED", "BLOCKED"):
            with self.assertRaises(AssuranceError) as caught:
                kf.approve(build(rights=rights(rights_gate_state=state)),
                           reviewer_id="dtalex66", reviewer_kind="human",
                           reviewed_at=REVIEWED_AT)
            self.assertIn("only CHECKED may be reviewed", str(caught.exception))

    def test_approval_refuses_an_unredacted_client_asset(self):
        forged = build()
        forged["rights"]["contains_client_asset"] = True
        with self.assertRaises(AssuranceError):
            kf.approve(forged, reviewer_id="dtalex66", reviewer_kind="human",
                       reviewed_at=REVIEWED_AT)

    def test_approval_refuses_unverifiable_digests(self):
        forged = build()
        forged["payload_sha256"] = ZERO
        with self.assertRaises(AssuranceError) as caught:
            kf.approve(forged, reviewer_id="dtalex66", reviewer_kind="human",
                       reviewed_at=REVIEWED_AT)
        self.assertIn("payload_sha256", str(caught.exception))
        forged_evidence = build()
        forged_evidence["source"]["evidence_sha256"] = "sha256:" + "0" * 64
        with self.assertRaises(AssuranceError):
            kf.approve(forged_evidence, reviewer_id="dtalex66", reviewer_kind="human",
                       reviewed_at=REVIEWED_AT)

    def test_a_human_approval_is_recorded_without_mutating_the_candidate(self):
        candidate = build()
        document = kf.approve(candidate, reviewer_id="dtalex66", reviewer_kind="human",
                              reviewed_at=REVIEWED_AT, note="rights checked by hand")
        self.assertEqual("APPROVED", document["review"]["state"])
        self.assertEqual("human", document["review"]["reviewer_kind"])
        self.assertEqual(REVIEWED_AT, document["review"]["reviewed_at"])
        self.assertEqual("PENDING_HUMAN_APPROVAL", candidate["review"]["state"])
        jsonschema.validate(instance=document, schema=kf.schema())

    def test_a_decision_is_not_resigned(self):
        document = approved()
        with self.assertRaises(AssuranceError) as caught:
            kf.approve(document, reviewer_id="dtalex66", reviewer_kind="human",
                       reviewed_at=REVIEWED_AT)
        self.assertIn("already APPROVED", str(caught.exception))

    def test_a_human_rejection_is_also_a_human_decision(self):
        with self.assertRaises(AssuranceError) as caught:
            kf.reject(build(), reviewer_id="agent-1", reviewer_kind="agent",
                      reviewed_at=REVIEWED_AT, reason="not useful")
        self.assertIn("an agent cannot approve an export to ArcheAxis", str(caught.exception))
        document = kf.reject(build(), reviewer_id="dtalex66", reviewer_kind="human",
                             reviewed_at=REVIEWED_AT, reason="restates an existing method card")
        self.assertEqual("REJECTED", document["review"]["state"])
        with self.assertRaises(AssuranceError) as caught:
            kf.approve(document, reviewer_id="dtalex66", reviewer_kind="human",
                       reviewed_at=REVIEWED_AT)
        self.assertIn("was already REJECTED", str(caught.exception))


class KnowledgeExportTests(unittest.TestCase):
    def test_only_an_human_approved_candidate_is_exported(self):
        with self.assertRaises(AssuranceError) as caught:
            kf.export_payload(build())
        self.assertIn("only a candidate approved by a named human", str(caught.exception))
        with self.assertRaises(AssuranceError):
            kf.export_payload(kf.reject(build(), reviewer_id="dtalex66", reviewer_kind="human",
                                        reviewed_at=REVIEWED_AT, reason="duplicate"))
        forged = approved()
        forged["review"]["reviewer_kind"] = "agent"
        with self.assertRaises(AssuranceError):
            kf.export_payload(forged)

    def test_export_carries_the_loop_and_nothing_private(self):
        candidate = approved(note="checked against the method card index")
        exported = kf.export_payload(candidate)
        jsonschema.validate(instance=exported, schema=self.subschema("export"))
        self.assertEqual("design-lab/assurance-knowledge-candidate-export/v1",
                         exported["schemaVersion"])
        self.assertEqual(source(), exported["source"])
        self.assertEqual(SHA, exported["source"]["evidence_sha256"])
        self.assertEqual("MIT", exported["license_id"])
        self.assertEqual("METHOD", exported["candidate_type"])
        self.assertIsNone(exported["supersedes"])
        self.assertEqual(kf.DEFAULT_REVOCATION_ENTRYPOINT,
                         exported["revocation"]["entrypoint"])
        self.assertTrue(exported["revocation"]["revocable"])
        self.assertEqual("human", exported["review"]["reviewer_kind"])
        self.assertEqual(candidate["payload_sha256"], exported["payload_sha256"])
        self.assertNotIn("redaction_note", json.dumps(exported))
        self.assertNotIn("note", exported["review"])
        self.assertNotIn("client_brief", json.dumps(exported))

    def test_export_of_a_superseding_candidate_keeps_the_edge(self):
        exported = kf.export_payload(approved(supersedes="kb-0"))
        self.assertEqual("kb-0", exported["supersedes"])

    def subschema(self, name):
        schema = kf.schema()
        subschema = dict(schema["$defs"][name])
        subschema["$defs"] = schema["$defs"]
        return subschema

    def test_export_refuses_a_candidate_whose_rights_were_reset(self):
        forged = approved()
        forged["rights"]["rights_gate_state"] = "UNCHECKED"
        with self.assertRaises(AssuranceError) as caught:
            kf.export_payload(forged)
        self.assertIn("CHECKED rights gate", str(caught.exception))


class KnowledgeRevocationTests(unittest.TestCase):
    def test_a_revoked_candidate_can_never_be_exported(self):
        candidate = approved()
        self.assertIsInstance(kf.export_payload(candidate), dict)
        record = kf.revoke(candidate, reason="the method was superseded by a safer variant",
                           revoked_by="dtalex66")
        jsonschema.validate(instance=record, schema=self.subschema("revocation_record"))
        self.assertTrue(record["export_blocked"])
        self.assertEqual("kb-1", record["candidate_id"])
        revoked = kf.apply_revocation(candidate, record)
        self.assertEqual("REVOKED", revoked["revocation"]["state"])
        self.assertEqual("ACTIVE", candidate["revocation"]["state"])
        jsonschema.validate(instance=revoked, schema=kf.schema())
        with self.assertRaises(AssuranceError) as caught:
            kf.export_payload(revoked)
        self.assertIn("can never be exported", str(caught.exception))
        with self.assertRaises(AssuranceError) as again:
            kf.revoke(revoked, reason="again", revoked_by="dtalex66")
        self.assertIn("already revoked", str(again.exception))

    def test_a_revocation_is_bound_to_one_candidate(self):
        record = kf.revoke(approved(), reason="wrong licence", revoked_by="dtalex66")
        other = build(candidate_id="kb-2")
        with self.assertRaises(AssuranceError) as caught:
            kf.apply_revocation(other, record)
        self.assertIn("never transferable", str(caught.exception))
        with self.assertRaises(AssuranceError):
            kf.revoke(approved(), reason="  ", revoked_by="dtalex66")
        with self.assertRaises(AssuranceError):
            kf.apply_revocation(other, {**record, "export_blocked": False})

    def subschema(self, name):
        schema = kf.schema()
        subschema = dict(schema["$defs"][name])
        subschema["$defs"] = schema["$defs"]
        return subschema


class PrivatePayloadTests(unittest.TestCase):
    def test_private_material_is_refused_with_a_reason(self):
        rejects = {
            "windows path": {"statement": "open D:\\clients\\acme\\hero.psd"},
            "unc path": {"statement": r"open \\fileserver\share\acme\hero.psd"},
            "posix path": {"statement": "open /mnt/clients/acme/hero.psd"},
            "home path": {"statement": "open ~/clients/acme/hero.psd"},
            "file url": {"statement": "file:///clients/acme/hero.psd"},
            "relative file": {"statement": "see reports/current/PROJECT_STATUS.json"},
            "traversal": {"statement": "see ../../clients/acme"},
            "email": {"statement": "ask the brand lead at lead@acme.example"},
            "credential url": {"statement": "fetched from https://user:pass@cdn.example/x.png"},
            "transcript": {"chat_log": [{"role": "user", "content": "make it pop"}]},
            "role marker": {"statement": '{"role": "assistant", "content": "here you go"}'},
            "private flag": {"notes": {"private": True, "text": "internal"}},
            "private suffix": {"notes_private": "internal only"},
            "client asset": {"client_asset": "base64..."},
            "data uri": {"statement": "data:image/png;base64,iVBORw0KGgo="},
            "token": {"api_key": "sk-live-1234"},
            "path key": {"source_path": "somewhere/else"},
        }
        for name, value in rejects.items():
            with self.subTest(name=name):
                with self.assertRaises(AssuranceError) as caught:
                    kf.assert_no_private_payload(value)
                self.assertIn("must not leave this project", str(caught.exception))

    def test_a_clean_payload_passes_and_contact_email_is_opt_in(self):
        kf.assert_no_private_payload(payload())
        kf.assert_no_private_payload(
            {"reviewer_id": "lead@acme.example"}, allow_contact_email=True)
        with self.assertRaises(AssuranceError):
            kf.assert_no_private_payload({"reviewer_id": "lead@acme.example"})


class V1ProjectionTests(unittest.TestCase):
    def test_the_v2_candidate_projects_onto_the_existing_v1_contract(self):
        v1_schema = json.loads(kf.V1_SCHEMA_PATH.read_text(encoding="utf-8"))
        expectations = {
            "PENDING_HUMAN_APPROVAL": "review-required",
            "APPROVED": "compiled",
        }
        documents = {"PENDING_HUMAN_APPROVAL": build(), "APPROVED": approved()}
        for state, document in documents.items():
            projection = kf.to_v1_projection(document)
            jsonschema.validate(instance=projection, schema=v1_schema)
            self.assertEqual(expectations[state], projection["state"])
            self.assertEqual("design-lab/candidate-knowledge/v1", projection["schemaVersion"])
            self.assertEqual("job-1:op-1", projection["source_id"])
            self.assertEqual("method", projection["knowledge_type"])
            self.assertEqual(document["payload_sha256"], projection["content_hash"])
            self.assertIsNone(projection["compiled_ref"])

    def test_projection_maps_each_candidate_type_and_revocation(self):
        v1_schema = json.loads(kf.V1_SCHEMA_PATH.read_text(encoding="utf-8"))
        for candidate_type, knowledge_type in kf.V1_KNOWLEDGE_TYPES.items():
            projection = kf.to_v1_projection(approved(candidate_type=candidate_type))
            jsonschema.validate(instance=projection, schema=v1_schema)
            self.assertEqual(knowledge_type, projection["knowledge_type"])
        revoked = kf.apply_revocation(
            approved(), kf.revoke(approved(), reason="licence expired", revoked_by="dtalex66"))
        projection = kf.to_v1_projection(revoked)
        jsonschema.validate(instance=projection, schema=v1_schema)
        self.assertEqual("quarantined", projection["state"])

    def test_projection_refuses_a_non_document(self):
        with self.assertRaises(AssuranceError):
            kf.to_v1_projection("kb-1")
        with self.assertRaises(AssuranceError):
            kf.to_v1_projection({})


if __name__ == "__main__":
    unittest.main(verbosity=2)
