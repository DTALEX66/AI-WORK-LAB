"""后端2 guard: an issue row becomes a handoff pack, or the projection says exactly why it did not.

The closed-loop distance the 2026-10-21 audit recorded for row 3 was "案例已有，通用入口缺失": ML-001 proved a
human could carry a problem to an external agent, and nothing general existed to carry the second one. These
tests are about the general entry point and, more than about what it produces, about what it must refuse to
produce -- a pack that claims it was sent, names an executor nobody chose, invents a verification command for
a project it cannot see, or quietly drops the issues it did not bind.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rpp = _load("repair_pack_projection", "packages/client-neutral-core/scripts/repair_pack_projection.py")
ACTION_SCHEMA = json.loads((ROOT / "packages/contracts/schemas/workflow/action-plan.schema.json")
                           .read_text(encoding="utf-8"))
PACK_SCHEMA = json.loads((ROOT / "packages/contracts/schemas/workflow/repair-pack.schema.json")
                         .read_text(encoding="utf-8"))

GENERATED_AT = "2026-10-22T00:00:00Z"
REGISTRY = {"entries": [
    {"id": "codex", "display_name": "Codex", "support_level": "deep",
     "operations": ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"]},
    {"id": "cc-switch", "display_name": "CC Switch", "support_level": "deep",
     "operations": ["detect", "capabilities", "observe"]},
]}


class FakeEntry:
    def __init__(self, owner: "FakeRoot", tail: str):
        self.owner, self.tail = owner, tail

    def is_file(self) -> bool:
        return self.owner.entry

    def as_posix(self) -> str:
        return f"{self.owner.as_posix()}/{self.tail}"


class FakeRoot:
    """A project root whose answers are supplied, so 'does the gate exist here' is a controllable fact.

    It mimics the part of `pathlib.Path` the projection actually uses (join and exists) rather than being a
    Path, so the production code keeps its real shape and the test still controls both answers.
    """

    def __init__(self, value: str, *, exists: bool, entry_present: bool):
        self.value, self.exists_, self.entry = value, exists, entry_present

    def exists(self) -> bool:
        return self.exists_

    def is_file(self) -> bool:
        return self.entry

    def as_posix(self) -> str:
        return self.value.replace("\\", "/")

    def __truediv__(self, other: str) -> FakeEntry:
        return FakeEntry(self, other)


def issue(fingerprint: str, project: str | None, *, issue_class: str = "SOURCE_STALE",
          priority: str = "P2", software: str | None = None) -> dict:
    row = {
        "schemaVersion": "workflow/issue/v1", "fingerprint": fingerprint, "class": issue_class,
        "projectId": project, "subject": f"subject-{fingerprint[:6]}", "origin": "telemetry_events",
        "evidenceRef": f"telemetry_events:{fingerprint}", "priority": priority,
        "priorityRule": "rule sentence", "safeToReread": True, "firstSeenAt": GENERATED_AT,
        "lastSeenAt": GENERATED_AT, "occurrences": 1, "magnitude": {}, "detail": "d", "status": "OPEN",
        "softwareId": software, "softwareVersion": None, "softwareVersionSource": "unattributable",
    }
    return row


def project(project_id: str, root: str = "D:/somewhere/work-lab") -> dict:
    return {"project_id": project_id, "root_path": root, "display_name": project_id, "status": "REGISTERED"}


def make_root(exists: bool = True, entry_present: bool = True):
    def probe(value: str) -> FakeRoot:
        return FakeRoot(value, exists=exists, entry_present=entry_present)
    return probe


class VocabularyTests(unittest.TestCase):
    def test_observe_only_adapter_is_refused_by_its_own_declared_verbs(self) -> None:
        out = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")],
                                       registry=REGISTRY, adapters=["cc-switch"], generated_at=GENERATED_AT,
                                       root_probe=make_root())
        self.assertEqual([], out["packs"])
        self.assertEqual([{"adapter": "cc-switch", "reason": "adapter-does-not-declare-invoke"}],
                         out["summary"]["refusals"])
        self.assertEqual(1, out["summary"]["unboundOpenIssueCount"],
                         "an issue with no eligible executor must still be counted as unbound")

    def test_an_unregistered_adapter_is_named_as_unregistered_not_defaulted(self) -> None:
        out = rpp.project_repair_packs(issues=[issue("b" * 16, "work-lab")], projects=[project("work-lab")],
                                       registry=REGISTRY, adapters=["nonexistent"], generated_at=GENERATED_AT,
                                       root_probe=make_root())
        self.assertEqual([{"adapter": "nonexistent", "reason": "adapter-not-declared"}],
                         out["summary"]["refusals"])

    def test_issues_that_name_no_project_cannot_be_routed_and_say_so(self) -> None:
        out = rpp.project_repair_packs(issues=[issue("c" * 16, None)], projects=[project("work-lab")],
                                       registry=REGISTRY, adapters=["codex"], generated_at=GENERATED_AT,
                                       root_probe=make_root())
        self.assertEqual([], out["packs"])
        self.assertEqual([{"adapter": "codex", "reason": "issue-has-no-project"}],
                         out["summary"]["refusals"])
        self.assertEqual(1, out["summary"]["issuesWithoutProject"])

    def test_refusal_vocabulary_in_the_module_and_the_schema_are_one_list(self) -> None:
        declared = set(PACK_SCHEMA["properties"]["readiness"]["properties"]["reasons"]["items"]["enum"])
        self.assertEqual(set(rpp.READINESS_REASONS), declared,
                         "a reason the module can emit that the contract does not allow would be rejected "
                         "at read time, and one the contract allows but nothing emits is a dead promise")


class FanOutTests(unittest.TestCase):
    def test_each_project_is_decided_on_its_own(self) -> None:
        issues = [issue("d" * 16, "work-lab"), issue("e" * 16, "ghost-proj")]
        out = rpp.project_repair_packs(issues=issues, projects=[project("work-lab")], registry=REGISTRY,
                                        adapters=["codex"], generated_at=GENERATED_AT,
                                        root_probe=make_root())
        self.assertEqual(["work-lab"], [pack["target"]["projectId"] for pack in out["packs"]])
        self.assertEqual([{"adapter": "codex", "projectId": "ghost-proj", "reason": "project-unregistered"}],
                         out["summary"]["refusals"])
        summary = out["summary"]
        self.assertEqual(2, summary["projectsSeen"])
        self.assertEqual(1, summary["boundIssueCount"])
        self.assertEqual(1, summary["unboundOpenIssueCount"])
        self.assertEqual(summary["openIssueCount"],
                         summary["boundIssueCount"] + summary["unboundOpenIssueCount"])

    def test_two_issues_on_one_project_fold_into_one_pack(self) -> None:
        out = rpp.project_repair_packs(
            issues=[issue("1" * 16, "work-lab"), issue("2" * 16, "work-lab")],
            projects=[project("work-lab")], registry=REGISTRY, adapters=["codex"],
            generated_at=GENERATED_AT, root_probe=make_root())
        self.assertEqual(1, len(out["packs"]))
        self.assertEqual(2, out["packs"][0]["binds"]["issueCount"])
        self.assertEqual(2, out["summary"]["boundIssueCount"])

    def test_the_cap_is_disclosed_as_refusals_not_as_missing_packs(self) -> None:
        count = rpp.MAX_PACKS + 3
        issues = [issue(f"{i:016x}", f"proj-{i}") for i in range(count)]
        projects = [project(f"proj-{i}", root=f"D:/p{i}") for i in range(count)]
        out = rpp.project_repair_packs(issues=issues, projects=projects, registry=REGISTRY,
                                       adapters=["codex"], generated_at=GENERATED_AT,
                                       root_probe=make_root())
        dropped = [item for item in out["summary"]["refusals"] if item["reason"] == "pack-cap-reached"]
        self.assertTrue(out["summary"]["truncated"])
        self.assertEqual(rpp.MAX_PACKS, len(out["packs"]))
        self.assertEqual(count - rpp.MAX_PACKS, len(dropped),
                         "every pack the cap dropped must be visible as a named refusal")
        self.assertEqual(out["summary"]["cap"], rpp.MAX_PACKS)


class ShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = rpp.project_repair_packs(
            issues=[issue("f" * 16, "work-lab", software="codex")], projects=[project("work-lab")],
            registry=REGISTRY, adapters=["codex"], generated_at=GENERATED_AT,
            root_probe=make_root())["packs"][0]

    def test_the_envelope_and_its_plan_body_both_validate(self) -> None:
        from jsonschema import Draft202012Validator
        self.assertEqual([], [e.message for e in Draft202012Validator(PACK_SCHEMA).iter_errors(self.pack)])
        self.assertEqual([], [e.message for e in Draft202012Validator(ACTION_SCHEMA).iter_errors(self.pack["plan"])])
        self.assertEqual([], rpp.validate_repair_pack(self.pack, schema=ACTION_SCHEMA))

    def test_the_inlined_plan_body_has_not_drifted_from_the_action_plan_contract(self) -> None:
        """The envelope inlines the plan shape because the code generator cannot follow a $ref -- so the
        copy has to be pinned against the original or the two files silently become two definitions."""
        inline = PACK_SCHEMA["properties"]["plan"]
        self.assertEqual(sorted(ACTION_SCHEMA["required"]), sorted(inline["required"]))
        self.assertEqual(sorted(ACTION_SCHEMA["properties"]), sorted(inline["properties"]))
        for name, prop in inline["properties"].items():
            self.assertEqual(ACTION_SCHEMA["properties"][name], prop, f"{name} drifted")

    def test_the_issue_vocabulary_the_pack_repeats_is_still_the_projection_s(self) -> None:
        """The envelope copies the issue classes, priorities and fingerprint shape out of the problem
        projection rather than $ref'ing it, so the copy has to be pinned to the original every run."""
        ip = _load("issue_projection", "packages/client-neutral-core/scripts/issue_projection.py")
        binds = PACK_SCHEMA["properties"]["binds"]["properties"]
        self.assertEqual(sorted(ip.CLASSES), sorted(binds["classes"]["items"]["enum"]))
        self.assertEqual(sorted(ip.PRIORITY_RANK), sorted(binds["priorities"]["items"]["enum"]))
        self.assertEqual("^[0-9a-f]{16}$", binds["issueFingerprints"]["items"]["pattern"],
                         "the fingerprint shape is the blocker contract's; a pack that accepts anything "
                         "longer cannot be matched back to an issue row")

    def test_a_pack_is_never_issued_in_a_finished_state(self) -> None:
        self.assertIn(self.pack["status"], rpp.PACK_STATUSES)
        self.assertNotIn("APPROVED", PACK_SCHEMA["properties"]["status"]["enum"])
        self.assertNotIn("SUCCEEDED", PACK_SCHEMA["properties"]["status"]["enum"])
        forged = copy.deepcopy(self.pack)
        forged["status"] = "SUCCEEDED"
        from jsonschema import Draft202012Validator
        self.assertTrue(list(Draft202012Validator(PACK_SCHEMA).iter_errors(forged)))
        self.assertTrue(rpp.validate_repair_pack(forged))

    def test_planting_a_handoff_claim_is_caught_by_the_validator_and_the_schema(self) -> None:
        from jsonschema import Draft202012Validator
        for key in ("sent", "dispatched"):
            forged = copy.deepcopy(self.pack)
            forged["handoff"][key] = True
            self.assertTrue(rpp.validate_repair_pack(forged), f"{key}=True must be refused")
            self.assertTrue(list(Draft202012Validator(PACK_SCHEMA).iter_errors(forged)), f"{key} schema")
        granted = copy.deepcopy(self.pack)
        granted["handoff"]["authorizationRef"] = "grant-1"
        self.assertTrue(rpp.validate_repair_pack(granted),
                        "a generated pack cannot carry a grant; that is a later slice's decision")

    def test_the_pack_id_is_content_addressed_and_per_executor(self) -> None:
        again = rpp.project_repair_packs(
            issues=[issue("f" * 16, "work-lab", software="codex")], projects=[project("work-lab")],
            registry=REGISTRY, adapters=["codex"], generated_at=GENERATED_AT,
            root_probe=make_root())["packs"][0]
        self.assertEqual(self.pack["packId"], again["packId"])
        hermes = rpp.project_repair_packs(
            issues=[issue("f" * 16, "work-lab", software="codex")], projects=[project("work-lab")],
            registry={"entries": REGISTRY["entries"] + [
                {"id": "hermes", "display_name": "Hermes", "support_level": "deep",
                 "operations": ["invoke", "observe"]}]},
            adapters=["hermes"], generated_at=GENERATED_AT, root_probe=make_root())["packs"][0]
        self.assertNotEqual(self.pack["packId"], hermes["packId"],
                            "the same problem handed to a different executor is a different pack")

    def test_attribution_is_bound_as_evidence_and_stays_honest_about_gaps(self) -> None:
        self.assertEqual(["codex"], self.pack["binds"]["softwareIds"])
        self.assertEqual(0, self.pack["binds"]["unattributedCount"])
        blank = rpp.project_repair_packs(
            issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")], registry=REGISTRY,
            adapters=["codex"], generated_at=GENERATED_AT, root_probe=make_root())["packs"][0]
        self.assertEqual([], blank["binds"]["softwareIds"])
        self.assertEqual(1, blank["binds"]["unattributedCount"],
                         "no identity is reported as no identity, never as an empty list that reads as none needed")


