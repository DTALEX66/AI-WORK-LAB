# SPDX-License-Identifier: MIT
"""DL-P1-131 / DLDS-F080: video boundary rule engine tests (STRUCTURAL / E1 evidence only).

No video host is launched, nothing is rendered or encoded, and no GPU is
touched. The tests prove the ownership rules, the versioned capability-id
contract that replaced the free-text ``host_classes``, and the fail-closed
paths - including that no logic path reads a display label.
"""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from jsonschema import Draft202012Validator  # noqa: E402

from design_lab.creative.media import MediaError, load_schema  # noqa: E402
from design_lab.creative.media import video_boundary as vb  # noqa: E402

HANDOFF_CLAIMS = [
    "frame-accurate output at 23.976 fps",
    "colour-managed encode to Rec.709",
    "hardware encode on the local GPU",
    "rendered preview of the first 240 frames",
]

RENDER_REF = "capability:video/render@1"


def entry(document, operation):
    return next(item for item in document["entries"] if item["operation"] == operation)


class CapabilityIdentifierTests(unittest.TestCase):
    """DLDS-F080: host requirements are versioned capability-registry ids."""

    def test_the_document_declares_capability_ids_not_free_strings(self):
        document = vb.boundary_document()
        self.assertEqual(
            document["schemaVersion"], "design-lab/media-video-boundary/v2"
        )
        declared = [item["capability_ref"] for item in document["host_capabilities"]]
        self.assertTrue(declared)
        self.assertEqual(len(declared), len(set(declared)))
        for ref in declared:
            self.assertRegex(ref, vb.CAPABILITY_REF_PATTERN)
            self.assertTrue(ref.startswith(vb.CAPABILITY_PREFIX), ref)
            self.assertNotIn(" ", ref)
        for item in document["entries"]:
            for ref in item["host_capability_refs"]:
                self.assertIn(ref, declared, item["id"])
        # The retired free-text list is gone, not renamed.
        self.assertNotIn("host_classes", document)
        self.assertNotIn("host_classes", vb.boundary_document())

    def test_the_old_free_text_form_is_not_a_capability_id(self):
        for value in ("editor", "Premiere Pro class non-linear editor",
                      "capability:video/render", "capability:video/render@",
                      "capability:video/render@x", "capability:/render@1",
                      "capability:video//render@1", "capability:video/render@1.0",
                      "video/render@1", "", "   "):
            with self.subTest(value=value):
                with self.assertRaises(MediaError) as caught:
                    vb.require_capability_ref(value)
                self.assertEqual("VIDEO_CAPABILITY_REF_INVALID", caught.exception.code)
        for value in (None, 1, ["capability:video/render@1"], {"ref": "x"}):
            with self.subTest(value=value):
                with self.assertRaises(MediaError) as caught:
                    vb.require_capability_ref(value)
                self.assertEqual("VIDEO_CAPABILITY_REF_INVALID", caught.exception.code)

    def test_the_versioned_grammar_is_accepted(self):
        for value in ("capability:video/render@1", "capability:video/render@10",
                      "capability:video.render@1", "capability:video/render@0",
                      "capability:video/colour-managed-export@2",
                      "capability:audio/mixdown@3"):
            with self.subTest(value=value):
                self.assertEqual(value, vb.require_capability_ref(value))
        # Version 0 is an integer version, not an omission.
        self.assertEqual(
            "capability:video/render@0",
            vb.require_capability_ref("capability:video/render@0"),
        )
        unversioned = "capability:video/render@1".split("@")[0]
        with self.assertRaises(MediaError) as caught:
            vb.require_capability_ref(unversioned)
        self.assertIn("integer version", str(caught.exception))

    def test_duplicate_capability_ids_are_refused(self):
        with self.assertRaises(MediaError) as caught:
            vb.validate_capability_refs(
                ["capability:video/render@1", "capability:video/render@1"],
                "host_capability_refs",
            )
        self.assertEqual("VIDEO_CAPABILITY_DUPLICATE", caught.exception.code)

        document = copy.deepcopy(vb.boundary_document())
        document["host_capabilities"].append(
            copy.deepcopy(document["host_capabilities"][0])
        )
        with self.assertRaises(MediaError) as declared:
            vb.validate_boundary(document)
        self.assertEqual("VIDEO_CAPABILITY_DUPLICATE", declared.exception.code)
        self.assertIn("ambiguous", str(declared.exception))

        document = copy.deepcopy(vb.boundary_document())
        entry(document, "render")["host_capability_refs"] = [RENDER_REF, RENDER_REF]
        with self.assertRaises(MediaError) as repeated:
            vb.validate_boundary(document)
        self.assertIn(
            repeated.exception.code,
            {"VIDEO_CAPABILITY_DUPLICATE", "MEDIA_SCHEMA_INVALID"},
        )

    def test_a_rule_may_only_reference_a_declared_capability(self):
        document = copy.deepcopy(vb.boundary_document())
        entry(document, "render")["host_capability_refs"] = [
            "capability:video/undeclared@1"
        ]
        with self.assertRaises(MediaError) as caught:
            vb.validate_boundary(document)
        self.assertEqual("VIDEO_CAPABILITY_UNDECLARED", caught.exception.code)
        message = str(caught.exception)
        self.assertIn("capability:video/undeclared@1", message)
        self.assertIn("does not declare", message)

        # Removing a declared capability while a rule still references it is the
        # same failure seen from the other side.
        document = copy.deepcopy(vb.boundary_document())
        document["host_capabilities"] = [
            item for item in document["host_capabilities"]
            if item["capability_ref"] != RENDER_REF
        ]
        with self.assertRaises(MediaError) as caught:
            vb.validate_boundary(document)
        self.assertEqual("VIDEO_CAPABILITY_UNDECLARED", caught.exception.code)
        self.assertIn(RENDER_REF, str(caught.exception))

    def test_a_host_side_operation_must_declare_its_capability(self):
        document = copy.deepcopy(vb.boundary_document())
        entry(document, "render")["host_capability_refs"] = []
        with self.assertRaises(MediaError) as caught:
            vb.validate_boundary(document)
        self.assertEqual("VIDEO_CAPABILITY_MISSING", caught.exception.code)
        self.assertIn("host capability", str(caught.exception))

        document = copy.deepcopy(vb.boundary_document())
        entry(document, "frame-accuracy-contract")["host_capability_refs"] = []
        with self.assertRaises(MediaError) as shared:
            vb.validate_boundary(document)
        self.assertEqual("VIDEO_CAPABILITY_MISSING", shared.exception.code)

        # An operation DESIGN-LAB owns outright needs no host capability at all.
        design_only = copy.deepcopy(vb.boundary_document())
        design_entry = entry(design_only, "visual-design")
        self.assertEqual([], design_entry["host_capability_refs"])
        self.assertEqual("design-lab", design_entry["owner"])
        vb.validate_boundary(design_only)

    def test_malformed_ids_and_empty_refs_are_refused_by_the_document(self):
        for value in ("editor", "", "capability:video/render"):
            with self.subTest(value=value):
                document = copy.deepcopy(vb.boundary_document())
                entry(document, "render")["host_capability_refs"] = [value]
                with self.assertRaises(MediaError) as caught:
                    vb.validate_boundary(document)
                self.assertIn(
                    caught.exception.code,
                    {"MEDIA_SCHEMA_INVALID", "VIDEO_CAPABILITY_REF_INVALID"},
                )

    def test_the_retired_free_text_field_is_refused_by_the_schema(self):
        document = copy.deepcopy(vb.boundary_document())
        document["host_classes"] = ["editor"]
        with self.assertRaises(MediaError) as caught:
            vb.validate_boundary(document)
        self.assertEqual("MEDIA_SCHEMA_INVALID", caught.exception.code)
        self.assertIn("host_classes", str(caught.exception))

    def test_the_decision_carries_the_capability_ids_it_depends_on(self):
        allowed = vb.assert_within_boundary(
            {"operation": "render", "requested_owner": "host"}
        )
        self.assertEqual([RENDER_REF], allowed["host_capability_refs"])
        shared = vb.assert_within_boundary(
            {"operation": "frame-accuracy-contract", "requested_owner": "host"}
        )
        self.assertEqual(
            sorted(["capability:video/nonlinear-edit@1", RENDER_REF]),
            sorted(shared["host_capability_refs"]),
        )
        for ref in allowed["host_capability_refs"] + shared["host_capability_refs"]:
            self.assertRegex(ref, vb.CAPABILITY_REF_PATTERN)


