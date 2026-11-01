"""Gate: the generated TypeScript projection must say what the JSON Schemas say, and match the hand-written model.

WUI-15's open clause is "the front end keeps a second, hand-maintained spelling of the main contract". The
blunt fix -- point `apps/observer/frontend/src/types.ts` at `generated/contracts.ts` -- was not available, and
measuring why is what this file is for. The projection had three defects that made it *weaker and wronger*
than the hand-written file:

* every `enum` was emitted as `["LIVE", "DELAYED", ...]`, which TypeScript reads as a tuple: a string field
  was typed as an array of five strings. No consumer could have imported that.
* `const` (e.g. `schemaVersion`) fell through to `unknown`.
* with `MAX_DEPTH = 2`, `projects[]`, `executions[]` and `governance.families` collapsed to
  `Record<string, unknown>`, so the fields the pages actually read were unrepresentable.

All three are fixed in `scripts/ci/generate_contract_types.py`; this gate is what keeps them fixed, and the
last case is the bridge to the single-source goal: the unions the front end declares by hand must equal the
unions the schema declares, member for member, so the day the projection covers the nested shapes the switch
is mechanical instead of hopeful.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "apps/observer/frontend"
GENERATED = ROOT / "packages/client-neutral-core/generated/contracts.ts"
CATALOG = ROOT / ".project/governance/contracts/contract-catalog.json"
TYPES_TS = ROOT / "apps/observer/frontend/src/types.ts"

sys.path.insert(0, str(ROOT / "packages/client-neutral-core/scripts"))
import project_temp  # noqa: E402  the bounded fixture root, shared with the runtime

TS_LITERAL = {"string": str, "boolean": bool, "integer": int, "number": (int, float)}


def walk_properties(node, trail=()):
    """Yield (path, schema) for every property schema in a document, nested objects included."""
    if isinstance(node, dict):
        if "enum" in node:
            yield trail, node
        if node.get("type") == "array" and isinstance(node.get("items"), dict):
            yield from walk_properties(node["items"], trail + ("[]",))
        for key, value in (node.get("properties") or {}).items():
            yield from walk_properties(value, trail + (key,))


def ts_union(values) -> str:
    return " | ".join(json.dumps(value) for value in values)


def generated_text() -> str:
    # The generator writes CRLF on Windows checkouts; a $-anchored or multi-line search would match nothing.
    return GENERATED.read_bytes().decode("utf-8").replace("\r\n", "\n")


def hand_written_union(name: str) -> set[str]:
    text = TYPES_TS.read_text(encoding="utf-8")
    match = re.search(rf"^export type {name} =\s*\|?((?:\s*\|?\s*'[^']+')+)", text, re.MULTILINE)
    assert match, f"apps/observer/frontend/src/types.ts no longer declares {name}"
    return set(re.findall(r"'([^']+)'", match.group(1)))


class EnumProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.body = generated_text()
        cls.entries = json.loads(CATALOG.read_text(encoding="utf-8"))["contracts"]
        cls.enums: list[tuple[str, list]] = []
        cls.arrays_of_enum: list[tuple[str, list]] = []
        for entry in cls.entries:
            document = json.loads((ROOT / entry["schemaPath"]).read_text(encoding="utf-8"))
            for path, schema in walk_properties(document):
                if "[]" in path:
                    cls.arrays_of_enum.append((entry["id"], schema["enum"]))
                else:
                    cls.enums.append((entry["id"], schema["enum"]))

    def test_the_scan_saw_enums_at_all(self) -> None:
        self.assertGreaterEqual(len(self.enums), 20,
                                f"only {len(self.enums)} enum properties were read across "
                                f"{len(self.entries)} contracts; the walker stopped descending, so an empty "
                                "problem list below would mean nothing")

    def test_no_enum_is_projected_as_a_tuple(self) -> None:
        wrong = [(contract, ts_union(values)) for contract, values in self.enums
                 if ("[" + ts_union(values) + "]") in self.body and ts_union(values) not in self.body]
        self.assertEqual([], wrong[:6], f"{len(wrong)} enum properties are emitted as TypeScript tuples, "
                                        f"which type a string field as an array: {wrong[:3]}")

    def test_every_enum_appears_as_the_union_the_schema_declares(self) -> None:
        missing = []
        for contract, values in self.enums:
            union = ts_union(values)
            if f": {union}" not in self.body and f": ({union})[]" not in self.body \
                    and f": {union} | null" not in self.body and f": ({union})[] | null" not in self.body:
                missing.append((contract, union[:70]))
        self.assertEqual([], missing[:8], f"{len(missing)} enum unions are absent from the generated file")

    def test_an_array_of_enum_keeps_its_parentheses(self) -> None:
        offenders = []
        for contract, values in self.arrays_of_enum:
            union = ts_union(values)
            for line in self.body.splitlines():
                if f": {union}[]" in line:
                    offenders.append((contract, line.strip()[:80]))
        self.assertEqual([], offenders,
                         f"an unparenthesised union followed by [] parses as A | (B[]), so a bare member "
                         f"would be accepted: {offenders[:3]}")

    def test_const_scalars_are_literals_and_not_unknown(self) -> None:
        found = 0
        for entry in self.entries:
            document = json.loads((ROOT / entry["schemaPath"]).read_text(encoding="utf-8"))
            for path, schema in _walk_consts(document):
                if isinstance(schema["const"], list):
                    continue
                # `name?: value` is how the generator writes a const the schema does not require, so a plain
                # substring check for the colon form failed on every optional field -- the const was there.
                pattern = re.compile(rf"{re.escape(path[-1])}\??: {re.escape(json.dumps(schema['const']))}")
                self.assertTrue(pattern.search(self.body),
                                f"{entry['id']} lost the const {schema['const']!r} on {path[-1]}")
                found += 1
        self.assertGreaterEqual(found, 4, f"only {found} const scalars were checked; the sweep is thin")


def _walk_consts(node, trail=()):
    """Consts the generator can project: a named property, or an array item of a named property."""
    if isinstance(node, dict):
        if "const" in node and trail:
            yield trail, node
        for key, value in (node.get("properties") or {}).items():
            yield from _walk_consts(value, trail + (key,))
        if isinstance(node.get("items"), dict):
            yield from _walk_consts(node["items"], trail + ("[]",))


class HandWrittenModelAgreementTests(unittest.TestCase):
    """The four state unions the front end declares by hand must equal the schema's."""

    CASES = (
        ("TransportState", "workflow/snapshot/v3", "transportState"),
        ("FamilyState", "workflow/snapshot/v3", "state"),
        ("GitMatchState", "workflow/snapshot/v3", "matchState"),
        ("CostQuality", "workflow/snapshot/v3", "costQuality"),
    )

    def snapshot_enum(self, field: str) -> list[str]:
        document = json.loads((ROOT / "packages/contracts/schemas/workflow/snapshot-v3.schema.json")
                              .read_text(encoding="utf-8"))
        for path, schema in walk_properties(document):
            if path and path[-1] == field:
                return [str(value) for value in schema["enum"]]
        raise AssertionError(f"snapshot-v3 no longer declares an enum on {field!r}")

    def test_hand_written_unions_equal_the_schema_enums_member_for_member(self) -> None:
        for type_name, _contract, field in self.CASES:
            with self.subTest(field=field):
                schema_values = set(self.snapshot_enum(field))
                hand = hand_written_union(type_name)
                self.assertEqual(schema_values, hand,
                                 f"{type_name} in types.ts and snapshot-v3's {field} disagree: "
                                 f"hand-only={sorted(hand - schema_values)} "
                                 f"schema-only={sorted(schema_values - hand)}")

    def test_the_comparison_itself_can_fail(self) -> None:
        """A guard that cannot report a disagreement is decoration."""
        with self.assertRaises(AssertionError):
            _assert_union_equal({"A", "B"}, {"A", "C"}, "synthetic")
        _assert_union_equal({"A", "B"}, {"A", "B"}, "synthetic")