class VerificationTests(unittest.TestCase):
    def test_a_command_is_named_only_when_the_entry_point_actually_exists(self) -> None:
        pack = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")],
                                        registry=REGISTRY, adapters=["codex"], generated_at=GENERATED_AT,
                                        root_probe=make_root(entry_present=False))["packs"][0]
        self.assertIs(False, pack["verification"]["known"])
        self.assertEqual("BLOCKED", pack["status"])
        self.assertEqual(["verification-command-unknown"], pack["readiness"]["reasons"])
        verify_step = [step for step in pack["plan"]["steps"] if step["id"] == "verify"][0]
        self.assertNotIn("run_quality_gate", verify_step["action"],
                         "a command may not appear in a step the pack says it does not know")

    def test_a_missing_project_root_is_refused_rather_than_relativised(self) -> None:
        out = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")],
                                       projects=[project("work-lab")], registry=REGISTRY,
                                       adapters=["codex"], generated_at=GENERATED_AT,
                                       root_probe=make_root(exists=False))
        self.assertEqual([{"adapter": "codex", "projectId": "work-lab", "reason": "project-root-missing"}],
                         out["summary"]["refusals"])


class AbsentSourceTests(unittest.TestCase):
    def test_an_unreadable_source_absents_the_key_and_names_itself(self) -> None:
        out = rpp.project_repair_packs(issues=None, projects=[project("work-lab")], registry=REGISTRY,
                                        adapters=["codex"], generated_at=GENERATED_AT)
        self.assertEqual([], out["packs"])
        self.assertEqual("issues", out["summary"]["absentReason"])
        self.assertEqual("absent", out["summary"]["sources"]["issues"])
        self.assertIsNone(out["summary"]["openIssueCount"],
                          "an unread source is not zero open issues")

    def test_no_adapter_requested_produces_no_pack_and_no_invented_executor(self) -> None:
        out = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")],
                                       registry=REGISTRY, adapters=[], generated_at=GENERATED_AT)
        self.assertEqual([], out["packs"])
        self.assertEqual([], out["summary"]["refusals"])
        self.assertEqual(1, out["summary"]["unboundOpenIssueCount"])