class DisplayLabelTests(unittest.TestCase):
    """A label is prose for a human reader; no logic may branch on one."""

    def test_labels_are_display_only_and_optional(self):
        labels = vb.capability_labels()
        self.assertEqual(len(vb.HOST_CAPABILITIES), len(labels))
        for ref, label in vb.HOST_CAPABILITIES:
            self.assertEqual(label, labels[ref])
            self.assertNotEqual(ref, label)
        # Nothing depends on a label being present at all.
        stripped = copy.deepcopy(vb.boundary_document())
        for item in stripped["host_capabilities"]:
            del item["display_label"]
        vb.validate_boundary(stripped)
        self.assertEqual(
            vb.boundary_document()["entries"], stripped["entries"]
        )
        self.assertEqual({}, {k: v for k, v in vb.capability_labels(stripped).items() if v})

    def test_no_logic_path_reads_a_display_label(self):
        # A hostile label would flip an ownership decision if any rule read it:
        # the host capability of a host-owned entry is labelled 'design-lab'.
        poisoned = copy.deepcopy(vb.boundary_document())
        for item in poisoned["host_capabilities"]:
            item["display_label"] = "design-lab"
        self.assertEqual(
            vb.boundary_entries_by_operation(),
            vb.boundary_entries_by_operation(poisoned),
        )
        for request in (
            {"operation": "render", "requested_owner": "host"},
            {"operation": "design-ir", "requested_owner": "design-lab"},
            {"operation": "colour-space-declaration", "requested_owner": "host"},
        ):
            with self.subTest(request=request):
                self.assertEqual(
                    vb.assert_within_boundary(dict(request)),
                    vb.assert_within_boundary(dict(request), document=poisoned),
                )
        with self.assertRaises(MediaError) as caught:
            vb.assert_within_boundary(
                {"operation": "render", "requested_owner": "design-lab"},
                document=poisoned,
            )
        self.assertEqual("VIDEO_BOUNDARY_OWNERSHIP_CONFLICT", caught.exception.code)

    def test_only_the_display_accessor_mentions_the_label_field(self):
        tree = ast.parse(Path(vb.__file__).read_text(encoding="utf-8"))
        branch_nodes = (ast.If, ast.IfExp, ast.While, ast.Assert, ast.BoolOp,
                        ast.comprehension, ast.Match if hasattr(ast, "Match") else ast.If)
        branching = []
        mentioning = set()
        for node in ast.walk(tree):
            if not self._mentions(node, "display_label"):
                continue
            if isinstance(node, branch_nodes):
                branching.append(type(node).__name__)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                mentioning.add(node.name)
        self.assertEqual([], branching, "no condition may branch on display_label")
        self.assertEqual(
            {"_document", "capability_labels"}, mentioning,
            "only the document builder and the display accessor may mention display_label",
        )

    @staticmethod
    def _mentions(node, field):
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and child.value == field:
                return True
            if isinstance(child, ast.Attribute) and child.attr == field:
                return True
        return False