def _assert_union_equal(left: set[str], right: set[str], label: str) -> None:
    if left != right:
        raise AssertionError(f"{label}: {sorted(left ^ right)}")


class NestingDepthTests(unittest.TestCase):
    def test_the_snapshot_sections_are_not_collapsed_to_opaque_records(self) -> None:
        body = generated_text()
        start = body.index("export type WorkflowSnapshotV3")
        block = body[start:start + 4000]
        for field in ("projects", "executions", "governance"):
            self.assertNotIn(f"{field}: Record<string, unknown>", block,
                             f"{field} collapsed again, so the pages cannot read any field inside it "
                             "and the hand-written model stays the only usable one")
        for field in ("identityState", "activityState", "families", "matchState"):
            self.assertIn(field, block, f"{field} disappeared from the projection")


class GeneratedFileCompilesTests(unittest.TestCase):
    """Nothing imports `generated/contracts.ts` today, which is exactly why it could be broken TypeScript.

    A projection no compiler reads is a projection no one can consume: the enum-as-tuple defect survived for
    as long as it did because the only reader of the file was a text comparison in the SSOT verifier. This case
    type-checks the shipped file, and proves it has teeth by checking a planted copy that must fail.
    """

    @staticmethod
    def _tsc() -> tuple[list[str], Path] | None:
        sys.path.insert(0, str(ROOT / "apps/observer/scripts"))
        try:
            toolchain = importlib.import_module("frontend_toolchain")
        except Exception:  # noqa: BLE001 - an unavailable host must show up as the skip message below
            return None
        try:
            node = toolchain.find_node()
        except SystemExit:
            return None
        typescript = FRONTEND / "node_modules/typescript/bin/tsc"
        if not node.is_file() or not typescript.is_file():
            return None
        return ([str(node), str(typescript), "--noEmit", "--strict", "--target", "ES2020",
                 "--module", "esnext", "--moduleResolution", "bundler"], node)

    def _run(self, command: list[str], target: Path) -> tuple[int, str]:
        proc = subprocess.run(command + [str(target)], cwd=FRONTEND, capture_output=True)
        return proc.returncode, (proc.stdout + proc.stderr).decode("utf-8", "replace")

    def test_the_generated_projection_type_checks_and_can_reject_a_bad_one(self) -> None:
        resolved = self._tsc()
        if resolved is None:
            self.skipTest("GENERATED_TS_NOT_CHECKED: the declared Node runtime or typescript is unavailable "
                          "on this host; the textual projection cases above still ran")
        command, _node = resolved
        code, output = self._run(command, GENERATED)
        self.assertEqual(0, code, f"generated/contracts.ts does not compile:\n{output[-1200:]}")

        broken = GENERATED.read_bytes().replace(
            b'export type ContractId =',
            b'export const broken: number = "not a number";\nexport type ContractId =', 1)
        scratch = project_temp.fixture_dir("generated-ts-probe-")
        probe = Path(scratch) / "contracts-broken.ts"
        probe.write_bytes(broken)
        try:
            code, output = self._run(command, probe)
            self.assertNotEqual(0, code,
                                "the planted type error compiled clean, so the check above proves nothing")
            self.assertIn("TS2322", output, f"expected an assignability error, got: {output[-400:]}")
        finally:
            project_temp.force_release(scratch)