class PolishTests(unittest.TestCase):
    def test_an_unslug_safe_adapter_id_still_mints_a_pack_id_the_contract_accepts(self) -> None:
        registry = {"entries": [{"id": "Bad Name!", "display_name": None, "support_level": "deep",
                                "operations": ["invoke"]}]}
        pack = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")],
                                       registry=registry, adapters=["Bad Name!"],
                                       generated_at=GENERATED_AT, root_probe=make_root())["packs"][0]
        import re
        self.assertRegex(pack["packId"], r"^[A-Za-z0-9._-]{3,120}$")
        self.assertEqual([], rpp.validate_repair_pack(pack))

    def test_a_quoted_prefix_of_the_bound_evidence_says_the_rest_exists(self) -> None:
        many = [issue(f"{i:016x}", "work-lab") for i in range(12)]
        pack = rpp.project_repair_packs(issues=many, projects=[project("work-lab")], registry=REGISTRY,
                                        adapters=["codex"], generated_at=GENERATED_AT,
                                        root_probe=make_root())["packs"][0]
        self.assertEqual(12, pack["binds"]["issueCount"])
        read_step = [step for step in pack["plan"]["steps"] if step["id"] == "read-evidence"][0]
        self.assertIn("另有 4 条在 binds.evidenceRefs 里逐条列出", read_step["action"],
                      "eight refs shown out of twelve reads as twelve shown")
        self.assertEqual(12, len(pack["binds"]["evidenceRefs"]))

    def setUp(self) -> None:
        self.pack = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")],
                                             projects=[project("work-lab")], registry=REGISTRY,
                                             adapters=["codex"], generated_at=GENERATED_AT,
                                             root_probe=make_root())["packs"][0]

    def test_the_envelope_and_the_plan_body_must_name_the_same_target(self) -> None:
        for path, value in ((("plan", "target", "project_root"), "D:/elsewhere"),
                            (("plan", "target", "adapter"), "hermes")):
            forged = copy.deepcopy(self.pack)
            forged["plan"]["target"][path[-1]] = value
            problems = rpp.validate_repair_pack(forged)
            self.assertTrue(any("different" in problem for problem in problems),
                            f"{path} mismatch must be visible: {problems}")

    def test_readiness_and_status_cannot_disagree(self) -> None:
        split = copy.deepcopy(self.pack)
        split["status"] = "BLOCKED"
        self.assertTrue(any("readiness.state" in problem
                            for problem in rpp.validate_repair_pack(split)),
                        "one field says blocked and the other says ready")
        mute = copy.deepcopy(self.pack)
        mute["status"] = "BLOCKED"
        mute["readiness"] = {"state": "BLOCKED", "reasons": []}
        self.assertTrue(any("name what blocks it" in problem for problem in rpp.validate_repair_pack(mute)),
                        "a blocked pack with no reason is a blocked pack nobody can act on")

    def test_a_repeated_adapter_mints_one_pack_and_discloses_the_repeat(self) -> None:
        """The defect this guards: `--adapter codex --adapter codex` produced two packs sharing one
        content-addressed id and counted the same issue twice, so bound=2 while open=1 -- every pack valid,
        the denominators invented."""
        out = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")],
                                       registry=REGISTRY, adapters=["codex", "codex", "codex"],
                                       generated_at=GENERATED_AT, root_probe=make_root())
        self.assertEqual(1, len(out["packs"]))
        self.assertEqual(2, out["summary"]["duplicateAdaptersDropped"],
                         "three requests, one executor: two repeats dropped and both counted")
        self.assertEqual(1, out["summary"]["boundIssueCount"])
        self.assertEqual([], rpp.validate_repair_pack_set(out["packs"], out["summary"]))

    def test_a_second_pack_on_the_same_issue_is_convicted_at_the_set_level(self) -> None:
        out = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")],
                                       registry=REGISTRY, adapters=["codex"], generated_at=GENERATED_AT,
                                       root_probe=make_root())
        twin = copy.deepcopy(out["packs"][0])
        twin["packId"] = "rp-work-lab-codex-deadbeefdeadbeef"
        twin["plan"]["plan_id"] = twin["packId"]
        summary = dict(out["summary"])
        summary["boundIssueCount"] = 2
        problems = rpp.validate_repair_pack_set(out["packs"] + [twin], summary)
        self.assertTrue(any("more than one pack" in p for p in problems), problems)

    def test_bound_may_never_exceed_open(self) -> None:
        out = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")],
                                       registry=REGISTRY, adapters=["codex"], generated_at=GENERATED_AT,
                                       root_probe=make_root())
        summary = dict(out["summary"])
        summary["openIssueCount"] = 1
        summary["boundIssueCount"] = 3
        summary["unboundOpenIssueCount"] = -2
        problems = rpp.validate_repair_pack_set(out["packs"], summary)
        self.assertTrue(any("more issues bound than open" in p for p in problems), problems)

    def test_a_pack_without_a_verify_step_is_refused(self) -> None:
        pack = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")],
                                        registry=REGISTRY, adapters=["codex"], generated_at=GENERATED_AT,
                                        root_probe=make_root())["packs"][0]
        stripped = copy.deepcopy(pack)
        stripped["plan"]["steps"] = [s for s in stripped["plan"]["steps"] if s["id"] != "verify"]
        self.assertTrue(any("verify step" in problem for problem in rpp.validate_repair_pack(stripped)),
                        "a handoff with no check step cannot be verified by anyone")