class BoundaryDocumentTests(unittest.TestCase):
    def test_document_matches_its_schema(self) -> None:
        document = vb.boundary_document()
        schema = load_schema("media-video-boundary")
        self.assertEqual(
            schema["$id"], "https://dtalex66.local/schemas/media-video-boundary.json"
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(document)
        self.assertEqual(document["schemaVersion"], "design-lab/media-video-boundary/v2")
        self.assertEqual(document["task_ids"], ["DL-P1-131"])
        self.assertEqual(document["evidence_level"], "E1")
        self.assertEqual(document["host_execution"], "NOT_EXECUTED")
        json.dumps(document)

    def test_ownership_split_is_the_declared_one(self) -> None:
        entries = vb.boundary_entries_by_operation()
        self.assertEqual(set(entries), set(vb.OPERATIONS))
        self.assertEqual(entries["visual-design"]["owner"], "design-lab")
        self.assertEqual(entries["design-ir"]["owner"], "design-lab")
        self.assertEqual(entries["timeline-contract"]["owner"], "design-lab")
        self.assertEqual(entries["handoff-bundle"]["owner"], "design-lab")
        self.assertEqual(entries["delivery-receipt"]["owner"], "design-lab")
        for operation in (
            "render",
            "encode",
            "colour-managed-export",
            "audio-mixdown",
            "hardware-acceleration",
        ):
            self.assertEqual(entries[operation]["owner"], "host", operation)
            self.assertTrue(entries[operation]["rule"])
            self.assertTrue(entries[operation]["host_capability_refs"], operation)
        for operation, entry in entries.items():
            self.assertIn(entry["owner"], vb.OWNERS)
            self.assertIsInstance(entry["rule"], str)
            self.assertGreaterEqual(len(entry["rule"]), 8)

    def test_document_is_regenerated_not_shared(self) -> None:
        first = vb.boundary_document()
        first["entries"][0]["owner"] = "host"
        self.assertEqual(vb.boundary_document()["entries"][0]["owner"], "design-lab")

    def test_design_lab_may_not_own_rendered_or_encoded_work_without_evidence(self) -> None:
        document = copy.deepcopy(vb.boundary_document())
        render = entry(document, "render")
        render["owner"] = "design-lab"
        with self.assertRaises(MediaError) as caught:
            vb.validate_boundary(document)
        self.assertEqual(caught.exception.code, "VIDEO_BOUNDARY_OWNERSHIP_UNPROVEN")
        self.assertIn("host-live:", str(caught.exception))

        render["host_live_evidence_ref"] = "measured-by-hand"
        with self.assertRaises(MediaError) as caught:
            vb.validate_boundary(document)
        self.assertEqual(caught.exception.code, "MEDIA_SCHEMA_INVALID")
        self.assertIn("host_live_evidence_ref", str(caught.exception))

        render["host_live_evidence_ref"] = "host-live:export-2026-09-01-0001"
        vb.validate_boundary(document)

    def test_a_host_may_never_own_the_design_record(self) -> None:
        document = copy.deepcopy(vb.boundary_document())
        entry(document, "design-ir")["owner"] = "host"
        with self.assertRaises(MediaError) as caught:
            vb.validate_boundary(document)
        self.assertEqual(caught.exception.code, "VIDEO_BOUNDARY_FOREIGN_OWNERSHIP")

    def test_ambiguous_or_incomplete_ownership_fails_closed(self) -> None:
        document = copy.deepcopy(vb.boundary_document())
        document["entries"].append(copy.deepcopy(document["entries"][0]))
        with self.assertRaises(MediaError) as duplicate:
            vb.validate_boundary(document)
        self.assertEqual(duplicate.exception.code, "VIDEO_BOUNDARY_DUPLICATE_OPERATION")

        document = copy.deepcopy(vb.boundary_document())
        document["entries"] = [
            item for item in document["entries"] if item["operation"] != "encode"
        ]
        with self.assertRaises(MediaError) as undeclared:
            vb.validate_boundary(document)
        self.assertEqual(undeclared.exception.code, "VIDEO_BOUNDARY_OPERATION_UNDECLARED")

        document = copy.deepcopy(vb.boundary_document())
        document["operations"] = [op for op in document["operations"] if op != "render"]
        with self.assertRaises(MediaError) as operation_set:
            vb.validate_boundary(document)
        self.assertEqual(operation_set.exception.code, "VIDEO_BOUNDARY_OPERATION_SET")

    def test_schema_violations_are_refused(self) -> None:
        document = copy.deepcopy(vb.boundary_document())
        document["entries"][0]["owner"] = "designlab"
        with self.assertRaises(MediaError) as caught:
            vb.validate_boundary(document)
        self.assertEqual(caught.exception.code, "MEDIA_SCHEMA_INVALID")
        with self.assertRaises(MediaError):
            vb.validate_boundary(["not", "a", "document"])


class AssertWithinBoundaryTests(unittest.TestCase):
    def test_matching_requests_are_allowed(self) -> None:
        allowed = vb.assert_within_boundary(
            {"operation": "render", "requested_owner": "host"}
        )
        self.assertTrue(allowed["allowed"])
        self.assertEqual(allowed["owner"], "host")
        self.assertTrue(allowed["reason"])

        design = vb.assert_within_boundary(
            {"operation": "design-ir", "requested_owner": "design-lab"}
        )
        self.assertEqual(design["owner"], "design-lab")

        shared = vb.assert_within_boundary(
            {"operation": "colour-space-declaration", "requested_owner": "design-lab"}
        )
        self.assertEqual(shared["owner"], "shared")
        self.assertIn("shared", shared["reason"])
        shared_host = vb.assert_within_boundary(
            {"operation": "colour-space-declaration", "requested_owner": "host"}
        )
        self.assertTrue(shared_host["allowed"])

    def test_out_of_boundary_requests_fail_closed(self) -> None:
        with self.assertRaises(MediaError) as caught:
            vb.assert_within_boundary(
                {
                    "operation": "render",
                    "requested_owner": "design-lab",
                    "frames": [1, 240],
                }
            )
        self.assertEqual(caught.exception.code, "VIDEO_BOUNDARY_OWNERSHIP_CONFLICT")
        self.assertIn("owned by 'host'", str(caught.exception))

        with self.assertRaises(MediaError) as caught:
            vb.assert_within_boundary(
                {"operation": "encode", "requested_owner": "design-lab"}
            )
        self.assertEqual(caught.exception.code, "VIDEO_BOUNDARY_OWNERSHIP_CONFLICT")

        with self.assertRaises(MediaError) as caught:
            vb.assert_within_boundary(
                {"operation": "design-ir", "requested_owner": "host"}
            )
        self.assertEqual(caught.exception.code, "VIDEO_BOUNDARY_OWNERSHIP_CONFLICT")

    def test_unknown_input_fails_closed(self) -> None:
        with self.assertRaises(MediaError) as unknown_operation:
            vb.assert_within_boundary(
                {"operation": "transcode", "requested_owner": "host"}
            )
        self.assertEqual(unknown_operation.exception.code, "VIDEO_BOUNDARY_OPERATION_UNKNOWN")

        with self.assertRaises(MediaError) as unknown_owner:
            vb.assert_within_boundary(
                {"operation": "render", "requested_owner": "design-lab-orchestrator"}
            )
        self.assertEqual(unknown_owner.exception.code, "VIDEO_BOUNDARY_OWNER_UNKNOWN")

        with self.assertRaises(MediaError) as missing:
            vb.assert_within_boundary({"operation": "render"})
        self.assertEqual(missing.exception.code, "VIDEO_REQUEST_INVALID")

        with self.assertRaises(MediaError) as not_mapping:
            vb.assert_within_boundary("render")
        self.assertEqual(not_mapping.exception.code, "VIDEO_REQUEST_INVALID")

    def test_an_amended_document_is_honoured(self) -> None:
        document = copy.deepcopy(vb.boundary_document())
        render = entry(document, "render")
        render["owner"] = "design-lab"
        render["host_live_evidence_ref"] = "host-live:measured-export-0001"
        allowed = vb.assert_within_boundary(
            {"operation": "render", "requested_owner": "design-lab"}, document=document
        )
        self.assertEqual(allowed["owner"], "design-lab")

    def test_an_undeclared_capability_makes_the_amended_document_unusable(self) -> None:
        document = copy.deepcopy(vb.boundary_document())
        entry(document, "encode")["host_capability_refs"] = [
            "capability:video/not-in-registry@9"
        ]
        with self.assertRaises(MediaError) as caught:
            vb.assert_within_boundary(
                {"operation": "encode", "requested_owner": "host"}, document=document
            )
        self.assertEqual(caught.exception.code, "VIDEO_CAPABILITY_UNDECLARED")


class UnsupportedClaimTests(unittest.TestCase):
    def test_structural_bundle_supports_no_host_claim(self) -> None:
        unsupported = vb.unsupported_video_claims(
            {"handoff_id": "h-1", "claims": list(HANDOFF_CLAIMS), "evidence_level": "E1"}
        )
        self.assertEqual(len(unsupported), len(HANDOFF_CLAIMS))
        for line, claim in zip(unsupported, HANDOFF_CLAIMS):
            self.assertTrue(line.startswith(claim))
            self.assertIn("NOT_EXECUTED", line)
        self.assertIn("frame-accuracy receipt", unsupported[0])
        self.assertIn("colour-managed export receipt", unsupported[1])
        self.assertIn("accelerator", unsupported[2])
        self.assertIn("render receipt", unsupported[3])

    def test_only_a_measured_host_live_receipt_clears_a_claim(self) -> None:
        bundle = {
            "handoff_id": "h-2",
            "claims": list(HANDOFF_CLAIMS),
            "host_live_receipts": [
                {
                    "claim": "frame-accurate output",
                    "receipt_ref": "host-live:export-0001",
                    "evidence_level": "E2",
                },
                {
                    "claim": "rendered preview",
                    "receipt_ref": "premiere-project-file-0007",
                    "evidence_level": "E3",
                },
                {
                    "claim": "hardware encode",
                    "receipt_ref": "host-live:gpu-0002",
                    "evidence_level": "E1",
                },
            ],
        }
        unsupported = vb.unsupported_video_claims(bundle)
        self.assertEqual(len(unsupported), 3)
        self.assertNotIn("frame-accurate", " ".join(unsupported))
        self.assertIn("rendered preview", " ".join(unsupported))
        self.assertIn("hardware encode", " ".join(unsupported))
        self.assertIn("colour-managed encode", " ".join(unsupported))

    def test_unknown_claims_are_reported_not_ignored(self) -> None:
        unsupported = vb.unsupported_video_claims(
            {"handoff_id": "h-3", "claims": ["ships an Oscar-winning edit"]}
        )
        self.assertEqual(len(unsupported), 1)
        self.assertIn("unrecognised claim class", unsupported[0])
        self.assertIn("NOT_EXECUTED", unsupported[0])

    def test_malformed_bundles_fail_closed(self) -> None:
        for bundle in (
            {"handoff_id": "h-4"},
            {"handoff_id": "h-4", "claims": []},
            {"handoff_id": "h-4", "claims": "frame-accurate output"},
            {"handoff_id": "h-4", "claims": [""]},
            {"handoff_id": "h-4", "claims": ["render"], "host_live_receipts": {}},
        ):
            with self.subTest(bundle=bundle):
                with self.assertRaises(MediaError) as caught:
                    vb.unsupported_video_claims(bundle)
                self.assertIn(
                    caught.exception.code, {"VIDEO_CLAIMS_MISSING", "VIDEO_BUNDLE_INVALID"}
                )
        with self.assertRaises(MediaError) as not_mapping:
            vb.unsupported_video_claims(["rendered preview"])
        self.assertEqual(not_mapping.exception.code, "VIDEO_BUNDLE_INVALID")

    def test_receipt_without_a_measured_level_is_ignored(self) -> None:
        unsupported = vb.unsupported_video_claims(
            {
                "handoff_id": "h-5",
                "claims": ["hardware encode"],
                "host_live_receipts": [
                    {
                        "claim": "hardware encode",
                        "receipt_ref": "host-live:gpu-0003",
                        "evidence_level": "E0",
                    }
                ],
            }
        )
        self.assertEqual(len(unsupported), 1)
        self.assertIn("requires a host-live receipt naming the accelerator", unsupported[0])


if __name__ == "__main__":
    unittest.main()