class FrontModelConsumesGeneratedContractTests(unittest.TestCase):
    """WUI-15: the front model must IMPORT the generated projection, and name every place it cannot.

    Until this batch the generated artifact was checked against `types.ts` by a Python gate that read both as
    text, and the front end itself consumed neither. `apps/observer/frontend/src/contractConformance.ts` is
    the seam, and it only means anything if two things stay true: the front keeps importing the generated
    module, and its list of COLLAPSED paths is exactly the set the generator actually produces. The second is
    the one that rots silently -- if the schema names a section the generator used to collapse, the front
    would be exempting a path that no longer needs exempting, and the compile-time assertions would simply
    cover less while still passing.
    """


    def _block(self) -> str:
        text = generated_text()
        start = text.index("export type WorkflowSnapshotV3 = {")
        start = text.index("{", start)
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
        raise AssertionError("the generated snapshot block is unbalanced")

    def test_the_front_end_imports_the_generated_contract_module(self) -> None:
        importers = sorted(str(path.relative_to(ROOT)).replace("\\", "/")
                           for path in (FRONTEND / "src").rglob("*.ts*")
                           if "packages/client-neutral-core/generated/contracts"
                           in path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(importers), 2,
                                "no front-end file imports the generated contract, so the SSOT projection "
                                f"is decorative again: {importers}")
        self.assertIn("apps/observer/frontend/src/contractConformance.ts", importers)

    COLLAPSE_LINE = re.compile(r"^\s+(\w+)\??: (Record<string, unknown>(\[\])?|unknown(\[\])?)\s*,?$", re.M)

    def test_the_collapse_inventory_is_exactly_what_the_generator_produces(self) -> None:
        """Leaf names must match one-for-one, and each declared parent must really be the object it is in.

        The comparison is line-shaped on purpose: an indent- or brace-tracking parser inside a gate test is
        its own bug farm (mine missed six of the seven collapses first time). What is proven here is the
        thing that can rot -- a collapse the generator no longer produces staying on the front's exemption
        list, or a new collapse arriving unnamed -- plus the claim that each entry sits under the object it
        says it does.
        """
        block = self._block()
        measured = sorted(match.group(1) for match in self.COLLAPSE_LINE.finditer(block))
        # The floor is a "the scan is still reading" tripwire, not an inventory: it was 7 before
        # WUI-21 (2026-10-11) added `operationProgress` / `isolatedTrials`, whose `isolation` object is
        # free-form in the contract and therefore one more measured collapse. (Four more appeared first,
        # because the stages were declared through $defs and the generator cannot follow a $ref; inlining
        # the stage shape in the schema named them.) WUI-15 (2026-10-18) then took it 8 -> 6 by naming both
        # `ci` levels in the schema, so the projection carries those fields instead of collapsing them.
        # Pinning a count would make the gate red on a correct contract; the real invariant is the equality
        # with GENERATED_COLLAPSED_PATHS checked immediately below, which fails on ANY difference either way.
        self.assertGreaterEqual(len(measured), 6,
                                f"the scan found {measured}; a collapse set this small means the "
                                "scan stopped reading the block, not that the contract got clean")
        source = (FRONTEND / "src/contractConformance.ts").read_text(encoding="utf-8")
        listed = re.search(r"GENERATED_COLLAPSED_PATHS = \[([\s\S]*?)\] as const", source)
        self.assertIsNotNone(listed, "contractConformance.ts no longer declares GENERATED_COLLAPSED_PATHS")
        declared = re.findall(r"'([^']+)'", listed.group(1))
        self.assertEqual(measured, sorted(path.split(".")[-1].replace("[]", "") for path in declared),
                         f"the generated projection collapses {measured} but the front model exempts "
                         f"{declared} -- an exemption that no longer matches a real collapse silently "
                         "shrinks what the compile-time refinements cover")
        for path in declared:
            if "." not in path:
                self.assertTrue(re.search(rf"^    {re.escape(path)}\??:", block, re.M),
                                f"{path} is declared top-level but the generated block has no such key")
                continue
            parent, leaf = path.rsplit(".", 1)
            parent = parent.replace("[]", "")
            opener = rf"{re.escape(parent)}\??:\s*\(?{{"
            self.assertRegex(block, opener,
                             f"{path} claims its parent is {parent!r}, which the generated block never opens")
            self.assertIn(leaf, block.split(f"{parent}", 1)[1][:4000],
                          f"{leaf} is not inside the {parent} section as claimed")

    def test_every_pinned_refinement_path_is_a_declared_key_of_the_contract(self) -> None:
        source = (FRONTEND / "src/contractConformance.ts").read_text(encoding="utf-8")
        block = re.search(r"PINNED_REFINEMENT_PATHS = \[([\s\S]*?)\] as const", source)
        self.assertIsNotNone(block, "the refinement list disappeared; the seam pins nothing")
        pinned = re.findall(r"'([^']+)'", block.group(1))
        self.assertGreaterEqual(len(pinned), 8, f"only {len(pinned)} paths are pinned: {pinned}")
        schema = json.loads((ROOT / "packages/contracts/schemas/workflow/snapshot-v3.schema.json")
                            .read_text(encoding="utf-8"))
        declared = set(schema["required"]) | set(schema.get("properties", {}))
        missing = [name for name in pinned if name not in declared]
        self.assertEqual([], missing,
                         f"pinned paths that the contract does not declare: {missing}")


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