class ManualTargetTests(unittest.TestCase):
    """CL-03: material a human copies to any tool, with no adapter capability borrowed.

    The route exists because "the executor declares invoke" is a fact about a registry entry, and a user with
    an issue and an arbitrary tool has no such entry. The tests below pin the two claims that could inflate:
    a manual pack naming an adapter, and a user statement being stored where a receipt belongs.
    """

    def setUp(self) -> None:
        self.pack = rpp.project_repair_packs(
            issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")], registry=REGISTRY,
            adapters=[], generated_at=GENERATED_AT, root_probe=make_root(), manual=True)["packs"][0]

    def test_a_manual_pack_names_no_adapter_and_claims_no_invoke(self) -> None:
        from jsonschema import Draft202012Validator
        self.assertEqual("MANUAL_COPY", self.pack["target"]["kind"])
        self.assertEqual("copy-handoff", self.pack["target"]["operation"])
        self.assertIsNone(self.pack["target"]["adapter"])
        self.assertIsNone(self.pack["target"]["adapterSupportLevel"])
        self.assertEqual([], self.pack["target"]["declaredOperations"])
        self.assertEqual("manual-copy", self.pack["plan"]["target"]["adapter"],
                         "the plan body still needs a non-empty executor label; the reserved label is not "
                         "an adapter id and the envelope's kind says so")
        self.assertEqual("copy-handoff", self.pack["plan"]["target"]["operation"])
        self.assertEqual([], rpp.validate_repair_pack(self.pack))
        self.assertEqual([], [e.message for e in Draft202012Validator(PACK_SCHEMA).iter_errors(self.pack)])

    def test_the_manual_route_does_not_read_the_adapter_registry(self) -> None:
        out = rpp.project_repair_packs(issues=[issue("a" * 16, "work-lab")],
                                       projects=[project("work-lab")], registry=None, adapters=[],
                                       generated_at=GENERATED_AT, root_probe=make_root(), manual=True)
        self.assertEqual(1, len(out["packs"]))
        self.assertNotIn("adapterRegistry", out["summary"]["sources"],
                         "a route that never consulted the registry may not report it as a missing source")
        self.assertEqual("MANUAL_COPY", out["summary"]["targetKind"])

    def test_the_same_issue_handed_manually_and_to_an_adapter_is_two_materials(self) -> None:
        adapter_pack = rpp.project_repair_packs(
            issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")], registry=REGISTRY,
            adapters=["codex"], generated_at=GENERATED_AT, root_probe=make_root())["packs"][0]
        self.assertNotEqual(self.pack["packId"], adapter_pack["packId"])
        self.assertEqual("ADAPTER_INVOKE", adapter_pack["target"]["kind"])
        self.assertEqual("invoke", adapter_pack["target"]["operation"])
        self.assertEqual("codex", adapter_pack["target"]["adapter"])

    def test_a_user_statement_cannot_fill_the_external_receipt(self) -> None:
        from jsonschema import Draft202012Validator
        forged = copy.deepcopy(self.pack)
        forged["handoff"]["userDeclaredHandoff"] = {
            "declared": True, "declaredAt": GENERATED_AT, "channel": "clipboard",
            "claimedRecipient": "some-tool"}
        self.assertTrue(any("userDeclaredHandoff" in p or "user statement" in p
                            for p in rpp.validate_repair_pack(forged)))
        self.assertIs(False, forged["handoff"]["externalReceipt"]["received"],
                      "writing one field must not fill the other; the claim and the evidence are separate")
        self.assertTrue(list(Draft202012Validator(PACK_SCHEMA).iter_errors(forged)))

    def test_an_unknown_verification_command_blocks_a_manual_pack_too(self) -> None:
        pack = rpp.project_repair_packs(
            issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")], registry=REGISTRY,
            adapters=[], generated_at=GENERATED_AT, root_probe=make_root(entry_present=False),
            manual=True)["packs"][0]
        self.assertEqual("BLOCKED", pack["status"])
        self.assertEqual(["verification-command-unknown"], pack["readiness"]["reasons"])

    def test_the_two_routes_cannot_be_combined_in_one_run(self) -> None:
        self.assertEqual(4, rpp.main(["--adapter", "codex", "--manual"]),
                         "the set-level check refuses to bind one issue twice, so the CLI must refuse the "
                         "combination before it reads a store")


class HandoffTextGuardTests(unittest.TestCase):
    """The material is the product a human carries away; these are the ways it can lie."""

    def setUp(self) -> None:
        many = [issue(f"{i:016x}", "work-lab") for i in range(12)]
        self.pack = rpp.project_repair_packs(issues=many, projects=[project("work-lab")],
                                             registry=REGISTRY, adapters=["codex"],
                                             generated_at=GENERATED_AT,
                                             root_probe=make_root())["packs"][0]

    def test_every_bound_evidence_ref_appears_in_the_material(self) -> None:
        text = rpp.render_handoff_text(self.pack)
        self.assertEqual([], rpp.validate_handoff_text(self.pack, text))
        for ref in self.pack["binds"]["evidenceRefs"]:
            self.assertIn(f"`{ref}`", text,
                          "the material is what a tool reads; an omitted ref is a row nobody can re-read")

    def test_the_guard_names_a_missing_ref(self) -> None:
        text = rpp.render_handoff_text(self.pack)
        missing = self.pack["binds"]["evidenceRefs"][0]
        problems = rpp.validate_handoff_text(self.pack, text.replace(missing, "REMOVED"))
        self.assertTrue(any("omits" in problem and missing in problem for problem in problems), problems)

    def test_the_guard_rejects_a_completed_claim(self) -> None:
        for phrase in rpp.HANDOFF_FORBIDDEN_PHRASES:
            self.assertTrue(rpp.validate_handoff_text(self.pack, f"header\n{phrase}\nrest"),
                            f"{phrase} must be refused")

    def test_the_rendered_material_carries_none_of_them(self) -> None:
        text = rpp.render_handoff_text(self.pack)
        for phrase in ("已发送", "已执行", "已批准"):
            self.assertNotIn(phrase, text,
                             "the negative framing 未发送/未执行 is fine; the completed claim is not")

    def test_the_preview_explains_the_blocking_condition(self) -> None:
        blocked = rpp.project_repair_packs(
            issues=[issue("a" * 16, "work-lab")], projects=[project("work-lab")], registry=REGISTRY,
            adapters=["codex"], generated_at=GENERATED_AT,
            root_probe=make_root(entry_present=False))["packs"][0]
        text = rpp.render_handoff_text(blocked)
        self.assertIn("还缺什么条件", text)
        self.assertIn("verification-command-unknown", text)
        self.assertIn("检查入口", text)
        ready = rpp.render_handoff_text(self.pack)
        self.assertIn("材料可以直接复制", ready)


if __name__ == "__main__":
    unittest.main()
